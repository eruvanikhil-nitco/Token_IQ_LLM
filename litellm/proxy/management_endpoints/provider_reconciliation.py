"""What we recorded against what the provider charged.

Only rows the provider has actually priced count toward their total. Treating a missing
provider figure as zero would report a saving that does not exist, so those rows are
counted separately and shown rather than dropped: each one is either a polling backlog or
spend the provider never billed, and an operator needs to be able to tell which.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Final

import fastapi
from fastapi import APIRouter, Depends, HTTPException, status

from litellm.provider_billing.connector import BillingConnector, registered_connectors
from litellm.provider_billing.runner import LOOKBACK
from litellm.provider_billing.scheduled import build_billing_credential_lookup
from litellm.proxy._types import CommonProxyErrors, LitellmUserRoles, UserAPIKeyAuth
from litellm.proxy.auth.user_api_key_auth import user_api_key_auth
from litellm.types.proxy.management_endpoints.team_endpoints import (
    BillingProbeResponse,
    ReconciliationResponse,
    ReconciliationRow,
)
from litellm.types.proxy.provider_billing import Fetched, FetchFailed, NotConfigured

router: Final = APIRouter()

_MAX_ROWS: Final = 1000
"""Spend logs grow without limit. An unbounded query here would eventually take the
database down while someone is looking at a dashboard."""

_SQL: Final = f"""
SELECT s.request_id,
       s.model,
       COALESCE(s.provider_credential, '') AS credential_name,
       s.spend::numeric       AS our_cost,
       f.billed_cost::numeric AS their_cost,
       COALESCE(f.evidence, 'allocated') AS evidence
  FROM "LiteLLM_SpendLogs" s
  LEFT JOIN "LiteLLM_ProviderUsageFact" f
         ON f.provider_request_id = s.request_id
        AND f.provider = $1
 WHERE s.custom_llm_provider = $1
   AND s."startTime" >= NOW() - ($2 || ' days')::interval
 ORDER BY s."startTime" DESC
 LIMIT {_MAX_ROWS}
"""


def _plain(value: Decimal) -> str:
    """Fixed-point, never scientific notation.

    Decimal renders small results as 5E-7, and subtracting two token costs almost always
    produces one. A finance screen showing 5E-7 reads as broken.
    """
    return format(value, "f")


def _decimal(value: object) -> Decimal | None:
    if isinstance(value, Decimal):
        return value
    if not isinstance(value, (int, float, str)):
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


@router.get(
    "/provider/reconciliation",
    tags=["provider billing"],
    dependencies=[Depends(user_api_key_auth)],
    response_model=ReconciliationResponse,
)
async def provider_reconciliation(
    provider: str = fastapi.Query(description="Which provider to reconcile, for example openrouter"),
    days: int = fastapi.Query(default=7, ge=1, le=31),
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
) -> ReconciliationResponse:
    """Every request in the window, priced by us and by the provider, with the difference."""
    from litellm.proxy.proxy_server import prisma_client

    if user_api_key_dict.user_role != LitellmUserRoles.PROXY_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "Only a proxy admin may read cross-team provider reconciliation."},
        )
    if prisma_client is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": CommonProxyErrors.db_not_connected_error.value},
        )

    raw: Final[Sequence[Mapping[str, object]]] = await prisma_client.db.query_raw(_SQL, provider, str(days))

    priced: Final = tuple(
        (
            str(row.get("request_id") or ""),
            row.get("model") if isinstance(row.get("model"), str) else None,
            str(row.get("credential_name") or ""),
            _decimal(row.get("our_cost")) or Decimal(0),
            _decimal(row.get("their_cost")),
            str(row.get("evidence") or "allocated"),
        )
        for row in raw
    )

    our_total: Final = sum((ours for _, _, _, ours, _, _ in priced), Decimal(0))
    their_total: Final = sum((theirs for *_, theirs, _ in priced if theirs is not None), Decimal(0))

    return ReconciliationResponse(
        provider=provider,
        rows=[
            ReconciliationRow(
                request_id=request_id,
                model=model,
                credential_name=credential_name,
                our_cost=_plain(ours),
                their_cost=None if theirs is None else _plain(theirs),
                delta=None if theirs is None else _plain(ours - theirs),
                evidence=evidence,
            )
            for request_id, model, credential_name, ours, theirs, evidence in priced
        ],
        our_total=_plain(our_total),
        their_total=_plain(their_total),
        delta=_plain(our_total - their_total),
        unmatched_our_rows=sum(1 for *_, theirs, _ in priced if theirs is None),
    )


async def run_billing_probe(
    *,
    provider: str,
    connectors: Sequence[BillingConnector],
    credentials_for: Callable[[str], Awaitable[tuple[str, Mapping[str, str]] | None]],
) -> BillingProbeResponse:
    """One fetch from a provider's billing API, reported without storing anything.

    Split out of the route so it can be exercised directly: the Anthropic and OpenAI
    connectors could not be verified against a live provider when they were written,
    because this deployment had no organisation admin key.
    """
    connector: Final = next((entry for entry in connectors if entry.provider == provider), None)
    if connector is None:
        return BillingProbeResponse(
            provider=provider,
            outcome="no_connector",
            facts_found=0,
            sample_cost=None,
            detail="This build ships no billing connector for that provider.",
        )

    credential: Final = await credentials_for(provider)
    if credential is None:
        return BillingProbeResponse(
            provider=provider,
            outcome="not_configured",
            facts_found=0,
            sample_cost=None,
            detail=(
                "No stored credential is marked for this provider. Create one whose "
                f'credential_info is {{"purpose": "billing_ingestion", "provider": "{provider}"}}.'
            ),
        )
    credential_name, credential_values = credential

    now: Final = datetime.now(timezone.utc)
    result: Final = await connector.fetch(
        since=now - LOOKBACK,
        until=now,
        credential_name=credential_name,
        credential_values=credential_values,
    )

    match result:
        case Fetched(facts=facts):
            return BillingProbeResponse(
                provider=provider,
                outcome="fetched",
                facts_found=len(facts),
                sample_cost=_plain(facts[0].billed_cost) if facts else None,
                detail=None if facts else "The provider answered but reported nothing in this window.",
            )
        case NotConfigured(reason=reason):
            return BillingProbeResponse(
                provider=provider, outcome="not_configured", facts_found=0, sample_cost=None, detail=reason
            )
        case FetchFailed(reason=reason, retryable=retryable):
            return BillingProbeResponse(
                provider=provider,
                outcome="failed",
                facts_found=0,
                sample_cost=None,
                detail=f"{reason} (retryable={retryable})",
            )


@router.post(
    "/provider/billing/probe",
    tags=["provider billing"],
    dependencies=[Depends(user_api_key_auth)],
    response_model=BillingProbeResponse,
)
async def provider_billing_probe(
    provider: str = fastapi.Query(description="Which provider's billing API to try"),
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
) -> BillingProbeResponse:
    """Try one provider's billing API now and report what came back."""
    from litellm.proxy.proxy_server import prisma_client

    if user_api_key_dict.user_role != LitellmUserRoles.PROXY_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "Only a proxy admin may probe a provider's billing API."},
        )

    return await run_billing_probe(
        provider=provider,
        connectors=registered_connectors(),
        credentials_for=build_billing_credential_lookup(prisma_client=prisma_client),
    )
