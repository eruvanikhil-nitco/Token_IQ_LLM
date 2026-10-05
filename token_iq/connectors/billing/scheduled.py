"""One replica polls; the rest stand down.

Polling from every replica multiplies the customer's provider rate-limit consumption by
the replica count, and OpenRouter's per-request endpoint is the tightest limit this
product touches. A deployment with no redis has nothing to coordinate through and is
assumed to be a single process, which is the common self-hosted case: refusing to run at
all there would mean those customers never ingest anything.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from datetime import datetime, timezone
from typing import Any, Final

from litellm._logging import verbose_proxy_logger
from litellm.types.proxy.provider_billing import BillingCredential
from token_iq.connectors.billing.credential_purpose import is_billing_credential

LOCK_ID: Final = "provider_billing_ingestion"

INTERVAL_SECONDS: Final = 300
"""Anthropic supports polling once a minute and OpenRouter rate limits per key. Five
minutes keeps a dashboard usefully fresh without spending a customer's limit on us."""


async def ingest_provider_billing(
    *,
    pod_lock_manager: Any,  # any-ok: PodLockManager is an untyped runtime collaborator
    run: Callable[..., Awaitable[object]],
    now: datetime,
) -> None:
    """Run one ingestion pass if this replica holds the lock."""
    redis_cache: Final = getattr(pod_lock_manager, "redis_cache", None)
    if redis_cache is None:
        await _guarded(run, now)
        return

    if not await pod_lock_manager.acquire_lock(cronjob_id=LOCK_ID):
        return
    try:
        await _guarded(run, now)
    finally:
        await pod_lock_manager.release_lock(cronjob_id=LOCK_ID)


async def _guarded(run: Callable[..., Awaitable[object]], now: datetime) -> None:
    """APScheduler drops a job that raises, so one bad tick would end ingestion for the
    life of the process."""
    try:
        await run(now=now)
    except Exception as exc:  # noqa: BLE001  # see docstring: a raised job is never scheduled again
        verbose_proxy_logger.exception("provider billing ingestion failed: %s", exc)


def build_billing_credentials_lookup(
    *, prisma_client: Any  # any-ok: PrismaClient is an untyped runtime wrapper
) -> Callable[[str], Awaitable[tuple[BillingCredential, ...]]]:
    """Every stored credential marked for reading a provider's bill.

    Rows come through CredentialsRepository, which that module documents as the only place
    that talks to its table. Values come through CredentialAccessor rather than off the row,
    so the decryption this needs is the same code path the request router uses.
    """

    async def credentials_for(provider: str) -> tuple[BillingCredential, ...]:
        from litellm.litellm_core_utils.credential_accessor import CredentialAccessor
        from litellm.repositories.credentials_repository import CredentialsRepository

        rows: Final = await CredentialsRepository(prisma_client).find_all()
        return tuple(
            BillingCredential(name=name, values={key: str(value) for key, value in values.items()})
            for row in rows
            if isinstance(info := getattr(row, "credential_info", None), Mapping)
            and is_billing_credential(info)
            and info.get("provider") == provider
            and (name := str(getattr(row, "credential_name", "")))
            and (values := CredentialAccessor.get_credential_values(name))
        )

    return credentials_for


def build_provider_billing_job(
    *, prisma_client: Any, proxy_logging_obj: Any  # any-ok: both are untyped runtime collaborators
) -> Callable[[], Awaitable[None]]:
    """Compose the repository, the registered connectors and the credential lookup."""
    from token_iq.connectors.billing.connector import registered_connectors
    from token_iq.connectors.billing.runner import run_ingestion
    from token_iq.repositories.provider_sync_run_repository import ProviderSyncRunRepository
    from token_iq.repositories.provider_usage_fact_repository import ProviderUsageFactRepository

    repository: Final = ProviderUsageFactRepository(prisma_client)
    sync_runs: Final = ProviderSyncRunRepository(prisma_client)

    credentials_for: Final = build_billing_credentials_lookup(prisma_client=prisma_client)

    async def job() -> None:
        await ingest_provider_billing(
            pod_lock_manager=getattr(
                getattr(proxy_logging_obj, "db_spend_update_writer", None), "pod_lock_manager", None
            ),
            run=lambda now: run_ingestion(
                repository=repository,
                sync_runs=sync_runs,
                connectors=registered_connectors(),
                credentials_for=credentials_for,
                now=now,
            ),
            now=datetime.now(timezone.utc),
        )

    return job
