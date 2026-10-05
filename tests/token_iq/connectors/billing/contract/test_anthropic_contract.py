"""Does our Anthropic connector speak the API Anthropic documents?

The response payload below is the example response printed on Anthropic's own reference page
for Get Cost Report, copied rather than written:
https://platform.claude.com/docs/en/api/admin-api/usage-cost/get-cost-report

That distinction is the whole point. A payload reverse-engineered from our parser proves only
that the parser agrees with itself. This one was produced by Anthropic, so parsing it is
evidence about their API rather than about our own assumptions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Final

import pytest

from tests.token_iq.connectors.billing.contract.conftest import Reply, Vendor

SINCE: Final = datetime(2026, 9, 1, tzinfo=timezone.utc)
UNTIL: Final = datetime(2026, 9, 3, tzinfo=timezone.utc)
CREDENTIAL: Final = {"api_key": "sk-ant-admin01-not-a-real-key"}

DOCUMENTED_PAGE: Final = {
    "data": [
        {
            "ending_at": "2025-08-02T00:00:00Z",
            "results": [
                {
                    "amount": "123.78912",
                    "context_window": "0-200k",
                    "cost_type": "tokens",
                    "currency": "USD",
                    "description": "Claude Opus 5 Usage - Input Tokens",
                    "inference_geo": "global",
                    "model": "claude-opus-5",
                    "service_tier": "standard",
                    "token_type": "uncached_input_tokens",
                    "workspace_id": "wrkspc_01JwQvzr7rXLA5AGx3HKfFUJ",
                }
            ],
            "starting_at": "2025-08-01T00:00:00Z",
        }
    ],
    "has_more": False,
    "next_page": None,
}


def _second_page() -> dict[str, object]:
    return {
        "data": [
            {
                "ending_at": "2025-08-03T00:00:00Z",
                "results": [
                    {
                        "amount": "50.5",
                        "context_window": "0-200k",
                        "cost_type": "tokens",
                        "currency": "USD",
                        "description": "Claude Opus 5 Usage - Output Tokens",
                        "inference_geo": "global",
                        "model": "claude-opus-5",
                        "service_tier": "standard",
                        "token_type": "output_tokens",
                        "workspace_id": None,
                    }
                ],
                "starting_at": "2025-08-02T00:00:00Z",
            }
        ],
        "has_more": False,
        "next_page": None,
    }


def _first_of_two() -> dict[str, object]:
    return {**DOCUMENTED_PAGE, "has_more": True, "next_page": "page_MjAyNS0wNS0xNFQwMDowMDowMFo="}


async def _fetch(vendor: Vendor, *, base_url: str = "https://api.anthropic.test"):
    from token_iq.connectors.billing.anthropic import AnthropicBillingConnector

    return await AnthropicBillingConnector(http_client_factory=vendor.client_factory(), base_url=base_url).fetch(
        since=SINCE, until=UNTIL, credential_name="acme-anthropic", credential_values=CREDENTIAL
    )


@pytest.mark.asyncio
async def test_it_asks_for_the_path_and_method_anthropic_documents(vendor):
    stand_in: Final = vendor(Reply(json=DOCUMENTED_PAGE))

    await _fetch(stand_in)

    assert stand_in.last.method == "GET"
    assert stand_in.last.path == "/v1/organizations/cost_report"


@pytest.mark.asyncio
async def test_it_authenticates_the_way_anthropic_documents(vendor):
    """Anthropic uses an api key header and a version header, not a bearer token. Sending
    `Authorization: Bearer` here is rejected, and no test that mocks the client can tell."""
    stand_in: Final = vendor(Reply(json=DOCUMENTED_PAGE))

    await _fetch(stand_in)

    assert stand_in.last.headers["x-api-key"] == "sk-ant-admin01-not-a-real-key"
    assert stand_in.last.headers["anthropic-version"] == "2023-06-01"
    assert "authorization" not in stand_in.last.headers


@pytest.mark.asyncio
async def test_it_sends_the_window_and_granularity_anthropic_documents(vendor):
    stand_in: Final = vendor(Reply(json=DOCUMENTED_PAGE))

    await _fetch(stand_in)

    assert stand_in.last.params["starting_at"] == "2026-09-01T00:00:00Z"
    assert stand_in.last.params["ending_at"] == "2026-09-03T00:00:00Z"
    assert stand_in.last.params["bucket_width"] == "1d"
    assert stand_in.last.params["group_by[]"] == "description"


@pytest.mark.asyncio
async def test_it_stays_inside_the_page_size_anthropic_allows(vendor):
    """The reference caps limit at 31. Asking for more is a 400 on the first real call."""
    stand_in: Final = vendor(Reply(json=DOCUMENTED_PAGE))

    await _fetch(stand_in)

    assert 1 <= int(stand_in.last.params["limit"]) <= 31


@pytest.mark.asyncio
async def test_it_reads_the_amount_out_of_anthropics_own_example(vendor):
    """Anthropic states amount in the lowest currency unit, so their documented "123.78912"
    is one dollar twenty-three, not a hundred and twenty-three dollars."""
    from token_iq.types.provider_billing import Fetched

    stand_in: Final = vendor(Reply(json=DOCUMENTED_PAGE))

    result: Final = await _fetch(stand_in)

    assert isinstance(result, Fetched)
    assert result.facts[0].billed_cost == Decimal("1.2378912")
    assert result.facts[0].billing_currency == "USD"


@pytest.mark.asyncio
async def test_it_follows_the_cursor_to_the_end(vendor):
    """A connector that stops at page one looks healthy and under-reports spend forever,
    which is the worst thing this product can do."""
    from token_iq.types.provider_billing import Fetched

    stand_in: Final = vendor(Reply(json=_first_of_two()), Reply(json=_second_page()))

    result: Final = await _fetch(stand_in)

    assert isinstance(result, Fetched)
    assert len(stand_in.requests) == 2
    assert stand_in.requests[1].params["page"] == "page_MjAyNS0wNS0xNFQwMDowMDowMFo="
    assert len(result.facts) == 2


@pytest.mark.parametrize(
    ("status", "retryable"),
    [(401, False), (403, False), (429, True), (500, True), (503, True)],
)
@pytest.mark.asyncio
async def test_it_turns_an_error_into_a_reason_rather_than_raising(vendor, status: int, retryable: bool):
    from token_iq.types.provider_billing import FetchFailed

    stand_in: Final = vendor(Reply(json={"error": "nope"}, status=status))

    result: Final = await _fetch(stand_in)

    assert isinstance(result, FetchFailed)
    assert result.retryable is retryable
    assert result.reason


@pytest.mark.asyncio
async def test_a_body_that_is_not_json_is_a_failure_not_a_crash(vendor):
    from token_iq.types.provider_billing import FetchFailed

    stand_in: Final = vendor(Reply(text="<html>maintenance</html>"))

    result: Final = await _fetch(stand_in)

    assert isinstance(result, FetchFailed)


@pytest.mark.asyncio
async def test_a_body_of_the_wrong_shape_is_a_failure_not_a_crash(vendor):
    from token_iq.types.provider_billing import FetchFailed

    stand_in: Final = vendor(Reply(json=["not", "an", "object"]))

    result: Final = await _fetch(stand_in)

    assert isinstance(result, FetchFailed)


@pytest.mark.asyncio
async def test_a_cost_with_more_digits_than_a_float_can_hold_survives(vendor):
    """The number below cannot be represented as a binary float, so any decode that passes
    through one silently rounds it. Anthropic states amounts as strings, but this connector
    shares its decoder with the ones whose vendors send JSON numbers, and that decoder is the
    only thing standing between a customer's bill and a rounded figure."""
    from token_iq.types.provider_billing import Fetched

    exact: Final = "12345678901234567890.12345"
    page: Final = {
        "data": [
            {
                "ending_at": "2025-08-02T00:00:00Z",
                "results": [{**DOCUMENTED_PAGE["data"][0]["results"][0], "amount": exact}],
                "starting_at": "2025-08-01T00:00:00Z",
            }
        ],
        "has_more": False,
        "next_page": None,
    }
    stand_in: Final = vendor(Reply(json=page))

    result: Final = await _fetch(stand_in)

    assert isinstance(result, Fetched)
    assert result.facts[0].billed_cost == Decimal(exact) / 100
