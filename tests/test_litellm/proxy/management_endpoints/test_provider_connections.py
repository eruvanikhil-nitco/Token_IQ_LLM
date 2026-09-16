from __future__ import annotations

from datetime import datetime, timezone

import pytest

from litellm.types.proxy.provider_billing import BillingCredential, ProviderSyncRun

NOW = datetime(2026, 9, 16, 9, 0, tzinfo=timezone.utc)


def _run(provider: str, credential_name: str, outcome: str, detail: str | None = None) -> ProviderSyncRun:
    return ProviderSyncRun(
        provider=provider,
        credential_name=credential_name,
        started_at=NOW,
        finished_at=NOW,
        outcome=outcome,
        facts_written=1,
        window_start=NOW,
        window_end=NOW,
        detail=detail,
    )


@pytest.mark.asyncio
async def test_a_provider_with_no_credential_is_reported_not_connected():
    from litellm.proxy.management_endpoints.provider_connections import build_provider_connections

    async def no_credentials(_provider: str) -> tuple[BillingCredential, ...]:
        return ()

    result = await build_provider_connections(
        providers=("openai",),
        credentials_for=no_credentials,
        recent_runs=(),
        fact_counts_for=lambda _provider: {},
    )

    assert result.providers[0].state == "not_connected"
    assert result.providers[0].accounts == ()


@pytest.mark.asyncio
async def test_each_account_gets_its_own_row_and_the_worst_one_sets_the_provider_state():
    from litellm.proxy.management_endpoints.provider_connections import build_provider_connections

    async def two(_provider: str) -> tuple[BillingCredential, ...]:
        return (
            BillingCredential(name="prod", values={"api_key": "k1"}),
            BillingCredential(name="staging", values={"api_key": "k2"}),
        )

    result = await build_provider_connections(
        providers=("openai",),
        credentials_for=two,
        recent_runs=(
            _run("openai", "prod", "fetched"),
            _run("openai", "staging", "failed", "openai refused credential staging"),
        ),
        fact_counts_for=lambda _provider: {"prod": 40},
    )

    connection = result.providers[0]
    assert connection.state == "needs_attention"
    assert {account.credential_name: account.state for account in connection.accounts} == {
        "prod": "healthy",
        "staging": "needs_attention",
    }
    assert connection.accounts[1].detail == "openai refused credential staging"


@pytest.mark.asyncio
async def test_only_the_newest_run_for_an_account_decides_its_state():
    """Runs arrive newest first. Letting an older failure win would leave a connection the
    customer already fixed showing as broken until the history rolled over."""
    from litellm.proxy.management_endpoints.provider_connections import build_provider_connections

    async def one(_provider: str) -> tuple[BillingCredential, ...]:
        return (BillingCredential(name="prod", values={"api_key": "k"}),)

    result = await build_provider_connections(
        providers=("openai",),
        credentials_for=one,
        recent_runs=(_run("openai", "prod", "fetched"), _run("openai", "prod", "failed", "was broken")),
        fact_counts_for=lambda _provider: {"prod": 5},
    )

    assert result.providers[0].accounts[0].state == "healthy"


@pytest.mark.asyncio
async def test_every_connection_says_what_it_fetches():
    from litellm.proxy.management_endpoints.provider_connections import build_provider_connections

    async def none(_provider: str) -> tuple[BillingCredential, ...]:
        return ()

    result = await build_provider_connections(
        providers=("openrouter",),
        credentials_for=none,
        recent_runs=(),
        fact_counts_for=lambda _provider: {},
    )

    fetches = result.providers[0].fetches
    assert fetches.grain == "request"
    assert fetches.refresh_seconds == 300
    assert "30 days" in fetches.delay_note
