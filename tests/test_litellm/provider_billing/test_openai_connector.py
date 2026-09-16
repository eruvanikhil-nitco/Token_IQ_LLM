from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

NOW = datetime(2026, 9, 13, 12, 0, tzinfo=timezone.utc)
CREDENTIAL = {"api_key": "sk-admin-test"}
DAY_START = int(datetime(2026, 9, 12, tzinfo=timezone.utc).timestamp())


def _http(*payloads: dict, status: int = 200) -> MagicMock:
    responses = []
    for payload in payloads:
        response = MagicMock()
        response.status_code = status
        response.json = MagicMock(return_value=payload)
        responses.append(response)
    client = MagicMock()
    client.get = AsyncMock(side_effect=responses)
    return client


def _bucket(*results: dict, start: int = DAY_START) -> dict:
    return {"object": "bucket", "start_time": start, "end_time": start + 86400, "results": list(results)}


def _result(value: float, line_item: str | None = "gpt-4o-mini, input") -> dict:
    return {
        "object": "organization.costs.result",
        "amount": {"value": value, "currency": "usd"},
        "line_item": line_item,
        "project_id": None,
        "api_key_id": None,
    }


def _page(*buckets: dict, has_more: bool = False, next_page: str | None = None) -> dict:
    return {"object": "page", "data": list(buckets), "has_more": has_more, "next_page": next_page}


async def _fetch(client: MagicMock, credential_values=None):
    from litellm.provider_billing.openai import OpenAIBillingConnector

    return await OpenAIBillingConnector(http_client_factory=lambda: client).fetch(
        since=NOW - timedelta(days=2),
        until=NOW,
        credential_name="acme-openai",
        credential_values=CREDENTIAL if credential_values is None else credential_values,
    )


@pytest.mark.asyncio
async def test_the_amount_is_already_dollars_and_is_not_scaled():
    """OpenAI reports dollars where Anthropic reports cents. Applying Anthropic's
    conversion here would understate every OpenAI bill by a factor of one hundred."""
    from litellm.types.proxy.provider_billing import Fetched

    result = await _fetch(_http(_page(_bucket(_result(0.06)))))

    assert isinstance(result, Fetched)
    assert result.facts[0].billed_cost == Decimal("0.06")


@pytest.mark.asyncio
async def test_a_float_amount_keeps_its_digits():
    """json hands back a float. Decimal(float) carries the binary approximation of it;
    going through str does not."""
    from litellm.types.proxy.provider_billing import Fetched

    result = await _fetch(_http(_page(_bucket(_result(0.1)))))

    assert isinstance(result, Fetched)
    assert result.facts[0].billed_cost == Decimal("0.1")


@pytest.mark.asyncio
async def test_the_unix_bucket_becomes_the_day_the_cost_belongs_to():
    from litellm.types.proxy.provider_billing import Fetched

    result = await _fetch(_http(_page(_bucket(_result(1.0)))))

    assert isinstance(result, Fetched)
    assert result.facts[0].bucket_start.date().isoformat() == "2026-09-12"


@pytest.mark.asyncio
async def test_the_window_is_sent_as_unix_seconds():
    """OpenAI rejects RFC 3339 here, where Anthropic requires it."""
    client = _http(_page())
    await _fetch(client)

    params = client.get.await_args.kwargs["params"]
    assert isinstance(params["start_time"], int)
    assert isinstance(params["end_time"], int)


@pytest.mark.asyncio
async def test_line_items_are_kept_separate_within_a_day():
    from litellm.types.proxy.provider_billing import Fetched

    result = await _fetch(
        _http(_page(_bucket(_result(0.06, "gpt-4o-mini, input"), _result(0.02, "gpt-4o-mini, output"))))
    )

    assert isinstance(result, Fetched)
    assert {fact.model for fact in result.facts} == {"gpt-4o-mini, input", "gpt-4o-mini, output"}


@pytest.mark.asyncio
async def test_the_fact_key_is_stable_so_a_refetch_overwrites():
    from litellm.types.proxy.provider_billing import Fetched

    first = await _fetch(_http(_page(_bucket(_result(1.0)))))
    second = await _fetch(_http(_page(_bucket(_result(1.0)))))

    assert isinstance(first, Fetched) and isinstance(second, Fetched)
    assert first.facts[0].fact_key == second.facts[0].fact_key


@pytest.mark.asyncio
async def test_every_page_is_followed():
    from litellm.types.proxy.provider_billing import Fetched

    client = _http(
        _page(_bucket(_result(1.0)), has_more=True, next_page="page_2"),
        _page(_bucket(_result(2.0), start=DAY_START - 86400)),
    )
    result = await _fetch(client)

    assert isinstance(result, Fetched)
    assert len(result.facts) == 2
    assert client.get.await_args_list[1].kwargs["params"]["page"] == "page_2"


@pytest.mark.asyncio
async def test_the_admin_key_goes_in_a_bearer_header():
    client = _http(_page())
    await _fetch(client)

    assert client.get.await_args.kwargs["headers"]["Authorization"] == "Bearer sk-admin-test"


@pytest.mark.asyncio
async def test_a_cost_with_no_line_item_is_still_recorded():
    from litellm.types.proxy.provider_billing import Fetched

    result = await _fetch(_http(_page(_bucket(_result(3.0, line_item=None)))))

    assert isinstance(result, Fetched)
    assert result.facts[0].billed_cost == Decimal("3.0")
    assert result.facts[0].fact_key == "openai:2026-09-12:unattributed"


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


def test_each_fact_keeps_the_result_openai_sent():
    from litellm.provider_billing.openai import _facts_from

    facts = _facts_from(
        [
            {
                "start_time": 1789344000,
                "results": [{"line_item": "gpt-4o", "amount": {"value": 1.25, "currency": "usd"}}],
            }
        ],
        "acct",
    )

    assert facts[0].raw == {"line_item": "gpt-4o", "amount": {"value": 1.25, "currency": "usd"}}
