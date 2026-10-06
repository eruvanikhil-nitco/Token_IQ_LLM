"""What state each provider connection is in, and what it has been doing.

The assembly is split out of the routes so it can be tested without a database: these are
the two screens a customer looks at when they think their bill is wrong.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping, Sequence
from types import MappingProxyType
from typing import Final, TypeAlias

import fastapi
from fastapi import APIRouter, Depends, HTTPException, status

from token_iq.gateway.proxy._types import CommonProxyErrors, LitellmUserRoles, UserAPIKeyAuth
from token_iq.gateway.proxy.auth.user_api_key_auth import user_api_key_auth
from token_iq.gateway.types.proxy.management_endpoints.team_endpoints import (
    ProviderConnection,
    ProviderConnectionAccount,
    ProviderConnectionsResponse,
    ProviderFetchDetail,
    ProviderSyncHistoryResponse,
    ProviderSyncHistoryRow,
)
from token_iq.connectors.billing.connection_state import (
    ConnectionState,
    account_state,
    provider_state,
    verified_against_real_account,
)
from token_iq.connectors.billing.credential_purpose import BILLING_PROVIDERS
from token_iq.connectors.billing.fetch_profile import FETCH_PROFILES, FetchProfile
from token_iq.connectors.billing.scheduled import build_billing_credentials_lookup
from token_iq.repositories.provider_sync_run_repository import ProviderSyncRunRepository
from token_iq.repositories.provider_usage_fact_repository import ProviderUsageFactRepository
from token_iq.types.provider_billing import BillingCredential, ProviderSyncRun

router: Final = APIRouter(
    tags=["provider billing"],  # mutable-ok: fixed single-element tag list, never grown after this line
    dependencies=(Depends(user_api_key_auth),),
)

_RUNS_FOR_STATE: Final = 200
"""Enough recent runs to find the newest one per account across every provider in one read."""

_MAX_HISTORY_ROWS: Final = 200

_AccountResult: TypeAlias = tuple[BillingCredential, ProviderSyncRun | None, ConnectionState, str | None]


def _proxy_error(status_code: int, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"error": message},  # mutable-ok: fixed one-key error envelope, matches every other proxy endpoint
    )


def _admin_or_403(user_api_key_dict: UserAPIKeyAuth) -> None:
    if user_api_key_dict.user_role != LitellmUserRoles.PROXY_ADMIN:
        raise _proxy_error(status.HTTP_403_FORBIDDEN, "Only a proxy admin may read provider connections.")


def _fetch_detail(profile: FetchProfile) -> ProviderFetchDetail:
    return ProviderFetchDetail(
        endpoint=profile.endpoint,
        endpoint_url=profile.endpoint_url,
        grain=profile.grain,
        refresh_seconds=profile.refresh_seconds,
        window_hours=profile.window_hours,
        delay_note=profile.delay_note,
        history_note=profile.history_note,
    )


def _newest_per_account(runs: Sequence[ProviderSyncRun], provider: str) -> Mapping[str, ProviderSyncRun]:
    """Runs arrive newest first. Iterating in reverse makes the newest run for an account
    the last write into the map, so it is the one that survives."""
    return MappingProxyType({run.credential_name: run for run in reversed(runs) if run.provider == provider})


def _account_result(
    credential: BillingCredential, *, newest: Mapping[str, ProviderSyncRun], counts: Mapping[str, int]
) -> _AccountResult:
    last_run: Final = newest.get(credential.name)
    state, detail = account_state(last_run=last_run, facts_stored=counts.get(credential.name, 0))
    return (credential, last_run, state, detail)


def _connection(
    *,
    provider: str,
    credentials: Sequence[BillingCredential],
    newest: Mapping[str, ProviderSyncRun],
    counts: Mapping[str, int],
) -> ProviderConnection:
    """One provider's row, and one row per stored account inside it."""
    results: Final = tuple(_account_result(credential, newest=newest, counts=counts) for credential in credentials)
    profile: Final = FETCH_PROFILES[provider]

    return ProviderConnection(
        provider=provider,
        display_name=profile.display_name,
        state=provider_state(tuple(state for _, _, state, _ in results)),
        accounts=tuple(
            ProviderConnectionAccount(
                credential_name=credential.name,
                state=state,
                detail=detail,
                last_sync_at=None if last_run is None else last_run.finished_at.isoformat(),
                last_outcome=None if last_run is None else last_run.outcome,
                facts_stored=counts.get(credential.name, 0),
            )
            for credential, last_run, state, detail in results
        ),
        fetches=_fetch_detail(profile),
        verified_against_real_account=verified_against_real_account(
            tuple(counts.get(credential.name, 0) for credential in credentials)
        ),
    )


async def build_provider_connections(
    *,
    providers: Sequence[str],
    credentials_for: Callable[[str], Awaitable[tuple[BillingCredential, ...]]],
    recent_runs: Sequence[ProviderSyncRun],
    fact_counts_for: Callable[[str], Mapping[str, int]],
) -> ProviderConnectionsResponse:
    """One row per provider, with one row per stored account inside it.

    Credentials for every provider are fetched concurrently, since nothing below needs
    them in provider order and awaiting one provider at a time would only make the
    endpoint slower as more providers are added.
    """
    credential_sets: Final = await asyncio.gather(*(credentials_for(provider) for provider in providers))

    return ProviderConnectionsResponse(
        providers=tuple(
            _connection(
                provider=provider,
                credentials=credentials,
                newest=_newest_per_account(recent_runs, provider),
                counts=fact_counts_for(provider),
            )
            for provider, credentials in zip(providers, credential_sets)
        )
    )


@router.get("/provider/connections", response_model=ProviderConnectionsResponse)
async def provider_connections(
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
) -> ProviderConnectionsResponse:
    """Every provider this build can read a bill from, and the state of each connection."""
    from token_iq.gateway.proxy.proxy_server import prisma_client

    _admin_or_403(user_api_key_dict)
    if prisma_client is None:
        raise _proxy_error(status.HTTP_500_INTERNAL_SERVER_ERROR, CommonProxyErrors.db_not_connected_error.value)

    facts: Final = ProviderUsageFactRepository(prisma_client)
    counts: Final = MappingProxyType(
        {provider: await facts.counts_by_credential(provider) for provider in sorted(BILLING_PROVIDERS)}
    )

    return await build_provider_connections(
        providers=sorted(BILLING_PROVIDERS),
        credentials_for=build_billing_credentials_lookup(prisma_client=prisma_client),
        recent_runs=await ProviderSyncRunRepository(prisma_client).recent(limit=_RUNS_FOR_STATE),
        fact_counts_for=lambda provider: counts[provider],
    )


@router.get("/provider/sync-history", response_model=ProviderSyncHistoryResponse)
async def provider_sync_history(
    provider: str = fastapi.Query(description="Which provider's fetch history to read"),
    limit: int = fastapi.Query(default=50, ge=1, le=_MAX_HISTORY_ROWS),
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
) -> ProviderSyncHistoryResponse:
    """Recent fetch attempts for one provider, newest first."""
    from token_iq.gateway.proxy.proxy_server import prisma_client

    _admin_or_403(user_api_key_dict)
    if prisma_client is None:
        raise _proxy_error(status.HTTP_500_INTERNAL_SERVER_ERROR, CommonProxyErrors.db_not_connected_error.value)

    runs: Final = await ProviderSyncRunRepository(prisma_client).recent(provider=provider, limit=limit)

    return ProviderSyncHistoryResponse(
        rows=tuple(
            ProviderSyncHistoryRow(
                provider=run.provider,
                credential_name=run.credential_name,
                started_at=run.started_at.isoformat(),
                finished_at=run.finished_at.isoformat(),
                outcome=run.outcome,
                facts_written=run.facts_written,
                window_start=run.window_start.isoformat(),
                window_end=run.window_end.isoformat(),
                detail=run.detail,
            )
            for run in runs
        )
    )
