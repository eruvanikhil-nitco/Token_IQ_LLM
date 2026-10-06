from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

NOW = datetime(2026, 9, 13, 12, 0, tzinfo=timezone.utc)


def _lock(acquired: bool = True, with_redis: bool = True) -> MagicMock:
    lock = MagicMock()
    lock.redis_cache = MagicMock() if with_redis else None
    lock.acquire_lock = AsyncMock(return_value=acquired)
    lock.release_lock = AsyncMock()
    return lock


@pytest.mark.asyncio
async def test_only_one_replica_polls_the_provider():
    """Every replica running this would multiply the customer's provider rate-limit
    consumption by the replica count, and OpenRouter's per-request endpoint is the
    tightest limit we touch."""
    from token_iq.connectors.billing.scheduled import ingest_provider_billing

    ran = AsyncMock()
    await ingest_provider_billing(pod_lock_manager=_lock(acquired=False), run=ran, now=NOW)

    ran.assert_not_awaited()


@pytest.mark.asyncio
async def test_the_holder_of_the_lock_does_the_work():
    from token_iq.connectors.billing.scheduled import ingest_provider_billing

    ran = AsyncMock()
    await ingest_provider_billing(pod_lock_manager=_lock(acquired=True), run=ran, now=NOW)

    ran.assert_awaited_once()


@pytest.mark.asyncio
async def test_the_lock_is_released_even_when_the_run_fails():
    """A lock held by a crashed run would stop ingestion until the next restart, and the
    customer would see stale provider figures with no error to explain it."""
    from token_iq.connectors.billing.scheduled import ingest_provider_billing

    lock = _lock(acquired=True)

    async def boom(**_: object):
        raise RuntimeError("boom")

    await ingest_provider_billing(pod_lock_manager=lock, run=boom, now=NOW)

    lock.release_lock.assert_awaited()


@pytest.mark.asyncio
async def test_a_failing_run_does_not_take_the_scheduler_down():
    """APScheduler drops a job that raises. One bad tick must not end ingestion for the
    life of the process."""
    from token_iq.connectors.billing.scheduled import ingest_provider_billing

    async def boom(**_: object):
        raise RuntimeError("boom")

    await ingest_provider_billing(pod_lock_manager=_lock(acquired=True), run=boom, now=NOW)


@pytest.mark.asyncio
async def test_without_redis_a_single_process_still_ingests():
    """A self-hosted single-replica customer has no redis. Requiring a lock would mean
    they never ingest anything at all."""
    from token_iq.connectors.billing.scheduled import ingest_provider_billing

    ran = AsyncMock()
    await ingest_provider_billing(pod_lock_manager=_lock(with_redis=False), run=ran, now=NOW)

    ran.assert_awaited_once()


@pytest.mark.asyncio
async def test_the_lookup_returns_only_the_credential_marked_for_that_providers_bill():
    """A model access key for the same provider must never be sent to a cost endpoint."""
    from types import SimpleNamespace
    from unittest.mock import patch

    from token_iq import gateway as litellm
    from token_iq.connectors.billing.credential_purpose import BILLING_PURPOSE
    from token_iq.connectors.billing.scheduled import build_billing_credentials_lookup
    from token_iq.types.provider_billing import BillingCredential
    from token_iq.gateway.types.utils import CredentialItem

    stored = (
        ("openai-models", {"custom_llm_provider": "openai", "provider": "openai"}, "sk-proj-test-not-real"),
        ("anthropic-billing", {"purpose": BILLING_PURPOSE, "provider": "anthropic"}, "sk-ant-admin01-test-not-real"),
        ("openai-billing", {"purpose": BILLING_PURPOSE, "provider": "openai"}, "sk-admin-test-not-real"),
    )
    prisma_client = MagicMock()
    prisma_client.db.litellm_credentialstable.find_many = AsyncMock(
        return_value=[SimpleNamespace(credential_name=name, credential_info=info) for name, info, _ in stored]
    )
    credentials = [
        CredentialItem(credential_name=name, credential_info=info, credential_values={"api_key": key})
        for name, info, key in stored
    ]

    with patch.object(litellm, "credential_list", credentials):
        credentials_for = build_billing_credentials_lookup(prisma_client=prisma_client)
        openai = await credentials_for("openai")
        openrouter = await credentials_for("openrouter")

    assert openai == (BillingCredential(name="openai-billing", values={"api_key": "sk-admin-test-not-real"}),)
    assert openrouter == ()


@pytest.mark.asyncio
async def test_the_lookup_returns_every_matching_credential_not_just_the_first():
    """A company with two OpenAI organisations stores two billing credentials. Returning
    only the first would silently drop one organisation's spend from every ingestion run."""
    from types import SimpleNamespace
    from unittest.mock import patch

    from token_iq import gateway as litellm
    from token_iq.connectors.billing.credential_purpose import BILLING_PURPOSE
    from token_iq.connectors.billing.scheduled import build_billing_credentials_lookup
    from token_iq.types.provider_billing import BillingCredential
    from token_iq.gateway.types.utils import CredentialItem

    stored = (
        ("openai-prod", {"purpose": BILLING_PURPOSE, "provider": "openai"}, "sk-admin-prod-not-real"),
        ("openai-staging", {"purpose": BILLING_PURPOSE, "provider": "openai"}, "sk-admin-staging-not-real"),
    )
    prisma_client = MagicMock()
    prisma_client.db.litellm_credentialstable.find_many = AsyncMock(
        return_value=[SimpleNamespace(credential_name=name, credential_info=info) for name, info, _ in stored]
    )
    credentials = [
        CredentialItem(credential_name=name, credential_info=info, credential_values={"api_key": key})
        for name, info, key in stored
    ]

    with patch.object(litellm, "credential_list", credentials):
        openai = await build_billing_credentials_lookup(prisma_client=prisma_client)("openai")

    assert openai == (
        BillingCredential(name="openai-prod", values={"api_key": "sk-admin-prod-not-real"}),
        BillingCredential(name="openai-staging", values={"api_key": "sk-admin-staging-not-real"}),
    )


@pytest.mark.asyncio
async def test_no_lock_manager_at_all_still_ingests():
    """proxy_logging_obj may not carry one. Silently never running would be worse than
    running unlocked on a single replica."""
    from token_iq.connectors.billing.scheduled import ingest_provider_billing

    ran = AsyncMock()
    await ingest_provider_billing(pod_lock_manager=None, run=ran, now=NOW)

    ran.assert_awaited_once()
