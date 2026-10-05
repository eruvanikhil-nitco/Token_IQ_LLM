"""Tests for the Vertex AI BigQuery billing export connector.

Every response fixture here is transcribed from the published BigQuery REST API reference
(the `jobs.query` and `jobs.getQueryResults` resources, whose rows arrive as `rows[].f[].v`
matched against `schema.fields`) and from the documented Cloud Billing detailed export
schema (`service.description`, `usage_start_time`, `cost`, `currency`, and the repeated
`credits` field). Nothing in this file has been checked against a live Google Cloud project,
because this deployment has no Google Cloud account. A fixture invented to make a test pass
would encode a wire format nobody has seen, so each shape below traces to a published
reference rather than to a guess.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from token_iq.types.provider_billing import BillingCredential

NOW = datetime(2026, 9, 18, 12, 0, tzinfo=timezone.utc)
CREDENTIAL = {
    "billing_project_id": "billing-proj",
    "billing_export_table": "my-billing-project.export_ds.gcp_billing",
}
"""The hyphenated project segment here is deliberate: it is the ordinary, common-case shape
of a real GCP project id, and every test that fetches through this credential doubles as a
regression against rejecting it."""

_FIELDS = [
    {"name": "usage_day", "type": "DATE"},
    {"name": "service_description", "type": "STRING"},
    {"name": "currency", "type": "STRING"},
    {"name": "gross_cost", "type": "NUMERIC"},
    {"name": "credit_cost", "type": "NUMERIC"},
    {"name": "net_cost", "type": "NUMERIC"},
]


def _row(*values: str) -> dict:
    return {"f": [{"v": value} for value in values]}


def _cost_row(
    day: str = "2026-09-17",
    service: str = "Vertex AI",
    net: str = "1",
    *,
    currency: str = "USD",
    gross: str | None = None,
    credits: str = "0",
) -> dict:
    return _row(day, service, currency, net if gross is None else gross, credits, net)


def _response(payload: dict, status: int = 200) -> MagicMock:
    response = MagicMock()
    response.status_code = status
    response.text = json.dumps(payload)
    return response


def _body(
    *rows: dict,
    fields: list | None = None,
    job_id: str = "job-1",
    page_token: str | None = None,
    job_complete: bool = True,
) -> dict:
    return {
        "schema": {"fields": fields if fields is not None else _FIELDS},
        "rows": list(rows),
        "jobReference": {"projectId": "billing-proj", "jobId": job_id, "location": "US"},
        "pageToken": page_token,
        "jobComplete": job_complete,
    }


def _http_single_page(payload: dict, status: int = 200) -> MagicMock:
    client = MagicMock()
    client.post = AsyncMock(return_value=_response(payload, status=status))
    client.get = AsyncMock()
    return client


def _bigquery_that_honours_the_window(*charges: tuple[datetime, str]) -> MagicMock:
    """A BigQuery that applies the connector's own `usage_start_time >= @since` filter.

    The export holds one row per usage interval, and the query groups those into days. Ask
    it from the middle of a day and it answers with the tail of that day, filed under the
    whole day, which is exactly what the real query would do.
    """
    dumps = json.dumps

    async def post(_url, *, json, headers):
        params = {param["name"]: param["parameterValue"]["value"] for param in json["queryParameters"]}
        since = datetime.strptime(params["since"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        until = datetime.strptime(params["until"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        totals: dict[str, Decimal] = {}
        for at, amount in charges:
            if since <= at < until:
                day = at.date().isoformat()
                totals[day] = totals.get(day, Decimal("0")) + Decimal(amount)
        rows = [_cost_row(day, net=str(total)) for day, total in sorted(totals.items())]
        response = MagicMock()
        response.status_code = 200
        response.text = dumps(_body(*rows))
        return response

    client = MagicMock()
    client.post = AsyncMock(side_effect=post)
    client.get = AsyncMock()
    return client


def _bigquery_that_groups_the_way_the_query_asks(*charges: tuple[str, str, str]) -> MagicMock:
    """A BigQuery holding (day, currency, amount) rows that aggregates on exactly the keys
    the connector's own SQL groups by.

    A query that leaves currency out of its GROUP BY gets one row per day back: an amount
    summed across every currency in the table and a label that is whichever currency the
    engine happened to reach first. That is what the real engine answers, and it is the
    whole reason the grouping matters.
    """
    dumps = json.dumps

    async def post(_url, *, json, headers):
        grouped_by_currency = "currency" in json["query"].split("GROUP BY ")[1]
        totals: dict[tuple[str, str], Decimal] = {}
        labels: dict[tuple[str, str], str] = {}
        for day, currency, amount in charges:
            bucket = (day, currency) if grouped_by_currency else (day, "")
            totals[bucket] = totals.get(bucket, Decimal("0")) + Decimal(amount)
            labels.setdefault(bucket, currency)
        rows = [_cost_row(bucket[0], net=str(total), currency=labels[bucket]) for bucket, total in totals.items()]
        response = MagicMock()
        response.status_code = 200
        response.text = dumps(_body(*rows))
        return response

    client = MagicMock()
    client.post = AsyncMock(side_effect=post)
    client.get = AsyncMock()
    return client


def _connector(client: MagicMock, token: str | None = "google-token"):
    from token_iq.connectors.billing.vertex import VertexBillingConnector

    async def token_factory(_name, _values):
        return token

    return VertexBillingConnector(http_client_factory=lambda: client, token_factory=token_factory)


async def _fetch(client: MagicMock, values=None, token: str | None = "google-token", since=None):
    return await _connector(client, token).fetch(
        since=NOW - timedelta(days=7) if since is None else since,
        until=NOW,
        credential_name="vertex-prod",
        credential_values=CREDENTIAL if values is None else values,
    )


@pytest.mark.asyncio
async def test_a_row_becomes_a_fact_with_the_exact_cost_google_reported():
    client = _http_single_page(_body(_cost_row(net="0.00780515")))

    result = await _fetch(client)

    fact = result.facts[0]
    assert fact.billed_cost == Decimal("0.00780515")
    assert fact.provider == "vertex_ai"
    assert fact.grain == "day"
    assert fact.evidence == "reconciled"


@pytest.mark.asyncio
async def test_a_mid_day_window_still_sums_the_whole_day():
    """The fact is keyed to a whole day and written by upsert, so a run that asks from the
    middle of a day replaces that day's complete total with the slice it happened to see.
    A settled day would converge on a few minutes of spend while every sync reported
    healthy."""
    client = _bigquery_that_honours_the_window(
        (datetime(2026, 9, 17, 3, 0, tzinfo=timezone.utc), "4"),
        (datetime(2026, 9, 17, 21, 0, tzinfo=timezone.utc), "1"),
    )

    result = await _fetch(client, since=datetime(2026, 9, 17, 14, 37, 11, tzinfo=timezone.utc))

    assert [fact.billed_cost for fact in result.facts] == [Decimal("5")]


@pytest.mark.asyncio
async def test_the_runners_own_window_still_reports_a_whole_day():
    """Every other test here chooses its own window. The runner does not: it asks for the
    last 24 hours from a live clock, so `since` lands mid-day. Driving the connector the way
    the product actually drives it is the only thing that catches a partial day being
    written over a complete one."""
    from token_iq.connectors.billing.runner import run_ingestion

    now = datetime(2026, 9, 18, 14, 37, 11, tzinfo=timezone.utc)
    client = _bigquery_that_honours_the_window(
        (datetime(2026, 9, 17, 3, 0, tzinfo=timezone.utc), "4"),
        (datetime(2026, 9, 17, 21, 0, tzinfo=timezone.utc), "1"),
    )
    written: list = []
    repository = MagicMock()
    repository.upsert_many = AsyncMock(side_effect=lambda facts: written.extend(facts) or len(facts))
    sync_runs = MagicMock()
    sync_runs.record = AsyncMock()

    async def credentials_for(_provider: str):
        return (BillingCredential(name="vertex-prod", values=CREDENTIAL),)

    await run_ingestion(
        repository=repository,
        sync_runs=sync_runs,
        connectors=(_connector(client),),
        credentials_for=credentials_for,
        now=now,
    )

    day = [fact for fact in written if fact.bucket_start.date().isoformat() == "2026-09-17"]
    assert [fact.billed_cost for fact in day] == [Decimal("5")]


@pytest.mark.asyncio
async def test_a_discounted_account_is_reported_at_what_google_invoiced():
    """Committed-use discounts, sustained-use discounts and promotions arrive as negative
    credit amounts. Reporting gross cost overstates a discounted account against the
    gateway's own figure, which manufactures the very gap this product exists to explain.
    The gross survives into the fact's raw payload, so nothing Google said is discarded."""
    client = _http_single_page(_body(_cost_row(gross="10", credits="-3", net="7")))

    result = await _fetch(client)

    assert result.facts[0].billed_cost == Decimal("7")
    assert result.facts[0].raw["gross_cost"] == "10"
    assert result.facts[0].raw["credit_cost"] == "-3"


@pytest.mark.asyncio
async def test_the_query_nets_off_credits_and_sums_in_numeric():
    """The export's `cost` column is FLOAT64, so BigQuery itself adds it up in binary
    floating point unless the sum is cast first, and the credits are a repeated field the
    query has to unnest or the discount never reaches the total at all."""
    client = _http_single_page(_body())

    await _fetch(client)

    query = client.post.await_args.kwargs["json"]["query"]
    assert "UNNEST(credits)" in query
    assert "SUM(CAST(cost AS NUMERIC)" in query
    assert "SUM(cost)" not in query


@pytest.mark.asyncio
async def test_the_currency_google_billed_in_is_kept():
    """A euro-billed account stored as dollars is compared against dollar gateway spend,
    and the difference reads as a leak that does not exist."""
    client = _http_single_page(_body(_cost_row(currency="EUR")))

    result = await _fetch(client)

    assert result.facts[0].billing_currency == "EUR"


@pytest.mark.asyncio
async def test_two_currencies_on_one_day_stay_two_facts_rather_than_one_mislabelled_sum():
    """An export table holding more than one billing account's rows carries more than one
    currency. Summing across them produces a number that is not money in any currency, and
    labelling it with whichever one the engine picked presents that number with full
    confidence. Each currency has to be its own fact, and the fact key has to carry the
    currency or the second one silently overwrites the first on upsert."""
    client = _bigquery_that_groups_the_way_the_query_asks(
        ("2026-09-17", "USD", "10"),
        ("2026-09-17", "EUR", "7"),
    )

    result = await _fetch(client)

    assert {(fact.billing_currency, fact.billed_cost) for fact in result.facts} == {
        ("USD", Decimal("10")),
        ("EUR", Decimal("7")),
    }
    assert len({fact.fact_key for fact in result.facts}) == 2


@pytest.mark.asyncio
async def test_a_response_with_no_currency_column_keeps_the_default():
    """Guessing is worse than the default. A response that names no currency leaves the
    stored default alone rather than inventing one."""
    fields = [field for field in _FIELDS if field["name"] != "currency"]
    client = _http_single_page(_body(_row("2026-09-17", "Vertex AI", "1", "0", "1"), fields=fields))

    result = await _fetch(client)

    assert result.facts[0].billing_currency == "USD"


@pytest.mark.asyncio
async def test_the_fact_key_carries_the_credential_name_so_two_projects_cannot_collide():
    """fact_key is the upsert key. Without the credential in it, a second Google project's
    row for a day overwrites the first's and the reported bill silently halves."""

    async def fetch_as(name: str):
        return await _connector(_http_single_page(_body(_cost_row()))).fetch(
            since=NOW - timedelta(days=7), until=NOW, credential_name=name, credential_values=CREDENTIAL
        )

    prod = await fetch_as("vertex-prod")
    staging = await fetch_as("vertex-staging")

    assert prod.facts[0].fact_key != staging.facts[0].fact_key
    assert "vertex-prod" in prod.facts[0].fact_key


@pytest.mark.asyncio
async def test_each_fact_keeps_the_row_google_sent():
    """Raw Data renders the provider's own line. A payload dropped at parse time can never
    be shown, and BigQuery will not serve that day again."""
    client = _http_single_page(_body(_cost_row(net="1.5")))

    result = await _fetch(client)

    assert result.facts[0].raw == {
        "usage_day": "2026-09-17",
        "service_description": "Vertex AI",
        "currency": "USD",
        "gross_cost": "1.5",
        "credit_cost": "0",
        "net_cost": "1.5",
    }


@pytest.mark.asyncio
async def test_a_row_shorter_than_its_schema_fields_is_dropped_rather_than_guessed():
    """BigQuery rows are positional cells with no field names of their own; the meaning comes
    from a separate `schema.fields` array. A truncated `f` array means the response is not
    the shape we believe, and filling the gap would put a wrong number into a billing table."""
    client = _http_single_page(_body(_row("2026-09-17", "Vertex AI")))

    result = await _fetch(client)

    assert result.facts == ()


@pytest.mark.asyncio
async def test_fields_in_a_different_order_still_read_correctly():
    """Reading by position works until BigQuery reorders its schema fields, at which point the
    wrong number is reported rather than an error raised."""
    reordered_fields = [
        {"name": "service_description", "type": "STRING"},
        {"name": "net_cost", "type": "NUMERIC"},
        {"name": "usage_day", "type": "DATE"},
    ]
    client = _http_single_page(_body(_row("Vertex AI", "9.99", "2026-09-17"), fields=reordered_fields))

    result = await _fetch(client)

    assert result.facts[0].billed_cost == Decimal("9.99")


@pytest.mark.asyncio
async def test_paging_follows_page_token_until_it_is_absent():
    client = MagicMock()
    client.post = AsyncMock(
        return_value=_response(_body(_cost_row(), job_id="job-1", page_token="page-2"))
    )
    client.get = AsyncMock(
        return_value=_response(_body(_cost_row(day="2026-09-16", net="2"), job_id="job-1"))
    )

    result = await _fetch(client)

    assert len(result.facts) == 2
    assert client.post.await_count == 1
    assert client.get.await_count == 1
    call_args, call_kwargs = client.get.await_args
    assert call_args[0] == "https://bigquery.googleapis.com/bigquery/v2/projects/billing-proj/queries/job-1"
    assert call_kwargs["params"] == {"pageToken": "page-2"}


@pytest.mark.asyncio
async def test_a_pager_that_never_stops_is_cut_off_at_the_page_cap():
    """A paging bug or a hostile server that never drops `pageToken` must not spin the
    ingestion run forever; the cap is what stops it."""
    from token_iq.connectors.billing.vertex import MAX_PAGES_PER_RUN

    client = MagicMock()
    client.post = AsyncMock(
        return_value=_response(_body(_cost_row(), job_id="job-1", page_token="always-more"))
    )
    client.get = AsyncMock(
        return_value=_response(_body(_cost_row(day="2026-09-16"), job_id="job-1", page_token="always-more"))
    )

    result = await _fetch(client)

    assert client.post.await_count + client.get.await_count == MAX_PAGES_PER_RUN
    assert len(result.facts) == MAX_PAGES_PER_RUN


@pytest.mark.asyncio
async def test_a_job_that_has_not_finished_is_a_retryable_failure_not_a_silent_zero():
    """A query that comes back before it finishes running answers `jobComplete: false`
    instead of a page of rows. Reading that as zero rows would file the customer's bill as
    zero while BigQuery is still computing it, which is worse than reporting nothing at all;
    treating it as a retryable failure means the next run gets a real number instead."""
    from token_iq.types.provider_billing import FetchFailed

    client = _http_single_page(_body(_cost_row(), job_complete=False))

    result = await _fetch(client)

    assert isinstance(result, FetchFailed)
    assert result.retryable is True


@pytest.mark.asyncio
async def test_a_credential_with_no_billing_project_id_is_not_configured():
    from token_iq.types.provider_billing import NotConfigured

    result = await _fetch(
        _http_single_page(_body()), values={"billing_export_table": "proj.ds.export"}
    )

    assert isinstance(result, NotConfigured)


@pytest.mark.asyncio
async def test_a_credential_with_no_billing_export_table_is_not_configured():
    from token_iq.types.provider_billing import NotConfigured

    result = await _fetch(
        _http_single_page(_body()), values={"billing_project_id": "billing-proj"}
    )

    assert isinstance(result, NotConfigured)


_MALFORMED_TABLES = (
    "billing.export; DROP TABLE x",
    "billing.export` SELECT * FROM secrets --",
    "billing.export UNION SELECT * FROM secrets",
    "../../etc/passwd",
    "billing.export'",
    "a.b.c.d.e",
    "bad-dataset.tbl",
)
"""Six attack shapes -- a statement terminator, a backtick escape, a union select, a path
traversal, a bare quote, an over-deep dotted name -- plus one non-attack shape that must
still be refused: a hyphen inside the dataset segment, which BigQuery itself never allows
there even though the leading project segment allows one."""


@pytest.mark.asyncio
@pytest.mark.parametrize("table", _MALFORMED_TABLES)
async def test_a_malformed_export_table_is_refused_before_any_request_is_made(table: str):
    """The table name is customer configuration interpolated straight into SQL, since BigQuery
    has no bound parameter for an identifier. A value that does not match the strict table
    reference pattern must be refused before the http client is even built, let alone called,
    or this is a live SQL injection surface into the customer's own billing data."""
    from token_iq.connectors.billing.vertex import VertexBillingConnector
    from token_iq.types.provider_billing import NotConfigured

    http_client_factory = MagicMock()

    async def token_factory(_name, _values):
        return "google-token"

    result = await VertexBillingConnector(
        http_client_factory=http_client_factory, token_factory=token_factory
    ).fetch(
        since=NOW - timedelta(days=7),
        until=NOW,
        credential_name="vertex-prod",
        credential_values={"billing_project_id": "billing-proj", "billing_export_table": table},
    )

    assert isinstance(result, NotConfigured)
    assert table not in result.reason
    http_client_factory.assert_not_called()


@pytest.mark.asyncio
async def test_no_token_is_not_configured_rather_than_failed():
    from token_iq.types.provider_billing import NotConfigured

    result = await _fetch(_http_single_page(_body()), token=None)

    assert isinstance(result, NotConfigured)


@pytest.mark.asyncio
async def test_a_refused_credential_is_a_permanent_failure_not_a_retryable_one():
    """A 403 means the identity lacks BigQuery Data Viewer / Job User on that billing export.
    Retrying that every five minutes spends quota on a request that cannot start working
    until a human grants the role."""
    from token_iq.types.provider_billing import FetchFailed

    result = await _fetch(_http_single_page({}, status=403))

    assert isinstance(result, FetchFailed)
    assert result.retryable is False


@pytest.mark.asyncio
async def test_a_rate_limit_is_retryable():
    from token_iq.types.provider_billing import FetchFailed

    result = await _fetch(_http_single_page({}, status=429))

    assert isinstance(result, FetchFailed)
    assert result.retryable is True


@pytest.mark.asyncio
async def test_an_unparseable_day_is_dropped_rather_than_filed_under_today():
    """Filing an unparseable charge under today would corrupt the comparison silently."""
    client = _http_single_page(_body(_cost_row(day="not-a-date", net="1.5")))

    result = await _fetch(client)

    assert result.facts == ()


@pytest.mark.asyncio
async def test_it_calls_the_host_google_documents():
    client = _http_single_page(_body(_cost_row()))

    await _fetch(client)

    expected = "https://bigquery.googleapis.com/bigquery/v2/projects/billing-proj/queries"
    assert client.post.call_args.args[0] == expected


@pytest.mark.asyncio
async def test_a_deployment_can_point_the_connector_at_its_own_host():
    """A customer behind a proxy, or a test standing in for BigQuery, needs somewhere to put
    their host rather than forking the file."""
    from token_iq.connectors.billing.vertex import VertexBillingConnector

    client = _http_single_page(_body(_cost_row()))

    async def token_factory(_name, _values):
        return "google-token"

    connector = VertexBillingConnector(
        http_client_factory=lambda: client,
        token_factory=token_factory,
        base_url="https://bigquery.internal.example",
    )
    await connector.fetch(
        since=NOW - timedelta(days=7), until=NOW, credential_name="vertex-prod", credential_values=CREDENTIAL
    )

    expected = "https://bigquery.internal.example/bigquery/v2/projects/billing-proj/queries"
    assert client.post.call_args.args[0] == expected
