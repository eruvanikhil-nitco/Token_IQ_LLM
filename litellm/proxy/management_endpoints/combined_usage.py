"""Serve the Combined usage views: what the providers billed against what the gateway recorded.

The comparison itself lives in `token_iq/repositories/gap_repository.py` and the decision about
who owns each difference in `token_iq/attribution/gap_owner.py`, both tested there. This module
reads the rows, calls them, and shapes the answer into strings a JSON client cannot round.

The two figures are reported side by side and never added. A customer reading one number that
mixed them would be counting the same request twice: once where the gateway logged it and once
where the provider billed it.
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
from litellm.types.proxy.management_endpoints.combined_endpoints import (
    ComparisonDay,
    ComparisonResponse,
    ComparisonStatus,
    ExplorerResponse,
    ExplorerSlice,
)
from token_iq.attribution.gap_owner import AttributedGap, attribute
from token_iq.connectors.billing.fetch_profile import FETCH_PROFILES
from token_iq.repositories.attribution_rule_repository import AttributionRuleRepository
from token_iq.repositories.gap_repository import GapRepository
from token_iq.repositories.gateway_spend_repository import (
    ExplorerDimension,
    GatewaySpendRepository,
    SpendSlice,
)

router: Final = APIRouter(
    tags=["combined usage"],  # mutable-ok: fixed single-element tag list, never grown after this line
    dependencies=(Depends(user_api_key_auth),),
)

SETTLING_DAYS: Final = 2
"""Cloud billing lands one to two days behind, so a day newer than this is still settling."""

_STATUS_OF: Final[Mapping[str, ComparisonStatus]] = MappingProxyType(
    {
        "owned": "gap",
        "unallocated": "gap",
        "matched": "matched",
        "not_settled": "not_settled",
        "no_provider_data": "no_provider_data",
    }
)
"""Owned and unallocated are both a gap.

The status column answers one question, whether the two sources agree. Who owns the difference
is a separate column, so collapsing them here keeps each column honest about what it reports."""


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
        raise _proxy_error(status.HTTP_403_FORBIDDEN, "Only a proxy admin may read cross-team combined usage.")


def _display_name(provider: str) -> str:
    """The same name the connections and usage pages use, so one provider is never called two
    things on two screens. A provider with no profile falls back to its own slug rather than
    disappearing from a comparison it belongs in."""
    profile: Final = FETCH_PROFILES.get(provider)
    return profile.display_name if profile is not None else provider


def _comparison_day(attributed: AttributedGap) -> ComparisonDay:
    return ComparisonDay(
        day=attributed.row.day.date().isoformat(),
        provider=attributed.row.provider,
        display_name=_display_name(attributed.row.provider),
        credential_name=attributed.row.credential_name,
        gateway_cost=_plain(attributed.row.gateway_cost),
        provider_cost=None if attributed.row.provider_cost is None else _plain(attributed.row.provider_cost),
        gap=_plain(attributed.gap),
        status=_STATUS_OF[attributed.state],
        owner_type=attributed.owner_type,
        owner_id=attributed.owner_id,
    )


def comparison_response(*, days: int, attributed: tuple[AttributedGap, ...]) -> ComparisonResponse:
    """Shape the decided rows into the response the Combined screen reads.

    Split out of the route so the shaping, in particular that the three totals stay three
    figures, can be tested without a database.

    A day that was not compared contributes to no total: an unsettled day or one the provider
    has said nothing about would otherwise drag the gateway total up against a provider total
    that has no matching figure yet.
    """
    compared: Final = tuple(a for a in attributed if a.state in ("owned", "unallocated", "matched"))
    return ComparisonResponse(
        days=days,
        rows=tuple(_comparison_day(a) for a in attributed),
        total_gateway=_plain(sum((a.row.gateway_cost for a in compared), Decimal(0))),
        total_provider=_plain(sum((a.row.provider_cost or Decimal(0) for a in compared), Decimal(0))),
        total_gap=_plain(sum((a.gap for a in compared), Decimal(0))),
    )


@router.get("/usage/combined/comparison", response_model=ComparisonResponse)
async def combined_comparison(
    days: int = fastapi.Query(default=30, ge=1, le=90),
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
) -> ComparisonResponse:
    """Per provider per day: what the provider billed, what the gateway recorded, and the difference."""
    from litellm.proxy.proxy_server import prisma_client

    _admin_or_403(user_api_key_dict)
    if prisma_client is None:
        raise _proxy_error(status.HTTP_500_INTERNAL_SERVER_ERROR, CommonProxyErrors.db_not_connected_error.value)

    rows: Final = await GapRepository(prisma_client).rows(provider=None, days=days)
    rules: Final = await AttributionRuleRepository(prisma_client).all()
    settled_before: Final = datetime.now(timezone.utc) - timedelta(days=SETTLING_DAYS)

    return comparison_response(days=days, attributed=attribute(rows, rules, settled_before=settled_before))


_OWNER_DIMENSIONS: Final[frozenset[str]] = frozenset({"team", "project", "user"})
"""The only dimensions an attribution rule can name.

A rule assigns an account to a team, project or user, never to a model or a provider. So when
the reader groups by model or provider, outside-gateway spend has nowhere to land and belongs
in its own figure rather than being spread across slices it was never attributed to."""


def _note_for(dimension: str, *, slices: int, unattributable: Decimal) -> str:
    """Plain sentences a customer reads, and the only place this screen explains itself.

    Each branch names something the numbers cannot say on their own, so a reader is never left
    to guess why a figure is absent or why one sits apart from the rest.
    """
    if slices == 0:
        return f"No {dimension} spend recorded in this window."
    if dimension not in _OWNER_DIMENSIONS and unattributable > 0:
        return (
            f"Spend that bypassed the gateway cannot be shown per {dimension}, because an "
            f"attribution rule names a team, project or user and not a {dimension}. It is "
            f"reported on its own below."
        )
    if unattributable > 0:
        return "Some spend that bypassed the gateway has no rule assigning it to an owner."
    return ""


def explorer_response(
    *,
    dimension: str,
    days: int,
    slices: tuple[SpendSlice, ...],
    gateway_total: Decimal,
    attributed: tuple[AttributedGap, ...],
) -> ExplorerResponse:
    """Put the two sources side by side for one grouping, without ever adding them.

    Split out of the route so the arithmetic, in particular that nothing is invented and
    nothing is quietly dropped, can be tested without a database.
    """
    owned: Final = tuple(a for a in attributed if a.state == "owned" and a.owner_id is not None)
    per_owner: Final[Mapping[str, Decimal]] = MappingProxyType(
        {
            owner: sum((a.gap for a in owned if a.owner_id == owner and a.owner_type == dimension), Decimal(0))
            for owner in frozenset(a.owner_id for a in owned if a.owner_type == dimension)
        }
    )
    placed: Final = sum(per_owner.values(), Decimal(0))
    outside_total: Final = sum((a.gap for a in attributed if a.state in ("owned", "unallocated")), Decimal(0))
    sliced: Final = sum((s.gateway_cost for s in slices), Decimal(0))
    unattributable: Final = outside_total - placed

    return ExplorerResponse(
        dimension=dimension,
        days=days,
        slices=tuple(
            ExplorerSlice(
                key=s.key,
                through_gateway=_plain(s.gateway_cost),
                outside_gateway=_plain(per_owner.get(s.key, Decimal(0))),
            )
            for s in slices
        ),
        total_through_gateway=_plain(gateway_total),
        total_outside_gateway=_plain(outside_total),
        unallocated_to_a_slice=_plain(gateway_total - sliced),
        unattributable_outside_gateway=_plain(unattributable),
        note=_note_for(dimension, slices=len(slices), unattributable=unattributable),
    )


@router.get("/usage/combined/explorer", response_model=ExplorerResponse)
async def combined_explorer(
    dimension: ExplorerDimension = fastapi.Query(default="team", description="Group spend by this"),
    days: int = fastapi.Query(default=30, ge=1, le=90),
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
) -> ExplorerResponse:
    """Gateway spend and spend that bypassed the gateway, grouped by one dimension."""
    from litellm.proxy.proxy_server import prisma_client

    _admin_or_403(user_api_key_dict)
    if prisma_client is None:
        raise _proxy_error(status.HTTP_500_INTERNAL_SERVER_ERROR, CommonProxyErrors.db_not_connected_error.value)

    spend: Final = GatewaySpendRepository(prisma_client)
    slices: Final = await spend.by_dimension(dimension=dimension, days=days)
    gateway_total: Final = await spend.total(dimension=dimension, days=days)
    rows: Final = await GapRepository(prisma_client).rows(provider=None, days=days)
    rules: Final = await AttributionRuleRepository(prisma_client).all()
    settled_before: Final = datetime.now(timezone.utc) - timedelta(days=SETTLING_DAYS)

    return explorer_response(
        dimension=dimension,
        days=days,
        slices=slices,
        gateway_total=gateway_total,
        attributed=attribute(rows, rules, settled_before=settled_before),
    )
