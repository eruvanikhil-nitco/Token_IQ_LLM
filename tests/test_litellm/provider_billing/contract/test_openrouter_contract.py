"""Does our OpenRouter connector speak the API OpenRouter documents?

The response payload below is the example response printed on OpenRouter's own reference page
for the generation metadata endpoint, copied rather than written:
https://openrouter.ai/docs/api-reference/get-a-generation

OpenRouter is the one provider here that has met a real account, so this file is less about
discovering a surprise and more about keeping the one connector that works from drifting.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Final

import pytest

from tests.test_litellm.provider_billing.contract.conftest import Reply, Vendor

SINCE: Final = datetime(2026, 9, 1, tzinfo=timezone.utc)
UNTIL: Final = datetime(2026, 9, 2, tzinfo=timezone.utc)
CREDENTIAL: Final = {"api_key": "sk-or-not-a-real-key"}

DOCUMENTED_GENERATION: Final = {
    "data": {
        "id": "gen-3bhGkxlo4XFrqiabUM7NDtwDzWwG",
        "upstream_id": "chatcmpl-791bcf62-080e-4568-87d0-94c72e3b4946",
        "total_cost": 0.0015,
        "cache_discount": None,
        "upstream_inference_cost": 0.0012,
        "created_at": "2024-07-15T23:33:19.433273+00:00",
        "model": "sao10k/l3-stheno-8b",
        "streamed": True,
        "cancelled": False,
        "provider_name": "Infermatic",
        "latency": 1250,
        "generation_time": 1200,
        "finish_reason": "stop",
        "tokens_prompt": 10,
        "tokens_completion": 25,
        "native_tokens_prompt": 10,
        "native_tokens_completion": 25,
        "native_tokens_reasoning": 5,
        "native_tokens_cached": 3,
        "usage": 0.0015,
        "is_byok": False,
        "native_finish_reason": "stop",
    }
}


async def _fetch(vendor: Vendor, *ids: str):
    from token_iq.connectors.billing.openrouter import OpenRouterBillingConnector

    async def unpriced() -> tuple[str, ...]:
        return ids

    return await OpenRouterBillingConnector(
        unpriced_request_ids=unpriced,
        http_client_factory=vendor.client_factory(),
        base_url="https://openrouter.test",
    ).fetch(since=SINCE, until=UNTIL, credential_name="acme-openrouter", credential_values=CREDENTIAL)


@pytest.mark.asyncio
async def test_it_asks_for_the_path_and_method_openrouter_documents(vendor):
    stand_in: Final = vendor(Reply(json=DOCUMENTED_GENERATION))

    await _fetch(stand_in, "gen-1")

    assert stand_in.last.method == "GET"
    assert stand_in.last.path == "/api/v1/generation"


@pytest.mark.asyncio
async def test_it_names_the_generation_in_the_parameter_openrouter_documents(vendor):
    stand_in: Final = vendor(Reply(json=DOCUMENTED_GENERATION))

    await _fetch(stand_in, "gen-1")

    assert stand_in.last.params == {"id": "gen-1"}


@pytest.mark.asyncio
async def test_it_authenticates_the_way_openrouter_documents(vendor):
    stand_in: Final = vendor(Reply(json=DOCUMENTED_GENERATION))

    await _fetch(stand_in, "gen-1")

    assert stand_in.last.headers["authorization"] == "Bearer sk-or-not-a-real-key"


@pytest.mark.asyncio
async def test_it_reads_the_cost_out_of_openrouters_own_example(vendor):
    from litellm.types.proxy.provider_billing import Fetched

    stand_in: Final = vendor(Reply(json=DOCUMENTED_GENERATION))

    result: Final = await _fetch(stand_in, "gen-1")

    assert isinstance(result, Fetched)
    assert result.facts[0].billed_cost == Decimal("0.0015")
    assert result.facts[0].evidence == "reconciled"
    assert result.facts[0].model == "sao10k/l3-stheno-8b"


@pytest.mark.asyncio
async def test_a_cost_with_more_digits_than_a_float_can_hold_survives(vendor):
    from litellm.types.proxy.provider_billing import Fetched

    stand_in: Final = vendor(Reply(text='{"data":{"id":"gen-1","total_cost":0.10000000000000000555}}'))

    result: Final = await _fetch(stand_in, "gen-1")

    assert isinstance(result, Fetched)
    assert result.facts[0].billed_cost == Decimal("0.10000000000000000555")


@pytest.mark.asyncio
async def test_it_prices_every_generation_it_was_given(vendor):
    """One request per generation is how this endpoint works. Stopping after the first would
    leave the rest unpriced forever, because the run records them as already looked at."""
    from litellm.types.proxy.provider_billing import Fetched

    stand_in: Final = vendor(Reply(json=DOCUMENTED_GENERATION))

    result: Final = await _fetch(stand_in, "gen-1", "gen-2", "gen-3")

    assert isinstance(result, Fetched)
    assert [request.params["id"] for request in stand_in.requests] == ["gen-1", "gen-2", "gen-3"]


@pytest.mark.parametrize(
    ("status", "retryable"),
    [(401, False), (403, False), (429, True), (500, True), (503, True)],
)
@pytest.mark.asyncio
async def test_it_turns_an_error_into_a_reason_rather_than_raising(vendor, status: int, retryable: bool):
    from litellm.types.proxy.provider_billing import FetchFailed

    stand_in: Final = vendor(Reply(json={"error": "nope"}, status=status))

    result: Final = await _fetch(stand_in, "gen-1")

    assert isinstance(result, FetchFailed)
    assert result.retryable is retryable
    assert result.reason


@pytest.mark.asyncio
async def test_a_body_that_is_not_json_leaves_the_generation_unpriced_rather_than_crashing(vendor):
    """Unpriced is the right answer here rather than a failure: the generation stays in the
    queue and is tried again, which is exactly what should happen to one bad response."""
    from litellm.types.proxy.provider_billing import Fetched

    stand_in: Final = vendor(Reply(text="<html>maintenance</html>"))

    result: Final = await _fetch(stand_in, "gen-1")

    assert isinstance(result, Fetched)
    assert result.facts == ()
