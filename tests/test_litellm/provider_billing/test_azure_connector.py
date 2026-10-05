"""Tests for the Azure Cost Management connector.

Every response fixture here is transcribed from Azure's published Cost Management query
reference, including the shape of a cost (a JSON number, not a string) and the `Currency`
column the reference's own sample responses carry. Nothing in this file has been checked
against a live subscription, because this deployment has no Azure account. A fixture
invented to make a test pass would encode a wire format nobody has seen, so each shape
below traces to the reference rather than to a guess.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from litellm.types.proxy.provider_billing import BillingCredential

NOW = datetime(2026, 9, 18, 12, 0, tzinfo=timezone.utc)
CREDENTIAL = {"subscription_id": "sub-123"}

_COLUMNS = [
    {"name": "Cost", "type": "Number"},
    {"name": "UsageDate", "type": "Number"},
    {"name": "ServiceName", "type": "String"},
    {"name": "Currency", "type": "String"},
]


def _row(cost: object, day: object = 20260917, service: str = "Cognitive Services", currency: str = "USD") -> list:
    return [cost, day, service, currency]


def _response(text: str, status: int) -> MagicMock:
    response = MagicMock()
    response.status_code = status
    response.text = text
    return response


def _http(*payloads: dict, status: int = 200) -> MagicMock:
    client = MagicMock()
    client.post = AsyncMock(side_effect=[_response(json.dumps(payload), status) for payload in payloads])
    return client


def _http_text(*bodies: str) -> MagicMock:
    client = MagicMock()
    client.post = AsyncMock(side_effect=[_response(body, 200) for body in bodies])
    return client


def _body(*rows: list, columns: list | None = None, next_link: str | None = None) -> dict:
    return {
        "properties": {
            "columns": columns if columns is not None else _COLUMNS,
            "rows": [list(row) for row in rows],
            "nextLink": next_link,
        }
    }


def _connector(client: MagicMock, token: str | None = "entra-token"):
    from token_iq.connectors.billing.azure import AzureBillingConnector

    async def token_factory(_name, _values):
        return token

    return AzureBillingConnector(http_client_factory=lambda: client, token_factory=token_factory)


async def _fetch(client: MagicMock, values=None, token: str | None = "entra-token", since=None):
    return await _connector(client, token).fetch(
        since=NOW - timedelta(days=7) if since is None else since,
        until=NOW,
        credential_name="azure-prod",
        credential_values=CREDENTIAL if values is None else values,
    )


def _cost_management_that_honours_the_window(*charges: tuple[datetime, str]) -> MagicMock:
    """A Cost Management that answers for exactly the instants it was asked for.

    Whether the real service truncates `timePeriod` to whole dates is undocumented. A
    connector that reports by day has to be right under either reading, so this fake takes
    the request at its word: ask it from the middle of a day and it answers with the tail
    of that day, filed under the whole day.
    """

    dumps = json.dumps

    async def post(_url, *, json, headers):
        period = json["timePeriod"]
        since = datetime.strptime(period["from"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        until = datetime.strptime(period["to"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        totals: dict[str, Decimal] = {}
        for at, amount in charges:
            if since <= at < until:
                packed = at.strftime("%Y%m%d")
                totals[packed] = totals.get(packed, Decimal("0")) + Decimal(amount)
        rows = [_row(float(total), int(packed)) for packed, total in sorted(totals.items())]
        return _response(dumps(_body(*rows)), 200)

    client = MagicMock()
    client.post = AsyncMock(side_effect=post)
    return client


@pytest.mark.asyncio
async def test_a_row_becomes_a_fact_with_the_exact_cost_azure_reported():
    result = await _fetch(_http(_body(_row(12.345678))))

    fact = result.facts[0]
    assert fact.billed_cost == Decimal("12.345678")
    assert fact.provider == "azure"
    assert fact.grain == "day"
    assert fact.evidence == "reconciled"


@pytest.mark.asyncio
async def test_a_cost_no_float_can_hold_keeps_every_digit_azure_sent():
    """Azure returns a cost as a JSON number, and `json.loads` decodes a JSON number to a
    binary float unless it is told otherwise. The digits are gone by then: no Decimal built
    afterwards can recover what the float never held, and this is money."""
    exact = "1.0000000000000002e-05"
    body = (
        '{"properties": {"columns": '
        + json.dumps(_COLUMNS)
        + ', "rows": [['
        + exact
        + ', 20260917, "Cognitive Services", "USD"]], "nextLink": null}}'
    )

    result = await _fetch(_http_text(body))

    assert result.facts[0].billed_cost == Decimal(exact)


@pytest.mark.asyncio
async def test_the_window_asked_for_starts_at_a_utc_midnight():
    """Cost Management is asked for `Daily` granularity and the fact is keyed to the whole
    day. Asking from the middle of a day risks an answer covering only the tail of it, filed
    under the whole day's name, overwriting the complete total already stored for it."""
    client = _http(_body())

    await _fetch(client, since=datetime(2026, 9, 11, 14, 37, 11, tzinfo=timezone.utc))

    period = client.post.await_args.kwargs["json"]["timePeriod"]
    assert period["from"] == "2026-09-11T00:00:00Z"
    assert period["to"] == "2026-09-18T12:00:00Z"


@pytest.mark.asyncio
async def test_the_runners_own_window_still_reports_a_whole_day():
    """Every other test here chooses its own window. The runner does not: it asks for the
    last 24 hours from a live clock, so `since` lands mid-day. Driving the connector the way
    the product actually drives it is the only thing that catches a partial day being
    written over a complete one."""
    from token_iq.connectors.billing.runner import run_ingestion

    now = datetime(2026, 9, 19, 14, 37, 11, tzinfo=timezone.utc)
    client = _cost_management_that_honours_the_window(
        (datetime(2026, 9, 18, 2, 0, tzinfo=timezone.utc), "4"),
        (datetime(2026, 9, 18, 20, 0, tzinfo=timezone.utc), "1"),
    )
    written: list = []
    repository = MagicMock()
    repository.upsert_many = AsyncMock(side_effect=lambda facts: written.extend(facts) or len(facts))
    sync_runs = MagicMock()
    sync_runs.record = AsyncMock()

    async def credentials_for(_provider: str):
        return (BillingCredential(name="azure-prod", values=CREDENTIAL),)

    await run_ingestion(
        repository=repository,
        sync_runs=sync_runs,
        connectors=(_connector(client),),
        credentials_for=credentials_for,
        now=now,
    )

    day = [fact for fact in written if fact.bucket_start.date().isoformat() == "2026-09-18"]
    assert [fact.billed_cost for fact in day] == [Decimal("5")]


@pytest.mark.asyncio
async def test_the_currency_azure_billed_in_is_kept():
    """A euro-billed subscription stored as dollars is compared against dollar gateway
    spend, and the difference reads as a leak that does not exist."""
    result = await _fetch(_http(_body(_row(1.5, currency="EUR"))))

    assert result.facts[0].billing_currency == "EUR"


@pytest.mark.asyncio
async def test_a_response_with_no_currency_column_keeps_the_default():
    """Guessing is worse than the default. A response that names no currency leaves the
    stored default alone rather than inventing one."""
    columns = [column for column in _COLUMNS if column["name"] != "Currency"]
    result = await _fetch(_http(_body([1.5, 20260917, "Cognitive Services"], columns=columns)))

    assert result.facts[0].billing_currency == "USD"


@pytest.mark.asyncio
async def test_the_fact_key_carries_the_account_so_two_subscriptions_cannot_collide():
    """fact_key is the upsert key. Without the credential in it, a second subscription's
    row for a day overwrites the first's and the reported bill silently halves."""

    async def fetch_as(name: str):
        return await _connector(_http(_body(_row(1)))).fetch(
            since=NOW - timedelta(days=7), until=NOW, credential_name=name, credential_values=CREDENTIAL
        )

    prod = await fetch_as("azure-prod")
    staging = await fetch_as("azure-staging")

    assert prod.facts[0].fact_key != staging.facts[0].fact_key
    assert "azure-prod" in prod.facts[0].fact_key


@pytest.mark.asyncio
async def test_each_fact_keeps_the_row_azure_sent():
    """Raw Data renders the provider's own line. A payload dropped at parse time can never
    be shown, and Azure will not serve that day again. The cost keeps its own digits as
    text, since an exact amount has no JSON encoder and would fail the write for the whole
    fact."""
    result = await _fetch(_http(_body(_row(1.5))))

    assert result.facts[0].raw == {
        "Cost": "1.5",
        "UsageDate": 20260917,
        "ServiceName": "Cognitive Services",
        "Currency": "USD",
    }


@pytest.mark.asyncio
async def test_a_row_shorter_than_its_columns_is_dropped_rather_than_guessed():
    """Azure rows are positional and their meaning comes from a separate columns array. A
    truncated row means the response is not the shape we believe, and filling the gap would
    put a wrong number into a billing table."""
    result = await _fetch(_http(_body([1.5, 20260917])))

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
    result = await _fetch(_http(_body(["Cognitive Services", 9.99, 20260917], columns=reordered)))

    assert result.facts[0].billed_cost == Decimal("9.99")


@pytest.mark.asyncio
async def test_paging_follows_next_link_until_it_is_absent():
    client = _http(
        _body(_row(1), next_link="https://management.azure.com/next"),
        _body(_row(2, day=20260916)),
    )

    result = await _fetch(client)

    assert len(result.facts) == 2
    assert client.post.await_count == 2


def _http_pages(*statuses: int) -> MagicMock:
    """A first page that answers one charge and links to a second page that fails."""
    client = MagicMock()
    client.post = AsyncMock(
        side_effect=[
            _response(json.dumps(_body(_row(1), next_link="https://management.azure.com/next")), 200),
            *(_response("", status) for status in statuses),
        ]
    )
    return client


@pytest.mark.asyncio
async def test_a_page_that_fails_transiently_keeps_what_the_earlier_pages_returned():
    """Day-keyed facts are upserted and the window is a rolling 24 hours, so a short page is
    corrected on the next tick. A discarded page is simply lost."""
    result = await _fetch(_http_pages(500))

    assert [fact.billed_cost for fact in result.facts] == [Decimal("1")]


@pytest.mark.asyncio
async def test_a_rate_limited_later_page_still_keeps_what_the_earlier_pages_returned():
    """A 429 is the subscription asking us to come back, not a broken connection. The next
    tick re-reads the same rolling window, so page one's facts are worth keeping."""
    from litellm.types.proxy.provider_billing import Fetched

    result = await _fetch(_http_pages(429))

    assert isinstance(result, Fetched)
    assert [fact.billed_cost for fact in result.facts] == [Decimal("1")]


@pytest.mark.asyncio
async def test_a_credential_refused_part_way_through_paging_is_a_failure_not_a_healthy_sync():
    """A 401 or 403 on page two means the credential is rejected, and nothing about the run
    will improve until a human fixes it. Returning the pages already in hand would record a
    successful sync and show the customer a healthy Azure connection over a dead credential.
    Losing page one costs nothing: the facts are keyed by day, upserted, and re-read on a
    rolling window, so the next run that works restores them."""
    from litellm.types.proxy.provider_billing import FetchFailed

    result = await _fetch(_http_pages(401))

    assert isinstance(result, FetchFailed)
    assert result.retryable is False


@pytest.mark.asyncio
async def test_a_first_page_that_fails_is_still_a_failure_not_an_empty_success():
    """Nothing was collected, so reporting a successful fetch of nothing would file a
    confident zero against a subscription that never answered."""
    from litellm.types.proxy.provider_billing import FetchFailed

    result = await _fetch(_http({}, status=500))

    assert isinstance(result, FetchFailed)


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
    result = await _fetch(_http(_body(_row(1.5, day="not-a-date"))))

    assert result.facts == ()


@pytest.mark.asyncio
async def test_it_calls_the_host_azure_documents():
    client = _http(_body())

    await _fetch(client)

    assert client.post.call_args.args[0].startswith(
        "https://management.azure.com/subscriptions/sub-123/providers/Microsoft.CostManagement/query"
    )


@pytest.mark.asyncio
async def test_a_sovereign_cloud_can_point_the_connector_at_its_own_host():
    """Azure Government and Azure China serve Cost Management from different hosts entirely,
    so a hardcoded commercial host means those customers cannot connect at all."""
    from token_iq.connectors.billing.azure import AzureBillingConnector

    client = _http(_body())

    async def token_factory(_name, _values):
        return "entra-token"

    await AzureBillingConnector(
        http_client_factory=lambda: client,
        token_factory=token_factory,
        base_url="https://management.usgovcloudapi.net",
    ).fetch(since=NOW - timedelta(days=7), until=NOW, credential_name="azure-prod", credential_values=CREDENTIAL)

    assert client.post.call_args.args[0].startswith(
        "https://management.usgovcloudapi.net/subscriptions/sub-123/providers/Microsoft.CostManagement/query"
    )
