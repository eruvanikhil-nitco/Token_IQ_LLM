# Cloud Billing Connectors, Phase 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ingest what AWS, Azure and Google charge for their model services, at day grain, from the cloud billing systems that are the only place those numbers exist.

**Architecture:** Three more connectors behind the Phase 1 contract. Unlike OpenAI and Anthropic these have no LLM-specific API, so each reads its cloud's general billing pipeline: Cost Explorer for AWS, the Cost Management query API for Azure, the billing export in BigQuery for Google. Each needs configuration as well as a credential, which rides in the encrypted credential values rather than changing the connector contract.

**Tech Stack:** Python 3.12, boto3 (already a core dependency), azure-identity (already a proxy dependency), google-auth (already present for Vertex), httpx via the proxy's own client.

**Spec:** `docs/superpowers/specs/2026-09-13-provider-billing-ingestion-design.md`

**Depends on:** Phase 1 (`2026-09-13-provider-billing-ingestion.md`) and Phase 2 (`2026-09-13-anthropic-openai-billing-connectors.md`), both complete.
n**Superseded by:** `docs/superpowers/plans/2026-09-18-azure-vertex-connectors.md`. Tasks 1 and 2 of this plan shipped; Tasks 3 to 5 were written before the multi-account, raw-payload and fetch-profile interfaces existed. Do not execute this plan.

## Global Constraints

Phase 1 and Phase 2 constraints all still apply. In addition:

- **No new dependencies.** boto3 is core, azure-identity ships in the proxy extra, google-auth is already installed for Vertex. Adding an SDK for this would be disproportionate.
- **None of the three can be verified on this machine.** There are no AWS, Azure or Google credentials here, and no deployment configured for any of them. Every response fixture is transcribed from published API reference.
- **All three return positional data and each is easy to get subtly wrong.** Azure returns bare `rows` that must be matched against a separate `columns` array by name, never by position. BigQuery returns `rows[].f[].v` matched against `schema.fields` in order. AWS nests the amount under a metric name chosen by the request. Map by name wherever a name exists.
- **These providers report 24 to 48 hours late.** Facts must be re-fetchable and self-correcting rather than written once.
- **Configuration lives in the encrypted credential values**, beside the secret, so the connector contract does not change. A cloud connector needs more than a key: a region, a subscription, a table name.

---

## What is different about this family

Worth stating plainly before the tasks, because it changes what these connectors are worth.

The three LLM-native providers answer questions about tokens and models. These three answer questions about cloud resources, and the model spend is a line on a much larger bill. The consequences:

**The service filter is a guess until a real bill proves it.** AWS bills Bedrock under the service name `Amazon Bedrock`. Azure bills Azure OpenAI under `Cognitive Services` on most subscriptions, but the meter naming has changed more than once. Google bills Vertex under a service description that varies by SKU family. Every one of these is configurable with a documented default rather than hard-coded, because a wrong filter silently reports zero rather than failing.

**There is no user or team dimension at all.** Google's billing export does not carry one. AWS can attribute by tag or IAM principal only if the customer set that up. This data answers "what did the cloud charge for this service on this day" and nothing finer.

**Latency makes recent days meaningless.** A day less than 48 hours old will under-report, and comparing it against the gateway's own figure would show a false leak. The daily reconciliation from Phase 2 flags escaped spend when the provider charged more; here the risk is the opposite, and the connector must not present a still-settling day as final.

---

## File Structure

| File | Responsibility |
|---|---|
| `litellm/provider_billing/cloud_rows.py` | Mapping positional cloud responses to day and amount, shared by all three |
| `litellm/provider_billing/bedrock.py` | AWS Cost Explorer connector |
| `litellm/provider_billing/azure.py` | Azure Cost Management connector |
| `litellm/provider_billing/vertex.py` | Google BigQuery billing export connector |
| `litellm/provider_billing/startup.py` | Register all six connectors |

---

### Task 1: Day and amount from a positional response

**Files:**
- Create: `litellm/provider_billing/cloud_rows.py`
- Test: `tests/test_litellm/provider_billing/test_cloud_rows.py`

**Interfaces:**
- Produces: `day_from_iso(value: object) -> datetime | None`,
  `decimal_or_none(value: object) -> Decimal | None`,
  `by_column_name(columns: Sequence[object], row: Sequence[object], name_key: str = "name") -> dict[str, object]`,
  `settling_cutoff(now: datetime, hours: int) -> datetime`

`by_column_name` exists because Azure and BigQuery both return rows as bare arrays whose
meaning comes from a separate column list. Reading those by position works until the
provider reorders them, and then it silently reports the wrong number rather than failing.

- [ ] **Step 1: Write the failing test**

```python
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal


def test_a_row_is_read_by_column_name_never_by_position():
    """Azure and BigQuery both return bare arrays whose meaning comes from a separate
    column list. Reading by position works until the provider reorders them, and then it
    reports the wrong number instead of failing."""
    from litellm.provider_billing.cloud_rows import by_column_name

    columns = [{"name": "Cost", "type": "Number"}, {"name": "UsageDate", "type": "Number"}]
    row = [12.5, 20260912]

    assert by_column_name(columns, row) == {"Cost": 12.5, "UsageDate": 20260912}


def test_a_reordered_response_still_reads_correctly():
    from litellm.provider_billing.cloud_rows import by_column_name

    columns = [{"name": "UsageDate"}, {"name": "Cost"}]
    row = [20260912, 12.5]

    assert by_column_name(columns, row)["Cost"] == 12.5


def test_a_row_shorter_than_its_columns_is_not_guessed_at():
    """A truncated row means the response is not what we think it is. Filling the gap
    with None would put a null cost in a billing table."""
    from litellm.provider_billing.cloud_rows import by_column_name

    assert by_column_name([{"name": "a"}, {"name": "b"}], [1]) == {}


def test_bigquery_style_field_names_are_supported():
    """BigQuery calls the key 'name' too, but its columns arrive under schema.fields."""
    from litellm.provider_billing.cloud_rows import by_column_name

    fields = [{"name": "day", "type": "DATE"}, {"name": "cost", "type": "NUMERIC"}]

    assert by_column_name(fields, ["2026-09-12", "1.25"]) == {"day": "2026-09-12", "cost": "1.25"}


def test_an_iso_day_becomes_a_utc_datetime():
    from litellm.provider_billing.cloud_rows import day_from_iso

    parsed = day_from_iso("2026-09-12")

    assert parsed is not None
    assert parsed.date().isoformat() == "2026-09-12"
    assert parsed.tzinfo == timezone.utc


def test_a_full_timestamp_is_reduced_to_its_day():
    from litellm.provider_billing.cloud_rows import day_from_iso

    parsed = day_from_iso("2026-09-12T15:04:05Z")

    assert parsed is not None
    assert parsed.date().isoformat() == "2026-09-12"


def test_nonsense_is_none_rather_than_today():
    """Defaulting a bad date to now would file an unparseable charge under the current
    day and quietly corrupt the comparison."""
    from litellm.provider_billing.cloud_rows import day_from_iso

    assert day_from_iso("not a date") is None
    assert day_from_iso(None) is None
    assert day_from_iso(20260912) is None


def test_a_string_amount_keeps_its_digits():
    """AWS returns Amount as a string precisely so it does not lose precision. Passing it
    through float would undo that."""
    from litellm.provider_billing.cloud_rows import decimal_or_none

    assert decimal_or_none("0.000001234567") == Decimal("0.000001234567")


def test_a_float_amount_goes_through_str():
    from litellm.provider_billing.cloud_rows import decimal_or_none

    assert decimal_or_none(0.1) == Decimal("0.1")


def test_a_bad_amount_is_none_rather_than_zero():
    """Zero is a claim that the provider charged nothing. None is a claim that we do not
    know, and only one of those is true here."""
    from litellm.provider_billing.cloud_rows import decimal_or_none

    assert decimal_or_none("n/a") is None
    assert decimal_or_none(None) is None


def test_the_settling_cutoff_excludes_days_the_cloud_has_not_finished_billing():
    """These bills land 24 to 48 hours late. A day still settling under-reports, and
    comparing it against our own figure would show a leak that does not exist."""
    from litellm.provider_billing.cloud_rows import settling_cutoff

    now = datetime(2026, 9, 13, 12, 0, tzinfo=timezone.utc)

    assert settling_cutoff(now, hours=48) == now - timedelta(hours=48)
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_litellm/provider_billing/test_cloud_rows.py -q -p no:randomly`
Expected: FAIL, `ModuleNotFoundError`

- [ ] **Step 3: Write the module**

```python
"""Reading a day and an amount out of a cloud billing response.

The three cloud billing systems answer in positional shapes. Azure returns bare `rows`
whose meaning comes from a separate `columns` array; BigQuery returns `rows[].f[].v`
matched against `schema.fields` in order. Reading either by position works until the
provider reorders its columns, at which point the wrong number is reported rather than an
error raised, which in a billing table is the worst possible failure.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation


def by_column_name(
    columns: Sequence[object], row: Sequence[object], name_key: str = "name"
) -> dict[str, object]:
    """Pair a positional row with its column names.

    An empty result when the row is shorter than its columns: a truncated row means the
    response is not the shape we believe it is, and filling the gap would put a null cost
    into a billing table.
    """
    names = [
        name
        for column in columns
        if isinstance(column, Mapping) and isinstance(name := column.get(name_key), str)
    ]
    if len(names) != len(columns) or len(row) < len(names):
        return {}
    return dict(zip(names, row, strict=False))


def day_from_iso(value: object) -> datetime | None:
    """The UTC day an ISO date or timestamp belongs to, or None if it is not one.

    None rather than a default: filing an unparseable charge under today would corrupt
    the comparison silently.
    """
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    aware = parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)
    return aware.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)


def decimal_or_none(value: object) -> Decimal | None:
    """An exact amount, or None when the provider did not give one.

    None rather than zero: zero asserts the provider charged nothing, which is a different
    and much more dangerous claim than not knowing.
    """
    if not isinstance(value, (int, float, str)) or isinstance(value, bool):
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def settling_cutoff(now: datetime, hours: int) -> datetime:
    """The latest instant whose day a cloud has finished billing.

    Cost Explorer, Azure Cost Management and the BigQuery billing export all land 24 to 48
    hours behind. A day still settling under-reports, and comparing it against the
    gateway's own figure would show a leak that does not exist.
    """
    return now - timedelta(hours=hours)
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_litellm/provider_billing/test_cloud_rows.py -q -p no:randomly`
Expected: `11 passed`

- [ ] **Step 5: Commit**

```bash
git add litellm/provider_billing/cloud_rows.py tests/test_litellm/provider_billing/test_cloud_rows.py
git commit -m "feat(billing): read cloud billing rows by column name, never by position"
```

---

### Task 2: The Bedrock connector

**Files:**
- Create: `litellm/provider_billing/bedrock.py`
- Test: `tests/test_litellm/provider_billing/test_bedrock_connector.py`

**Interfaces:**
- Produces: `BedrockBillingConnector(cost_explorer_factory)` with `provider = "bedrock"`.
  `cost_explorer_factory` is `Callable[[Mapping[str, str]], Any]`, injected so tests never
  construct a boto3 client and production reads credentials from the credential values.
- Fact key: `bedrock:{YYYY-MM-DD}:{usage_type or "all"}`
- Credential values: `aws_access_key_id`, `aws_secret_access_key`, optional
  `aws_session_token`, optional `aws_region_name` (default `us-east-1`, because Cost
  Explorer is only served there), optional `service_name` (default `Amazon Bedrock`)

- [ ] **Step 1: Write the failing test**

```python
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

NOW = datetime(2026, 9, 13, 12, 0, tzinfo=timezone.utc)
CREDENTIAL = {"aws_access_key_id": "AKIA-test", "aws_secret_access_key": "secret"}


def _client(*pages: dict) -> MagicMock:
    client = MagicMock()
    client.get_cost_and_usage = MagicMock(side_effect=list(pages))
    return client


def _page(*groups: dict, start: str = "2026-09-11", estimated: bool = False, next_token: str | None = None) -> dict:
    page = {
        "ResultsByTime": [
            {
                "TimePeriod": {"Start": start, "End": "2026-09-12"},
                "Total": {},
                "Groups": list(groups),
                "Estimated": estimated,
            }
        ]
    }
    if next_token is not None:
        page["NextPageToken"] = next_token
    return page


def _group(amount: str, usage_type: str = "USE1-Bedrock-Input-Tokens") -> dict:
    return {"Keys": [usage_type], "Metrics": {"UnblendedCost": {"Amount": amount, "Unit": "USD"}}}


async def _fetch(client: MagicMock, credential_values=None):
    from litellm.provider_billing.bedrock import BedrockBillingConnector

    return await BedrockBillingConnector(cost_explorer_factory=lambda _values: client).fetch(
        since=NOW - timedelta(days=7),
        until=NOW,
        credential_name="acme-aws",
        credential_values=CREDENTIAL if credential_values is None else credential_values,
    )


@pytest.mark.asyncio
async def test_a_grouped_cost_becomes_a_day_fact():
    from litellm.types.proxy.provider_billing import Fetched

    result = await _fetch(_client(_page(_group("1.25"))))

    assert isinstance(result, Fetched)
    fact = result.facts[0]
    assert fact.provider == "bedrock"
    assert fact.grain == "day"
    assert fact.billed_cost == Decimal("1.25")
    assert fact.bucket_start.date().isoformat() == "2026-09-11"
    assert fact.fact_key == "bedrock:2026-09-11:USE1-Bedrock-Input-Tokens"


@pytest.mark.asyncio
async def test_the_amount_string_keeps_its_precision():
    """Cost Explorer returns Amount as a string for exactly this reason."""
    from litellm.types.proxy.provider_billing import Fetched

    result = await _fetch(_client(_page(_group("0.000001234567"))))

    assert isinstance(result, Fetched)
    assert result.facts[0].billed_cost == Decimal("0.000001234567")


@pytest.mark.asyncio
async def test_the_query_is_filtered_to_the_model_service_and_grouped_daily():
    """Without the service filter this ingests the customer's whole AWS bill and reports
    their EC2 spend as model spend."""
    client = _client(_page())
    await _fetch(client)

    call = client.get_cost_and_usage.call_args.kwargs
    assert call["Granularity"] == "DAILY"
    assert call["Filter"]["Dimensions"]["Key"] == "SERVICE"
    assert call["Filter"]["Dimensions"]["Values"] == ["Amazon Bedrock"]


@pytest.mark.asyncio
async def test_the_service_name_can_be_overridden_because_a_wrong_one_reports_zero():
    """A filter that matches nothing returns an empty result rather than an error, so a
    customer whose bill names the service differently would see a silent zero."""
    client = _client(_page())
    await _fetch(client, credential_values={**CREDENTIAL, "service_name": "Amazon Bedrock Marketplace"})

    assert client.get_cost_and_usage.call_args.kwargs["Filter"]["Dimensions"]["Values"] == [
        "Amazon Bedrock Marketplace"
    ]


@pytest.mark.asyncio
async def test_a_still_settling_day_is_not_recorded():
    """Cost Explorer lags roughly 34 hours for Bedrock. A partial day compared against our
    own figure would look like the gateway overcharging."""
    from litellm.types.proxy.provider_billing import Fetched

    today = NOW.date().isoformat()
    result = await _fetch(_client(_page(_group("9.99"), start=today)))

    assert isinstance(result, Fetched)
    assert result.facts == ()


@pytest.mark.asyncio
async def test_an_estimated_day_is_still_recorded_because_it_self_corrects():
    """AWS marks a recent day Estimated and finalises it later. The fact key is stable per
    day, so the next run overwrites it with the settled figure."""
    from litellm.types.proxy.provider_billing import Fetched

    result = await _fetch(_client(_page(_group("1.00"), estimated=True)))

    assert isinstance(result, Fetched)
    assert result.facts[0].billed_cost == Decimal("1.00")


@pytest.mark.asyncio
async def test_every_page_is_followed():
    from litellm.types.proxy.provider_billing import Fetched

    client = _client(_page(_group("1.00"), next_token="tok"), _page(_group("2.00"), start="2026-09-10"))
    result = await _fetch(client)

    assert isinstance(result, Fetched)
    assert len(result.facts) == 2
    assert client.get_cost_and_usage.call_args_list[1].kwargs["NextPageToken"] == "tok"


@pytest.mark.asyncio
async def test_a_missing_credential_is_reported_not_raised():
    from litellm.types.proxy.provider_billing import NotConfigured

    assert isinstance(await _fetch(_client(_page()), credential_values={}), NotConfigured)


@pytest.mark.asyncio
async def test_a_refused_key_is_a_permanent_failure_and_throttling_is_not():
    """Cost Explorer throttles aggressively and charges per request, so a retry next tick
    is right. An access-denied error will never fix itself."""
    from litellm.types.proxy.provider_billing import FetchFailed

    throttled = MagicMock()
    throttled.get_cost_and_usage = MagicMock(side_effect=RuntimeError("ThrottlingException: rate exceeded"))
    denied = MagicMock()
    denied.get_cost_and_usage = MagicMock(side_effect=RuntimeError("AccessDeniedException: not authorized"))

    assert isinstance(slow := await _fetch(throttled), FetchFailed) and slow.retryable is True
    assert isinstance(no := await _fetch(denied), FetchFailed) and no.retryable is False


@pytest.mark.asyncio
async def test_an_ungrouped_total_is_still_recorded():
    """A period with no Groups but a Total is a real charge that Cost Explorer could not
    break down. Dropping it would understate the bill."""
    from litellm.types.proxy.provider_billing import Fetched

    page = {
        "ResultsByTime": [
            {
                "TimePeriod": {"Start": "2026-09-11", "End": "2026-09-12"},
                "Total": {"UnblendedCost": {"Amount": "3.50", "Unit": "USD"}},
                "Groups": [],
                "Estimated": False,
            }
        ]
    }
    result = await _fetch(_client(page))

    assert isinstance(result, Fetched)
    assert result.facts[0].billed_cost == Decimal("3.50")
    assert result.facts[0].fact_key == "bedrock:2026-09-11:all"
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_litellm/provider_billing/test_bedrock_connector.py -q -p no:randomly`
Expected: FAIL, `ModuleNotFoundError`

- [ ] **Step 3: Write the connector**

```python
"""What AWS charges for Bedrock.

There is no Bedrock usage API. Model spend is a line on the AWS bill, so this reads Cost
Explorer, which is the same place the customer's finance team looks.

Three things to know. Cost Explorer is only served from us-east-1 regardless of where the
models run. It lags roughly 34 hours for Bedrock, so a recent day is partial and is skipped
rather than compared. And the service filter is configurable, because a filter that matches
nothing returns an empty result rather than an error: a customer whose bill names the
service differently would otherwise see a confident zero.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from typing import Any, Final

from litellm.provider_billing.cloud_rows import day_from_iso, decimal_or_none, settling_cutoff
from litellm.types.proxy.provider_billing import (
    Fetched,
    FetchFailed,
    FetchResult,
    NotConfigured,
    ProviderUsageFact,
)

COST_EXPLORER_REGION: Final = "us-east-1"
"""Cost Explorer is only served here, whatever region the models run in."""

DEFAULT_SERVICE_NAME: Final = "Amazon Bedrock"

METRIC: Final = "UnblendedCost"
"""What the account was actually charged, as opposed to amortised or blended views."""

SETTLING_HOURS: Final = 48
"""Cost Explorer lags roughly 34 hours for Bedrock; 48 leaves margin."""

MAX_PAGES_PER_RUN: Final = 12

UNGROUPED: Final = "all"

_PERMANENT: Final = ("AccessDenied", "UnrecognizedClient", "InvalidClientTokenId", "SignatureDoesNotMatch")


def _facts_from(periods: Sequence[object], credential_name: str, cutoff: datetime) -> tuple[ProviderUsageFact, ...]:
    facts: list[ProviderUsageFact] = []  # mutable-ok: accumulated across periods
    for period in periods:
        if not isinstance(period, Mapping):
            continue
        window = period.get("TimePeriod")
        day = day_from_iso(window.get("Start")) if isinstance(window, Mapping) else None
        if day is None or day >= cutoff:
            continue

        groups = period.get("Groups")
        entries: list[tuple[str, object]] = []  # mutable-ok: built per period
        if isinstance(groups, Sequence) and groups:
            for group in groups:
                if not isinstance(group, Mapping):
                    continue
                keys = group.get("Keys")
                metrics = group.get("Metrics")
                usage_type = keys[0] if isinstance(keys, Sequence) and keys and isinstance(keys[0], str) else UNGROUPED
                metric = metrics.get(METRIC) if isinstance(metrics, Mapping) else None
                if isinstance(metric, Mapping):
                    entries.append((usage_type, metric.get("Amount")))
        else:
            total = period.get("Total")
            metric = total.get(METRIC) if isinstance(total, Mapping) else None
            if isinstance(metric, Mapping):
                entries.append((UNGROUPED, metric.get("Amount")))

        facts.extend(
            ProviderUsageFact(
                fact_key=f"bedrock:{day.date().isoformat()}:{usage_type}",
                provider="bedrock",
                credential_name=credential_name,
                grain="day",
                bucket_start=day,
                evidence="reconciled",
                billed_cost=amount,
                model=None if usage_type == UNGROUPED else usage_type,
            )
            for usage_type, raw in entries
            if (amount := decimal_or_none(raw)) is not None
        )
    return tuple(facts)


class BedrockBillingConnector:
    def __init__(self, cost_explorer_factory: Callable[[Mapping[str, str]], Any]) -> None:  # any-ok: boto3 client
        self._cost_explorer_factory = cost_explorer_factory

    @property
    def provider(self) -> str:
        return "bedrock"

    async def fetch(
        self,
        *,
        since: datetime,
        until: datetime,
        credential_name: str,
        credential_values: Mapping[str, str],
    ) -> FetchResult:
        if not credential_values.get("aws_access_key_id") or not credential_values.get("aws_secret_access_key"):
            return NotConfigured(reason=f"credential {credential_name} carries no AWS access key")

        client: Final = self._cost_explorer_factory(credential_values)
        cutoff: Final = settling_cutoff(until, SETTLING_HOURS)
        request: dict[str, object] = {  # mutable-ok: the page token advances across requests
            "TimePeriod": {"Start": since.date().isoformat(), "End": until.date().isoformat()},
            "Granularity": "DAILY",
            "Metrics": [METRIC],
            "Filter": {
                "Dimensions": {
                    "Key": "SERVICE",
                    "Values": [credential_values.get("service_name") or DEFAULT_SERVICE_NAME],
                }
            },
            "GroupBy": [{"Type": "DIMENSION", "Key": "USAGE_TYPE"}],
        }

        facts: list[ProviderUsageFact] = []  # mutable-ok: accumulated across pages
        for _ in range(MAX_PAGES_PER_RUN):
            try:
                page = await asyncio.to_thread(lambda: client.get_cost_and_usage(**request))
            except Exception as exc:  # noqa: BLE001  # boto3 raises a generated class this module must not import
                text = str(exc)
                permanent = any(marker in text for marker in _PERMANENT)
                return FetchFailed(reason=f"cost explorer: {text}", retryable=not permanent)

            if not isinstance(page, Mapping):
                return FetchFailed(reason="cost explorer returned an unexpected shape", retryable=True)

            periods = page.get("ResultsByTime")
            if isinstance(periods, Sequence) and not isinstance(periods, (str, bytes)):
                facts.extend(_facts_from(periods, credential_name, cutoff))

            token = page.get("NextPageToken")
            if not isinstance(token, str) or not token:
                break
            request["NextPageToken"] = token

        return Fetched(facts=tuple(facts), watermark=until)


def build_cost_explorer(credential_values: Mapping[str, str]) -> Any:  # any-ok: boto3 client is untyped
    """A Cost Explorer client from the credential's own AWS keys."""
    import boto3

    return boto3.client(
        "ce",
        region_name=credential_values.get("aws_region_name") or COST_EXPLORER_REGION,
        aws_access_key_id=credential_values.get("aws_access_key_id"),
        aws_secret_access_key=credential_values.get("aws_secret_access_key"),
        aws_session_token=credential_values.get("aws_session_token") or None,
    )
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_litellm/provider_billing/test_bedrock_connector.py -q -p no:randomly`
Expected: `10 passed`

- [ ] **Step 5: Prove the settling skip has teeth**

Remove `or day >= cutoff` from the guard, re-run, confirm
`test_a_still_settling_day_is_not_recorded` FAILS, then restore it.

- [ ] **Step 6: Commit**

```bash
git add litellm/provider_billing/bedrock.py tests/test_litellm/provider_billing/test_bedrock_connector.py
git commit -m "feat(billing): read what AWS charges for Bedrock"
```

---

### Task 3: The Azure connector

**Files:**
- Create: `litellm/provider_billing/azure.py`
- Test: `tests/test_litellm/provider_billing/test_azure_connector.py`

**Interfaces:**
- Produces: `AzureBillingConnector(http_client_factory, token_factory)` with `provider = "azure"`.
  `token_factory` is `Callable[[Mapping[str, str]], Awaitable[str | None]]`, injected so tests
  never touch azure-identity.
- Fact key: `azure:{YYYY-MM-DD}:{service or "all"}`
- Endpoint: `POST https://management.azure.com/subscriptions/{id}/providers/Microsoft.CostManagement/query?api-version=2025-03-01`
- Credential values: `subscription_id` (required), optional `service_name`
  (default `Cognitive Services`), plus whatever the token factory needs

Azure returns `properties.rows` as bare arrays whose meaning comes from `properties.columns`.
Task 1's `by_column_name` is what keeps that safe.

- [ ] **Step 1: Write the failing test**

```python
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

NOW = datetime(2026, 9, 13, 12, 0, tzinfo=timezone.utc)
CREDENTIAL = {"subscription_id": "sub-123"}


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
            "columns": columns
            or [
                {"name": "Cost", "type": "Number"},
                {"name": "UsageDate", "type": "Number"},
                {"name": "ServiceName", "type": "String"},
            ],
            "rows": [list(row) for row in rows],
            "nextLink": next_link,
        }
    }


async def _fetch(client: MagicMock, credential_values=None, token: str | None = "aad-token"):
    from litellm.provider_billing.azure import AzureBillingConnector

    async def token_factory(_values):
        return token

    return await AzureBillingConnector(
        http_client_factory=lambda: client, token_factory=token_factory
    ).fetch(
        since=NOW - timedelta(days=7),
        until=NOW,
        credential_name="acme-azure",
        credential_values=CREDENTIAL if credential_values is None else credential_values,
    )


@pytest.mark.asyncio
async def test_a_row_becomes_a_day_fact():
    from litellm.types.proxy.provider_billing import Fetched

    result = await _fetch(_http(_body([1.25, 20260911, "Cognitive Services"])))

    assert isinstance(result, Fetched)
    fact = result.facts[0]
    assert fact.provider == "azure"
    assert fact.grain == "day"
    assert fact.billed_cost == Decimal("1.25")
    assert fact.bucket_start.date().isoformat() == "2026-09-11"


@pytest.mark.asyncio
async def test_columns_are_read_by_name_so_a_reorder_cannot_swap_cost_for_a_date():
    """Azure chooses its own column order. Reading positionally would file the date as the
    cost the first time it changes, and report a bill of twenty million."""
    from litellm.types.proxy.provider_billing import Fetched

    reordered = _body(
        [20260911, 1.25, "Cognitive Services"],
        columns=[
            {"name": "UsageDate", "type": "Number"},
            {"name": "Cost", "type": "Number"},
            {"name": "ServiceName", "type": "String"},
        ],
    )
    result = await _fetch(_http(reordered))

    assert isinstance(result, Fetched)
    assert result.facts[0].billed_cost == Decimal("1.25")


@pytest.mark.asyncio
async def test_the_compact_usage_date_is_understood():
    """Azure returns the day as the integer 20260911, not an ISO string."""
    from litellm.types.proxy.provider_billing import Fetched

    result = await _fetch(_http(_body([1.0, 20260911, "Cognitive Services"])))

    assert isinstance(result, Fetched)
    assert result.facts[0].bucket_start.date().isoformat() == "2026-09-11"


@pytest.mark.asyncio
async def test_a_still_settling_day_is_not_recorded():
    from litellm.types.proxy.provider_billing import Fetched

    today = int(NOW.date().isoformat().replace("-", ""))
    result = await _fetch(_http(_body([9.99, today, "Cognitive Services"])))

    assert isinstance(result, Fetched)
    assert result.facts == ()


@pytest.mark.asyncio
async def test_the_query_is_daily_and_filtered_to_the_model_service():
    client = _http(_body())
    await _fetch(client)

    body = client.post.await_args.kwargs["json"]
    assert body["type"] == "Usage"
    assert body["dataset"]["granularity"] == "Daily"
    assert "sub-123" in client.post.await_args.args[0]


@pytest.mark.asyncio
async def test_the_token_is_sent_as_a_bearer_header():
    client = _http(_body())
    await _fetch(client)

    assert client.post.await_args.kwargs["headers"]["Authorization"] == "Bearer aad-token"


@pytest.mark.asyncio
async def test_no_subscription_is_reported_not_raised():
    from litellm.types.proxy.provider_billing import NotConfigured

    assert isinstance(await _fetch(_http(_body()), credential_values={}), NotConfigured)


@pytest.mark.asyncio
async def test_a_token_that_cannot_be_obtained_is_reported_not_raised():
    """azure-identity fails in a dozen ways depending on how the customer authenticates.
    None of them should end the run for the other providers."""
    from litellm.types.proxy.provider_billing import FetchFailed

    result = await _fetch(_http(_body()), token=None)

    assert isinstance(result, FetchFailed)


@pytest.mark.asyncio
async def test_a_rate_limit_is_retryable_and_a_refused_token_is_not():
    from litellm.types.proxy.provider_billing import FetchFailed

    limited = await _fetch(_http({}, status=429))
    refused = await _fetch(_http({}, status=403))

    assert isinstance(limited, FetchFailed) and limited.retryable is True
    assert isinstance(refused, FetchFailed) and refused.retryable is False


@pytest.mark.asyncio
async def test_every_page_is_followed():
    from litellm.types.proxy.provider_billing import Fetched

    client = _http(
        _body([1.0, 20260911, "Cognitive Services"], next_link="https://management.azure.com/next"),
        _body([2.0, 20260910, "Cognitive Services"]),
    )
    result = await _fetch(client)

    assert isinstance(result, Fetched)
    assert len(result.facts) == 2
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_litellm/provider_billing/test_azure_connector.py -q -p no:randomly`
Expected: FAIL, `ModuleNotFoundError`

- [ ] **Step 3: Write the connector**

```python
"""What Azure charges for its model services.

There is no Azure OpenAI usage API worth reading: the token counts shown in Azure's own
studio are usage statistics, not billing. The charge is a line on the subscription's bill,
so this reads Cost Management, which is where the customer's finance team looks.

Azure returns `properties.rows` as bare arrays whose meaning comes from a separate
`columns` array, and it chooses that order itself. Reading positionally would file the
date as the cost the first time the order changed, and report a bill of twenty million.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from datetime import datetime, timezone
from typing import Any, Final

from litellm.provider_billing.cloud_rows import by_column_name, decimal_or_none, settling_cutoff
from litellm.types.proxy.provider_billing import (
    Fetched,
    FetchFailed,
    FetchResult,
    NotConfigured,
    ProviderUsageFact,
)

API_VERSION: Final = "2025-03-01"

SCOPE: Final = "https://management.azure.com/.default"

DEFAULT_SERVICE_NAME: Final = "Cognitive Services"
"""Where Azure OpenAI charges land on most subscriptions. Overridable, because the meter
naming has changed more than once and a wrong filter reports zero rather than failing."""

SETTLING_HOURS: Final = 48

MAX_PAGES_PER_RUN: Final = 12

UNGROUPED: Final = "all"


def _query_url(subscription_id: str) -> str:
    return (
        f"https://management.azure.com/subscriptions/{subscription_id}"
        f"/providers/Microsoft.CostManagement/query?api-version={API_VERSION}"
    )


def _day_from_compact(value: object) -> datetime | None:
    """Azure reports the day as the integer 20260911, not an ISO string."""
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    text = str(int(value)) if isinstance(value, (int, float)) else value.strip()
    if len(text) != 8 or not text.isdigit():
        return None
    try:
        return datetime(int(text[:4]), int(text[4:6]), int(text[6:]), tzinfo=timezone.utc)
    except ValueError:
        return None


def _facts_from(body: Mapping[str, object], credential_name: str, cutoff: datetime) -> tuple[ProviderUsageFact, ...]:
    properties = body.get("properties")
    if not isinstance(properties, Mapping):
        return ()
    columns = properties.get("columns")
    rows = properties.get("rows")
    if not isinstance(columns, Sequence) or not isinstance(rows, Sequence):
        return ()

    facts: list[ProviderUsageFact] = []  # mutable-ok: accumulated across rows
    for row in rows:
        if not isinstance(row, Sequence) or isinstance(row, (str, bytes)):
            continue
        cells = by_column_name(columns, row)
        day = _day_from_compact(cells.get("UsageDate"))
        amount = decimal_or_none(cells.get("Cost"))
        if day is None or amount is None or day >= cutoff:
            continue
        service = cells.get("ServiceName")
        label = service if isinstance(service, str) and service else UNGROUPED
        facts.append(
            ProviderUsageFact(
                fact_key=f"azure:{day.date().isoformat()}:{label}",
                provider="azure",
                credential_name=credential_name,
                grain="day",
                bucket_start=day,
                evidence="reconciled",
                billed_cost=amount,
                model=None if label == UNGROUPED else label,
            )
        )
    return tuple(facts)


class AzureBillingConnector:
    def __init__(
        self,
        http_client_factory: Callable[[], Any],  # any-ok: untyped httpx wrapper
        token_factory: Callable[[Mapping[str, str]], Awaitable[str | None]],
    ) -> None:
        self._http_client_factory = http_client_factory
        self._token_factory = token_factory

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

        token: Final = await self._token_factory(credential_values)
        if not token:
            return FetchFailed(reason=f"could not obtain an Azure token for {credential_name}", retryable=True)

        client: Final = self._http_client_factory()
        headers: Final = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        payload: Final = {
            "type": "Usage",
            "timeframe": "Custom",
            "timePeriod": {"from": since.date().isoformat(), "to": until.date().isoformat()},
            "dataset": {
                "granularity": "Daily",
                "aggregation": {"totalCost": {"name": "Cost", "function": "Sum"}},
                "grouping": [{"type": "Dimension", "name": "ServiceName"}],
                "filter": {
                    "dimensions": {
                        "name": "ServiceName",
                        "operator": "In",
                        "values": [credential_values.get("service_name") or DEFAULT_SERVICE_NAME],
                    }
                },
            },
        }

        url: str = _query_url(subscription_id)  # rebind-ok: nextLink is an absolute URL for the following page
        facts: list[ProviderUsageFact] = []  # mutable-ok: accumulated across pages
        cutoff: Final = settling_cutoff(until, SETTLING_HOURS)

        for _ in range(MAX_PAGES_PER_RUN):
            response = await client.post(url, json=payload, headers=headers)
            status = getattr(response, "status_code", 0)
            if status == 429:
                return FetchFailed(reason="azure rate limited this token", retryable=True)
            if status in (401, 403):
                return FetchFailed(reason=f"azure refused credential {credential_name}", retryable=False)
            if status != 200:
                return FetchFailed(reason=f"azure returned {status}", retryable=True)

            body = response.json()
            if not isinstance(body, Mapping):
                return FetchFailed(reason="azure returned a body that is not an object", retryable=True)

            facts.extend(_facts_from(body, credential_name, cutoff))

            properties = body.get("properties")
            next_link = properties.get("nextLink") if isinstance(properties, Mapping) else None
            if not isinstance(next_link, str) or not next_link:
                break
            url = next_link

        return Fetched(facts=tuple(facts), watermark=until)


async def azure_access_token(credential_values: Mapping[str, str]) -> str | None:
    """A management-plane token from whatever identity the host provides.

    DefaultAzureCredential covers a managed identity, a service principal in the
    environment, and a developer's own login, which is the range of ways a customer will
    actually run this.
    """
    from azure.identity.aio import DefaultAzureCredential

    async with DefaultAzureCredential() as credential:
        token = await credential.get_token(SCOPE)
        return getattr(token, "token", None)
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_litellm/provider_billing/test_azure_connector.py -q -p no:randomly`
Expected: `10 passed`

- [ ] **Step 5: Prove the column-name mapping has teeth**

Replace `by_column_name(columns, row)` with positional indexing, re-run, confirm
`test_columns_are_read_by_name_so_a_reorder_cannot_swap_cost_for_a_date` FAILS, restore.

- [ ] **Step 6: Commit**

```bash
git add litellm/provider_billing/azure.py tests/test_litellm/provider_billing/test_azure_connector.py
git commit -m "feat(billing): read what Azure charges for its model services"
```

---

### Task 4: The Vertex connector

**Files:**
- Create: `litellm/provider_billing/vertex.py`
- Test: `tests/test_litellm/provider_billing/test_vertex_connector.py`

**Interfaces:**
- Produces: `VertexBillingConnector(http_client_factory, token_factory)` with `provider = "vertex_ai"`.
- Fact key: `vertex_ai:{YYYY-MM-DD}:{sku or "all"}`
- Endpoint: `POST https://bigquery.googleapis.com/bigquery/v2/projects/{project}/queries`
- Credential values: `billing_project_id` and `billing_export_table` (both required),
  optional `service_name` (default `Vertex AI`)

Google has no billing API for this at all: the only source is the detailed billing export
the customer must enable into BigQuery. That makes this the most configuration-heavy of the
three and the one most likely to be unavailable.

- [ ] **Step 1: Write the failing test**

```python
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

NOW = datetime(2026, 9, 13, 12, 0, tzinfo=timezone.utc)
CREDENTIAL = {
    "billing_project_id": "acme-billing",
    "billing_export_table": "acme-billing.billing.gcp_billing_export_v1_XXXX",
}


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


def _body(*rows: list, complete: bool = True) -> dict:
    return {
        "jobComplete": complete,
        "schema": {"fields": [{"name": "day", "type": "DATE"}, {"name": "sku", "type": "STRING"},
                              {"name": "cost", "type": "NUMERIC"}]},
        "rows": [{"f": [{"v": value} for value in row]} for row in rows],
    }


async def _fetch(client: MagicMock, credential_values=None, token: str | None = "gcp-token"):
    from litellm.provider_billing.vertex import VertexBillingConnector

    async def token_factory(_values):
        return token

    return await VertexBillingConnector(
        http_client_factory=lambda: client, token_factory=token_factory
    ).fetch(
        since=NOW - timedelta(days=7),
        until=NOW,
        credential_name="acme-gcp",
        credential_values=CREDENTIAL if credential_values is None else credential_values,
    )


@pytest.mark.asyncio
async def test_a_row_becomes_a_day_fact():
    from litellm.types.proxy.provider_billing import Fetched

    result = await _fetch(_http(_body(["2026-09-11", "Gemini 2.5 Input", "1.25"])))

    assert isinstance(result, Fetched)
    fact = result.facts[0]
    assert fact.provider == "vertex_ai"
    assert fact.grain == "day"
    assert fact.billed_cost == Decimal("1.25")
    assert fact.bucket_start.date().isoformat() == "2026-09-11"
    assert fact.model == "Gemini 2.5 Input"


@pytest.mark.asyncio
async def test_the_nested_cell_shape_is_unwrapped():
    """BigQuery wraps every value as rows[].f[].v and returns them all as strings. Reading
    the row directly yields a list of dicts where a cost belongs."""
    from litellm.types.proxy.provider_billing import Fetched

    result = await _fetch(_http(_body(["2026-09-11", "sku", "0.000001234567"])))

    assert isinstance(result, Fetched)
    assert result.facts[0].billed_cost == Decimal("0.000001234567")


@pytest.mark.asyncio
async def test_a_still_settling_day_is_not_recorded():
    from litellm.types.proxy.provider_billing import Fetched

    result = await _fetch(_http(_body([NOW.date().isoformat(), "sku", "9.99"])))

    assert isinstance(result, Fetched)
    assert result.facts == ()


@pytest.mark.asyncio
async def test_an_incomplete_job_is_retryable_rather_than_reported_as_empty():
    """BigQuery can answer before the query has finished. Treating that as zero spend
    would report a customer's Vertex bill as nothing."""
    from litellm.types.proxy.provider_billing import FetchFailed

    result = await _fetch(_http(_body(complete=False)))

    assert isinstance(result, FetchFailed)
    assert result.retryable is True


@pytest.mark.asyncio
async def test_the_export_table_is_required_because_there_is_no_default():
    """Unlike the other two clouds there is no API to fall back on: without the export
    table there is no source of Vertex spend at all."""
    from litellm.types.proxy.provider_billing import NotConfigured

    result = await _fetch(_http(_body()), credential_values={"billing_project_id": "p"})

    assert isinstance(result, NotConfigured)


@pytest.mark.asyncio
async def test_the_table_name_is_validated_before_it_reaches_the_query():
    """The table name is interpolated into SQL because BigQuery cannot parameterise an
    identifier. Anything but a plain dotted name is refused rather than sent."""
    from litellm.types.proxy.provider_billing import NotConfigured

    result = await _fetch(
        _http(_body()),
        credential_values={**CREDENTIAL, "billing_export_table": "t`; DROP TABLE x; --"},
    )

    assert isinstance(result, NotConfigured)
    assert "table" in result.reason.lower()


@pytest.mark.asyncio
async def test_the_token_is_sent_as_a_bearer_header():
    client = _http(_body())
    await _fetch(client)

    assert client.post.await_args.kwargs["headers"]["Authorization"] == "Bearer gcp-token"


@pytest.mark.asyncio
async def test_the_window_is_a_bound_query_parameter_not_string_interpolation():
    """The dates are user-controlled input reaching SQL."""
    client = _http(_body())
    await _fetch(client)

    body = client.post.await_args.kwargs["json"]
    assert body["useLegacySql"] is False
    assert body["queryParameters"]


@pytest.mark.asyncio
async def test_a_missing_token_is_reported_not_raised():
    from litellm.types.proxy.provider_billing import FetchFailed

    assert isinstance(await _fetch(_http(_body()), token=None), FetchFailed)


@pytest.mark.asyncio
async def test_a_rate_limit_is_retryable_and_a_refused_token_is_not():
    from litellm.types.proxy.provider_billing import FetchFailed

    limited = await _fetch(_http({}, status=429))
    refused = await _fetch(_http({}, status=403))

    assert isinstance(limited, FetchFailed) and limited.retryable is True
    assert isinstance(refused, FetchFailed) and refused.retryable is False
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_litellm/provider_billing/test_vertex_connector.py -q -p no:randomly`
Expected: FAIL, `ModuleNotFoundError`

- [ ] **Step 3: Write the connector**

```python
"""What Google charges for Vertex AI.

Google publishes no billing API for this. The only source is the detailed billing export
the customer has to enable into BigQuery, which makes this the most configuration-heavy of
the three connectors and the one most likely to be simply unavailable.

The export table name is interpolated into SQL, because BigQuery cannot parameterise an
identifier. It is validated to a plain dotted name first; the dates, which are the part
that varies per run, are bound parameters.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable, Mapping, Sequence
from datetime import datetime
from typing import Any, Final

from litellm.provider_billing.cloud_rows import by_column_name, day_from_iso, decimal_or_none, settling_cutoff
from litellm.types.proxy.provider_billing import (
    Fetched,
    FetchFailed,
    FetchResult,
    NotConfigured,
    ProviderUsageFact,
)

QUERY_URL: Final = "https://bigquery.googleapis.com/bigquery/v2/projects/{project}/queries"

SCOPE: Final = "https://www.googleapis.com/auth/bigquery.readonly"

DEFAULT_SERVICE_NAME: Final = "Vertex AI"

SETTLING_HOURS: Final = 48

QUERY_TIMEOUT_MS: Final = 30_000

UNGROUPED: Final = "all"

_TABLE_NAME: Final = re.compile(r"^[A-Za-z0-9_\-]+(\.[A-Za-z0-9_\-]+){1,2}$")
"""project.dataset.table, and nothing that could close an identifier quote."""

_SQL: Final = """
SELECT FORMAT_DATE('%Y-%m-%d', DATE(usage_start_time)) AS day,
       sku.description AS sku,
       CAST(SUM(cost) AS STRING) AS cost
  FROM `{table}`
 WHERE DATE(usage_start_time) BETWEEN @since AND @until
   AND service.description = @service
 GROUP BY day, sku
 ORDER BY day DESC
"""


def _cell_values(row: object) -> list[object]:
    """BigQuery wraps every value as {"f": [{"v": value}, ...]}."""
    if not isinstance(row, Mapping):
        return []
    cells = row.get("f")
    if not isinstance(cells, Sequence):
        return []
    return [cell.get("v") if isinstance(cell, Mapping) else None for cell in cells]


def _facts_from(body: Mapping[str, object], credential_name: str, cutoff: datetime) -> tuple[ProviderUsageFact, ...]:
    schema = body.get("schema")
    fields = schema.get("fields") if isinstance(schema, Mapping) else None
    rows = body.get("rows")
    if not isinstance(fields, Sequence) or not isinstance(rows, Sequence):
        return ()

    facts: list[ProviderUsageFact] = []  # mutable-ok: accumulated across rows
    for row in rows:
        cells = by_column_name(fields, _cell_values(row))
        day = day_from_iso(cells.get("day"))
        amount = decimal_or_none(cells.get("cost"))
        if day is None or amount is None or day >= cutoff:
            continue
        sku = cells.get("sku")
        label = sku if isinstance(sku, str) and sku else UNGROUPED
        facts.append(
            ProviderUsageFact(
                fact_key=f"vertex_ai:{day.date().isoformat()}:{label}",
                provider="vertex_ai",
                credential_name=credential_name,
                grain="day",
                bucket_start=day,
                evidence="reconciled",
                billed_cost=amount,
                model=None if label == UNGROUPED else label,
            )
        )
    return tuple(facts)


class VertexBillingConnector:
    def __init__(
        self,
        http_client_factory: Callable[[], Any],  # any-ok: untyped httpx wrapper
        token_factory: Callable[[Mapping[str, str]], Awaitable[str | None]],
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
        project: Final = credential_values.get("billing_project_id")
        table: Final = credential_values.get("billing_export_table")
        if not project or not table:
            return NotConfigured(
                reason=(
                    f"credential {credential_name} needs billing_project_id and billing_export_table; "
                    "Google publishes no billing API, so the BigQuery export is the only source"
                )
            )
        if not _TABLE_NAME.match(table):
            return NotConfigured(reason=f"billing_export_table on {credential_name} is not a plain table name")

        token: Final = await self._token_factory(credential_values)
        if not token:
            return FetchFailed(reason=f"could not obtain a Google token for {credential_name}", retryable=True)

        client: Final = self._http_client_factory()
        response: Final = await client.post(
            QUERY_URL.format(project=project),
            json={
                "query": _SQL.format(table=table),
                "useLegacySql": False,
                "timeoutMs": QUERY_TIMEOUT_MS,
                "queryParameters": [
                    {
                        "name": "since",
                        "parameterType": {"type": "DATE"},
                        "parameterValue": {"value": since.date().isoformat()},
                    },
                    {
                        "name": "until",
                        "parameterType": {"type": "DATE"},
                        "parameterValue": {"value": until.date().isoformat()},
                    },
                    {
                        "name": "service",
                        "parameterType": {"type": "STRING"},
                        "parameterValue": {"value": credential_values.get("service_name") or DEFAULT_SERVICE_NAME},
                    },
                ],
            },
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )

        status: Final = getattr(response, "status_code", 0)
        if status == 429:
            return FetchFailed(reason="bigquery rate limited this token", retryable=True)
        if status in (401, 403):
            return FetchFailed(reason=f"bigquery refused credential {credential_name}", retryable=False)
        if status != 200:
            return FetchFailed(reason=f"bigquery returned {status}", retryable=True)

        body: Final = response.json()
        if not isinstance(body, Mapping):
            return FetchFailed(reason="bigquery returned a body that is not an object", retryable=True)
        if not body.get("jobComplete"):
            return FetchFailed(reason="bigquery did not finish the query in time", retryable=True)

        return Fetched(
            facts=_facts_from(body, credential_name, settling_cutoff(until, SETTLING_HOURS)),
            watermark=until,
        )


async def google_access_token(credential_values: Mapping[str, str]) -> str | None:
    """A read-only BigQuery token from whatever identity the host provides."""
    import asyncio

    import google.auth
    import google.auth.transport.requests

    def _token() -> str | None:
        credentials, _project = google.auth.default(scopes=[SCOPE])
        credentials.refresh(google.auth.transport.requests.Request())
        return getattr(credentials, "token", None)

    return await asyncio.to_thread(_token)
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_litellm/provider_billing/test_vertex_connector.py -q -p no:randomly`
Expected: `10 passed`

- [ ] **Step 5: Prove the table-name validation has teeth**

Remove the `_TABLE_NAME.match` guard, re-run, confirm
`test_the_table_name_is_validated_before_it_reaches_the_query` FAILS, then restore it.

- [ ] **Step 6: Commit**

```bash
git add litellm/provider_billing/vertex.py tests/test_litellm/provider_billing/test_vertex_connector.py
git commit -m "feat(billing): read what Google charges for Vertex AI"
```

---

### Task 5: Register all six and prove the wiring

**Files:**
- Modify: `litellm/provider_billing/startup.py`
- Test: `tests/test_litellm/provider_billing/test_startup.py`

- [ ] **Step 1: Update the failing test**

Replace the expected set in both tests in `tests/test_litellm/provider_billing/test_startup.py`:

```python
    assert {connector.provider for connector in registered_connectors()} == {
        "openrouter",
        "anthropic",
        "openai",
        "bedrock",
        "azure",
        "vertex_ai",
    }
```

and in the second test:

```python
    assert len(registered_connectors()) == 6
```

Add a new test to the same file:

```python
def test_every_provider_this_gateway_serves_has_a_billing_connector():
    """A provider the gateway routes traffic to, with no way to read its bill, is a blind
    spot the customer cannot see. This is the list that decides which are covered."""
    from litellm.provider_billing.connector import clear_registry_for_tests, registered_connectors
    from litellm.provider_billing.startup import register_billing_connectors

    clear_registry_for_tests()
    register_billing_connectors(prisma_client=MagicMock())
    covered = {connector.provider for connector in registered_connectors()}

    assert {"openai", "anthropic", "bedrock", "azure", "vertex_ai", "openrouter"} <= covered
    clear_registry_for_tests()
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_litellm/provider_billing/test_startup.py -q -p no:randomly`
Expected: FAIL, the registered set is missing the three cloud providers

- [ ] **Step 3: Register the three cloud connectors**

In `litellm/provider_billing/startup.py`, add to the imports inside
`register_billing_connectors`:

```python
    from litellm.provider_billing.azure import AzureBillingConnector, azure_access_token
    from litellm.provider_billing.bedrock import BedrockBillingConnector, build_cost_explorer
    from litellm.provider_billing.vertex import VertexBillingConnector, google_access_token
```

and extend `candidates`:

```python
        BedrockBillingConnector(cost_explorer_factory=build_cost_explorer),
        AzureBillingConnector(http_client_factory=http, token_factory=azure_access_token),
        VertexBillingConnector(http_client_factory=http, token_factory=google_access_token),
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_litellm/provider_billing/ -q -p no:randomly`
Expected: all pass

- [ ] **Step 5: Prove the wiring against the running proxy**

```bash
bash ~/.claude/scripts/litellm-dev-up.sh

for P in openrouter anthropic openai bedrock azure vertex_ai voyage; do
  printf '%-12s -> ' "$P"
  curl -s -X POST -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
    "http://127.0.0.1:4001/provider/billing/probe?provider=$P" \
    | python -c "import sys,json; d=json.load(sys.stdin); print(d['outcome'])"
done
```

Expected: `openrouter -> fetched`, the next five `not_configured`, `voyage -> no_connector`.
That proves all six are registered and that each reports honestly with no credential. It
does **not** prove any cloud connector parses a real response.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(billing): register the Bedrock, Azure and Vertex connectors"
```

---

## Self-review notes

**Spec coverage.** Plan 3 of the design's five. All six providers the design names now have
a connector, and the day-grain reconciliation from Phase 2 serves all three cloud
providers unchanged.

**Deliberately not covered.** Per-team attribution, which none of these three can support:
Google's export carries no user dimension at all, and AWS only attributes by tag or IAM
principal if the customer configured that first. Also no UI, which remains plan 4.

**Type consistency.** `by_column_name`, `day_from_iso`, `decimal_or_none` and
`settling_cutoff` are defined in Task 1 and consumed by Tasks 2, 3 and 4. Each connector
matches the Phase 1 `BillingConnector` protocol, verified by the registry accepting it.

**The honest gap, larger here than in Phase 2.** None of these three can be verified on this
machine, and unlike Anthropic and OpenAI there is not even a deployment configured for them.
Three specific things are guesses until a real bill proves them: the AWS service name
`Amazon Bedrock`, the Azure service name `Cognitive Services`, and the Google service
description `Vertex AI`. Each is configurable for exactly that reason, and each fails by
reporting zero rather than erroring, which is the worst failure mode a billing filter can
have. The probe from Phase 2 is the intended way to check all three on the day credentials
exist.
