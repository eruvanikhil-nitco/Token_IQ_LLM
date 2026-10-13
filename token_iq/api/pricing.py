"""Serve Pricing & Rates: what this customer pays, as opposed to what a model costs at list.

The rules live in `token_iq/pricing/rates.py` and are tested without a database. This module reads
and writes the rows, refuses a rate that could never price anything, and answers the one question a
screen asks of the pair: which rate applies to this model and meter today, and what does it make a
million tokens cost.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Annotated, Final

import fastapi
from fastapi import APIRouter, Depends, HTTPException, status

from token_iq.access.scope import ScopeRefused, readable_scope, refusal_message
from token_iq.api.types.pricing import (
    ConversionAvailable,
    ConversionConflict,
    ConversionNotNeeded,
    ConversionResponse,
    ConversionUnavailable,
    CurrencyRateBody,
    CurrencyRateListResponse,
    CurrencyRateResponse,
    EffectiveRateResponse,
    ListPriceApplies,
    PriceUnknown,
    RateApplied,
    RateBody,
    RateDeletedResponse,
    RateListResponse,
    RateResponse,
    RatesConflict,
)
from token_iq.connectors.billing.credential_purpose import BILLING_PROVIDERS
from token_iq.gateway.proxy._types import CommonProxyErrors, UserAPIKeyAuth
from token_iq.gateway.proxy.auth.user_api_key_auth import user_api_key_auth
from token_iq.pricing.currency import (
    Conversion,
    CurrencyRate,
    NoConversionRate,
    RateConflict,
    SameCurrency,
    UseRate,
    conversion,
)
from token_iq.pricing.history import price_as_of
from token_iq.pricing.rates import (
    PER_MILLION,
    AppliedRate,
    ConflictingRates,
    Discount,
    NoCustomerRate,
    RateAnswer,
    RateRule,
    UnitPrice,
    cost_of,
    effective_rate,
    rate_problem,
)
from token_iq.repositories.currency_rate_repository import CurrencyRateRepository
from token_iq.repositories.provider_rate_repository import DISCOUNT, UNIT_PRICE, ProviderRateRepository

router: Final = APIRouter(
    tags=["pricing"],  # mutable-ok: fixed single-element tag list, never grown after this line
    dependencies=(Depends(user_api_key_auth),),
)

A_MILLION: Final = 1_000_000


def _proxy_error(status_code: int, message: str) -> HTTPException:
    """A refusal a client can read.

    A plain dict because FastAPI runs the detail through `json.dumps`, and a read-only mapping is
    not serialisable: the refusal would then reach the caller as a generic 500 with the reason gone.
    """
    return HTTPException(
        status_code=status_code,
        detail={"error": message},  # mutable-ok: fixed one-key error envelope, and json.dumps needs a dict
    )


def _admin_or_403(user_api_key_dict: UserAPIKeyAuth) -> None:
    refused: Final = readable_scope(user_api_key_dict, subject="the rates")
    if isinstance(refused, ScopeRefused):
        raise _proxy_error(status.HTTP_403_FORBIDDEN, refusal_message(refused))


def _known_provider_or_404(provider: str) -> None:
    if provider not in BILLING_PROVIDERS:
        raise _proxy_error(
            status.HTTP_404_NOT_FOUND,
            f"Unknown provider {provider!r}. Valid providers: {', '.join(sorted(BILLING_PROVIDERS))}.",
        )


def _day_or_400(value: str, field: str) -> date:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        raise _proxy_error(status.HTTP_400_BAD_REQUEST, f"{field} is not a date: {value!r}.") from None


def _amount_or_400(value: str | None, field: str) -> Decimal:
    if value is None:
        raise _proxy_error(status.HTTP_400_BAD_REQUEST, f"{field} is required for this kind of rate.")
    try:
        return Decimal(value)
    except ArithmeticError:
        raise _proxy_error(status.HTTP_400_BAD_REQUEST, f"{field} is not an amount: {value!r}.") from None


def rate_from_body(body: RateBody) -> RateRule:
    """The rate as it will be stored, with its amount read as exact digits."""
    basis: Final = (
        Discount(percent_off=_amount_or_400(body.percent_off, "percent_off"))
        if body.basis == DISCOUNT
        else UnitPrice(per_million=_amount_or_400(body.per_million, "per_million"))
    )
    return RateRule(
        rate_id="",
        provider=body.provider,
        model=body.model,
        field=body.field,
        basis=basis,
        effective_from=_day_or_400(body.effective_from, "effective_from"),
        effective_to=None if body.effective_to is None else _day_or_400(body.effective_to, "effective_to"),
        source=body.source,
    )


def _basis_columns(basis: Discount | UnitPrice) -> tuple[str, str | None, str | None]:
    """Which kind of rate it is, and whichever amount that kind carries."""
    match basis:
        case Discount(percent_off=percent_off):
            return (DISCOUNT, format(percent_off, "f"), None)
        case UnitPrice(per_million=per_million):
            return (UNIT_PRICE, None, format(per_million, "f"))


def rate_to_wire(rule: RateRule) -> RateResponse:
    """One rate as a screen reads it, with each amount on the field its kind uses."""
    basis, percent, per_million = _basis_columns(rule.basis)
    return RateResponse(
        rate_id=rule.rate_id,
        provider=rule.provider,
        model=rule.model,
        field=rule.field,
        basis=basis,  # pyright: ignore[reportArgumentType]  # both branches assign one of the two literals
        percent_off=percent,
        per_million=per_million,
        effective_from=rule.effective_from.isoformat(),
        effective_to=None if rule.effective_to is None else rule.effective_to.isoformat(),
        source=rule.source,
    )


def effective_rate_to_wire(answer: RateAnswer, list_price_per_token: Decimal | None) -> EffectiveRateResponse:
    """What prices a million tokens of this model and meter, exhaustive over every answer.

    An unknown list price is its own state. A caller that read it as zero would turn real spend into
    free usage, which is the one reading of a missing price that must never happen.
    """
    match answer:
        case ConflictingRates(rules=rules):
            return RatesConflict(rates=tuple(rate_to_wire(rule) for rule in rules))
        case NoCustomerRate():
            if list_price_per_token is None:
                return PriceUnknown(reason="Neither the price history nor the bundled list knows this model and meter.")
            return ListPriceApplies(cost_per_million=format(list_price_per_token * PER_MILLION, "f"))
        case AppliedRate(rule=rule):
            if list_price_per_token is None and isinstance(rule.basis, Discount):
                return PriceUnknown(
                    reason="A discount needs a list price, and neither the history nor the bundled list has one."
                )
            cost: Final = cost_of(
                tokens=A_MILLION,
                list_price_per_token=list_price_per_token or Decimal(0),
                rate=answer,
            )
            if cost is None:
                return PriceUnknown(reason="The rate that applies cannot price anything.")
            return RateApplied(rate=rate_to_wire(rule), cost_per_million=format(cost, "f"))


@router.get("/pricing/rates", response_model=RateListResponse)
async def list_rates(
    user_api_key_dict: Annotated[UserAPIKeyAuth, Depends(user_api_key_auth)],
) -> RateListResponse:
    """Every rate an administrator has recorded, newest period first within a provider."""
    from token_iq.gateway.proxy.proxy_server import prisma_client

    _admin_or_403(user_api_key_dict)
    if prisma_client is None:
        raise _proxy_error(status.HTTP_500_INTERNAL_SERVER_ERROR, CommonProxyErrors.db_not_connected_error.value)

    rates: Final = await ProviderRateRepository(prisma_client).all()
    return RateListResponse(rates=tuple(rate_to_wire(rule) for rule in rates))


@router.post("/pricing/rates", response_model=RateResponse)
async def add_rate(
    body: RateBody,
    user_api_key_dict: Annotated[UserAPIKeyAuth, Depends(user_api_key_auth)],
) -> RateResponse:
    """Record what a contract says. Refused when it could never price anything.

    An insert, never an update: a renegotiation is a new rate with its own period, because the old
    one priced months that have already been reported.
    """
    from token_iq.gateway.proxy.proxy_server import prisma_client

    _admin_or_403(user_api_key_dict)
    _known_provider_or_404(body.provider)
    rule: Final = rate_from_body(body)
    problem: Final = rate_problem(rule)
    if problem is not None:
        raise _proxy_error(status.HTTP_400_BAD_REQUEST, problem)
    if prisma_client is None:
        raise _proxy_error(status.HTTP_500_INTERNAL_SERVER_ERROR, CommonProxyErrors.db_not_connected_error.value)

    stored: Final = await ProviderRateRepository(prisma_client).add(rule)
    if stored is None:
        raise _proxy_error(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "The rate was written but could not be read back in a shape this server understands.",
        )
    return rate_to_wire(stored)


@router.delete("/pricing/rates/{rate_id}", response_model=RateDeletedResponse)
async def delete_rate(
    rate_id: str,
    user_api_key_dict: Annotated[UserAPIKeyAuth, Depends(user_api_key_auth)],
) -> RateDeletedResponse:
    """Remove a rate, after which its periods price at whatever else covers them."""
    from token_iq.gateway.proxy.proxy_server import prisma_client

    _admin_or_403(user_api_key_dict)
    if prisma_client is None:
        raise _proxy_error(status.HTTP_500_INTERNAL_SERVER_ERROR, CommonProxyErrors.db_not_connected_error.value)

    if not await ProviderRateRepository(prisma_client).delete(rate_id):
        raise _proxy_error(status.HTTP_404_NOT_FOUND, f"No rate with id {rate_id!r}.")
    return RateDeletedResponse(deleted=True)


@router.get("/pricing/effective-rate", response_model=EffectiveRateResponse)
async def read_effective_rate(
    user_api_key_dict: Annotated[UserAPIKeyAuth, Depends(user_api_key_auth)],
    provider: str = fastapi.Query(description="The provider whose bill this model is on"),
    model: str = fastapi.Query(description="The model as the price list names it"),
    field: str = fastapi.Query(
        default="input_cost_per_token", description="Which meter: input_cost_per_token and its siblings"
    ),
    on: str | None = fastapi.Query(default=None, description="The day to price, as YYYY-MM-DD. Today by default"),
) -> EffectiveRateResponse:
    """What prices this model and meter on a given day, and what that makes a million tokens cost.

    The day matters: a closed month prices with the rate and the list price that applied then, not
    with today's.
    """
    from token_iq.gateway.proxy.proxy_server import prisma_client

    _admin_or_403(user_api_key_dict)
    _known_provider_or_404(provider)
    when: Final = datetime.now(timezone.utc).date() if on is None else _day_or_400(on, "on")
    if prisma_client is None:
        raise _proxy_error(status.HTTP_500_INTERNAL_SERVER_ERROR, CommonProxyErrors.db_not_connected_error.value)

    rules: Final = await ProviderRateRepository(prisma_client).all()
    answer: Final = effective_rate(rules, provider=provider, model=model, field=field, when=when)
    return effective_rate_to_wire(answer, price_as_of(model, field, when))


def currency_rate_from_body(body: CurrencyRateBody) -> CurrencyRate:
    """The rate as it will be stored, with its digits read exactly."""
    rate: Final = _amount_or_400(body.rate, "rate")
    if rate <= 0:
        raise _proxy_error(status.HTTP_400_BAD_REQUEST, "A conversion rate has to be greater than zero.")
    if body.source_currency == body.target_currency:
        raise _proxy_error(
            status.HTTP_400_BAD_REQUEST,
            "A currency converts to itself at one, so there is no rate to record.",
        )
    effective_from: Final = _day_or_400(body.effective_from, "effective_from")
    effective_to: Final = None if body.effective_to is None else _day_or_400(body.effective_to, "effective_to")
    if effective_to is not None and effective_to < effective_from:
        raise _proxy_error(status.HTTP_400_BAD_REQUEST, "The period ends before it starts.")
    return CurrencyRate(
        rate_id="",
        source_currency=body.source_currency.upper(),
        target_currency=body.target_currency.upper(),
        rate=rate,
        effective_from=effective_from,
        effective_to=effective_to,
        source=body.source,
    )


def currency_rate_to_wire(rate: CurrencyRate) -> CurrencyRateResponse:
    return CurrencyRateResponse(
        rate_id=rate.rate_id,
        source_currency=rate.source_currency,
        target_currency=rate.target_currency,
        rate=format(rate.rate, "f"),
        effective_from=rate.effective_from.isoformat(),
        effective_to=None if rate.effective_to is None else rate.effective_to.isoformat(),
        source=rate.source,
    )


def conversion_to_wire(answer: Conversion) -> ConversionResponse:
    """Exhaustive over every answer, including the two that are refusals."""
    match answer:
        case SameCurrency():
            return ConversionNotNeeded()
        case UseRate(rate=rate):
            return ConversionAvailable(rate=currency_rate_to_wire(rate))
        case NoConversionRate(source=source, target=target):
            return ConversionUnavailable(
                source_currency=source,
                target_currency=target,
                reason=(
                    f"No rate is recorded for {source} to {target} on that day. A rate recorded the "
                    "other way round is not inverted, because one divided by a rate is a figure "
                    "nobody entered: record this direction to report in it."
                ),
            )
        case RateConflict(rates=rates):
            return ConversionConflict(rates=tuple(currency_rate_to_wire(rate) for rate in rates))


@router.get("/pricing/currency-rates", response_model=CurrencyRateListResponse)
async def list_currency_rates(
    user_api_key_dict: Annotated[UserAPIKeyAuth, Depends(user_api_key_auth)],
) -> CurrencyRateListResponse:
    """Every conversion rate an administrator has recorded, newest period first within a pair."""
    from token_iq.gateway.proxy.proxy_server import prisma_client

    _admin_or_403(user_api_key_dict)
    if prisma_client is None:
        raise _proxy_error(status.HTTP_500_INTERNAL_SERVER_ERROR, CommonProxyErrors.db_not_connected_error.value)

    rates: Final = await CurrencyRateRepository(prisma_client).all()
    return CurrencyRateListResponse(rates=tuple(currency_rate_to_wire(rate) for rate in rates))


@router.post("/pricing/currency-rates", response_model=CurrencyRateResponse)
async def add_currency_rate(
    body: CurrencyRateBody,
    user_api_key_dict: Annotated[UserAPIKeyAuth, Depends(user_api_key_auth)],
) -> CurrencyRateResponse:
    """Record the rate a period was booked at, in the direction being reported in."""
    from token_iq.gateway.proxy.proxy_server import prisma_client

    _admin_or_403(user_api_key_dict)
    rate: Final = currency_rate_from_body(body)
    if prisma_client is None:
        raise _proxy_error(status.HTTP_500_INTERNAL_SERVER_ERROR, CommonProxyErrors.db_not_connected_error.value)

    stored: Final = await CurrencyRateRepository(prisma_client).add(rate)
    if stored is None:
        raise _proxy_error(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "The rate was written but could not be read back in a shape this server understands.",
        )
    return currency_rate_to_wire(stored)


@router.delete("/pricing/currency-rates/{rate_id}", response_model=RateDeletedResponse)
async def delete_currency_rate(
    rate_id: str,
    user_api_key_dict: Annotated[UserAPIKeyAuth, Depends(user_api_key_auth)],
) -> RateDeletedResponse:
    """Remove a rate, after which any period it covered reports per currency again."""
    from token_iq.gateway.proxy.proxy_server import prisma_client

    _admin_or_403(user_api_key_dict)
    if prisma_client is None:
        raise _proxy_error(status.HTTP_500_INTERNAL_SERVER_ERROR, CommonProxyErrors.db_not_connected_error.value)

    if not await CurrencyRateRepository(prisma_client).delete(rate_id):
        raise _proxy_error(status.HTTP_404_NOT_FOUND, f"No currency rate with id {rate_id!r}.")
    return RateDeletedResponse(deleted=True)


@router.get("/pricing/conversion", response_model=ConversionResponse)
async def read_conversion(
    user_api_key_dict: Annotated[UserAPIKeyAuth, Depends(user_api_key_auth)],
    source_currency: str = fastapi.Query(description="The currency being converted"),
    target_currency: str = fastapi.Query(description="The currency being reported in"),
    on: str | None = fastapi.Query(default=None, description="The day to convert, as YYYY-MM-DD. Today by default"),
) -> ConversionResponse:
    """Whether one currency can be reported as another on a given day, and at whose rate."""
    from token_iq.gateway.proxy.proxy_server import prisma_client

    _admin_or_403(user_api_key_dict)
    when: Final = datetime.now(timezone.utc).date() if on is None else _day_or_400(on, "on")
    if prisma_client is None:
        raise _proxy_error(status.HTTP_500_INTERNAL_SERVER_ERROR, CommonProxyErrors.db_not_connected_error.value)

    rates: Final = await CurrencyRateRepository(prisma_client).all()
    return conversion_to_wire(
        conversion(rates, source=source_currency.upper(), target=target_currency.upper(), when=when)
    )
