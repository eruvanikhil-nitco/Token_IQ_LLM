"""Serve the recommendations, and remember what an admin decided about each.

The rules live in `token_iq/recommendations/` and are pure. This module gathers the slices they
read, once, runs them, and shapes the answer.

A card is never stored. It is recomputed from current data on every request, so a problem that
is fixed stops appearing on its own, and one that returns is seen again rather than staying
hidden behind a decision made months ago.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import MappingProxyType
from typing import Final

import fastapi
from fastapi import APIRouter, Depends, HTTPException, status

from litellm.proxy._types import CommonProxyErrors, LitellmUserRoles, UserAPIKeyAuth
from litellm.proxy.auth.user_api_key_auth import user_api_key_auth
from token_iq.api.types.recommendations import (
    DecisionBody,
    DecisionResponse,
    EvidenceResponse,
    RecommendationResponse,
    RecommendationsResponse,
)
from token_iq.attribution.gap_owner import attribute
from token_iq.recommendations.inputs import BudgetSnapshot, RuleInput
from token_iq.recommendations.registry import evaluate
from token_iq.repositories.attribution_rule_repository import AttributionRuleRepository
from token_iq.repositories.gap_repository import GapRepository
from token_iq.repositories.recommendation_state_repository import (
    DecisionState,
    RecommendationStateRepository,
)
from token_iq.types.recommendation import Recommendation

router: Final = APIRouter(
    tags=["recommendations"],  # mutable-ok: fixed single-element tag list, never grown after this line
    dependencies=(Depends(user_api_key_auth),),
)

SETTLING_DAYS: Final = 2

_FAILED_AND_TOTAL_SQL: Final = """
SELECT COALESCE(SUM(d.failed_requests), 0)::int AS failed,
       COALESCE(SUM(d.api_requests), 0)::int    AS total
  FROM "LiteLLM_DailyTeamSpend" d
 WHERE d.date >= $1 AND d.date <= $2
"""

_SPEND_BY_PROVIDER_SQL: Final = """
SELECT f.provider                        AS provider,
       SUM(f.billed_cost::numeric)::text AS spend
  FROM "LiteLLM_ProviderUsageFact" f
 WHERE f.bucket_start >= $1::timestamp AND f.bucket_start <= $2::timestamp
 GROUP BY 1
"""

_BUDGETS_SQL: Final = """
SELECT t.team_id                                AS owner,
       t.max_budget::numeric::text              AS limit_amount,
       COALESCE(t.spend, 0)::numeric::text      AS spent
  FROM "LiteLLM_TeamTable" t
 WHERE t.max_budget IS NOT NULL AND t.max_budget > 0
"""


def _plain(value: Decimal) -> str:
    return format(value, "f")


def _proxy_error(status_code: int, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"error": message},  # mutable-ok: fixed one-key error envelope, matches every other proxy endpoint
    )


def _admin_or_403(user_api_key_dict: UserAPIKeyAuth) -> None:
    if user_api_key_dict.user_role != LitellmUserRoles.PROXY_ADMIN:
        raise _proxy_error(status.HTTP_403_FORBIDDEN, "Only a proxy admin may read cross-team recommendations.")


def _day_or_400(value: str, field: str) -> datetime:
    try:
        parsed: Final = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise _proxy_error(status.HTTP_400_BAD_REQUEST, f"{field} is not a date: {value!r}.") from None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def _period_end_or_400(value: str, field: str) -> datetime:
    """The last instant of the period. `.999` not `.999999`, because these columns are
    TIMESTAMP(3) and Postgres rounds a microsecond value up into the next day."""
    parsed: Final = _day_or_400(value, field)
    names_a_time: Final = "T" in value or " " in value.strip()
    return parsed if names_a_time else parsed.replace(hour=23, minute=59, second=59, microsecond=999000)


def _decimal_or_zero(value: object) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return Decimal(0)
    try:
        return Decimal(str(value))
    except ArithmeticError:
        return Decimal(0)


def _card_response(card: Recommendation, state: DecisionState | None) -> RecommendationResponse:
    return RecommendationResponse(
        rule_id=card.rule_id,
        kind=card.kind,
        title=card.title,
        noticed=card.noticed,
        evidence=tuple(EvidenceResponse(label=e.label, value=e.value) for e in card.evidence),
        figure=None if card.figure is None else _plain(card.figure),
        figure_kind=card.figure_kind,
        currency=card.currency,
        who_should_act=card.who_should_act,
        state=state,
    )


def recommendations_response(
    *,
    period_start: datetime,
    period_end: datetime,
    cards: tuple[Recommendation, ...],
    states: Mapping[str, DecisionState],
) -> RecommendationsResponse:
    """Split the cards into the ones still open and the ones already decided.

    A decided card is still reported rather than dropped: someone needs to be able to see what
    was dismissed and bring it back, and a card that vanishes without trace looks like a bug.
    """
    shaped: Final = tuple(_card_response(card, states.get(card.rule_id)) for card in cards)
    return RecommendationsResponse(
        period_start=period_start.date().isoformat(),
        period_end=period_end.date().isoformat(),
        open=tuple(c for c in shaped if c.state is None),
        decided=tuple(c for c in shaped if c.state is not None),
    )


async def gather_rule_input(prisma_client: object, *, start: datetime, end: datetime) -> RuleInput:
    """Every slice the rules read, gathered once so each rule stays pure."""
    db: Final = prisma_client.db  # pyright: ignore[reportAttributeAccessIssue]  # object has no .db attr

    gaps: Final = await GapRepository(prisma_client).rows(provider=None, days=(end - start).days + 1)
    rules: Final = await AttributionRuleRepository(prisma_client).all()
    attributed: Final = attribute(
        gaps, rules, settled_before=datetime.now(timezone.utc) - timedelta(days=SETTLING_DAYS)
    )
    unallocated: Final = sum((a.gap for a in attributed if a.state == "unallocated"), Decimal(0))
    accounts: Final = tuple(sorted(frozenset(a.row.credential_name for a in attributed if a.state == "unallocated")))

    requests: Final = await db.query_raw(_FAILED_AND_TOTAL_SQL, start.date().isoformat(), end.date().isoformat())
    by_provider: Final = await db.query_raw(_SPEND_BY_PROVIDER_SQL, start.isoformat(), end.isoformat())
    budget_rows: Final = await db.query_raw(_BUDGETS_SQL)

    return RuleInput(
        unallocated=unallocated,
        unallocated_accounts=accounts,
        failed_requests=int(requests[0].get("failed") or 0) if requests else 0,
        total_requests=int(requests[0].get("total") or 0) if requests else 0,
        spend_on_failures=None,
        spend_by_provider=MappingProxyType(
            {str(row["provider"]): _decimal_or_zero(row.get("spend")) for row in by_provider}
        ),
        budgets=tuple(
            BudgetSnapshot(
                budget_id=str(row.get("owner")),
                owner=str(row.get("owner")),
                limit=_decimal_or_zero(row.get("limit_amount")),
                spent=_decimal_or_zero(row.get("spent")),
            )
            for row in budget_rows
        ),
    )


@router.get("/recommendations", response_model=RecommendationsResponse)
async def recommendations(
    period_start: str = fastapi.Query(description="First day of the period, as YYYY-MM-DD"),
    period_end: str = fastapi.Query(description="Last day of the period, as YYYY-MM-DD"),
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
) -> RecommendationsResponse:
    """Everything worth doing about this period, and what was already decided."""
    from litellm.proxy.proxy_server import prisma_client

    _admin_or_403(user_api_key_dict)
    start: Final = _day_or_400(period_start, "period_start")
    end: Final = _period_end_or_400(period_end, "period_end")
    if prisma_client is None:
        raise _proxy_error(status.HTTP_500_INTERNAL_SERVER_ERROR, CommonProxyErrors.db_not_connected_error.value)

    rule_input: Final = await gather_rule_input(prisma_client, start=start, end=end)
    states: Final = await RecommendationStateRepository(prisma_client).all()

    return recommendations_response(period_start=start, period_end=end, cards=evaluate(rule_input), states=states)


@router.post("/recommendations/{rule_id}/state", response_model=DecisionResponse)
async def decide_recommendation(
    rule_id: str,
    body: DecisionBody,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
) -> DecisionResponse:
    """Mark a card done or dismissed."""
    from litellm.proxy.proxy_server import prisma_client

    _admin_or_403(user_api_key_dict)
    if prisma_client is None:
        raise _proxy_error(status.HTTP_500_INTERNAL_SERVER_ERROR, CommonProxyErrors.db_not_connected_error.value)

    written: Final = await RecommendationStateRepository(prisma_client).decide(
        rule_id=rule_id, state=body.state, decided_by=user_api_key_dict.user_id, note=body.note
    )
    if not written:
        raise _proxy_error(status.HTTP_500_INTERNAL_SERVER_ERROR, "The decision could not be recorded.")
    return DecisionResponse(rule_id=rule_id, state=body.state)


@router.delete("/recommendations/{rule_id}/state", response_model=DecisionResponse)
async def undo_recommendation_decision(
    rule_id: str,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
) -> DecisionResponse:
    """Bring a card back to the open list."""
    from litellm.proxy.proxy_server import prisma_client

    _admin_or_403(user_api_key_dict)
    if prisma_client is None:
        raise _proxy_error(status.HTTP_500_INTERNAL_SERVER_ERROR, CommonProxyErrors.db_not_connected_error.value)

    cleared: Final = await RecommendationStateRepository(prisma_client).clear(rule_id)
    if not cleared:
        raise _proxy_error(status.HTTP_404_NOT_FOUND, f"No decision recorded for {rule_id!r}.")
    return DecisionResponse(rule_id=rule_id, state=None)
