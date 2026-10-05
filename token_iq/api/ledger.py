"""Serve the cost ledger, the invoices an admin entered, and the reconciliation between them.

The arithmetic lives in `token_iq/ledger/reconciliation.py` and the reads in the two repositories,
all tested there. This module shapes the answer into strings a JSON client cannot round, and
computes the clock-dependent parts so the arithmetic stays pure.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Final

import fastapi
from fastapi import APIRouter, Depends, HTTPException, status

from litellm.proxy._types import CommonProxyErrors, LitellmUserRoles, UserAPIKeyAuth
from litellm.proxy.auth.user_api_key_auth import user_api_key_auth
from token_iq.api.types.ledger import (
    AdjustmentBody,
    InvoiceBody,
    InvoiceDeletedResponse,
    InvoiceListResponse,
    InvoiceResponse,
    LedgerLineResponse,
    LedgerLinesResponse,
    ReconciliationResponse,
)
from token_iq.connectors.billing.credential_purpose import BILLING_PROVIDERS
from token_iq.connectors.billing.fetch_profile import FETCH_PROFILES
from token_iq.ledger.reconciliation import Reconciliation, reconcile
from token_iq.repositories.attribution_rule_repository import AttributionRuleRepository
from token_iq.repositories.invoice_repository import InvoiceRepository
from token_iq.repositories.ledger_repository import LedgerLine, LedgerRepository
from token_iq.types.attribution import AttributionRule
from token_iq.types.invoice import InvoiceAdjustment, ProviderInvoice

router: Final = APIRouter(
    tags=["ledger"],  # mutable-ok: fixed single-element tag list, never grown after this line
    dependencies=(Depends(user_api_key_auth),),
)


def _plain(value: Decimal) -> str:
    """Fixed-point, never scientific notation: Decimal renders small results as 5E-7."""
    return format(value, "f")


def _proxy_error(status_code: int, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"error": message},  # mutable-ok: fixed one-key error envelope, matches every other proxy endpoint
    )


def _admin_or_403(user_api_key_dict: UserAPIKeyAuth) -> None:
    if user_api_key_dict.user_role != LitellmUserRoles.PROXY_ADMIN:
        raise _proxy_error(status.HTTP_403_FORBIDDEN, "Only a proxy admin may read or change the ledger.")


def _known_provider_or_404(provider: str) -> None:
    if provider not in BILLING_PROVIDERS:
        raise _proxy_error(
            status.HTTP_404_NOT_FOUND,
            f"Unknown provider {provider!r}. Valid providers: {', '.join(sorted(BILLING_PROVIDERS))}.",
        )


def _display_name(provider: str) -> str:
    profile: Final = FETCH_PROFILES.get(provider)
    return profile.display_name if profile is not None else provider


def _day_or_400(value: str, field: str) -> datetime:
    """Refuse a date we cannot read rather than defaulting it.

    A period silently defaulted to today would reconcile a bill against the wrong month and
    report a difference the size of the whole ledger.
    """
    try:
        parsed: Final = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise _proxy_error(status.HTTP_400_BAD_REQUEST, f"{field} is not a date: {value!r}.") from None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def _period_end_or_400(value: str, field: str) -> datetime:
    """The last instant of the period, not its first.

    A reader who types 2026-09-30 means the whole of the thirtieth. Parsing that to midnight and
    comparing with `<=` excludes almost the entire final day, so a month's reconciliation would
    report a difference the size of that day's usage and blame the provider for it. A caller who
    sends an explicit time is taken at their word.
    """
    parsed: Final = _day_or_400(value, field)
    names_a_time: Final = "T" in value or " " in value.strip()
    # .999 rather than .999999: these columns are TIMESTAMP(3), and Postgres rounds a microsecond
    # value up on insert, pushing the instant into the next day and outside its own period.
    return parsed if names_a_time else parsed.replace(hour=23, minute=59, second=59, microsecond=999000)


def _amount_or_400(value: str, field: str) -> Decimal:
    try:
        return Decimal(value)
    except InvalidOperation:
        raise _proxy_error(status.HTTP_400_BAD_REQUEST, f"{field} is not an amount: {value!r}.") from None


def _encode_cursor(cursor: tuple[datetime, str]) -> str:
    """Both halves travel together: the day alone is not unique, since every fact one connector
    run writes shares that run's watermark."""
    return f"{cursor[0].isoformat()}|{cursor[1]}"


def _decode_cursor(raw: str) -> tuple[datetime, str] | None:
    timestamp, separator, fact_key = raw.partition("|")
    if not separator:
        return None
    try:
        return (datetime.fromisoformat(timestamp), fact_key)
    except ValueError:
        return None


def _owner_of(line: LedgerLine, rules: tuple[AttributionRule, ...]) -> AttributionRule | None:
    """The rule that claims this line's account, if any.

    The ledger stores no owner of its own: an owner is a statement about an account, and the
    attribution rules are where that statement lives.
    """
    return next(
        (r for r in rules if r.provider == line.provider and r.match_value == line.credential_name),
        None,
    )


def _line_response(line: LedgerLine, rules: tuple[AttributionRule, ...]) -> LedgerLineResponse:
    owner: Final = _owner_of(line, rules)
    return LedgerLineResponse(
        day=line.day.date().isoformat(),
        provider=line.provider,
        display_name=_display_name(line.provider),
        credential_name=line.credential_name,
        model=line.model,
        evidence=line.evidence,
        currency=line.currency,
        amount=_plain(line.amount),
        owner_type=owner.owner_type if owner is not None else None,
        owner_id=owner.owner_id if owner is not None else None,
    )


def _adjustment_body(adjustment: InvoiceAdjustment) -> AdjustmentBody:
    return AdjustmentBody(kind=adjustment.kind, amount=_plain(adjustment.amount), note=adjustment.note)


def _invoice_response(invoice: ProviderInvoice) -> InvoiceResponse:
    return InvoiceResponse(
        invoice_id=invoice.invoice_id,
        provider=invoice.provider,
        period_start=invoice.period_start.date().isoformat(),
        period_end=invoice.period_end.date().isoformat(),
        currency=invoice.currency,
        total=_plain(invoice.total),
        adjustments=tuple(_adjustment_body(a) for a in invoice.adjustments),
        note=invoice.note,
    )


def _reconciliation_note(result: Reconciliation, ledger_totals: Mapping[str, Decimal]) -> str:
    """The sentence that says what the numbers cannot.

    Each branch names something a reader would otherwise have to guess at, and the mismatch
    branch names both currencies, because saying two things do not match without saying which
    two is not something anyone can act on.
    """
    if result.outcome == "no_invoice":
        return "No bill entered for this period yet, so there is nothing to compare the ledger against."
    if result.outcome == "currency_mismatch":
        held: Final = ", ".join(sorted(ledger_totals)) or "nothing"
        return (
            f"The bill is in {result.currency} and the ledger holds {held}. No conversion is applied, "
            "because a rate nobody chose would look authoritative and not be."
        )
    if result.outcome == "balanced":
        return "The bill, its adjustments and the ledger agree exactly."
    return "Part of the difference is not accounted for by any adjustment on the bill."


def reconciliation_response(
    *,
    provider: str,
    period_start: datetime,
    period_end: datetime,
    result: Reconciliation,
    ledger_totals: Mapping[str, Decimal],
) -> ReconciliationResponse:
    """Shape the reconciliation into the response the Ledger screen reads.

    Split out of the route so the shaping, in particular that the unexplained remainder is
    always present even when zero, can be tested without a database.
    """
    return ReconciliationResponse(
        provider=provider,
        period_start=period_start.date().isoformat(),
        period_end=period_end.date().isoformat(),
        outcome=result.outcome,
        currency=result.currency,
        invoice_total=None if result.invoice_total is None else _plain(result.invoice_total),
        ledger_total=None if result.ledger_total is None else _plain(result.ledger_total),
        explained=tuple(_adjustment_body(a) for a in result.explained),
        explained_total=_plain(result.explained_total),
        unexplained=_plain(result.unexplained),
        note=_reconciliation_note(result, ledger_totals),
    )


@router.get("/ledger/lines", response_model=LedgerLinesResponse)
async def ledger_lines(
    provider: str | None = fastapi.Query(default=None, description="One provider, or every provider"),
    period_start: str = fastapi.Query(description="First day of the period, as YYYY-MM-DD"),
    period_end: str = fastapi.Query(description="Last day of the period, as YYYY-MM-DD"),
    limit: int = fastapi.Query(default=50, ge=1, le=500),
    cursor: str | None = fastapi.Query(default=None, description="Resume token from a previous page"),
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
) -> LedgerLinesResponse:
    """Every cost line in the period, with its source, evidence level and owner."""
    from litellm.proxy.proxy_server import prisma_client

    _admin_or_403(user_api_key_dict)
    if provider is not None:
        _known_provider_or_404(provider)
    start: Final = _day_or_400(period_start, "period_start")
    end: Final = _period_end_or_400(period_end, "period_end")
    resume: Final = _decode_cursor(cursor) if cursor is not None else None
    if prisma_client is None:
        raise _proxy_error(status.HTTP_500_INTERNAL_SERVER_ERROR, CommonProxyErrors.db_not_connected_error.value)

    ledger: Final = LedgerRepository(prisma_client)
    page: Final = await ledger.lines(provider=provider, period_start=start, period_end=end, limit=limit, cursor=resume)
    rules: Final = await AttributionRuleRepository(prisma_client).all()
    totals: Final[Mapping[str, Decimal]] = (
        await ledger.total(provider=provider, period_start=start, period_end=end)
        if provider is not None
        else {}  # mutable-ok: an empty literal for the all-providers case, never written to
    )

    return LedgerLinesResponse(
        lines=tuple(_line_response(line, rules) for line in page.lines),
        next_cursor=None if page.next_cursor is None else _encode_cursor(page.next_cursor),
        totals_by_currency={  # mutable-ok: pydantic serialises a dict field; a mappingproxy is rejected
            currency: _plain(amount) for currency, amount in totals.items()
        },
    )


@router.get("/ledger/invoices", response_model=InvoiceListResponse)
async def list_invoices(
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
) -> InvoiceListResponse:
    """Every bill an admin has entered, newest period first."""
    from litellm.proxy.proxy_server import prisma_client

    _admin_or_403(user_api_key_dict)
    if prisma_client is None:
        raise _proxy_error(status.HTTP_500_INTERNAL_SERVER_ERROR, CommonProxyErrors.db_not_connected_error.value)

    invoices: Final = await InvoiceRepository(prisma_client).all()
    return InvoiceListResponse(invoices=tuple(_invoice_response(i) for i in invoices))


@router.post("/ledger/invoices", response_model=InvoiceResponse)
async def upsert_invoice(
    body: InvoiceBody,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
) -> InvoiceResponse:
    """Enter a bill, or correct the one already entered for that period."""
    from litellm.proxy.proxy_server import prisma_client

    _admin_or_403(user_api_key_dict)
    _known_provider_or_404(body.provider)
    if prisma_client is None:
        raise _proxy_error(status.HTTP_500_INTERNAL_SERVER_ERROR, CommonProxyErrors.db_not_connected_error.value)

    stored: Final = await InvoiceRepository(prisma_client).upsert(
        ProviderInvoice(
            invoice_id="",
            provider=body.provider,
            period_start=_day_or_400(body.period_start, "period_start"),
            period_end=_day_or_400(body.period_end, "period_end"),
            currency=body.currency,
            total=_amount_or_400(body.total, "total"),
            adjustments=tuple(
                InvoiceAdjustment(kind=a.kind, amount=_amount_or_400(a.amount, f"adjustment {a.kind}"), note=a.note)
                for a in body.adjustments
            ),
            note=body.note,
        )
    )
    if stored is None:
        raise _proxy_error(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "The bill was written but could not be read back in a shape this server understands.",
        )
    return _invoice_response(stored)


@router.delete("/ledger/invoices/{invoice_id}", response_model=InvoiceDeletedResponse)
async def delete_invoice(
    invoice_id: str,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
) -> InvoiceDeletedResponse:
    """Remove a bill, after which its period has nothing to reconcile against."""
    from litellm.proxy.proxy_server import prisma_client

    _admin_or_403(user_api_key_dict)
    if prisma_client is None:
        raise _proxy_error(status.HTTP_500_INTERNAL_SERVER_ERROR, CommonProxyErrors.db_not_connected_error.value)

    deleted: Final = await InvoiceRepository(prisma_client).delete(invoice_id)
    if not deleted:
        raise _proxy_error(status.HTTP_404_NOT_FOUND, f"No invoice with id {invoice_id!r}.")
    return InvoiceDeletedResponse(deleted=True)


@router.get("/ledger/reconciliation", response_model=ReconciliationResponse)
async def ledger_reconciliation(
    provider: str = fastapi.Query(description="Which provider's bill to reconcile"),
    period_start: str = fastapi.Query(description="First day of the period, as YYYY-MM-DD"),
    period_end: str = fastapi.Query(description="Last day of the period, as YYYY-MM-DD"),
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
) -> ReconciliationResponse:
    """What the bill says, what the ledger says, and what is left over."""
    from litellm.proxy.proxy_server import prisma_client

    _admin_or_403(user_api_key_dict)
    _known_provider_or_404(provider)
    # The period is parsed before the database is consulted: a caller who sent a malformed date
    # needs to be told that, not that the database is unavailable.
    start: Final = _day_or_400(period_start, "period_start")
    end: Final = _period_end_or_400(period_end, "period_end")
    if prisma_client is None:
        raise _proxy_error(status.HTTP_500_INTERNAL_SERVER_ERROR, CommonProxyErrors.db_not_connected_error.value)

    totals: Final = await LedgerRepository(prisma_client).total(provider=provider, period_start=start, period_end=end)
    invoice: Final = await InvoiceRepository(prisma_client).for_period(
        provider=provider, period_start=start, period_end=end
    )

    return reconciliation_response(
        provider=provider,
        period_start=start,
        period_end=end,
        result=reconcile(invoice=invoice, ledger_totals=totals),
        ledger_totals=totals,
    )
