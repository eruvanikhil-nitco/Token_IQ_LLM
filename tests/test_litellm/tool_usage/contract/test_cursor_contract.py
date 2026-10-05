"""Does our Cursor connector speak the API Cursor documents?

The response payload below is the example printed on Cursor's own Admin API reference for
`POST /teams/filtered-usage-events`, copied rather than written:
https://cursor.com/docs/account/teams/admin-api

Three things in it are unlike every other connector here and each is wrong until a real server
says so. Cursor authenticates with HTTP Basic, the API key as the username and no password.
The window is epoch milliseconds in a POST body rather than query parameters. And the event
timestamp is epoch milliseconds delivered as a string.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Final

import pytest

from tests.test_litellm.provider_billing.contract.conftest import Reply, Vendor

SINCE: Final = datetime(2026, 9, 1, tzinfo=timezone.utc)
UNTIL: Final = datetime(2026, 9, 3, tzinfo=timezone.utc)
CREDENTIAL: Final = {"api_key": "key_not_a_real_cursor_key"}

DAY_ONE_MILLIS: Final = int(datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc).timestamp() * 1000)
DAY_TWO_MILLIS: Final = int(datetime(2026, 9, 2, 10, 0, tzinfo=timezone.utc).timestamp() * 1000)

DOCUMENTED_EVENT: Final = {
    "timestamp": str(DAY_ONE_MILLIS),
    "userEmail": "developer@company.com",
    "serviceAccountId": "sa_abc123",
    "serviceAccountName": "Nightly CI Agent",
    "cloudAgentId": "ca_xyz789",
    "automationId": "7fc64f90-6d7a-4a5d-91b1-bd1f529a85dd",
    "conversationId": "8f2e4a1b-6c3d-4e5f-9a7b-2d1c8e6f4a3b",
    "model": "claude-4.5-sonnet",
    "kind": "Usage-based",
    "maxMode": True,
    "requestsCosts": 5,
    "isTokenBasedCall": True,
    "isChargeable": True,
    "isHeadless": False,
    "tokenUsage": {
        "inputTokens": 126,
        "outputTokens": 450,
        "cacheWriteTokens": 6112,
        "cacheReadTokens": 11964,
        "totalCents": 20.18232,
        "discountPercentOff": 10,
    },
    "chargedCents": 21.36232,
    "cursorTokenFee": 1.18,
}


def _page(*events: dict[str, object], has_next: bool = False) -> dict[str, object]:
    return {
        "totalUsageEventsCount": len(events),
        "pagination": {
            "numPages": 1,
            "currentPage": 1,
            "pageSize": 25,
            "hasNextPage": has_next,
            "hasPreviousPage": False,
        },
        "usageEvents": list(events),
        "period": {"startDate": DAY_ONE_MILLIS, "endDate": DAY_TWO_MILLIS},
    }


async def _fetch(vendor: Vendor, *, until: datetime = UNTIL):
    from token_iq.connectors.tools.cursor import CursorConnector

    return await CursorConnector(http_client_factory=vendor.client_factory(), base_url="https://api.cursor.test").fetch(
        since=SINCE, until=until, credential_name="acme-cursor", credential_values=CREDENTIAL
    )


@pytest.mark.asyncio
async def test_it_posts_to_the_path_cursor_documents(vendor):
    stand_in: Final = vendor(Reply(json=_page(DOCUMENTED_EVENT)))

    await _fetch(stand_in)

    assert stand_in.last.method == "POST"
    assert stand_in.last.path == "/teams/filtered-usage-events"


@pytest.mark.asyncio
async def test_it_authenticates_with_basic_auth_the_way_cursor_documents(vendor):
    """The key is the username and the password is empty, which is not what any other
    connector here does. A bearer token is refused, and no mocked client can tell."""
    import base64

    stand_in: Final = vendor(Reply(json=_page(DOCUMENTED_EVENT)))

    await _fetch(stand_in)

    header: Final = stand_in.last.headers["authorization"]
    assert header.startswith("Basic ")
    assert base64.b64decode(header.removeprefix("Basic ")).decode() == "key_not_a_real_cursor_key:"


@pytest.mark.asyncio
async def test_it_sends_the_window_as_epoch_milliseconds_in_the_body(vendor):
    stand_in: Final = vendor(Reply(json=_page(DOCUMENTED_EVENT)))

    await _fetch(stand_in)

    sent: Final = json.loads(stand_in.last.body)
    assert sent["startDate"] == int(SINCE.timestamp() * 1000)
    assert sent["endDate"] == int(UNTIL.timestamp() * 1000)


@pytest.mark.asyncio
async def test_it_stays_inside_the_page_size_cursor_allows(vendor):
    stand_in: Final = vendor(Reply(json=_page(DOCUMENTED_EVENT)))

    await _fetch(stand_in)

    assert 1 <= json.loads(stand_in.last.body)["pageSize"] <= 1000


@pytest.mark.asyncio
async def test_a_charge_in_cents_becomes_dollars_without_rounding(vendor):
    """Cursor charges fractional cents, so 21.36232 is twenty-one and a third cents. Rounding
    it to a cent would drift a team's monthly figure by real money."""
    from litellm.types.proxy.tool_usage import ToolFetched

    stand_in: Final = vendor(Reply(json=_page(DOCUMENTED_EVENT)))

    result: Final = await _fetch(stand_in)

    assert isinstance(result, ToolFetched)
    assert result.facts[0].cost == Decimal("21.36232") / 100


@pytest.mark.asyncio
async def test_cursor_spend_is_new_money_because_it_is_on_no_provider_bill_we_read(vendor):
    """Cursor buys the models itself and bills the customer, so unlike Claude Code on an API
    organisation this never arrives twice."""
    from litellm.types.proxy.tool_usage import ToolFetched

    stand_in: Final = vendor(Reply(json=_page(DOCUMENTED_EVENT)))

    result: Final = await _fetch(stand_in)

    assert isinstance(result, ToolFetched)
    assert all(fact.basis == "new_money" for fact in result.facts)
    assert all(fact.counts_toward_total for fact in result.facts)


@pytest.mark.asyncio
async def test_a_persons_events_in_one_day_are_summed_into_one_fact(vendor):
    """Cursor reports one row per request. A busy team produces hundreds of thousands a month
    and nothing downstream asks a question that needs them individually."""
    from litellm.types.proxy.tool_usage import ToolFetched

    second: Final = {**DOCUMENTED_EVENT, "chargedCents": 10.0}
    stand_in: Final = vendor(Reply(json=_page(DOCUMENTED_EVENT, second)))

    result: Final = await _fetch(stand_in)

    assert isinstance(result, ToolFetched)
    assert len(result.facts) == 1
    assert result.facts[0].cost == (Decimal("21.36232") + Decimal("10.0")) / 100
    assert result.facts[0].input_tokens == 252


@pytest.mark.asyncio
async def test_two_days_stay_two_facts_so_a_day_can_still_be_read_on_its_own(vendor):
    from litellm.types.proxy.tool_usage import ToolFetched

    later: Final = {**DOCUMENTED_EVENT, "timestamp": str(DAY_TWO_MILLIS)}
    stand_in: Final = vendor(Reply(json=_page(DOCUMENTED_EVENT, later)))

    result: Final = await _fetch(stand_in)

    assert isinstance(result, ToolFetched)
    assert {fact.day for fact in result.facts} == {
        datetime(2026, 9, 1, tzinfo=timezone.utc),
        datetime(2026, 9, 2, tzinfo=timezone.utc),
    }


@pytest.mark.asyncio
async def test_two_models_in_one_day_stay_separate_rather_than_becoming_one_number(vendor):
    from litellm.types.proxy.tool_usage import ToolFetched

    other_model: Final = {**DOCUMENTED_EVENT, "model": "gpt-5"}
    stand_in: Final = vendor(Reply(json=_page(DOCUMENTED_EVENT, other_model)))

    result: Final = await _fetch(stand_in)

    assert isinstance(result, ToolFetched)
    assert {fact.model for fact in result.facts} == {"claude-4.5-sonnet", "gpt-5"}


@pytest.mark.asyncio
async def test_an_event_with_nobody_attached_is_left_out_rather_than_guessed_at(vendor):
    from litellm.types.proxy.tool_usage import ToolFetched

    anonymous: Final = {k: v for k, v in DOCUMENTED_EVENT.items() if k != "userEmail"}
    stand_in: Final = vendor(Reply(json=_page(anonymous)))

    result: Final = await _fetch(stand_in)

    assert isinstance(result, ToolFetched)
    assert result.facts == ()


@pytest.mark.asyncio
async def test_it_follows_pagination_to_the_end(vendor):
    from litellm.types.proxy.tool_usage import ToolFetched

    stand_in: Final = vendor(
        Reply(json=_page(DOCUMENTED_EVENT, has_next=True)),
        Reply(json=_page({**DOCUMENTED_EVENT, "userEmail": "other@company.com"})),
    )

    result: Final = await _fetch(stand_in)

    assert isinstance(result, ToolFetched)
    assert json.loads(stand_in.requests[0].body)["page"] == 1
    assert json.loads(stand_in.requests[1].body)["page"] == 2
    assert {fact.person for fact in result.facts} == {"developer@company.com", "other@company.com"}


@pytest.mark.asyncio
async def test_a_long_period_is_split_into_windows_the_endpoint_accepts(vendor):
    """The team endpoints take at most thirty days in one call, so a quarter is several
    requests rather than one that comes back empty or refused."""
    stand_in: Final = vendor(Reply(json=_page()))

    await _fetch(stand_in, until=datetime(2026, 11, 30, tzinfo=timezone.utc))

    assert len(stand_in.requests) >= 3
    for request in stand_in.requests:
        sent = json.loads(request.body)
        assert sent["endDate"] - sent["startDate"] <= 30 * 24 * 60 * 60 * 1000


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
    from token_iq.connectors.tools.cursor import CursorConnector
    from litellm.types.proxy.tool_usage import ToolNotConfigured

    stand_in: Final = vendor(Reply(json=_page()))

    result: Final = await CursorConnector(
        http_client_factory=stand_in.client_factory(), base_url="https://api.cursor.test"
    ).fetch(since=SINCE, until=UNTIL, credential_name="acme", credential_values={})

    assert isinstance(result, ToolNotConfigured)
    assert stand_in.requests == []
