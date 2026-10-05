"""Serve the attribution rules and the spend that no rule claims.

The deciding is done by `token_iq/attribution/gap_owner.py` and tested there; this module
reads the rows, calls it, and shapes the answer into strings a JSON client cannot round.

`settled_before` is computed here rather than inside the decision, so the clock stays at the
edge of the system and the arithmetic stays a pure function.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Final

import fastapi
from fastapi import APIRouter, Depends, HTTPException, status

from litellm.proxy._types import CommonProxyErrors, LitellmUserRoles, UserAPIKeyAuth
from litellm.proxy.auth.user_api_key_auth import user_api_key_auth
from litellm.types.proxy.attribution import AttributionRule
from token_iq.api.types.attribution import (
    AttributionRuleBody,
    AttributionRuleDeletedResponse,
    AttributionRuleListResponse,
    AttributionRuleResponse,
    UnallocatedLine,
    UnallocatedResponse,
)
from token_iq.attribution.gap_owner import AttributedGap, attribute
from token_iq.connectors.billing.credential_purpose import BILLING_PROVIDERS
from token_iq.repositories.attribution_rule_repository import AttributionRuleRepository
from token_iq.repositories.gap_repository import GapRepository

router: Final = APIRouter(
    tags=["attribution"],  # mutable-ok: fixed single-element tag list, never grown after this line
    dependencies=(Depends(user_api_key_auth),),
)

SETTLING_DAYS: Final = 2
"""Cloud billing lands one to two days behind, so a day newer than this is still settling.

Reporting a gap on an unsettled day would show a customer money that has not finished
arriving, which reads as spend that escaped the gateway rather than a bill still in flight."""


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
        raise _proxy_error(status.HTTP_403_FORBIDDEN, "Only a proxy admin may read or change attribution rules.")


def _known_provider_or_404(provider: str) -> None:
    """Refuse a typo'd provider rather than answering an empty result.

    An empty unallocated list for a mistyped slug reads as "nothing is unassigned here",
    which is a reassuring claim we have no evidence for.
    """
    if provider not in BILLING_PROVIDERS:
        raise _proxy_error(
            status.HTTP_404_NOT_FOUND,
            f"Unknown provider {provider!r}. Valid providers: {', '.join(sorted(BILLING_PROVIDERS))}.",
        )


def _rule_response(rule: AttributionRule) -> AttributionRuleResponse:
    return AttributionRuleResponse(
        rule_id=rule.rule_id,
        provider=rule.provider,
        match_type=rule.match_type,
        match_value=rule.match_value,
        owner_type=rule.owner_type,
        owner_id=rule.owner_id,
        note=rule.note,
    )


def _line(attributed: AttributedGap) -> UnallocatedLine:
    return UnallocatedLine(
        day=attributed.row.day.date().isoformat(),
        provider=attributed.row.provider,
        credential_name=attributed.row.credential_name,
        provider_cost=None if attributed.row.provider_cost is None else _plain(attributed.row.provider_cost),
        gateway_cost=_plain(attributed.row.gateway_cost),
        gap=_plain(attributed.gap),
        state=attributed.state,
        owner_type=attributed.owner_type,
        owner_id=attributed.owner_id,
        rule_id=attributed.rule_id,
    )


def unallocated_response(*, provider: str, days: int, attributed: tuple[AttributedGap, ...]) -> UnallocatedResponse:
    """Shape the decided rows into the response the dashboard reads.

    Split out of the route so the shaping, in particular that every amount crosses as a
    string and that the two totals count disjoint sets of lines, can be tested without a
    database.
    """
    unallocated: Final = sum((a.gap for a in attributed if a.state == "unallocated"), Decimal(0))
    owned: Final = sum((a.gap for a in attributed if a.state == "owned"), Decimal(0))
    return UnallocatedResponse(
        provider=provider,
        days=days,
        total_unallocated=_plain(unallocated),
        total_owned=_plain(owned),
        lines=tuple(_line(a) for a in attributed),
    )


@router.get("/attribution/rules", response_model=AttributionRuleListResponse)
async def list_attribution_rules(
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
) -> AttributionRuleListResponse:
    """Every stored rule mapping a provider account to a team, project or user."""
    from litellm.proxy.proxy_server import prisma_client

    _admin_or_403(user_api_key_dict)
    if prisma_client is None:
        raise _proxy_error(status.HTTP_500_INTERNAL_SERVER_ERROR, CommonProxyErrors.db_not_connected_error.value)

    rules: Final = await AttributionRuleRepository(prisma_client).all()
    return AttributionRuleListResponse(rules=tuple(_rule_response(rule) for rule in rules))


@router.post("/attribution/rules", response_model=AttributionRuleResponse)
async def upsert_attribution_rule(
    body: AttributionRuleBody,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
) -> AttributionRuleResponse:
    """Assign a provider account to an owner, or reassign one that already has an owner.

    Keyed on the account, so sending a rule for an account that already has one changes its
    owner rather than failing: an admin changing their mind is the ordinary case, not an
    error.
    """
    from litellm.proxy.proxy_server import prisma_client

    _admin_or_403(user_api_key_dict)
    _known_provider_or_404(body.provider)
    if prisma_client is None:
        raise _proxy_error(status.HTTP_500_INTERNAL_SERVER_ERROR, CommonProxyErrors.db_not_connected_error.value)

    stored: Final = await AttributionRuleRepository(prisma_client).upsert(
        AttributionRule(
            rule_id="",
            provider=body.provider,
            match_type=body.match_type,
            match_value=body.match_value,
            owner_type=body.owner_type,
            owner_id=body.owner_id,
            note=body.note,
        )
    )
    if stored is None:
        raise _proxy_error(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "The rule was written but could not be read back in a shape this server understands.",
        )
    return _rule_response(stored)


@router.delete("/attribution/rules/{rule_id}", response_model=AttributionRuleDeletedResponse)
async def delete_attribution_rule(
    rule_id: str,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
) -> AttributionRuleDeletedResponse:
    """Remove a rule, after which the spend it claimed goes back to being unallocated."""
    from litellm.proxy.proxy_server import prisma_client

    _admin_or_403(user_api_key_dict)
    if prisma_client is None:
        raise _proxy_error(status.HTTP_500_INTERNAL_SERVER_ERROR, CommonProxyErrors.db_not_connected_error.value)

    deleted: Final = await AttributionRuleRepository(prisma_client).delete(rule_id)
    if not deleted:
        raise _proxy_error(status.HTTP_404_NOT_FOUND, f"No attribution rule with id {rule_id!r}.")
    return AttributionRuleDeletedResponse(deleted=True)


@router.get("/attribution/unallocated", response_model=UnallocatedResponse)
async def attribution_unallocated(
    provider: str = fastapi.Query(description="Which provider to attribute, for example openrouter"),
    days: int = fastapi.Query(default=30, ge=1, le=90),
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
) -> UnallocatedResponse:
    """Per account per day: what the provider billed, what the gateway saw, and who owns the rest."""
    from litellm.proxy.proxy_server import prisma_client

    _admin_or_403(user_api_key_dict)
    _known_provider_or_404(provider)
    if prisma_client is None:
        raise _proxy_error(status.HTTP_500_INTERNAL_SERVER_ERROR, CommonProxyErrors.db_not_connected_error.value)

    rows: Final = await GapRepository(prisma_client).rows(provider=provider, days=days)
    rules: Final = await AttributionRuleRepository(prisma_client).all()
    settled_before: Final = datetime.now(timezone.utc) - timedelta(days=SETTLING_DAYS)

    return unallocated_response(
        provider=provider, days=days, attributed=attribute(rows, rules, settled_before=settled_before)
    )
