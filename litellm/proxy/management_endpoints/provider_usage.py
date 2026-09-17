"""Serve one provider's usage summary over HTTP.

The arithmetic lives in `usage_summary.py` and is tested there; this module only reads the
rows, calls it, and shapes the result into strings a JSON client cannot round.
"""

from __future__ import annotations

from decimal import Decimal
from types import MappingProxyType
from typing import Final

import fastapi
from fastapi import APIRouter, Depends, HTTPException, status

from litellm.provider_billing.credential_purpose import BILLING_PROVIDERS
from litellm.provider_billing.fetch_profile import FETCH_PROFILES
from litellm.provider_billing.usage_summary import UsageSummary, build_usage_summary
from litellm.proxy._types import CommonProxyErrors, LitellmUserRoles, UserAPIKeyAuth
from litellm.proxy.auth.user_api_key_auth import user_api_key_auth
from litellm.repositories.provider_usage_fact_repository import ProviderUsageFactRepository
from litellm.types.proxy.management_endpoints.team_endpoints import (
    ProviderAccountSpend,
    ProviderModelSpend,
    ProviderTokenTotals,
    ProviderUsageSummaryResponse,
)

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
    if provider not in BILLING_PROVIDERS:
        raise _proxy_error(
            status.HTTP_404_NOT_FOUND,
            f"Unknown provider {provider!r}. Valid providers: {', '.join(sorted(BILLING_PROVIDERS))}.",
        )
    if prisma_client is None:
        raise _proxy_error(status.HTTP_500_INTERNAL_SERVER_ERROR, CommonProxyErrors.db_not_connected_error.value)

    facts: Final = ProviderUsageFactRepository(prisma_client)
    rows: Final = await facts.summary_rows(provider=provider, days=days)
    tokens: Final = await facts.token_totals(provider=provider, days=days)

    return usage_summary_response(provider=provider, days=days, summary=build_usage_summary(rows, tokens))
