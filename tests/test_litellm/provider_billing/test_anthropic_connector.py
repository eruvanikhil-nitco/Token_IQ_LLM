from __future__ import annotations

import json

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

NOW = datetime(2026, 9, 13, 12, 0, tzinfo=timezone.utc)
CREDENTIAL = {"api_key": "sk-ant-admin01-test"}


def _http(*payloads: dict, status: int = 200) -> MagicMock:
    """Serves the body as text, the way a real response does, so the connector's own decoding
    runs. Handing it a pre-parsed dict would skip the step where money becomes a Decimal."""
    responses = []
    for payload in payloads:
        response = MagicMock()
        response.status_code = status
        response.text = json.dumps(payload)
        responses.append(response)
    client = MagicMock()
    client.get = AsyncMock(side_effect=responses)
    return client


def _bucket(*results: dict, start: str = "2026-09-12T00:00:00Z", end: str = "2026-09-13T00:00:00Z") -> dict:
    return {"starting_at": start, "ending_at": end, "results": list(results)}


def _result(amount: str, model: str | None = "claude-opus-5", **extra: object) -> dict:
    return {
        "amount": amount,
        "currency": "USD",
        "model": model,
        "workspace_id": None,
        "cost_type": "tokens",
        "token_type": "uncached_input_tokens",
        **extra,
    }


async def _fetch(client: MagicMock, credential_values=None):
    from token_iq.connectors.billing.anthropic import AnthropicBillingConnector

    return await AnthropicBillingConnector(http_client_factory=lambda: client).fetch(
        since=NOW - timedelta(days=2),
        until=NOW,
        credential_name="acme-anthropic",
        credential_values=CREDENTIAL if credential_values is None else credential_values,
    )


@pytest.mark.asyncio
async def test_the_amount_is_cents_and_must_reach_the_table_as_dollars():
    """Anthropic documents amount in lowest currency units, so 123.45 means one dollar and
    twenty-three cents. Storing it verbatim would overstate every customer's Anthropic
    spend by a factor of one hundred, in the table whose whole purpose is to be the
    accurate one."""
    from litellm.types.proxy.provider_billing import Fetched

    result = await _fetch(_http({"data": [_bucket(_result("123.45"))], "has_more": False, "next_page": None}))

    assert isinstance(result, Fetched)
    assert result.facts[0].billed_cost == Decimal("1.2345")


@pytest.mark.asyncio
async def test_one_fact_per_model_per_day_summing_the_token_types():
    """A bucket carries a row per token type. The comparable unit against our own spend is
    the day's charge for a model, so they are summed rather than stored separately."""
    from litellm.types.proxy.provider_billing import Fetched

    result = await _fetch(
        _http(
            {
                "data": [
                    _bucket(
                        _result("100", token_type="uncached_input_tokens"),
                        _result("50", token_type="output_tokens"),
                        _result("25", model="claude-haiku-4-5"),
                    )
                ],
                "has_more": False,
                "next_page": None,
            }
        )
    )

    assert isinstance(result, Fetched)
    by_model = {fact.model: fact.billed_cost for fact in result.facts}
    assert by_model["claude-opus-5"] == Decimal("1.50")
    assert by_model["claude-haiku-4-5"] == Decimal("0.25")


@pytest.mark.asyncio
async def test_the_fact_key_is_stable_so_a_refetch_overwrites():
    """Every run re-reads the last day. Without a key identical across runs, the same
    day's cost would be inserted again on every tick."""
    from litellm.types.proxy.provider_billing import Fetched

    payload = {"data": [_bucket(_result("100"))], "has_more": False, "next_page": None}
    first = await _fetch(_http(payload))
    second = await _fetch(_http(payload))

    assert isinstance(first, Fetched) and isinstance(second, Fetched)
    assert first.facts[0].fact_key == second.facts[0].fact_key == "anthropic:acme-anthropic:2026-09-12:claude-opus-5"


@pytest.mark.asyncio
async def test_the_bucket_start_is_the_day_the_cost_belongs_to():
    """Stamping the fetch time instead would file yesterday's charges under today and make
    every daily comparison off by one."""
    from litellm.types.proxy.provider_billing import Fetched

    result = await _fetch(_http({"data": [_bucket(_result("100"))], "has_more": False, "next_page": None}))

    assert isinstance(result, Fetched)
    assert result.facts[0].bucket_start.date().isoformat() == "2026-09-12"


@pytest.mark.asyncio
async def test_every_page_is_followed():
    """A page holds at most 31 daily buckets. Reading only the first would silently drop
    history on any longer window."""
    from litellm.types.proxy.provider_billing import Fetched

    client = _http(
        {"data": [_bucket(_result("100"))], "has_more": True, "next_page": "page_2"},
        {
            "data": [_bucket(_result("200"), start="2026-09-11T00:00:00Z", end="2026-09-12T00:00:00Z")],
            "has_more": False,
            "next_page": None,
        },
    )
    result = await _fetch(client)

    assert isinstance(result, Fetched)
    assert len(result.facts) == 2
    assert client.get.await_args_list[1].kwargs["params"]["page"] == "page_2"


@pytest.mark.asyncio
async def test_a_cost_with_no_model_is_still_recorded():
    """Web search and code execution charges carry no model. Dropping them would
    understate the bill by exactly the amount hardest to explain later."""
    from litellm.types.proxy.provider_billing import Fetched

    result = await _fetch(
        _http(
            {
                "data": [_bucket(_result("500", model=None, cost_type="web_search"))],
                "has_more": False,
                "next_page": None,
            }
        )
    )

    assert isinstance(result, Fetched)
    assert result.facts[0].billed_cost == Decimal("5.00")
    assert result.facts[0].fact_key == "anthropic:acme-anthropic:2026-09-12:unattributed"


@pytest.mark.asyncio
async def test_a_missing_credential_is_reported_not_raised():
    from litellm.types.proxy.provider_billing import NotConfigured

    assert isinstance(await _fetch(_http({}), credential_values={}), NotConfigured)


@pytest.mark.asyncio
async def test_a_rate_limit_is_retryable_and_a_bad_key_is_not():
    from litellm.types.proxy.provider_billing import FetchFailed

    limited = await _fetch(_http({}, status=429))
    refused = await _fetch(_http({}, status=401))

    assert isinstance(limited, FetchFailed) and limited.retryable is True
    assert isinstance(refused, FetchFailed) and refused.retryable is False


@pytest.mark.asyncio
async def test_the_admin_key_goes_in_the_anthropic_header_not_a_bearer_token():
    """Anthropic authenticates with x-api-key. A Bearer header returns 401, which would
    read as a revoked key rather than a coding mistake."""
    client = _http({"data": [], "has_more": False, "next_page": None})
    await _fetch(client)

    headers = client.get.await_args.kwargs["headers"]
    assert headers["x-api-key"] == "sk-ant-admin01-test"
    assert headers["anthropic-version"] == "2023-06-01"
    assert "Authorization" not in headers


@pytest.mark.asyncio
async def test_an_empty_window_is_a_successful_empty_run():
    from litellm.types.proxy.provider_billing import Fetched

    result = await _fetch(_http({"data": [], "has_more": False, "next_page": None}))

    assert isinstance(result, Fetched)
    assert result.facts == ()


def test_each_fact_keeps_every_anthropic_row_that_fed_it():
    from token_iq.connectors.billing.anthropic import _facts_from

    facts = _facts_from(
        [
            {
                "starting_at": "2026-09-15T00:00:00Z",
                "results": [
                    {"model": "claude-sonnet-4", "amount": "100", "token_type": "input"},
                    {"model": "claude-sonnet-4", "amount": "200", "token_type": "output"},
                ],
            }
        ],
        "acct",
    )

    assert facts[0].raw == {
        "starting_at": "2026-09-15T00:00:00Z",
        "results": [
            {"model": "claude-sonnet-4", "amount": "100", "token_type": "input"},
            {"model": "claude-sonnet-4", "amount": "200", "token_type": "output"},
        ],
    }


@pytest.mark.asyncio
async def test_it_calls_the_host_anthropic_documents():
    client = _http({"data": [], "has_more": False, "next_page": None})

    await _fetch(client)

    assert client.get.call_args.args[0] == "https://api.anthropic.com/v1/organizations/cost_report"


@pytest.mark.asyncio
async def test_a_deployment_can_point_the_connector_at_its_own_host():
    """A customer on a sovereign cloud, behind a corporate proxy, or a test standing in for
    Anthropic needs somewhere to put their host. Without this the only way to reach a
    different endpoint is to fork the file."""
    from token_iq.connectors.billing.anthropic import AnthropicBillingConnector

    client = _http({"data": [], "has_more": False, "next_page": None})

    await AnthropicBillingConnector(
        http_client_factory=lambda: client, base_url="https://anthropic.internal.example"
    ).fetch(since=NOW - timedelta(days=2), until=NOW, credential_name="acme", credential_values=CREDENTIAL)

    assert client.get.call_args.args[0] == "https://anthropic.internal.example/v1/organizations/cost_report"
