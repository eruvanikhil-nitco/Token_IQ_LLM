"""Drive every registered connector once and record what came back.

A connector is contracted to return failure rather than raise, but a bug or a socket
timeout will raise anyway, so the loop contains that too. The alternative is one provider
ending the run for all of them.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final

from litellm._logging import verbose_proxy_logger
from litellm.provider_billing.connector import BillingConnector
from litellm.repositories.provider_usage_fact_repository import ProviderUsageFactRepository
from litellm.types.proxy.provider_billing import Fetched, FetchFailed, NotConfigured

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
    connectors: Sequence[BillingConnector],
    credentials_for: Callable[[str], Awaitable[tuple[str, Mapping[str, str]] | None]],
    now: datetime,
) -> IngestionReport:
    """Fetch from every connector that has a credential, and write what they return."""
    written = 0  # rebind-ok: accumulated across awaits in a loop
    skipped: list[str] = []  # mutable-ok: accumulated across awaits in a loop
    failed: list[str] = []  # mutable-ok: accumulated across awaits in a loop

    for connector in connectors:
        credential = await credentials_for(connector.provider)
        if credential is None:
            skipped.append(connector.provider)
            continue
        credential_name, credential_values = credential

        try:
            result = await connector.fetch(
                since=now - LOOKBACK,
                until=now,
                credential_name=credential_name,
                credential_values=credential_values,
            )
        except Exception as exc:  # noqa: BLE001  # a connector bug must not end the run for other providers
            verbose_proxy_logger.exception("billing connector %s raised: %s", connector.provider, exc)
            failed.append(connector.provider)
            continue

        match result:
            case Fetched(facts=facts):
                written += await repository.upsert_many(facts)
            case NotConfigured(reason=reason):
                verbose_proxy_logger.debug("billing connector %s skipped: %s", connector.provider, reason)
                skipped.append(connector.provider)
            case FetchFailed(reason=reason, retryable=retryable):
                verbose_proxy_logger.warning(
                    "billing connector %s failed (retryable=%s): %s", connector.provider, retryable, reason
                )
                failed.append(connector.provider)

    return IngestionReport(written=written, skipped=tuple(skipped), failed=tuple(failed))
