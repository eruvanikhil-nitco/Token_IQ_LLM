"""Serve one provider's usage summary over HTTP.

The arithmetic lives in `usage_summary.py` and is tested there; this module only reads the
rows, calls it, and shapes the result into strings a JSON client cannot round.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from types import MappingProxyType
from typing import Final

import fastapi
from fastapi import APIRouter, Depends, HTTPException, status

from litellm.proxy._types import CommonProxyErrors, LitellmUserRoles, UserAPIKeyAuth
from litellm.proxy.auth.user_api_key_auth import user_api_key_auth
from litellm.types.proxy.management_endpoints.team_endpoints import (
    ProviderAccountSpend,
    ProviderModelSpend,
    ProviderRawFact,
    ProviderTokenTotals,
    ProviderUsageRawResponse,
    ProviderUsageSummaryResponse,
)
from litellm.types.proxy.provider_billing import ProviderUsageFact
from token_iq.connectors.billing.credential_purpose import BILLING_PROVIDERS
from token_iq.connectors.billing.fetch_profile import FETCH_PROFILES
from token_iq.connectors.billing.usage_summary import UsageSummary, build_usage_summary
from token_iq.repositories.provider_usage_fact_repository import ProviderUsageFactRepository

router: Final = APIRouter(
    tags=["provider billing"],  # mutable-ok: fixed single-element tag list, never grown after this line
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
        raise _proxy_error(status.HTTP_403_FORBIDDEN, "Only a proxy admin may read provider usage.")


def _known_provider_or_404(provider: str) -> None:
    """Refuse a typo'd provider rather than answering an empty result.

    An empty summary or an empty raw page for a mistyped slug reads as "this provider sent
    nothing", which is a different and more alarming message than "no such provider".
    """
    if provider not in BILLING_PROVIDERS:
        raise _proxy_error(
            status.HTTP_404_NOT_FOUND,
            f"Unknown provider {provider!r}. Valid providers: {', '.join(sorted(BILLING_PROVIDERS))}.",
        )


def usage_summary_response(*, provider: str, days: int, summary: UsageSummary) -> ProviderUsageSummaryResponse:
    """Shape the pure `UsageSummary` into the response the dashboard reads.

    Split out of the route so the shaping, in particular that every cost crosses as a
    string and that the delay and settling notes survive the trip, can be tested without a
    database.
    """
    profile: Final = FETCH_PROFILES[provider]
    return ProviderUsageSummaryResponse(
        provider=provider,
        display_name=profile.display_name,
        days=days,
        total_cost=_plain(summary.total_cost),
        facts=summary.facts,
        by_model=tuple(
            ProviderModelSpend(model=spend.model, billed_cost=_plain(spend.billed_cost))
            for spend in summary.by_model
        ),
        by_account=tuple(
            ProviderAccountSpend(credential_name=spend.credential_name, billed_cost=_plain(spend.billed_cost))
            for spend in summary.by_account
        ),
        by_evidence=MappingProxyType({level: _plain(cost) for level, cost in summary.by_evidence.items()}),
        tokens=ProviderTokenTotals(
            input_tokens=summary.tokens.input_tokens,
            output_tokens=summary.tokens.output_tokens,
            cached_input_tokens=summary.tokens.cached_input_tokens,
            cache_write_tokens=summary.tokens.cache_write_tokens,
        ),
        grain=profile.grain,
        delay_note=profile.delay_note,
        settling_note=profile.settling_note,
    )


@router.get("/provider/usage/summary", response_model=ProviderUsageSummaryResponse)
async def provider_usage_summary(
    provider: str = fastapi.Query(description="Which provider's usage to summarise, for example openrouter"),
    days: int = fastapi.Query(default=30, ge=1, le=90),
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
) -> ProviderUsageSummaryResponse:
    """Cost and token totals for one provider over a window, by model, account and evidence level."""
    from litellm.proxy.proxy_server import prisma_client

    _admin_or_403(user_api_key_dict)
    _known_provider_or_404(provider)
    if prisma_client is None:
        raise _proxy_error(status.HTTP_500_INTERNAL_SERVER_ERROR, CommonProxyErrors.db_not_connected_error.value)

    facts: Final = ProviderUsageFactRepository(prisma_client)
    rows: Final = await facts.summary_rows(provider=provider, days=days)
    tokens: Final = await facts.token_totals(provider=provider, days=days)

    return usage_summary_response(provider=provider, days=days, summary=build_usage_summary(rows, tokens))


def _encode_cursor(bucket_start: datetime, fact_key: str) -> str:
    """`next_before` is bucket_start plus the fact_key that broke its tie.

    bucket_start on its own is not unique enough to resume on: a live check against real
    data found dozens of facts sharing one bucket_start, because one connector run stamps
    every fact it writes with that run's watermark. Filtering the next page on bucket_start
    alone at that boundary would drop every row at that exact value, including ones this
    page never returned. fact_key is unique, so carrying it alongside is what lets the
    repository's cursor exclude precisely the rows already served and nothing else.

    Takes the raw pair rather than a `ProviderUsageFact` because the repository's own cursor
    is read off the database's last row independently of whether that row parsed into a
    fact, so a page can need a cursor even when the fact it would have named was dropped.
    """
    return f"{bucket_start.isoformat()}|{fact_key}"


def _decode_cursor(raw: str) -> tuple[datetime, str | None]:
    timestamp, separator, fact_key = raw.partition("|")
    return datetime.fromisoformat(timestamp), fact_key if separator else None


def _raw_fact_or_none(fact: ProviderUsageFact) -> ProviderRawFact | None:
    """Shape one stored fact into the response row, carrying `raw` through untouched.

    `fetched_at` is dropped here rather than defaulted if it is somehow missing: it is
    guaranteed by the repository's own read guard, but the response field is not optional,
    so a fact that violates that guarantee must disappear rather than lie about when it was
    fetched.
    """
    if fact.fetched_at is None:
        return None
    return ProviderRawFact(
        bucket_start=fact.bucket_start.isoformat(),
        grain=fact.grain,
        evidence=fact.evidence,
        credential_name=fact.credential_name,
        model=fact.model,
        provider_request_id=fact.provider_request_id,
        provider_api_key_id=fact.provider_api_key_id,
        billed_cost=_plain(fact.billed_cost),
        billing_currency=fact.billing_currency,
        input_tokens=fact.input_tokens,
        output_tokens=fact.output_tokens,
        cached_input_tokens=fact.cached_input_tokens,
        cache_write_tokens=fact.cache_write_tokens,
        raw=fact.raw,
        fetched_at=fact.fetched_at.isoformat(),
    )


@router.get("/provider/usage/raw", response_model=ProviderUsageRawResponse)
async def provider_usage_raw(
    provider: str = fastapi.Query(description="Which provider's raw usage rows to read, for example openrouter"),
    limit: int = fastapi.Query(default=50, ge=1, le=200),
    before: str | None = fastapi.Query(
        default=None, description="Cursor from a previous page's next_before, to read older rows"
    ),
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
) -> ProviderUsageRawResponse:
    """The provider's own payload for one provider, newest first, keyset-paged on bucket_start."""
    from litellm.proxy.proxy_server import prisma_client

    _admin_or_403(user_api_key_dict)
    _known_provider_or_404(provider)
    if prisma_client is None:
        raise _proxy_error(status.HTTP_500_INTERNAL_SERVER_ERROR, CommonProxyErrors.db_not_connected_error.value)

    before_bucket_start: Final[datetime | None]
    before_fact_key: Final[str | None]
    if before is None:
        before_bucket_start, before_fact_key = None, None
    else:
        try:
            before_bucket_start, before_fact_key = _decode_cursor(before)
        except ValueError as error:
            raise _proxy_error(status.HTTP_400_BAD_REQUEST, f"Invalid before cursor: {error}") from error

    page: Final = await ProviderUsageFactRepository(prisma_client).recent_facts(
        provider=provider, limit=limit, before=before_bucket_start, before_fact_key=before_fact_key
    )
    rows: Final = tuple(row for fact in page.facts if (row := _raw_fact_or_none(fact)) is not None)
    next_before: Final = _encode_cursor(*page.next_cursor) if page.next_cursor is not None else None

    return ProviderUsageRawResponse(provider=provider, rows=rows, next_before=next_before)
