"""Drive every registered connector once and record what came back.

A connector is contracted to return failure rather than raise, but a bug or a socket
timeout will raise anyway, so the loop contains that too. The alternative is one provider
ending the run for all of them.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Final

from token_iq.connectors.billing.connector import BillingConnector
from token_iq.gateway._logging import verbose_proxy_logger
from token_iq.repositories.provider_sync_run_repository import ProviderSyncRunRepository
from token_iq.repositories.provider_usage_fact_repository import ProviderUsageFactRepository
from token_iq.types.provider_billing import (
    BillingCredential,
    Fetched,
    FetchFailed,
    NotConfigured,
    ProviderSyncRun,
)

LOOKBACK: Final = timedelta(days=1)
"""Each run re-reads the last day. A watermark with no overlap loses anything a provider
recorded after we last asked, and the fact key makes the overlap free."""


@dataclass(frozen=True, slots=True)
class IngestionReport:
    written: int
    skipped: tuple[str, ...]
    failed: tuple[str, ...]


async def run_ingestion(
    *,
    repository: ProviderUsageFactRepository,
    sync_runs: ProviderSyncRunRepository,
    connectors: Sequence[BillingConnector],
    credentials_for: Callable[[str], Awaitable[tuple[BillingCredential, ...]]],
    now: datetime,
) -> IngestionReport:
    """Fetch from every connector that has a credential, and write what they return.

    Several accounts on the same provider are fetched one at a time so one broken account
    cannot stop the others: `skipped` and `failed` may repeat a provider when several of its
    accounts hit either outcome, which is what the caller wants to see.
    """
    written = 0  # rebind-ok: accumulated across awaits in a loop
    skipped: list[str] = []  # mutable-ok: accumulated across awaits in a loop
    failed: list[str] = []  # mutable-ok: accumulated across awaits in a loop
    window_start: Final = now - LOOKBACK

    for connector in connectors:
        credentials = await credentials_for(connector.provider)
        if not credentials:
            skipped.append(connector.provider)
            continue

        for credential in credentials:
            started: Final = datetime.now(timezone.utc)
            try:
                result = await connector.fetch(
                    since=window_start,
                    until=now,
                    credential_name=credential.name,
                    credential_values=credential.values,
                )
            except Exception as exc:  # noqa: BLE001  # a connector bug must not end the run for other accounts
                failed_at: Final = datetime.now(timezone.utc)
                verbose_proxy_logger.exception("billing connector %s raised: %s", connector.provider, exc)
                failed.append(connector.provider)
                await _record(
                    sync_runs,
                    ProviderSyncRun(
                        provider=connector.provider,
                        credential_name=credential.name,
                        started_at=started,
                        finished_at=failed_at,
                        outcome="failed",
                        facts_written=0,
                        window_start=window_start,
                        window_end=now,
                        detail=f"{type(exc).__name__}: {exc}",
                    ),
                )
                continue

            finished: Final = datetime.now(timezone.utc)
            match result:
                case Fetched(facts=facts):
                    count: Final = await repository.upsert_many(facts)
                    written += count
                    await _record(
                        sync_runs,
                        ProviderSyncRun(
                            provider=connector.provider,
                            credential_name=credential.name,
                            started_at=started,
                            finished_at=finished,
                            outcome="fetched",
                            facts_written=count,
                            window_start=window_start,
                            window_end=now,
                        ),
                    )
                case NotConfigured(reason=reason):
                    verbose_proxy_logger.debug(
                        "billing connector %s skipped %s: %s", connector.provider, credential.name, reason
                    )
                    skipped.append(connector.provider)
                    await _record(
                        sync_runs,
                        ProviderSyncRun(
                            provider=connector.provider,
                            credential_name=credential.name,
                            started_at=started,
                            finished_at=finished,
                            outcome="not_configured",
                            facts_written=0,
                            window_start=window_start,
                            window_end=now,
                            detail=reason,
                        ),
                    )
                case FetchFailed(reason=reason, retryable=retryable):
                    verbose_proxy_logger.warning(
                        "billing connector %s failed for %s (retryable=%s): %s",
                        connector.provider,
                        credential.name,
                        retryable,
                        reason,
                    )
                    failed.append(connector.provider)
                    await _record(
                        sync_runs,
                        ProviderSyncRun(
                            provider=connector.provider,
                            credential_name=credential.name,
                            started_at=started,
                            finished_at=finished,
                            outcome="failed",
                            facts_written=0,
                            window_start=window_start,
                            window_end=now,
                            detail=reason,
                        ),
                    )

    return IngestionReport(written=written, skipped=tuple(skipped), failed=tuple(failed))


async def _record(sync_runs: ProviderSyncRunRepository, run: ProviderSyncRun) -> None:
    """The history is a convenience; the facts are the product. A bookkeeping insert that
    fails must not take a day of real cost data with it."""
    try:
        await sync_runs.record(run)
    except Exception as exc:  # noqa: BLE001  # see docstring: never lose facts over a history row
        verbose_proxy_logger.warning("could not record the %s sync run: %s", run.provider, exc)
