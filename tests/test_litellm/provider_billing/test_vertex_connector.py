"""Tests for the Vertex AI BigQuery billing export connector.

Every response fixture here is transcribed from the published BigQuery REST API reference
(the `jobs.query` and `jobs.getQueryResults` resources, whose rows arrive as `rows[].f[].v`
matched against `schema.fields`) and from the documented Cloud Billing detailed export
schema (`service.description`, `usage_start_time`, `cost`). Nothing in this file has been
checked against a live Google Cloud project, because this deployment has no Google Cloud
account. A fixture invented to make a test pass would encode a wire format nobody has seen,
so each shape below traces to a published reference rather than to a guess.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

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
    {"name": "cost", "type": "FLOAT"},
]


def _row(*values: str) -> dict:
    return {"f": [{"v": value} for value in values]}


def _response(payload: dict, status: int = 200) -> MagicMock:
    response = MagicMock()
    response.status_code = status
    response.json = MagicMock(return_value=payload)
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


async def _fetch(client: MagicMock, values=None, token: str | None = "google-token"):
    from litellm.provider_billing.vertex import VertexBillingConnector

    async def token_factory(_values):
        return token

    return await VertexBillingConnector(
        http_client_factory=lambda: client, token_factory=token_factory
    ).fetch(
        since=NOW - timedelta(days=7),
        until=NOW,
        credential_name="vertex-prod",
        credential_values=CREDENTIAL if values is None else values,
    )


@pytest.mark.asyncio
async def test_a_row_becomes_a_fact_with_the_exact_cost_google_reported():
    client = _http_single_page(_body(_row("2026-09-17", "Vertex AI", "0.00780515")))

    result = await _fetch(client)

    fact = result.facts[0]
    assert fact.billed_cost == Decimal("0.00780515")
    assert fact.provider == "vertex_ai"
    assert fact.grain == "day"
    assert fact.evidence == "reconciled"


@pytest.mark.asyncio
async def test_the_fact_key_carries_the_credential_name_so_two_projects_cannot_collide():
    """fact_key is the upsert key. Without the credential in it, a second Google project's
    row for a day overwrites the first's and the reported bill silently halves."""
    from litellm.provider_billing.vertex import VertexBillingConnector

    async def token_factory(_values):
        return "google-token"

    async def fetch_as(name: str):
        return await VertexBillingConnector(
            http_client_factory=lambda: _http_single_page(_body(_row("2026-09-17", "Vertex AI", "1"))),
            token_factory=token_factory,
        ).fetch(since=NOW - timedelta(days=7), until=NOW, credential_name=name, credential_values=CREDENTIAL)

    prod = await fetch_as("vertex-prod")
    staging = await fetch_as("vertex-staging")

    assert prod.facts[0].fact_key != staging.facts[0].fact_key
    assert "vertex-prod" in prod.facts[0].fact_key


@pytest.mark.asyncio
async def test_each_fact_keeps_the_row_google_sent():
    """Raw Data renders the provider's own line. A payload dropped at parse time can never
    be shown, and BigQuery will not serve that day again."""
    client = _http_single_page(_body(_row("2026-09-17", "Vertex AI", "1.5")))

    result = await _fetch(client)

    assert result.facts[0].raw == {
        "usage_day": "2026-09-17",
        "service_description": "Vertex AI",
        "cost": "1.5",
    }


@pytest.mark.asyncio
async def test_a_row_shorter_than_its_schema_fields_is_dropped_rather_than_guessed():
    """BigQuery rows are positional cells with no field names of their own; the meaning comes
    from a separate `schema.fields` array. A truncated `f` array means the response is not
    the shape we believe, and filling the gap would put a wrong number into a billing table."""
    short_row = {"f": [{"v": "2026-09-17"}, {"v": "Vertex AI"}]}
    client = _http_single_page(_body(short_row))

    result = await _fetch(client)

    assert result.facts == ()


@pytest.mark.asyncio
async def test_fields_in_a_different_order_still_read_correctly():
    """Reading by position works until BigQuery reorders its schema fields, at which point the
    wrong number is reported rather than an error raised."""
    reordered_fields = [
        {"name": "service_description", "type": "STRING"},
        {"name": "cost", "type": "FLOAT"},
        {"name": "usage_day", "type": "DATE"},
    ]
    client = _http_single_page(_body(_row("Vertex AI", "9.99", "2026-09-17"), fields=reordered_fields))

    result = await _fetch(client)

    assert result.facts[0].billed_cost == Decimal("9.99")


@pytest.mark.asyncio
async def test_paging_follows_page_token_until_it_is_absent():
    client = MagicMock()
    client.post = AsyncMock(
        return_value=_response(
            _body(_row("2026-09-17", "Vertex AI", "1"), job_id="job-1", page_token="page-2")
        )
    )
    client.get = AsyncMock(
        return_value=_response(_body(_row("2026-09-16", "Vertex AI", "2"), job_id="job-1"))
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
    from litellm.provider_billing.vertex import MAX_PAGES_PER_RUN

    client = MagicMock()
    client.post = AsyncMock(
        return_value=_response(
            _body(_row("2026-09-17", "Vertex AI", "1"), job_id="job-1", page_token="always-more")
        )
    )
    client.get = AsyncMock(
        return_value=_response(
            _body(_row("2026-09-16", "Vertex AI", "1"), job_id="job-1", page_token="always-more")
        )
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
    from litellm.types.proxy.provider_billing import FetchFailed

    client = _http_single_page(_body(_row("2026-09-17", "Vertex AI", "1"), job_complete=False))

    result = await _fetch(client)

    assert isinstance(result, FetchFailed)
    assert result.retryable is True


@pytest.mark.asyncio
async def test_a_credential_with_no_billing_project_id_is_not_configured():
    from litellm.types.proxy.provider_billing import NotConfigured

    result = await _fetch(
        _http_single_page(_body()), values={"billing_export_table": "proj.ds.export"}
    )

    assert isinstance(result, NotConfigured)


@pytest.mark.asyncio
async def test_a_credential_with_no_billing_export_table_is_not_configured():
    from litellm.types.proxy.provider_billing import NotConfigured

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
there even though the fix for Finding 1 now allows one in the leading project segment."""


@pytest.mark.asyncio
@pytest.mark.parametrize("table", _MALFORMED_TABLES)
async def test_a_malformed_export_table_is_refused_before_any_request_is_made(table: str):
    """The table name is customer configuration interpolated straight into SQL, since BigQuery
    has no bound parameter for an identifier. A value that does not match the strict table
    reference pattern must be refused before the http client is even built, let alone called,
    or this is a live SQL injection surface into the customer's own billing data."""
    from litellm.provider_billing.vertex import VertexBillingConnector
    from litellm.types.proxy.provider_billing import NotConfigured

    http_client_factory = MagicMock()

    async def token_factory(_values):
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
    from litellm.types.proxy.provider_billing import NotConfigured

    result = await _fetch(_http_single_page(_body()), token=None)

    assert isinstance(result, NotConfigured)


@pytest.mark.asyncio
async def test_a_refused_credential_is_a_permanent_failure_not_a_retryable_one():
    """A 403 means the identity lacks BigQuery Data Viewer / Job User on that billing export.
    Retrying that every five minutes spends quota on a request that cannot start working
    until a human grants the role."""
    from litellm.types.proxy.provider_billing import FetchFailed

    result = await _fetch(_http_single_page({}, status=403))

    assert isinstance(result, FetchFailed)
    assert result.retryable is False


@pytest.mark.asyncio
async def test_a_rate_limit_is_retryable():
    from litellm.types.proxy.provider_billing import FetchFailed

    result = await _fetch(_http_single_page({}, status=429))

    assert isinstance(result, FetchFailed)
    assert result.retryable is True


@pytest.mark.asyncio
async def test_an_unparseable_day_is_dropped_rather_than_filed_under_today():
    """Filing an unparseable charge under today would corrupt the comparison silently."""
    client = _http_single_page(_body(_row("not-a-date", "Vertex AI", "1.5")))

    result = await _fetch(client)

    assert result.facts == ()
