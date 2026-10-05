"""Does our OpenAI connector speak the API OpenAI documents?

The request contract and response shape below are taken from OpenAI's Costs API reference and
their own cookbook walkthrough of it: a page of buckets, each bucket holding results whose
amount is an object of value and currency, `start_time` and `end_time` as Unix seconds, and an
admin key sent as a bearer token.
https://developers.openai.com/cookbook/examples/completions_usage_api

Copied rather than written. A payload reverse-engineered from our own parser would prove only
that the parser agrees with itself.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Final

import pytest

from tests.token_iq.connectors.billing.contract.conftest import Reply, Vendor

SINCE: Final = datetime(2026, 9, 1, tzinfo=timezone.utc)
UNTIL: Final = datetime(2026, 9, 3, tzinfo=timezone.utc)
CREDENTIAL: Final = {"api_key": "sk-admin-not-a-real-key"}

DAY_START: Final = int(datetime(2026, 9, 1, tzinfo=timezone.utc).timestamp())


def _bucket(*results: dict[str, object], start: int = DAY_START) -> dict[str, object]:
    return {"object": "bucket", "start_time": start, "end_time": start + 86400, "results": list(results)}


def _result(value: object, line_item: str = "gpt-4o-mini, input") -> dict[str, object]:
    return {
        "object": "organization.costs.result",
        "amount": {"value": value, "currency": "usd"},
        "line_item": line_item,
        "project_id": "proj_abc",
    }


def _page(*buckets: dict[str, object], has_more: bool = False, next_page: str | None = None) -> dict[str, object]:
    return {"object": "page", "data": list(buckets), "has_more": has_more, "next_page": next_page}


async def _fetch(vendor: Vendor):
    from token_iq.connectors.billing.openai import OpenAIBillingConnector

    return await OpenAIBillingConnector(
        http_client_factory=vendor.client_factory(), base_url="https://api.openai.test"
    ).fetch(since=SINCE, until=UNTIL, credential_name="acme-openai", credential_values=CREDENTIAL)


@pytest.mark.asyncio
async def test_it_asks_for_the_path_and_method_openai_documents(vendor):
    stand_in: Final = vendor(Reply(json=_page(_bucket(_result(0.06)))))

    await _fetch(stand_in)

    assert stand_in.last.method == "GET"
    assert stand_in.last.path == "/v1/organization/costs"


@pytest.mark.asyncio
async def test_it_authenticates_the_way_openai_documents(vendor):
    """OpenAI takes an admin key as a bearer token. Anthropic takes a key header instead, and
    swapping the two schemes between connectors is invisible to a mocked client."""
    stand_in: Final = vendor(Reply(json=_page()))

    await _fetch(stand_in)

    assert stand_in.last.headers["authorization"] == "Bearer sk-admin-not-a-real-key"


@pytest.mark.asyncio
async def test_it_sends_the_window_as_unix_seconds_the_way_openai_documents(vendor):
    """OpenAI takes Unix seconds here while Anthropic takes RFC 3339 strings. Sending the wrong
    one is a 400 on the first real call and passes every mocked test."""
    stand_in: Final = vendor(Reply(json=_page()))

    await _fetch(stand_in)

    assert stand_in.last.params["start_time"] == str(int(SINCE.timestamp()))
    assert stand_in.last.params["end_time"] == str(int(UNTIL.timestamp()))
    assert stand_in.last.params["bucket_width"] == "1d"
    assert stand_in.last.params["group_by[]"] == "line_item"


@pytest.mark.asyncio
async def test_it_stays_inside_the_page_size_openai_allows(vendor):
    stand_in: Final = vendor(Reply(json=_page()))

    await _fetch(stand_in)

    assert 1 <= int(stand_in.last.params["limit"]) <= 180


@pytest.mark.asyncio
async def test_the_amount_openai_reports_is_already_dollars(vendor):
    """OpenAI reports dollars where Anthropic reports cents. Scaling this by a hundred, as the
    Anthropic connector correctly does, would overstate a customer's bill a hundredfold."""
    from token_iq.types.provider_billing import Fetched

    stand_in: Final = vendor(Reply(json=_page(_bucket(_result(0.06)))))

    result: Final = await _fetch(stand_in)

    assert isinstance(result, Fetched)
    assert result.facts[0].billed_cost == Decimal("0.06")


@pytest.mark.asyncio
async def test_a_cost_with_more_digits_than_a_float_can_hold_survives(vendor):
    """OpenAI sends the amount as a JSON number, so this is the connector where a decoder that
    goes through a binary float actually corrupts a customer's figure."""
    from token_iq.types.provider_billing import Fetched

    stand_in: Final = vendor(
        Reply(
            text='{"object":"page","data":[{"object":"bucket","start_time":%d,'
            '"end_time":%d,"results":[{"object":"organization.costs.result",'
            '"amount":{"value":0.10000000000000000555,"currency":"usd"},'
            '"line_item":"gpt-4o-mini, input","project_id":"proj_abc"}]}],'
            '"has_more":false,"next_page":null}' % (DAY_START, DAY_START + 86400)
        )
    )

    result: Final = await _fetch(stand_in)

    assert isinstance(result, Fetched)
    assert result.facts[0].billed_cost == Decimal("0.10000000000000000555")


@pytest.mark.asyncio
async def test_it_follows_the_cursor_to_the_end(vendor):
    from token_iq.types.provider_billing import Fetched

    stand_in: Final = vendor(
        Reply(json=_page(_bucket(_result(0.06)), has_more=True, next_page="page_2")),
        Reply(json=_page(_bucket(_result(0.07), start=DAY_START + 86400))),
    )

    result: Final = await _fetch(stand_in)

    assert isinstance(result, Fetched)
    assert len(stand_in.requests) == 2
    assert stand_in.requests[1].params["page"] == "page_2"
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

    stand_in: Final = vendor(Reply(text="<html>bad gateway</html>"))

    assert isinstance(await _fetch(stand_in), FetchFailed)


@pytest.mark.asyncio
async def test_a_body_of_the_wrong_shape_is_a_failure_not_a_crash(vendor):
    from token_iq.types.provider_billing import FetchFailed

    stand_in: Final = vendor(Reply(json=["not", "an", "object"]))

    assert isinstance(await _fetch(stand_in), FetchFailed)
