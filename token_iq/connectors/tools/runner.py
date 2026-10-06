"""Drive every registered tool connector once and record what came back.

Deliberately the same shape as `token_iq/connectors/billing/runner.py`, including recording into
the same sync-run history, so the Sync History screen works for tools with no new machinery.

A connector is contracted to return failure rather than raise, but a bug or a socket timeout
will raise anyway, so the loop contains that too. The alternative is one tool ending the run
for all of them.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Final

from token_iq.gateway._logging import verbose_proxy_logger
from token_iq.connectors.tools.connector import ToolConnector
from token_iq.repositories.provider_sync_run_repository import ProviderSyncRunRepository
from token_iq.repositories.tool_usage_fact_repository import ToolUsageFactRepository
from token_iq.types.provider_billing import BillingCredential, ProviderSyncRun
from token_iq.types.tool_usage import ToolFetched, ToolFetchFailed, ToolNotConfigured

LOOKBACK: Final = timedelta(days=2)
"""Each run re-reads the last two days. Tools revise a day after it ends, more than providers
do, and the fact key makes the overlap free."""


@dataclass(frozen=True, slots=True)
class ToolIngestionReport:
    written: int
    skipped: tuple[str, ...]
    failed: tuple[str, ...]


async def _record(sync_runs: ProviderSyncRunRepository, run: ProviderSyncRun) -> None:
    try:
        await sync_runs.record(run)
    except Exception as exc:  # noqa: BLE001  # history is useful, not load-bearing; losing a row must not end a run
        verbose_proxy_logger.warning("could not record a tool sync run for %s: %s", run.provider, exc)


async def run_tool_ingestion(
    *,
    repository: ToolUsageFactRepository,
    sync_runs: ProviderSyncRunRepository,
    connectors: Sequence[ToolConnector],
    credentials_for: Callable[[str], Awaitable[tuple[BillingCredential, ...]]],
    now: datetime,
) -> ToolIngestionReport:
    """Fetch from every tool that has a credential, and write what they return."""
    written = 0  # rebind-ok: accumulated across awaits in a loop
    skipped: Final[list[str]] = []  # mutable-ok: accumulated across awaits in a loop
    failed: Final[list[str]] = []  # mutable-ok: accumulated across awaits in a loop
    window_start: Final = now - LOOKBACK

    for connector in connectors:
        credentials = await credentials_for(connector.tool)
        if not credentials:
            skipped.append(connector.tool)
            continue

        for credential in credentials:
            started = datetime.now(timezone.utc)
            try:
                result = await connector.fetch(
                    since=window_start,
                    until=now,
                    credential_name=credential.name,
                    credential_values=credential.values,
                )
            except Exception as exc:  # noqa: BLE001  # a connector bug must not end the run for other tools
                verbose_proxy_logger.exception("tool connector %s raised: %s", connector.tool, exc)
                failed.append(connector.tool)
                await _record(
                    sync_runs,
                    ProviderSyncRun(
                        provider=connector.tool,
                        credential_name=credential.name,
                        started_at=started,
                        finished_at=datetime.now(timezone.utc),
                        outcome="failed",
                        facts_written=0,
                        window_start=window_start,
                        window_end=now,
                        detail=f"{type(exc).__name__}: {exc}",
                    ),
                )
                continue

            match result:
                case ToolFetched(facts=facts):
                    count = await repository.upsert_many(facts, credential_name=credential.name)
                    written += count
                    await _record(
                        sync_runs,
                        ProviderSyncRun(
                            provider=connector.tool,
                            credential_name=credential.name,
                            started_at=started,
                            finished_at=datetime.now(timezone.utc),
                            outcome="fetched",
                            facts_written=count,
                            window_start=window_start,
                            window_end=now,
                        ),
                    )
                case ToolNotConfigured(reason=reason):
                    skipped.append(connector.tool)
                    await _record(
                        sync_runs,
                        ProviderSyncRun(
                            provider=connector.tool,
                            credential_name=credential.name,
                            started_at=started,
                            finished_at=datetime.now(timezone.utc),
                            outcome="not_configured",
                            facts_written=0,
                            window_start=window_start,
                            window_end=now,
                            detail=reason,
                        ),
                    )
                case ToolFetchFailed(reason=reason, retryable=retryable):
                    failed.append(connector.tool)
                    await _record(
                        sync_runs,
                        ProviderSyncRun(
                            provider=connector.tool,
                            credential_name=credential.name,
                            started_at=started,
                            finished_at=datetime.now(timezone.utc),
                            outcome="failed",
                            facts_written=0,
                            window_start=window_start,
                            window_end=now,
                            detail=f"{reason} (retryable={retryable})",
                        ),
                    )

    return ToolIngestionReport(written=written, skipped=tuple(skipped), failed=tuple(failed))
