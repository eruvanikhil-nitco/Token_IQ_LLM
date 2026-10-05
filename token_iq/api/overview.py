"""The landing page's figures, gathered once for one period.

Composed on the server rather than in the browser so every tile covers the same period and
the counting rule is applied in one place. The rule itself lives in `token_iq/overview/totals.py`
and is tested there without a database.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Final

import fastapi
from fastapi import APIRouter, Depends, HTTPException, status

from litellm.proxy._types import CommonProxyErrors, LitellmUserRoles, UserAPIKeyAuth
from litellm.proxy.auth.user_api_key_auth import user_api_key_auth
from token_iq.api.types.overview import (
    FreshnessResponse,
    MatchStatus,
    OverviewRecommendation,
    OverviewResponse,
    ProviderStandingResponse,
)
from token_iq.overview.totals import Sources, Totals, totals_for
from token_iq.recommendations.registry import evaluate
from token_iq.repositories.overview_repository import OverviewRepository, ProviderStanding

router: Final = APIRouter(
    tags=["overview"],  # mutable-ok: fixed single-element tag list, never grown after this line
    dependencies=(Depends(user_api_key_auth),),
)

TOP_RECOMMENDATIONS: Final = 3
"""A landing page shows the few worth acting on and links to the rest. A full list here would
make the page a second Recommendations screen rather than a summary of one."""

MATCH_TOLERANCE: Final = Decimal("0.000001")
"""Below this a difference is rounding, not a gap worth showing a customer."""

DEFAULT_CURRENCY: Final = "USD"


def _proxy_error(status_code: int, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"error": message},  # mutable-ok: fixed one-key error envelope, matches every other proxy endpoint
    )


def _admin_or_403(user_api_key_dict: UserAPIKeyAuth) -> None:
    if user_api_key_dict.user_role != LitellmUserRoles.PROXY_ADMIN:
        raise _proxy_error(status.HTTP_403_FORBIDDEN, "Only a proxy admin may read the overview.")


def _day_or_400(value: str, field: str) -> datetime:
    try:
        parsed: Final = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise _proxy_error(status.HTTP_400_BAD_REQUEST, f"{field} is not a date: {value!r}.") from None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def _period_end_or_400(value: str, field: str) -> datetime:
    """The last instant of the period. `.999` not `.999999`: these columns are TIMESTAMP(3)
    and Postgres rounds a microsecond value up into the next day."""
    parsed: Final = _day_or_400(value, field)
    names_a_time: Final = "T" in value or " " in value.strip()
    return parsed if names_a_time else parsed.replace(hour=23, minute=59, second=59, microsecond=999000)


def _plain(value: Decimal | None) -> str | None:
    return None if value is None else format(value, "f")


def match_status(standing: ProviderStanding) -> MatchStatus:
    """How a provider's bill compares to what the gateway recorded for it.

    A provider the gateway never saw is its own state rather than a gap of the whole amount:
    reading a provider only through its bill is a normal way to run, and calling it a
    discrepancy would put a permanent red mark on a working connection.
    """
    if standing.recorded is None:
        return "not_seen_by_gateway"
    difference: Final = standing.billed - standing.recorded
    if abs(difference) <= MATCH_TOLERANCE:
        return "matched"
    return "gateway_saw_less" if difference > 0 else "gateway_saw_more"


def overview_response(
    *,
    period_start: datetime,
    period_end: datetime,
    totals: Totals,
    providers: Sequence[ProviderStanding],
    recommendations: Sequence[OverviewRecommendation],
    freshness: Mapping[str, str],
    sources_seen: Sequence[str],
) -> OverviewResponse:
    """Shape the figures for the screen, naming every source even when it has never synced."""
    return OverviewResponse(
        period_start=period_start.date().isoformat(),
        period_end=period_end.date().isoformat(),
        currency=DEFAULT_CURRENCY,
        total=_plain(totals.total),
        previous_total=_plain(totals.previous_total),
        change=_plain(totals.change),
        attributed=_plain(totals.attributed),
        unallocated=_plain(totals.unallocated),
        unallocated_share=_plain(totals.unallocated_share),
        providers=tuple(
            ProviderStandingResponse(
                provider=standing.provider,
                billed=format(standing.billed, "f"),
                recorded=_plain(standing.recorded),
                status=match_status(standing),
            )
            for standing in providers
        ),
        recommendations=tuple(recommendations),
        freshness=tuple(
            FreshnessResponse(source=source, last_sync_at=freshness.get(source)) for source in sources_seen
        ),
    )


async def _sources_for(repository: OverviewRepository, start: datetime, end: datetime, unallocated: Decimal) -> Sources:
    provider_billed: Final = await repository.provider_billed(start, end)
    tool_new_money: Final = await repository.tool_new_money(start, end)
    seats: Final = await repository.seats(start, end)
    gateway_recorded: Final = await repository.gateway_recorded(start, end)
    return Sources(
        provider_billed=provider_billed,
        tool_new_money=tool_new_money,
        seats=seats,
        gateway_recorded=gateway_recorded,
        unallocated=unallocated,
        has_any_data=any(figure > 0 for figure in (provider_billed, tool_new_money, seats, gateway_recorded)),
    )


@router.get("/overview", response_model=OverviewResponse)
async def overview(
    period_start: str = fastapi.Query(description="First day of the period, as YYYY-MM-DD"),
    period_end: str = fastapi.Query(description="Last day of the period, as YYYY-MM-DD"),
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
) -> OverviewResponse:
    """What was spent, whether the bills matched, what nobody owns, and what to do about it."""
    from litellm.proxy.proxy_server import prisma_client
    from token_iq.api.recommendations import gather_rule_input

    _admin_or_403(user_api_key_dict)
    start: Final = _day_or_400(period_start, "period_start")
    end: Final = _period_end_or_400(period_end, "period_end")
    if prisma_client is None:
        raise _proxy_error(status.HTTP_500_INTERNAL_SERVER_ERROR, CommonProxyErrors.db_not_connected_error.value)

    repository: Final = OverviewRepository(prisma_client)
    rule_input: Final = await gather_rule_input(prisma_client, start=start, end=end)

    current: Final = await _sources_for(repository, start, end, rule_input.unallocated)

    # The same length of period immediately before this one, so the comparison is like for like.
    span: Final = end - start
    previous: Final = await _sources_for(
        repository, start - span - timedelta(days=1), start - timedelta(days=1), Decimal(0)
    )

    providers: Final = await repository.by_provider(start, end)
    cards: Final = evaluate(rule_input)[:TOP_RECOMMENDATIONS]

    return overview_response(
        period_start=start,
        period_end=end,
        totals=totals_for(current, previous),
        providers=providers,
        recommendations=tuple(
            OverviewRecommendation(
                rule_id=card.rule_id,
                title=card.title,
                kind=card.kind,
                figure=_plain(card.figure),
                figure_kind=card.figure_kind,
                currency=card.currency,
            )
            for card in cards
        ),
        freshness=await repository.freshness(),
        sources_seen=tuple(standing.provider for standing in providers),
    )
