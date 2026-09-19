"""What Google charges for Vertex AI.

There is no Vertex AI usage API for cost. Google publishes charges only into a detailed
billing export the customer enables into BigQuery, so this reads that export with a
parameterised query, the same place the customer's finance team would look.

BigQuery answers `rows[].f[].v`, values with no field names of their own, matched
positionally against the sibling `schema.fields` array. That is the same hazard
`by_column_name` exists for, but the shape is one level deeper than Azure's: the `v` values
have to be pulled out of each row's `f` array first, and a row whose `f` array is shorter
than `schema.fields` is dropped rather than guessed, before `by_column_name` ever sees it.

The billing export table name is the one piece of this query that cannot be a bound
parameter: BigQuery has no placeholder for an identifier, only for a value, so the table
has to be interpolated into the SQL text. That is a real SQL injection surface, since the
table name comes from the customer's own stored configuration and a mistake or an attacker
there would run inside the customer's own billing project. It is validated against a strict
`project.dataset.table` / `dataset.table` pattern before anything else happens; a name that
does not match is refused, not escaped, and the request is never built. The leading project
segment allows hyphens, since GCP project ids routinely carry them, but the dataset and
table segments do not, since BigQuery itself never allows a hyphen there. The interpolated
value is also wrapped in backticks in the SQL text, since an unquoted identifier would let a
hyphen parse as subtraction and a `--` parse as a comment; the pattern and the quoting are
both load-bearing, neither is a substitute for the other.

A query that does not finish inside its own request comes back with `jobComplete: false`
rather than a page of rows; this connector treats that as a retryable failure rather than
paging against a job that may still be running, since neither a partial page nor the
absence of one is a bill this build should overwrite the last read cost with.

Continuation pages are read with `jobs.getQueryResults` rather than by resending the
query, since that is where BigQuery hands back a `pageToken` for a job already running.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Final

from litellm.provider_billing.cloud_rows import by_column_name, day_from_iso, decimal_or_none
from litellm.types.proxy.provider_billing import (
    BillingTokenFactory,
    Fetched,
    FetchFailed,
    FetchResult,
    NotConfigured,
    ProviderUsageFact,
)

QUERY_URL_TEMPLATE: Final = "https://bigquery.googleapis.com/bigquery/v2/projects/{project_id}/queries"

RESULTS_URL_TEMPLATE: Final = "https://bigquery.googleapis.com/bigquery/v2/projects/{project_id}/queries/{job_id}"

DEFAULT_SERVICE_NAME: Final = "Vertex AI"

MAX_PAGES_PER_RUN: Final = 12
"""A stop, so a paging bug cannot spin against the provider forever."""

UNGROUPED: Final = "all"

TABLE_PATTERN: Final = re.compile(r"^(?:[A-Za-z0-9_-]+\.)?[A-Za-z0-9_]+\.[A-Za-z0-9_]+$")
"""A BigQuery table reference is `dataset.table` or `project.dataset.table`. GCP project ids
routinely contain hyphens, so the leading (optional) project segment allows them; BigQuery
dataset and table ids never do, so those two segments stay letters, digits and underscores
only. Anything else -- a statement separator, a backtick, a quote, a slash, an extra dot --
is refused before it ever reaches the interpolated SQL below."""

_SELECT_SQL: Final = (
    "SELECT DATE(usage_start_time) AS usage_day, service.description AS service_description, "
    "SUM(cost) AS cost FROM `{table}` "
    "WHERE service.description = @service_name AND usage_start_time >= @since AND usage_start_time < @until "
    "GROUP BY usage_day, service_description"
)


def _bq_timestamp(value: datetime) -> str:
    """GoogleSQL's TIMESTAMP literal grammar accepts ISO 8601, which this matches exactly."""
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _query_parameter(name: str, bq_type: str, value: str) -> Mapping[str, object]:
    return {  # mutable-ok: httpx serialises this with json.dumps, which has no mappingproxy encoder
        "name": name,
        "parameterType": {"type": bq_type},  # mutable-ok: same json.dumps gap
        "parameterValue": {"value": value},  # mutable-ok: same json.dumps gap
    }


def _query_body(since: datetime, until: datetime, table: str, service_name: str) -> Mapping[str, object]:
    return {  # mutable-ok: httpx serialises this with json.dumps, which has no mappingproxy encoder
        "query": _SELECT_SQL.format(table=table),
        "useLegacySql": False,
        "parameterMode": "NAMED",
        "queryParameters": (
            _query_parameter("service_name", "STRING", service_name),
            _query_parameter("since", "TIMESTAMP", _bq_timestamp(since)),
            _query_parameter("until", "TIMESTAMP", _bq_timestamp(until)),
        ),
    }


def _row_values(row: object) -> tuple[object, ...] | None:
    """The `v` values out of one row's `f` array, or None when the shape is not what BigQuery
    documents: a row that short-circuits here would otherwise be padded with a guessed value."""
    if not isinstance(row, Mapping):
        return None
    cells: Final = row.get("f")
    if not isinstance(cells, Sequence) or isinstance(cells, (str, bytes)):
        return None
    if not all(isinstance(cell, Mapping) for cell in cells):
        return None
    return tuple(cell.get("v") for cell in cells)


def _fact_from_row(fields: Mapping[str, object], credential_name: str) -> ProviderUsageFact | None:
    if not fields:
        return None
    amount: Final = decimal_or_none(fields.get("cost"))
    day: Final = day_from_iso(fields.get("usage_day"))
    if amount is None or day is None:
        return None

    raw_service: Final = fields.get("service_description")
    service: Final = raw_service if isinstance(raw_service, str) and raw_service else UNGROUPED
    return ProviderUsageFact(
        fact_key=f"vertex_ai:{credential_name}:{day.date().isoformat()}:{service}",
        provider="vertex_ai",
        credential_name=credential_name,
        grain="day",
        bucket_start=day,
        evidence="reconciled",
        billed_cost=amount,
        model=None if service == UNGROUPED else service,
        raw=fields,
    )


def _facts_from(payload: Mapping[str, object], credential_name: str) -> tuple[ProviderUsageFact, ...]:
    schema: Final = payload.get("schema")
    fields: Final = schema.get("fields") if isinstance(schema, Mapping) else None
    rows: Final = payload.get("rows")
    if not isinstance(fields, Sequence) or isinstance(fields, (str, bytes)):
        return ()
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        return ()

    return tuple(
        fact
        for row in rows
        if (values := _row_values(row)) is not None
        if (fact := _fact_from_row(by_column_name(fields, values), credential_name)) is not None
    )


class VertexBillingConnector:
    def __init__(
        self,
        http_client_factory: Callable[[], Any],  # any-ok: untyped httpx wrapper
        token_factory: BillingTokenFactory,
    ) -> None:
        self._http_client_factory = http_client_factory
        self._token_factory = token_factory

    @property
    def provider(self) -> str:
        return "vertex_ai"

    async def fetch(
        self,
        *,
        since: datetime,
        until: datetime,
        credential_name: str,
        credential_values: Mapping[str, str],
    ) -> FetchResult:
        project_id: Final = credential_values.get("billing_project_id")
        if not project_id:
            return NotConfigured(reason=f"credential {credential_name} carries no billing_project_id")

        table: Final = credential_values.get("billing_export_table")
        if not table:
            return NotConfigured(reason=f"credential {credential_name} carries no billing_export_table")

        if not TABLE_PATTERN.fullmatch(table):
            return NotConfigured(
                reason=f"credential {credential_name} has a billing_export_table that is not a valid "
                "bigquery table reference"
            )

        token: Final = await self._token_factory(credential_name, credential_values)
        if not token:
            return NotConfigured(reason=f"credential {credential_name} has no google access token")

        client: Final = self._http_client_factory()
        headers: Final = {"Authorization": f"Bearer {token}"}
        service_name: Final = credential_values.get("service_name") or DEFAULT_SERVICE_NAME
        body: Final = _query_body(since, until, table, service_name)

        facts: list[ProviderUsageFact] = []  # mutable-ok: accumulated across pages
        state: dict[str, str] = {}  # mutable-ok: job id and page token, discovered only after the first response
        for page_index in range(MAX_PAGES_PER_RUN):
            if page_index == 0:
                response = await client.post(
                    QUERY_URL_TEMPLATE.format(project_id=project_id), json=body, headers=headers
                )
            else:
                response = await client.get(
                    RESULTS_URL_TEMPLATE.format(project_id=project_id, job_id=state["job_id"]),
                    params=MappingProxyType({"pageToken": state["page_token"]}),
                    headers=headers,
                )

            status: Final = getattr(response, "status_code", 0)
            if status == 429:
                return FetchFailed(reason="vertex ai bigquery rate limited this project", retryable=True)
            if status in (401, 403):
                return FetchFailed(reason=f"vertex ai bigquery refused credential {credential_name}", retryable=False)
            if status != 200:
                return FetchFailed(reason=f"vertex ai bigquery returned {status}", retryable=True)

            payload = response.json()
            if not isinstance(payload, Mapping):
                return FetchFailed(reason="vertex ai bigquery returned a body that is not an object", retryable=True)
            if payload.get("jobComplete") is False:
                return FetchFailed(reason="vertex ai bigquery job did not complete synchronously", retryable=True)

            facts.extend(_facts_from(payload, credential_name))

            job_reference = payload.get("jobReference")
            job_id = job_reference.get("jobId") if isinstance(job_reference, Mapping) else None
            page_token = payload.get("pageToken")
            if not isinstance(job_id, str) or not job_id or not isinstance(page_token, str) or not page_token:
                break
            state["job_id"] = job_id
            state["page_token"] = page_token

        return Fetched(facts=tuple(facts), watermark=until)
