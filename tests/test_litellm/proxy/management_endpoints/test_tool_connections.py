from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Final

import pytest

from litellm.proxy.management_endpoints.tool_connections import build_tool_connection, build_tool_connections
from litellm.types.proxy.provider_billing import BillingCredential, ProviderSyncRun

NOW: Final = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)


def _credential(name: str = "acme") -> BillingCredential:
    return BillingCredential(name=name, values={"api_key": "k"})


def _run(credential_name: str = "acme", *, tool: str = "cursor", outcome: str = "fetched") -> ProviderSyncRun:
    return ProviderSyncRun(
        provider=tool,
        credential_name=credential_name,
        started_at=NOW,
        finished_at=NOW,
        outcome=outcome,  # pyright: ignore[reportArgumentType]  # the literal is validated at the boundary
        facts_written=3,
        window_start=NOW,
        window_end=NOW,
        detail=None,
    )


def test_a_tool_with_no_credential_reads_as_not_connected() -> None:
    connection: Final = build_tool_connection(tool="cursor", credentials=(), newest={}, counts={})

    assert connection.state == "not_connected"
    assert connection.accounts == ()


def test_a_tool_that_has_never_stored_a_row_is_not_verified() -> None:
    connection: Final = build_tool_connection(
        tool="cursor", credentials=(_credential(),), newest={"acme": _run()}, counts={}
    )

    assert connection.verified_against_real_account is False


def test_a_tool_with_real_rows_is_verified() -> None:
    connection: Final = build_tool_connection(
        tool="cursor", credentials=(_credential(),), newest={"acme": _run()}, counts={"acme": 12}
    )

    assert connection.verified_against_real_account is True
    assert connection.accounts[0].rows_stored == 12


def test_every_tool_says_what_it_cannot_tell_us() -> None:
    """Two of the three cannot report what a reader would assume, and a screen that showed
    only figures would leave a customer working out why on their own."""
    for tool in ("claude_code", "cursor", "copilot"):
        connection = build_tool_connection(tool=tool, credentials=(), newest={}, counts={})

        assert connection.fetches.what_it_cannot_give.strip() != ""


def test_copilot_says_it_reports_no_cost_at_all() -> None:
    connection: Final = build_tool_connection(tool="copilot", credentials=(), newest={}, counts={})

    assert "no cost" in connection.fetches.what_it_cannot_give.lower()


def test_claude_code_says_api_usage_is_already_on_the_anthropic_bill() -> None:
    """The one thing a customer must understand about this screen: the Claude Code figure and
    the Anthropic bill are partly the same money."""
    connection: Final = build_tool_connection(tool="claude_code", credentials=(), newest={}, counts={})

    assert "already" in connection.fetches.what_it_cannot_give.lower()
    assert "anthropic" in connection.fetches.what_it_cannot_give.lower()


def test_every_tool_says_it_has_never_met_a_real_account() -> None:
    for tool in ("claude_code", "cursor", "copilot"):
        connection = build_tool_connection(tool=tool, credentials=(), newest={}, counts={})

        assert "never run against a real account" in connection.fetches.verification_note.lower()


@pytest.mark.asyncio
async def test_the_response_carries_one_row_per_tool() -> None:
    async def credentials_for(_tool: str) -> tuple[BillingCredential, ...]:
        return ()

    async def counts_for(_tool: str) -> Mapping[str, int]:
        return {}

    response: Final = await build_tool_connections(
        tools=("claude_code", "cursor", "copilot"),
        credentials_for=credentials_for,
        recent_runs=(),
        counts_for=counts_for,
    )

    assert [tool.tool for tool in response.tools] == ["claude_code", "cursor", "copilot"]


@pytest.mark.asyncio
async def test_a_run_for_another_tool_does_not_colour_this_one() -> None:
    """Every tool records into the same sync history, so a Cursor failure must not make
    Claude Code look broken."""

    async def credentials_for(_tool: str) -> tuple[BillingCredential, ...]:
        return (_credential(),)

    async def counts_for(_tool: str) -> Mapping[str, int]:
        return {"acme": 5}

    runs: Final[Sequence[ProviderSyncRun]] = (_run(tool="cursor", outcome="failed"),)

    response: Final = await build_tool_connections(
        tools=("claude_code",), credentials_for=credentials_for, recent_runs=runs, counts_for=counts_for
    )

    assert response.tools[0].accounts[0].last_outcome is None
