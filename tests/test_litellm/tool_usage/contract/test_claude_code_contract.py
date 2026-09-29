"""Does our Claude Code connector speak the API Anthropic documents?

The response payload below is the example printed on Anthropic's own reference page for the
Claude Code usage report, copied rather than written:
https://platform.claude.com/docs/en/api/admin-api/claude-code/get-claude-code-usage-report

Two things in that example matter more than the rest. The estimated cost is stated in minor
currency units, so their 186 is one dollar eighty-six. And `customer_type` is what decides
whether these dollars are already on the Anthropic bill the provider connector reads.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Final

import pytest

from tests.test_litellm.provider_billing.contract.conftest import Reply, Vendor

SINCE: Final = datetime(2026, 9, 1, tzinfo=timezone.utc)
UNTIL: Final = datetime(2026, 9, 1, tzinfo=timezone.utc)
CREDENTIAL: Final = {"api_key": "sk-ant-admin01-not-a-real-key"}

DOCUMENTED_RECORD: Final = {
    "actor": {"email_address": "user@emaildomain.com", "type": "user_actor"},
    "core_metrics": {
        "commits_by_claude_code": 8,
        "lines_of_code": {"added": 342, "removed": 128},
        "num_sessions": 15,
        "pull_requests_by_claude_code": 2,
    },
    "customer_type": "api",
    "date": "2025-08-08T00:00:00Z",
    "is_remote": False,
    "model_breakdown": [
        {
            "estimated_cost": {"amount": 186, "currency": "USD"},
            "model": "claude-opus-5",
            "tokens": {"cache_creation": 2340, "cache_read": 8790, "input": 45230, "output": 12450},
        },
        {
            "estimated_cost": {"amount": 42, "currency": "USD"},
            "model": "claude-sonnet-5",
            "tokens": {"cache_creation": 890, "cache_read": 3420, "input": 23100, "output": 5680},
        },
    ],
    "organization_id": "12345678-1234-5678-1234-567812345678",
    "terminal_type": "iTerm.app",
    "tool_actions": {"edit_tool": {"accepted": 25, "rejected": 3}},
    "subscription_type": "enterprise",
}

DOCUMENTED_PAGE: Final = {"data": [DOCUMENTED_RECORD], "has_more": False, "next_page": None}


async def _fetch(vendor: Vendor, *, until: datetime = UNTIL):
    from litellm.tool_usage.claude_code import ClaudeCodeConnector

    return await ClaudeCodeConnector(
        http_client_factory=vendor.client_factory(), base_url="https://api.anthropic.test"
    ).fetch(since=SINCE, until=until, credential_name="acme-claude-code", credential_values=CREDENTIAL)


@pytest.mark.asyncio
async def test_it_asks_for_the_path_and_method_anthropic_documents(vendor):
    stand_in: Final = vendor(Reply(json=DOCUMENTED_PAGE))

    await _fetch(stand_in)

    assert stand_in.last.method == "GET"
    assert stand_in.last.path == "/v1/organizations/usage_report/claude_code"


@pytest.mark.asyncio
async def test_it_authenticates_the_way_anthropic_documents(vendor):
    stand_in: Final = vendor(Reply(json=DOCUMENTED_PAGE))

    await _fetch(stand_in)

    assert stand_in.last.headers["x-api-key"] == "sk-ant-admin01-not-a-real-key"
    assert stand_in.last.headers["anthropic-version"] == "2023-06-01"
    assert "authorization" not in stand_in.last.headers


@pytest.mark.asyncio
async def test_it_asks_for_one_day_at_a_time_because_that_is_all_the_endpoint_returns(vendor):
    """`starting_at` returns metrics for that single day only, so a week is seven requests.
    Sending a range would silently return one day and under-report the rest of the week."""
    stand_in: Final = vendor(Reply(json=DOCUMENTED_PAGE))

    await _fetch(stand_in, until=datetime(2026, 9, 3, tzinfo=timezone.utc))

    assert [request.params["starting_at"] for request in stand_in.requests] == [
        "2026-09-01",
        "2026-09-02",
        "2026-09-03",
    ]


@pytest.mark.asyncio
async def test_it_stays_inside_the_page_size_anthropic_allows(vendor):
    stand_in: Final = vendor(Reply(json=DOCUMENTED_PAGE))

    await _fetch(stand_in)

    assert 1 <= int(stand_in.last.params["limit"]) <= 1000


@pytest.mark.asyncio
async def test_the_cost_is_minor_units_so_186_is_one_dollar_eighty_six(vendor):
    """Anthropic states the estimated cost in the lowest currency unit. Storing it verbatim
    would overstate a customer's Claude Code spend a hundredfold."""
    from litellm.types.proxy.tool_usage import ToolFetched

    stand_in: Final = vendor(Reply(json=DOCUMENTED_PAGE))

    result: Final = await _fetch(stand_in)

    assert isinstance(result, ToolFetched)
    assert {fact.cost for fact in result.facts} == {Decimal("1.86"), Decimal("0.42")}


@pytest.mark.asyncio
async def test_usage_billed_to_an_api_account_is_marked_as_already_counted(vendor):
    """The documented example is an api customer, so these dollars are already on the Anthropic
    bill the provider connector reads. Counting them again would double a customer's largest
    Anthropic figure."""
    from litellm.types.proxy.tool_usage import ToolFetched

    stand_in: Final = vendor(Reply(json=DOCUMENTED_PAGE))

    result: Final = await _fetch(stand_in)

    assert isinstance(result, ToolFetched)
    assert all(fact.basis == "already_on_a_provider_bill" for fact in result.facts)
    assert not any(fact.counts_toward_total for fact in result.facts)


@pytest.mark.asyncio
async def test_usage_on_a_subscription_plan_is_new_money(vendor):
    from litellm.types.proxy.tool_usage import ToolFetched

    record: Final = {**DOCUMENTED_RECORD, "customer_type": "subscription"}
    stand_in: Final = vendor(Reply(json={"data": [record], "has_more": False, "next_page": None}))

    result: Final = await _fetch(stand_in)

    assert isinstance(result, ToolFetched)
    assert all(fact.basis == "new_money" for fact in result.facts)
    assert all(fact.counts_toward_total for fact in result.facts)


@pytest.mark.asyncio
async def test_it_keeps_the_person_the_tool_named(vendor):
    from litellm.types.proxy.tool_usage import ToolFetched

    stand_in: Final = vendor(Reply(json=DOCUMENTED_PAGE))

    result: Final = await _fetch(stand_in)

    assert isinstance(result, ToolFetched)
    assert {fact.person for fact in result.facts} == {"user@emaildomain.com"}


@pytest.mark.asyncio
async def test_usage_by_an_api_key_is_kept_under_the_key_rather_than_dropped(vendor):
    """It is real spend with no human attached. Dropping it would lose money; attributing it to
    a person would invent one."""
    from litellm.types.proxy.tool_usage import ToolFetched

    record: Final = {**DOCUMENTED_RECORD, "actor": {"api_key_name": "ci-runner", "type": "api_actor"}}
    stand_in: Final = vendor(Reply(json={"data": [record], "has_more": False, "next_page": None}))

    result: Final = await _fetch(stand_in)

    assert isinstance(result, ToolFetched)
    assert {fact.person for fact in result.facts} == {"api key: ci-runner"}


@pytest.mark.asyncio
async def test_it_follows_the_cursor_to_the_end(vendor):
    from litellm.types.proxy.tool_usage import ToolFetched

    first: Final = {"data": [DOCUMENTED_RECORD], "has_more": True, "next_page": "page_abc"}
    second: Final = {
        "data": [{**DOCUMENTED_RECORD, "actor": {"email_address": "other@example.test", "type": "user_actor"}}],
        "has_more": False,
        "next_page": None,
    }
    stand_in: Final = vendor(Reply(json=first), Reply(json=second))

    result: Final = await _fetch(stand_in)

    assert isinstance(result, ToolFetched)
    assert len(stand_in.requests) == 2
    assert stand_in.requests[1].params["page"] == "page_abc"
    assert {fact.person for fact in result.facts} == {"user@emaildomain.com", "other@example.test"}


@pytest.mark.parametrize(
    ("status", "retryable"),
    [(401, False), (403, False), (429, True), (500, True), (503, True)],
)
@pytest.mark.asyncio
async def test_it_turns_an_error_into_a_reason_rather_than_raising(vendor, status: int, retryable: bool):
    from litellm.types.proxy.tool_usage import ToolFetchFailed

    stand_in: Final = vendor(Reply(json={"error": "nope"}, status=status))

    result: Final = await _fetch(stand_in)

    assert isinstance(result, ToolFetchFailed)
    assert result.retryable is retryable
    assert result.reason


@pytest.mark.asyncio
async def test_a_body_that_is_not_json_is_a_failure_not_a_crash(vendor):
    from litellm.types.proxy.tool_usage import ToolFetchFailed

    stand_in: Final = vendor(Reply(text="<html>maintenance</html>"))

    assert isinstance(await _fetch(stand_in), ToolFetchFailed)


@pytest.mark.asyncio
async def test_a_credential_with_no_key_is_reported_before_any_request(vendor):
    from litellm.types.proxy.tool_usage import ToolNotConfigured
    from litellm.tool_usage.claude_code import ClaudeCodeConnector

    stand_in: Final = vendor(Reply(json=DOCUMENTED_PAGE))

    result: Final = await ClaudeCodeConnector(
        http_client_factory=stand_in.client_factory(), base_url="https://api.anthropic.test"
    ).fetch(since=SINCE, until=UNTIL, credential_name="acme", credential_values={})

    assert isinstance(result, ToolNotConfigured)
    assert stand_in.requests == []
