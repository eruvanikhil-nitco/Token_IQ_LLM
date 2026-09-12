from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

NOW = datetime(2026, 9, 13, 12, 0, tzinfo=timezone.utc)
CREDENTIAL = {"api_key": "sk-or-test"}


def _http(payload: dict, status: int = 200) -> MagicMock:
    response = MagicMock()
    response.status_code = status
    response.json = MagicMock(return_value=payload)
    client = MagicMock()
    client.get = AsyncMock(return_value=response)
    return client


def _connector(ids: list[str], client: MagicMock):
    from litellm.provider_billing.openrouter import OpenRouterBillingConnector

    async def unpriced() -> list[str]:
        return ids

    return OpenRouterBillingConnector(unpriced_request_ids=unpriced, http_client_factory=lambda: client)


async def _fetch(ids: list[str], client: MagicMock, credential_values=None):
    return await _connector(ids, client).fetch(
        since=NOW - timedelta(days=1),
        until=NOW,
        credential_name="acme-openrouter",
        credential_values=CREDENTIAL if credential_values is None else credential_values,
    )


@pytest.mark.asyncio
async def test_a_generation_becomes_a_reconciled_fact():
    """OpenRouter states the dollars for this exact request, which is the strongest
    evidence any provider gives. Recording it as anything weaker would understate what we
    can prove to a customer."""
    from litellm.types.proxy.provider_billing import Fetched

    client = _http(
        {
            "data": {
                "id": "gen-1",
                "total_cost": 0.0000025,
                "model": "openai/gpt-4o-mini",
                "tokens_prompt": 7,
                "tokens_completion": 4,
            }
        }
    )
    result = await _fetch(["gen-1"], client)

    assert isinstance(result, Fetched)
    fact = result.facts[0]
    assert fact.fact_key == "openrouter:gen-1"
    assert fact.evidence == "reconciled"
    assert fact.billed_cost == Decimal("0.0000025")
    assert fact.provider_request_id == "gen-1"
    assert fact.model == "openai/gpt-4o-mini"
    assert fact.input_tokens == 7
    assert fact.output_tokens == 4


@pytest.mark.asyncio
async def test_the_cost_survives_as_a_decimal_from_the_json():
    """json.loads hands back a float. Going through str keeps the digits OpenRouter sent
    rather than the nearest binary approximation of them."""
    from litellm.types.proxy.provider_billing import Fetched

    result = await _fetch(["gen-2"], _http({"data": {"id": "gen-2", "total_cost": 0.000001234567}}))

    assert isinstance(result, Fetched)
    assert result.facts[0].billed_cost == Decimal("0.000001234567")


@pytest.mark.asyncio
async def test_a_missing_credential_is_reported_not_raised():
    from litellm.types.proxy.provider_billing import NotConfigured

    assert isinstance(await _fetch(["gen-1"], _http({}), credential_values={}), NotConfigured)


@pytest.mark.asyncio
async def test_a_rate_limit_is_retryable_and_a_revoked_key_is_not():
    """Retrying a 429 next tick is correct. Retrying a 401 forever hides a revoked key
    from the operator who needs to replace it."""
    from litellm.types.proxy.provider_billing import FetchFailed

    limited = await _fetch(["gen-1"], _http({}, status=429))
    revoked = await _fetch(["gen-1"], _http({}, status=401))

    assert isinstance(limited, FetchFailed) and limited.retryable is True
    assert isinstance(revoked, FetchFailed) and revoked.retryable is False


@pytest.mark.asyncio
async def test_one_run_is_capped_so_it_cannot_exhaust_the_rate_limit():
    """This endpoint prices one request per call, against a limit shared with the
    customer's real traffic. An unbounded run against a backlog would spend their limit on
    our polling."""
    from litellm.provider_billing.openrouter import MAX_LOOKUPS_PER_RUN
    from litellm.types.proxy.provider_billing import Fetched

    client = _http({"data": {"id": "gen-x", "total_cost": 0.000001}})
    result = await _fetch([f"gen-{i}" for i in range(MAX_LOOKUPS_PER_RUN + 25)], client)

    assert isinstance(result, Fetched)
    assert client.get.await_count == MAX_LOOKUPS_PER_RUN


@pytest.mark.asyncio
async def test_nothing_to_price_is_a_successful_empty_run():
    from litellm.types.proxy.provider_billing import Fetched

    client = _http({})
    result = await _fetch([], client)

    assert isinstance(result, Fetched)
    assert result.facts == ()
    client.get.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_generation_with_no_cost_yet_is_skipped_rather_than_recorded_as_free():
    """OpenRouter can answer before it has priced a generation. Storing that as zero would
    report a request that cost nothing, which is worse than reporting nothing yet."""
    from litellm.types.proxy.provider_billing import Fetched

    result = await _fetch(["gen-3"], _http({"data": {"id": "gen-3"}}))

    assert isinstance(result, Fetched)
    assert result.facts == ()


@pytest.mark.asyncio
async def test_the_key_is_sent_as_a_bearer_token():
    await _fetch(["gen-1"], client := _http({"data": {"id": "gen-1", "total_cost": 0.1}}))

    assert client.get.await_args.kwargs["headers"]["Authorization"] == "Bearer sk-or-test"
    assert client.get.await_args.kwargs["params"] == {"id": "gen-1"}
