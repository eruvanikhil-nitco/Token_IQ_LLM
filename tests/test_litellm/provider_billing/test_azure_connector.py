"""Tests for the Azure Cost Management connector.

Every response fixture here is transcribed from Azure's published Cost Management query
reference. Nothing in this file has been checked against a live subscription, because this
deployment has no Azure account. A fixture invented to make a test pass would encode a wire
format nobody has seen, so each shape below traces to the reference rather than to a guess.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

NOW = datetime(2026, 9, 18, 12, 0, tzinfo=timezone.utc)
CREDENTIAL = {"subscription_id": "sub-123"}

_COLUMNS = [
    {"name": "Cost", "type": "Number"},
    {"name": "UsageDate", "type": "Number"},
    {"name": "ServiceName", "type": "String"},
]


def _http(*payloads: dict, status: int = 200) -> MagicMock:
    responses = []
    for payload in payloads:
        response = MagicMock()
        response.status_code = status
        response.json = MagicMock(return_value=payload)
        responses.append(response)
    client = MagicMock()
    client.post = AsyncMock(side_effect=responses)
    return client


def _body(*rows: list, columns: list | None = None, next_link: str | None = None) -> dict:
    return {
        "properties": {
            "columns": columns if columns is not None else _COLUMNS,
            "rows": [list(row) for row in rows],
            "nextLink": next_link,
        }
    }


async def _fetch(client: MagicMock, values=None, token: str | None = "aad-token"):
    from litellm.provider_billing.azure import AzureBillingConnector

    async def token_factory(_name, _values):
        return token

    return await AzureBillingConnector(
        http_client_factory=lambda: client, token_factory=token_factory
    ).fetch(
        since=NOW - timedelta(days=7),
        until=NOW,
        credential_name="azure-prod",
        credential_values=CREDENTIAL if values is None else values,
    )


@pytest.mark.asyncio
async def test_a_row_becomes_a_fact_with_the_exact_cost_azure_reported():
    result = await _fetch(_http(_body(["12.345678", "20260917", "Cognitive Services"])))

    fact = result.facts[0]
    assert fact.billed_cost == Decimal("12.345678")
    assert fact.provider == "azure"
    assert fact.grain == "day"
    assert fact.evidence == "reconciled"


@pytest.mark.asyncio
async def test_the_fact_key_carries_the_account_so_two_subscriptions_cannot_collide():
    """fact_key is the upsert key. Without the credential in it, a second subscription's
    row for a day overwrites the first's and the reported bill silently halves."""
    from litellm.provider_billing.azure import AzureBillingConnector

    async def token_factory(_name, _values):
        return "aad-token"

    async def fetch_as(name: str):
        return await AzureBillingConnector(
            http_client_factory=lambda: _http(_body(["1", "20260917", "Cognitive Services"])),
            token_factory=token_factory,
        ).fetch(since=NOW - timedelta(days=7), until=NOW, credential_name=name, credential_values=CREDENTIAL)

    prod = await fetch_as("azure-prod")
    staging = await fetch_as("azure-staging")

    assert prod.facts[0].fact_key != staging.facts[0].fact_key
    assert "azure-prod" in prod.facts[0].fact_key


@pytest.mark.asyncio
async def test_each_fact_keeps_the_row_azure_sent():
    """Raw Data renders the provider's own line. A payload dropped at parse time can never
    be shown, and Azure will not serve that day again."""
    result = await _fetch(_http(_body(["1.5", "20260917", "Cognitive Services"])))

    assert result.facts[0].raw == {
        "Cost": "1.5",
        "UsageDate": "20260917",
        "ServiceName": "Cognitive Services",
    }


@pytest.mark.asyncio
async def test_a_row_shorter_than_its_columns_is_dropped_rather_than_guessed():
    """Azure rows are positional and their meaning comes from a separate columns array. A
    truncated row means the response is not the shape we believe, and filling the gap would
    put a wrong number into a billing table."""
    result = await _fetch(_http(_body(["1.5", "20260917"])))

    assert result.facts == ()


@pytest.mark.asyncio
async def test_columns_in_a_different_order_still_read_correctly():
    """Reading by position works until Azure reorders its columns, at which point the wrong
    number is reported rather than an error raised."""
    reordered = [
        {"name": "ServiceName", "type": "String"},
        {"name": "Cost", "type": "Number"},
        {"name": "UsageDate", "type": "Number"},
    ]
    result = await _fetch(_http(_body(["Cognitive Services", "9.99", "20260917"], columns=reordered)))

    assert result.facts[0].billed_cost == Decimal("9.99")


@pytest.mark.asyncio
async def test_paging_follows_next_link_until_it_is_absent():
    client = _http(
        _body(["1", "20260917", "Cognitive Services"], next_link="https://management.azure.com/next"),
        _body(["2", "20260916", "Cognitive Services"]),
    )

    result = await _fetch(client)

    assert len(result.facts) == 2
    assert client.post.await_count == 2


@pytest.mark.asyncio
async def test_a_credential_with_no_subscription_is_not_configured_rather_than_failed():
    """Most customers configure one or two providers. Treating an unconfigured one as a
    failure would make a healthy run look broken on every tick."""
    from litellm.types.proxy.provider_billing import NotConfigured

    result = await _fetch(_http(_body()), values={})

    assert isinstance(result, NotConfigured)


@pytest.mark.asyncio
async def test_no_token_is_not_configured_rather_than_failed():
    from litellm.types.proxy.provider_billing import NotConfigured

    result = await _fetch(_http(_body()), token=None)

    assert isinstance(result, NotConfigured)


@pytest.mark.asyncio
async def test_a_refused_token_is_a_permanent_failure_not_a_retryable_one():
    """A 403 means the identity lacks Cost Management reader on that subscription. Retrying
    that every five minutes spends the customer's rate limit on a request that cannot start
    working until a human grants the role."""
    from litellm.types.proxy.provider_billing import FetchFailed

    result = await _fetch(_http({}, status=403))

    assert isinstance(result, FetchFailed)
    assert result.retryable is False


@pytest.mark.asyncio
async def test_a_rate_limit_is_retryable():
    from litellm.types.proxy.provider_billing import FetchFailed

    result = await _fetch(_http({}, status=429))

    assert isinstance(result, FetchFailed)
    assert result.retryable is True


@pytest.mark.asyncio
async def test_an_unparseable_day_is_dropped_rather_than_filed_under_today():
    """Filing an unparseable charge under today would corrupt the comparison silently."""
    result = await _fetch(_http(_body(["1.5", "not-a-date", "Cognitive Services"])))

    assert result.facts == ()
