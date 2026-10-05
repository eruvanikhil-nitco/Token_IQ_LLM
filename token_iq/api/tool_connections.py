"""What state each user tool connection is in, and what it can tell us.

Mirrors `provider_connections.py`, with one addition that matters more here than there. No
tool connector has met a real account, and two of the three cannot report everything a reader
would assume, so each tool states plainly what it gives and what it cannot.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from types import MappingProxyType
from typing import Final

from fastapi import APIRouter, Depends, HTTPException, status

from litellm.proxy._types import CommonProxyErrors, LitellmUserRoles, UserAPIKeyAuth
from litellm.proxy.auth.user_api_key_auth import user_api_key_auth
from litellm.types.proxy.provider_billing import BillingCredential, ProviderSyncRun
from token_iq.api.types.tool_connections import (
    ToolConnection,
    ToolConnectionAccount,
    ToolConnectionsResponse,
    ToolFetchDetail,
)
from token_iq.connectors.billing.connection_state import (
    account_state,
    provider_state,
    verified_against_real_account,
)
from token_iq.connectors.tools.credential_purpose import TOOL_NAMES
from token_iq.connectors.tools.fetch_profile import TOOL_FETCH_PROFILES
from token_iq.repositories.provider_sync_run_repository import ProviderSyncRunRepository
from token_iq.repositories.tool_usage_fact_repository import ToolUsageFactRepository

router: Final = APIRouter(
    tags=["user tools"],  # mutable-ok: fixed single-element tag list, never grown after this line
    dependencies=(Depends(user_api_key_auth),),
)

_RUNS_FOR_STATE: Final = 200


def _proxy_error(status_code: int, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"error": message},  # mutable-ok: fixed one-key error envelope, matches every other proxy endpoint
    )


def _newest_per_account(runs: Sequence[ProviderSyncRun], tool: str) -> Mapping[str, ProviderSyncRun]:
    """Runs arrive newest first, so iterating in reverse leaves the newest one per account."""
    return MappingProxyType({run.credential_name: run for run in reversed(runs) if run.provider == tool})


def _fetch_detail(tool: str) -> ToolFetchDetail:
    profile: Final = TOOL_FETCH_PROFILES[tool]
    return ToolFetchDetail(
        endpoint=profile.endpoint,
        endpoint_url=profile.endpoint_url,
        what_it_gives=profile.what_it_gives,
        what_it_cannot_give=profile.what_it_cannot_give,
        backfill_note=profile.backfill_note,
        verification_note=profile.verification_note,
    )


def _account(
    credential: BillingCredential, run: ProviderSyncRun | None, counts: Mapping[str, int]
) -> ToolConnectionAccount:
    state, detail = account_state(last_run=run, facts_stored=counts.get(credential.name, 0))
    return ToolConnectionAccount(
        credential_name=credential.name,
        state=state,
        detail=detail,
        last_sync_at=None if run is None else run.finished_at.isoformat(),
        last_outcome=None if run is None else run.outcome,
        rows_stored=counts.get(credential.name, 0),
    )


def build_tool_connection(
    *,
    tool: str,
    credentials: Sequence[BillingCredential],
    newest: Mapping[str, ProviderSyncRun],
    counts: Mapping[str, int],
) -> ToolConnection:
    """One tool's row, and one row per stored account inside it."""
    accounts: Final = tuple(_account(credential, newest.get(credential.name), counts) for credential in credentials)

    return ToolConnection(
        tool=tool,
        display_name=TOOL_FETCH_PROFILES[tool].display_name,
        state=provider_state(tuple(account.state for account in accounts)),
        accounts=accounts,
        fetches=_fetch_detail(tool),
        verified_against_real_account=verified_against_real_account(
            tuple(counts.get(credential.name, 0) for credential in credentials)
        ),
    )


async def build_tool_connections(
    *,
    tools: Sequence[str],
    credentials_for: Callable[[str], Awaitable[tuple[BillingCredential, ...]]],
    recent_runs: Sequence[ProviderSyncRun],
    counts_for: Callable[[str], Awaitable[Mapping[str, int]]],
) -> ToolConnectionsResponse:
    return ToolConnectionsResponse(
        tools=tuple(
            [
                build_tool_connection(
                    tool=tool,
                    credentials=await credentials_for(tool),
                    newest=_newest_per_account(recent_runs, tool),
                    counts=await counts_for(tool),
                )
                for tool in tools
            ]
        )
    )


def _admin_or_403(user_api_key_dict: UserAPIKeyAuth) -> None:
    if user_api_key_dict.user_role != LitellmUserRoles.PROXY_ADMIN:
        raise _proxy_error(status.HTTP_403_FORBIDDEN, "Only a proxy admin may read user tool connections.")


@router.get("/tool/connections", response_model=ToolConnectionsResponse)
async def tool_connections(
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
) -> ToolConnectionsResponse:
    """One row per user tool, with one row per stored account inside it."""
    from litellm.proxy.proxy_server import prisma_client
    from token_iq.connectors.tools.scheduled import build_tool_credentials_lookup

    _admin_or_403(user_api_key_dict)
    if prisma_client is None:
        raise _proxy_error(status.HTTP_500_INTERNAL_SERVER_ERROR, CommonProxyErrors.db_not_connected_error.value)

    facts: Final = ToolUsageFactRepository(prisma_client)
    runs: Final = await ProviderSyncRunRepository(prisma_client).recent(limit=_RUNS_FOR_STATE)

    return await build_tool_connections(
        tools=sorted(TOOL_NAMES),
        credentials_for=build_tool_credentials_lookup(prisma_client=prisma_client),
        recent_runs=runs,
        counts_for=facts.counts_by_credential,
    )
