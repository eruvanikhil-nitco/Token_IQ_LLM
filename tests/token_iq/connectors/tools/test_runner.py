from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Final

import pytest

from token_iq.connectors.tools.runner import run_tool_ingestion
from token_iq.types.provider_billing import BillingCredential, ProviderSyncRun
from token_iq.types.tool_usage import (
    ToolFetched,
    ToolFetchFailed,
    ToolFetchResult,
    ToolName,
    ToolNotConfigured,
    ToolUsageFact,
)

NOW: Final = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)


def _fact(person: str = "dev@example.test") -> ToolUsageFact:
    return ToolUsageFact(
        tool="claude_code",
        person=person,
        day=datetime(2026, 9, 28, tzinfo=timezone.utc),
        cost=Decimal("1.86"),
        currency="USD",
        basis="new_money",
    )


@dataclass
class FakeConnector:
    tool_name: ToolName
    result: ToolFetchResult | None = None
    raises: Exception | None = None
    calls: list[str] = field(default_factory=list)  # mutable-ok: a spy the test reads

    @property
    def tool(self) -> ToolName:
        return self.tool_name

    async def fetch(self, *, since, until, credential_name, credential_values) -> ToolFetchResult:
        self.calls.append(credential_name)
        if self.raises is not None:
            raise self.raises
        assert self.result is not None
        return self.result


@dataclass
class FakeRepository:
    written: list[tuple[str, int]] = field(default_factory=list)  # mutable-ok: a spy the test reads

    async def upsert_many(self, facts, *, credential_name: str) -> int:
        self.written.append((credential_name, len(facts)))
        return len(facts)


@dataclass
class FakeSyncRuns:
    runs: list[ProviderSyncRun] = field(default_factory=list)  # mutable-ok: a spy the test reads
    raises: Exception | None = None

    async def record(self, run: ProviderSyncRun) -> None:
        if self.raises is not None:
            raise self.raises
        self.runs.append(run)


def _credentials(*names: str):
    async def lookup(_tool: str) -> tuple[BillingCredential, ...]:
        return tuple(BillingCredential(name=name, values={"api_key": "k"}) for name in names)

    return lookup


async def _run(connectors: Sequence[FakeConnector], *, credentials=None, sync_runs=None, repository=None):
    return await run_tool_ingestion(
        repository=repository or FakeRepository(),  # pyright: ignore[reportArgumentType]  # injected fake
        sync_runs=sync_runs or FakeSyncRuns(),  # pyright: ignore[reportArgumentType]  # injected fake
        connectors=connectors,  # pyright: ignore[reportArgumentType]  # injected fakes
        credentials_for=credentials or _credentials("acme"),
        now=NOW,
    )


@pytest.mark.asyncio
async def test_a_tool_that_raises_does_not_stop_the_others() -> None:
    """The whole reason the runner contains exceptions. One tool with a bug or a socket
    timeout must not cost a customer every other tool's data for that tick."""
    broken: Final = FakeConnector("claude_code", raises=RuntimeError("boom"))
    working: Final = FakeConnector("cursor", result=ToolFetched(facts=(_fact(),), watermark=NOW))

    report: Final = await _run([broken, working])

    assert report.failed == ("claude_code",)
    assert report.written == 1
    assert working.calls == ["acme"]


@pytest.mark.asyncio
async def test_a_tool_with_no_credential_is_skipped_without_being_called() -> None:
    async def none_configured(_tool: str) -> tuple[BillingCredential, ...]:
        return ()

    connector: Final = FakeConnector("cursor", result=ToolFetched(facts=(), watermark=NOW))

    report: Final = await _run([connector], credentials=none_configured)

    assert report.skipped == ("cursor",)
    assert connector.calls == []


@pytest.mark.asyncio
async def test_every_account_of_one_tool_is_fetched_separately() -> None:
    """One broken account must not stop the customer's other accounts on the same tool."""
    connector: Final = FakeConnector("cursor", result=ToolFetched(facts=(_fact(),), watermark=NOW))

    report: Final = await _run([connector], credentials=_credentials("first", "second"))

    assert connector.calls == ["first", "second"]
    assert report.written == 2


@pytest.mark.asyncio
async def test_what_a_tool_returned_is_written_against_the_account_it_came_from() -> None:
    repository: Final = FakeRepository()
    connector: Final = FakeConnector("cursor", result=ToolFetched(facts=(_fact(), _fact("b@x.test")), watermark=NOW))

    await _run([connector], repository=repository)

    assert repository.written == [("acme", 2)]


@pytest.mark.asyncio
async def test_a_failure_is_recorded_with_the_reason_the_tool_gave() -> None:
    sync_runs: Final = FakeSyncRuns()
    connector: Final = FakeConnector("cursor", result=ToolFetchFailed(reason="cursor refused", retryable=False))

    report: Final = await _run([connector], sync_runs=sync_runs)

    assert report.failed == ("cursor",)
    assert sync_runs.runs[0].outcome == "failed"
    assert "cursor refused" in (sync_runs.runs[0].detail or "")


@pytest.mark.asyncio
async def test_a_tool_that_says_it_is_not_configured_is_skipped_not_failed() -> None:
    """These are different problems. A missing credential is something an admin fixes in a
    minute; a failure may be an outage or a revoked key."""
    sync_runs: Final = FakeSyncRuns()
    connector: Final = FakeConnector("cursor", result=ToolNotConfigured(reason="no api_key"))

    report: Final = await _run([connector], sync_runs=sync_runs)

    assert report.skipped == ("cursor",)
    assert report.failed == ()
    assert sync_runs.runs[0].outcome == "not_configured"


@pytest.mark.asyncio
async def test_losing_the_history_row_does_not_lose_the_data() -> None:
    """Sync history is useful, not load-bearing. A run that wrote a customer's spend must not
    be reported as failed because a log row could not be saved."""
    repository: Final = FakeRepository()
    connector: Final = FakeConnector("cursor", result=ToolFetched(facts=(_fact(),), watermark=NOW))

    report: Final = await _run(
        [connector], sync_runs=FakeSyncRuns(raises=RuntimeError("history down")), repository=repository
    )

    assert report.written == 1
    assert report.failed == ()


@pytest.mark.asyncio
async def test_the_window_looks_back_far_enough_to_catch_a_revised_day() -> None:
    """Tools revise a day after it ends. A window with no overlap silently loses those
    revisions, and the fact key makes the overlap free."""
    seen: Final[list[tuple[datetime, datetime]]] = []

    @dataclass
    class Recording:
        @property
        def tool(self) -> ToolName:
            return "cursor"

        async def fetch(self, *, since, until, credential_name, credential_values) -> ToolFetchResult:
            seen.append((since, until))
            return ToolFetched(facts=(), watermark=until)

    await _run([Recording()])  # pyright: ignore[reportArgumentType]  # injected fake

    since, until = seen[0]
    assert until == NOW
    assert (until - since).days >= 1
