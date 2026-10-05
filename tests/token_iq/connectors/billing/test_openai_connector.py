from __future__ import annotations

import json

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

NOW = datetime(2026, 9, 13, 12, 0, tzinfo=timezone.utc)
CREDENTIAL = {"api_key": "sk-admin-test"}
DAY_START = int(datetime(2026, 9, 12, tzinfo=timezone.utc).timestamp())


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
    from token_iq.connectors.billing.openai import OpenAIBillingConnector

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
    from token_iq.types.provider_billing import Fetched

    result = await _fetch(_http(_page(_bucket(_result(0.06)))))

    assert isinstance(result, Fetched)
    assert result.facts[0].billed_cost == Decimal("0.06")


@pytest.mark.asyncio
async def test_a_float_amount_keeps_its_digits():
    """json hands back a float. Decimal(float) carries the binary approximation of it;
    going through str does not."""
    from token_iq.types.provider_billing import Fetched

    result = await _fetch(_http(_page(_bucket(_result(0.1)))))

    assert isinstance(result, Fetched)
    assert result.facts[0].billed_cost == Decimal("0.1")


@pytest.mark.asyncio
async def test_the_unix_bucket_becomes_the_day_the_cost_belongs_to():
    from token_iq.types.provider_billing import Fetched

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
    from token_iq.types.provider_billing import Fetched

    result = await _fetch(
        _http(_page(_bucket(_result(0.06, "gpt-4o-mini, input"), _result(0.02, "gpt-4o-mini, output"))))
    )

    assert isinstance(result, Fetched)
    # Still two facts, now one model with two meters rather than two models.
    assert {(fact.model, fact.meter) for fact in result.facts} == {
        ("gpt-4o-mini", "input"),
        ("gpt-4o-mini", "output"),
    }


@pytest.mark.asyncio
async def test_the_fact_key_is_stable_so_a_refetch_overwrites():
    from token_iq.types.provider_billing import Fetched

    first = await _fetch(_http(_page(_bucket(_result(1.0)))))
    second = await _fetch(_http(_page(_bucket(_result(1.0)))))

    assert isinstance(first, Fetched) and isinstance(second, Fetched)
    assert first.facts[0].fact_key == second.facts[0].fact_key


@pytest.mark.asyncio
async def test_every_page_is_followed():
    from token_iq.types.provider_billing import Fetched

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
    from token_iq.types.provider_billing import Fetched

    result = await _fetch(_http(_page(_bucket(_result(3.0, line_item=None)))))

    assert isinstance(result, Fetched)
    assert result.facts[0].billed_cost == Decimal("3.0")
    assert result.facts[0].fact_key == "openai:acme-openai:2026-09-12:unattributed"


@pytest.mark.asyncio
async def test_a_missing_credential_is_reported_not_raised():
    from token_iq.types.provider_billing import NotConfigured

    assert isinstance(await _fetch(_http({}), credential_values={}), NotConfigured)


@pytest.mark.asyncio
async def test_a_rate_limit_is_retryable_and_a_bad_key_is_not():
    from token_iq.types.provider_billing import FetchFailed

    limited = await _fetch(_http({}, status=429))
    refused = await _fetch(_http({}, status=401))

    assert isinstance(limited, FetchFailed) and limited.retryable is True
    assert isinstance(refused, FetchFailed) and refused.retryable is False


def test_each_fact_keeps_the_result_openai_sent():
    from token_iq.connectors.billing.openai import _facts_from

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


def test_two_openai_accounts_do_not_share_a_fact_key():
    """fact_key is the upsert key. Without the credential in it, the second account's row for
    a day overwrites the first account's row for that day and the total silently halves."""
    from token_iq.connectors.billing.openai import _facts_from

    bucket = [
        {
            "start_time": 1789344000,
            "results": [{"line_item": "gpt-4o", "amount": {"value": 1.25, "currency": "usd"}}],
        }
    ]

    prod = _facts_from(bucket, "prod")
    staging = _facts_from(bucket, "staging")

    assert prod[0].fact_key != staging[0].fact_key


@pytest.mark.asyncio
async def test_it_calls_the_host_openai_documents():
    client = _http(_page())

    await _fetch(client)

    assert client.get.call_args.args[0] == "https://api.openai.com/v1/organization/costs"


@pytest.mark.asyncio
async def test_a_deployment_can_point_the_connector_at_its_own_host():
    """A customer behind a gateway or proxy, or a test standing in for OpenAI, needs
    somewhere to put their host rather than forking the file."""
    from token_iq.connectors.billing.openai import OpenAIBillingConnector

    client = _http(_page())

    await OpenAIBillingConnector(http_client_factory=lambda: client, base_url="https://openai.internal.example").fetch(
        since=NOW - timedelta(days=2), until=NOW, credential_name="acme", credential_values=CREDENTIAL
    )

    assert client.get.call_args.args[0] == "https://openai.internal.example/v1/organization/costs"


class TestLineItemSplitsIntoModelAndMeter:
    """OpenAI bills per line item, and the whole string used to land in `model`.

    So the model list read "gpt-4.1-2026-04-14, input", "gpt-4.1-2026-04-14, output" and
    "web search tool calls" as three different models, and nothing could total a model's cost
    across its meters. The money was always right; the label was not.
    """

    @pytest.mark.parametrize(
        ("line_item", "model", "meter"),
        [
            ("gpt-4.1-2026-04-14, input", "gpt-4.1-2026-04-14", "input"),
            ("gpt-4.1-2026-04-14, output", "gpt-4.1-2026-04-14", "output"),
            ("o3-mini, cached input", "o3-mini", "cached input"),
            # A meter against no model. Putting this in `model` is what made the list unreadable.
            ("web search tool calls", None, "web search tool calls"),
            ("code interpreter sessions", None, "code interpreter sessions"),
            # A bare model with no meter part: the model is known, the meter is not stated.
            ("gpt-4o", "gpt-4o", None),
            ("text-embedding-3-small", "text-embedding-3-small", None),
        ],
    )
    def test_the_split(self, line_item: str, model: str | None, meter: str | None) -> None:
        from token_iq.connectors.billing.openai import split_line_item

        assert split_line_item(line_item) == (model, meter)

    def test_a_line_item_openai_did_not_send_is_neither(self) -> None:
        """`line_item` absent is already handled as unattributed; this is the split's own view."""
        from token_iq.connectors.billing.openai import split_line_item

        assert split_line_item("") == (None, None)


class TestTheFactCarriesBothHalves:
    @staticmethod
    def _one(line_item: str):
        from token_iq.connectors.billing.openai import _facts_from

        return _facts_from(
            [
                {
                    "start_time": 1789344000,
                    "results": [{"line_item": line_item, "amount": {"value": 2.50, "currency": "usd"}}],
                }
            ],
            "acct",
        )[0]

    def test_a_metered_model_records_both(self) -> None:
        fact = self._one("gpt-4.1-2026-04-14, input")
        assert (fact.model, fact.meter) == ("gpt-4.1-2026-04-14", "input")

    def test_a_tool_call_records_a_meter_against_no_model(self) -> None:
        fact = self._one("web search tool calls")
        assert (fact.model, fact.meter) == (None, "web search tool calls")

    def test_the_fact_key_still_uses_the_raw_line_item(self) -> None:
        """This is the hinge of the whole change.

        The connector is idempotent on `fact_key`, so re-running a sync is what fills `meter` on
        rows stored before the split, without a data migration that a Prisma migration may not do
        anyway. That only works while the key keeps the unsplit line item: change it and
        re-ingestion inserts beside the old rows instead of replacing them, and the period's cost
        doubles while every individual row looks correct.
        """
        assert self._one("gpt-4.1-2026-04-14, input").fact_key == (
            "openai:acct:2026-09-14:gpt-4.1-2026-04-14, input"
        )

    def test_the_money_is_untouched_by_the_split(self) -> None:
        for line_item in ("gpt-4.1-2026-04-14, input", "web search tool calls", "gpt-4o"):
            assert self._one(line_item).billed_cost == Decimal("2.50"), line_item
