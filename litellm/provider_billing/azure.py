"""What Azure charges for its model services.

There is no Azure OpenAI usage API for cost, so this reads Cost Management, the same place
the customer's finance team looks at the subscription's bill.

Two traps live in this response. `properties.rows` carries no field names of its own; the
order is only promised by the sibling `properties.columns` array, so every row here is read
through `by_column_name` rather than by index, and a row shorter than its columns is
dropped rather than guessed. And the day arrives packed as `20260917` rather than an ISO
date, so it is unpacked before `day_from_iso` ever sees it.

Cost Management reports by whole days, so the window asked for starts at UTC midnight
rather than wherever the ingestion run happens to fall. A request from the middle of a day
risks an answer covering only the tail of it, filed under the whole day's name, which would
overwrite the complete total an earlier run already stored.

The service filter is settable on the billing credential, because a filter that matches
nothing returns an empty page rather than an error. A subscription that books its model
charges under a name other than the default would otherwise report a confident zero, which
reads as "you spent nothing" rather than "we looked in the wrong place".

Pagination hands back a `nextLink` carrying a skip token in its query string, and only the
first request carries a query body. Microsoft's reference documents the link and the token
but says nothing either way about the body, and no real subscription has answered this yet,
so a later page that fails transiently keeps the facts the earlier pages already returned
rather than discarding the run with them. A refused credential is the other case: a 401 or
403 part-way through paging fails the whole run, because keeping the pages would record a
successful sync and show a healthy connection over a credential nothing but a human can fix.
Losing those pages costs nothing, since the facts are keyed by day, upserted, and re-read on
a rolling window.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from typing import Any, Final

from litellm.provider_billing.cloud_rows import (
    by_column_name,
    currency_or_default,
    day_from_iso,
    decimal_or_none,
    exact_json,
    json_safe_row,
    utc_day_start,
)
from litellm.types.proxy.provider_billing import (
    BillingTokenFactory,
    Fetched,
    FetchFailed,
    FetchResult,
    NotConfigured,
    ProviderUsageFact,
)

DEFAULT_BASE_URL: Final = "https://management.azure.com"

QUERY_PATH_TEMPLATE: Final = (
    "/subscriptions/{subscription_id}/providers/Microsoft.CostManagement/query?api-version=2025-03-01"
)

DEFAULT_SERVICE_NAME: Final = "Cognitive Services"

MAX_PAGES_PER_RUN: Final = 12
"""A stop, so a paging bug cannot spin against the provider forever."""

UNGROUPED: Final = "all"


def _day_from_usage_date(value: object) -> datetime | None:
    """`UsageDate` arrives as an integer-shaped `20260917`, not an ISO date.

    None rather than a default: filing an unparseable charge under today would corrupt the
    comparison silently.
    """
    text: Final = str(value) if isinstance(value, (int, str)) and not isinstance(value, bool) else ""
    if len(text) != 8 or not text.isdigit():
        return None
    return day_from_iso(f"{text[0:4]}-{text[4:6]}-{text[6:8]}")


def _fact_from_row(fields: Mapping[str, object], credential_name: str) -> ProviderUsageFact | None:
    if not fields:
        return None
    amount: Final = decimal_or_none(fields.get("Cost"))
    day: Final = _day_from_usage_date(fields.get("UsageDate"))
    if amount is None or day is None:
        return None

    raw_service: Final = fields.get("ServiceName")
    service: Final = raw_service if isinstance(raw_service, str) and raw_service else UNGROUPED
    return ProviderUsageFact(
        fact_key=f"azure:{credential_name}:{day.date().isoformat()}:{service}",
        provider="azure",
        credential_name=credential_name,
        grain="day",
        bucket_start=day,
        evidence="reconciled",
        billed_cost=amount,
        billing_currency=currency_or_default(fields.get("Currency")),
        model=None if service == UNGROUPED else service,
        raw=json_safe_row(fields),
    )


def _facts_from(properties: Mapping[str, object], credential_name: str) -> tuple[ProviderUsageFact, ...]:
    columns = properties.get("columns")
    rows = properties.get("rows")
    if not isinstance(columns, Sequence) or isinstance(columns, (str, bytes)):
        return ()
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        return ()

    return tuple(
        fact
        for row in rows
        if isinstance(row, Sequence) and not isinstance(row, (str, bytes))
        if (fact := _fact_from_row(by_column_name(columns, row), credential_name)) is not None
    )


def _query_body(since: datetime, until: datetime, service_name: str) -> Mapping[str, object]:
    """The Cost Management request payload.

    Every nested mapping below carries its own `# mutable-ok`: httpx hands this straight to
    `json.dumps`, which has no encoder for `MappingProxyType`, so freezing these would raise
    at request time rather than at review time. That failure was proven live on this branch
    against prisma-client-py, which serialises the same way; wrapping only the outer mapping
    does not help either, since each nested literal is its own construction. The tuples
    (`grouping`, `values`) are left alone because tuples serialise to JSON arrays natively.
    """
    return {  # mutable-ok: httpx serialises this with json.dumps, which has no mappingproxy encoder
        "type": "ActualCost",
        "timeframe": "Custom",
        "timePeriod": {  # mutable-ok: httpx serialises this with json.dumps, no mappingproxy encoder
            "from": utc_day_start(since).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "to": until.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "dataset": {  # mutable-ok: httpx serialises this with json.dumps, no mappingproxy encoder
            "granularity": "Daily",
            "aggregation": {"totalCost": {"name": "Cost", "function": "Sum"}},  # mutable-ok: same json.dumps gap
            "grouping": ({"type": "Dimension", "name": "ServiceName"},),  # mutable-ok: same json.dumps gap
            "filter": {  # mutable-ok: httpx serialises this with json.dumps, no mappingproxy encoder
                "dimensions": {  # mutable-ok: same json.dumps gap
                    "name": "ServiceName",
                    "operator": "In",
                    "values": (service_name,),
                },
            },
        },
    }


def _failure_for(status: object, credential_name: str) -> FetchFailed | None:
    if status == 429:
        return FetchFailed(reason="azure rate limited this subscription", retryable=True)
    if status in (401, 403):
        return FetchFailed(reason=f"azure refused credential {credential_name}", retryable=False)
    if status != 200:
        return FetchFailed(reason=f"azure cost management returned {status}", retryable=True)
    return None


class AzureBillingConnector:
    def __init__(
        self,
        http_client_factory: Callable[[], Any],  # any-ok: untyped httpx wrapper
        token_factory: BillingTokenFactory,
        base_url: str = DEFAULT_BASE_URL,
    ) -> None:
        self._http_client_factory = http_client_factory
        self._token_factory = token_factory
        self._base_url = base_url.rstrip("/")

    @property
    def provider(self) -> str:
        return "azure"

    async def fetch(
        self,
        *,
        since: datetime,
        until: datetime,
        credential_name: str,
        credential_values: Mapping[str, str],
    ) -> FetchResult:
        subscription_id: Final = credential_values.get("subscription_id")
        if not subscription_id:
            return NotConfigured(reason=f"credential {credential_name} carries no subscription_id")

        token: Final = await self._token_factory(credential_name, credential_values)
        if not token:
            return NotConfigured(reason=f"credential {credential_name} has no microsoft entra id token")

        client: Final = self._http_client_factory()
        headers: Final = {"Authorization": f"Bearer {token}"}
        body: Final = _query_body(since, until, credential_values.get("service_name") or DEFAULT_SERVICE_NAME)
        target: dict[str, str] = {  # mutable-ok: nextLink advances the request target across pages
            "url": self._base_url + QUERY_PATH_TEMPLATE.format(subscription_id=subscription_id)
        }

        facts: list[ProviderUsageFact] = []  # mutable-ok: accumulated across pages
        for page_index in range(MAX_PAGES_PER_RUN):
            payload_body: Final = body if page_index == 0 else None
            response = await client.post(target["url"], json=payload_body, headers=headers)
            failure: Final = _failure_for(getattr(response, "status_code", 0), credential_name)
            if failure is not None:
                return Fetched(facts=tuple(facts), watermark=until) if facts and failure.retryable else failure

            payload = exact_json(response.text)
            if not isinstance(payload, Mapping):
                return FetchFailed(reason="azure returned a body that is not an object", retryable=True)

            properties = payload.get("properties")
            if isinstance(properties, Mapping):
                facts.extend(_facts_from(properties, credential_name))

            next_link = properties.get("nextLink") if isinstance(properties, Mapping) else None
            if not isinstance(next_link, str) or not next_link:
                break
            target["url"] = next_link

        return Fetched(facts=tuple(facts), watermark=until)
