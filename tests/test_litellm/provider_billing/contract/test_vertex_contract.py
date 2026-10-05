"""Does our Vertex connector speak the BigQuery API Google documents?

The request and response shapes below come from Google's BigQuery REST reference for
`jobs.query` and `jobs.getQueryResults`, where a row arrives as `rows[].f[].v` and is matched
against `schema.fields` by position, and from the Cloud Billing detailed export schema.
https://cloud.google.com/bigquery/docs/reference/rest/v2/jobs/query

Two things here can only be caught by a real request. The query goes out as a POST body, so a
frozen mapping anywhere in it raises inside the HTTP client rather than in review. And the
second page is fetched with a different verb against a different path, which a mocked client
will happily accept in any shape at all.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Final

import pytest

from tests.test_litellm.provider_billing.contract.conftest import Reply, Vendor

SINCE: Final = datetime(2026, 9, 1, tzinfo=timezone.utc)
UNTIL: Final = datetime(2026, 9, 3, tzinfo=timezone.utc)
CREDENTIAL: Final = {
    "billing_project_id": "billing-proj",
    "billing_export_table": "my-billing-project.export_ds.gcp_billing",
}

FIELDS: Final = (
    {"name": "usage_day", "type": "DATE"},
    {"name": "service_description", "type": "STRING"},
    {"name": "currency", "type": "STRING"},
    {"name": "gross_cost", "type": "NUMERIC"},
    {"name": "credit_cost", "type": "NUMERIC"},
    {"name": "net_cost", "type": "NUMERIC"},
)


def _row(*values: str) -> dict[str, object]:
    return {"f": [{"v": value} for value in values]}


def _cost_row(day: str = "2026-09-01", net: str = "1.25") -> dict[str, object]:
    return _row(day, "Vertex AI", "USD", net, "0", net)


def _body(
    *rows: dict[str, object],
    job_id: str = "job-1",
    page_token: str | None = None,
) -> dict[str, object]:
    return {
        "jobComplete": True,
        "jobReference": {"projectId": "billing-proj", "jobId": job_id},
        "schema": {"fields": list(FIELDS)},
        "rows": list(rows),
        **({"pageToken": page_token} if page_token else {}),
    }


async def _fetch(vendor: Vendor):
    from token_iq.connectors.billing.vertex import VertexBillingConnector

    async def token_factory(_name: str, _values: object) -> str:
        return "google-token-not-real"

    return await VertexBillingConnector(
        http_client_factory=vendor.client_factory(),
        token_factory=token_factory,
        base_url="https://bigquery.googleapis.test",
    ).fetch(since=SINCE, until=UNTIL, credential_name="vertex-prod", credential_values=CREDENTIAL)


@pytest.mark.asyncio
async def test_it_posts_a_query_to_the_path_google_documents(vendor):
    stand_in: Final = vendor(Reply(json=_body(_cost_row())))

    await _fetch(stand_in)

    assert stand_in.first.method == "POST"
    assert stand_in.first.path == "/bigquery/v2/projects/billing-proj/queries"


@pytest.mark.asyncio
async def test_it_authenticates_with_the_google_token_as_a_bearer(vendor):
    stand_in: Final = vendor(Reply(json=_body(_cost_row())))

    await _fetch(stand_in)

    assert stand_in.first.headers["authorization"] == "Bearer google-token-not-real"


@pytest.mark.asyncio
async def test_it_sends_standard_sql_with_the_window_as_bound_parameters(vendor):
    """Bound parameters rather than a formatted string. The export table name is interpolated
    because BigQuery has no parameter for a table, which is why it is validated separately."""
    import json

    stand_in: Final = vendor(Reply(json=_body(_cost_row())))

    await _fetch(stand_in)

    sent: Final = json.loads(stand_in.first.body)
    assert sent["useLegacySql"] is False
    assert sent["parameterMode"] == "NAMED"
    assert {p["name"] for p in sent["queryParameters"]} == {"service_name", "since", "until"}
    assert CREDENTIAL["billing_export_table"] in sent["query"]


@pytest.mark.asyncio
async def test_the_query_body_is_something_json_can_actually_serialise(vendor):
    """A frozen mapping in this body raises inside the HTTP client, a failure nothing but a
    real request reproduces."""
    stand_in: Final = vendor(Reply(json=_body(_cost_row())))

    await _fetch(stand_in)

    assert stand_in.first.body


@pytest.mark.asyncio
async def test_a_row_is_read_against_the_schema_google_returned(vendor):
    from token_iq.types.provider_billing import Fetched

    stand_in: Final = vendor(Reply(json=_body(_cost_row(net="0.00780515"))))

    result: Final = await _fetch(stand_in)

    assert isinstance(result, Fetched)
    assert result.facts[0].billed_cost == Decimal("0.00780515")


@pytest.mark.asyncio
async def test_fields_in_a_different_order_still_read_correctly(vendor):
    """BigQuery returns unlabelled values matched to the schema it sends back, so reading by a
    remembered position rather than by the returned schema is wrong the day the query changes."""
    from token_iq.types.provider_billing import Fetched

    reordered: Final = {
        "jobComplete": True,
        "jobReference": {"projectId": "billing-proj", "jobId": "job-1"},
        "schema": {
            "fields": [
                {"name": "net_cost", "type": "NUMERIC"},
                {"name": "usage_day", "type": "DATE"},
                {"name": "service_description", "type": "STRING"},
                {"name": "currency", "type": "STRING"},
                {"name": "gross_cost", "type": "NUMERIC"},
                {"name": "credit_cost", "type": "NUMERIC"},
            ]
        },
        "rows": [_row("2.50", "2026-09-01", "Vertex AI", "USD", "2.50", "0")],
    }
    stand_in: Final = vendor(Reply(json=reordered))

    result: Final = await _fetch(stand_in)

    assert isinstance(result, Fetched)
    assert result.facts[0].billed_cost == Decimal("2.50")


@pytest.mark.asyncio
async def test_it_fetches_the_next_page_from_the_results_path(vendor):
    """The second page is a GET against the job's results, not another POST of the query.
    Repeating the POST would re-run the query and bill the customer for it again."""
    from token_iq.types.provider_billing import Fetched

    stand_in: Final = vendor(
        Reply(json=_body(_cost_row(), page_token="page-2")),
        Reply(json=_body(_cost_row(day="2026-09-02", net="2.50"))),
    )

    result: Final = await _fetch(stand_in)

    assert isinstance(result, Fetched)
    assert len(stand_in.requests) == 2
    assert stand_in.requests[1].method == "GET"
    assert stand_in.requests[1].path == "/bigquery/v2/projects/billing-proj/queries/job-1"
    assert stand_in.requests[1].params["pageToken"] == "page-2"
    assert len(result.facts) == 2


@pytest.mark.asyncio
async def test_a_job_that_has_not_finished_is_retryable_rather_than_a_silent_zero(vendor):
    from token_iq.types.provider_billing import FetchFailed

    stand_in: Final = vendor(Reply(json={"jobComplete": False}))

    result: Final = await _fetch(stand_in)

    assert isinstance(result, FetchFailed)
    assert result.retryable is True


@pytest.mark.parametrize(
    ("status", "retryable"),
    [(401, False), (403, False), (429, True), (500, True), (503, True)],
)
@pytest.mark.asyncio
async def test_it_turns_an_error_into_a_reason_rather_than_raising(vendor, status: int, retryable: bool):
    from token_iq.types.provider_billing import FetchFailed

    stand_in: Final = vendor(Reply(json={"error": {"message": "nope"}}, status=status))

    result: Final = await _fetch(stand_in)

    assert isinstance(result, FetchFailed)
    assert result.retryable is retryable
    assert result.reason


@pytest.mark.asyncio
async def test_a_body_that_is_not_json_is_a_failure_not_a_crash(vendor):
    from token_iq.types.provider_billing import FetchFailed

    stand_in: Final = vendor(Reply(text="<html>backend error</html>"))

    assert isinstance(await _fetch(stand_in), FetchFailed)
