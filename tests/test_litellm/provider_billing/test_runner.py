from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from litellm.types.proxy.provider_billing import (
    BillingCredential,
    Fetched,
    FetchFailed,
    NotConfigured,
    ProviderUsageFact,
)

NOW = datetime(2026, 9, 13, 12, 0, tzinfo=timezone.utc)


def _fact() -> ProviderUsageFact:
    return ProviderUsageFact(
        fact_key="p:1",
        provider="p",
        credential_name="c",
        grain="request",
        bucket_start=NOW,
        evidence="reconciled",
        billed_cost=Decimal("1"),
    )


class _Connector:
    def __init__(self, provider: str, result: object) -> None:
        self._provider = provider
        self._result = result

    @property
    def provider(self) -> str:
        return self._provider

    async def fetch(self, **_: object):
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


async def _creds(_provider: str) -> tuple[BillingCredential, ...]:
    return (BillingCredential(name="c", values={"api_key": "k"}),)


def _repo() -> MagicMock:
    repo = MagicMock()
    repo.upsert_many = AsyncMock(side_effect=lambda facts: len(facts))
    return repo


async def _run(connectors, credentials_for=_creds, repo=None):
    from litellm.provider_billing.runner import run_ingestion

    return await run_ingestion(
        repository=repo or _repo(),
        connectors=connectors,
        credentials_for=credentials_for,
        now=NOW,
    )


@pytest.mark.asyncio
async def test_facts_from_every_connector_are_written():
    report = await _run(
        (
            _Connector("a", Fetched(facts=(_fact(),), watermark=NOW)),
            _Connector("b", Fetched(facts=(_fact(),), watermark=NOW)),
        )
    )

    assert report.written == 2


@pytest.mark.asyncio
async def test_one_provider_failing_does_not_stop_the_others():
    """The whole point of a shared runner. A customer with five providers should not lose
    four of them because one returned a 500."""
    report = await _run(
        (
            _Connector("broken", FetchFailed(reason="500", retryable=True)),
            _Connector("fine", Fetched(facts=(_fact(),), watermark=NOW)),
        )
    )

    assert report.written == 1
    assert report.failed == ("broken",)


@pytest.mark.asyncio
async def test_a_connector_that_raises_anyway_is_contained():
    """Connectors are contracted not to raise, but a bug or an httpx timeout will. One
    unhandled exception must not end the run for every other provider."""
    report = await _run(
        (
            _Connector("rude", RuntimeError("boom")),
            _Connector("fine", Fetched(facts=(_fact(),), watermark=NOW)),
        )
    )

    assert report.written == 1
    assert report.failed == ("rude",)


@pytest.mark.asyncio
async def test_a_provider_with_no_credential_is_skipped_quietly():
    """Most customers configure one or two providers. Treating the rest as failures would
    make a healthy run look broken on every tick."""

    async def no_creds(_provider: str) -> tuple[BillingCredential, ...]:
        return ()

    repo = _repo()
    report = await _run((_Connector("a", Fetched(facts=(_fact(),), watermark=NOW)),), no_creds, repo)

    assert report.skipped == ("a",)
    assert report.failed == ()
    repo.upsert_many.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_not_configured_result_is_a_skip_not_a_failure():
    report = await _run((_Connector("a", NotConfigured(reason="no api_key")),))

    assert report.skipped == ("a",)
    assert report.failed == ()


@pytest.mark.asyncio
async def test_the_window_asked_for_overlaps_the_last_one():
    """A watermark with no overlap loses whatever the provider recorded after we last
    asked. The fact key makes re-reading free, so the window deliberately looks back."""
    from litellm.provider_billing.runner import LOOKBACK

    seen: dict[str, datetime] = {}

    class _Recording(_Connector):
        async def fetch(self, *, since: datetime, until: datetime, **_: object):
            seen["since"] = since
            seen["until"] = until
            return Fetched(facts=(), watermark=until)

    await _run((_Recording("a", None),))

    assert seen["until"] == NOW
    assert seen["since"] == NOW - LOOKBACK


@pytest.mark.asyncio
async def test_every_account_for_a_provider_is_fetched_separately():
    """A company with two OpenAI organisations has two billing credentials. Reading only the
    first silently halves their reported bill, and nothing in the product would say so."""
    seen: list[str] = []

    class _Recording(_Connector):
        async def fetch(self, *, credential_name: str, **_: object):
            seen.append(credential_name)
            return Fetched(facts=(_fact(),), watermark=NOW)

    async def two(_provider: str) -> tuple[BillingCredential, ...]:
        return (
            BillingCredential(name="prod", values={"api_key": "k1"}),
            BillingCredential(name="staging", values={"api_key": "k2"}),
        )

    report = await _run((_Recording("openai", None),), two)

    assert seen == ["prod", "staging"]
    assert report.written == 2


@pytest.mark.asyncio
async def test_one_account_failing_does_not_stop_the_others_on_the_same_provider():
    async def two(_provider: str) -> tuple[BillingCredential, ...]:
        return (
            BillingCredential(name="broken", values={"api_key": "k1"}),
            BillingCredential(name="fine", values={"api_key": "k2"}),
        )

    class _PerCredential(_Connector):
        async def fetch(self, *, credential_name: str, **_: object):
            if credential_name == "broken":
                return FetchFailed(reason="401", retryable=False)
            return Fetched(facts=(_fact(),), watermark=NOW)

    report = await _run((_PerCredential("openai", None),), two)

    assert report.written == 1
    assert report.failed == ("openai",)
