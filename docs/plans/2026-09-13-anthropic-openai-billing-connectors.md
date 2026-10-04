# Anthropic and OpenAI Billing Connectors, Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ingest what Anthropic and OpenAI say our usage cost, at day grain, and compare it to what the gateway recorded for the same day.

**Architecture:** Two more connectors behind the Phase 1 contract, writing into the same fact table. Both answer in daily aggregates rather than per request, so the comparison is per day rather than per call, and the reconciliation gains a day-grain mode. A probe endpoint runs one fetch on demand and returns the result verbatim, because neither connector can be verified on this machine.

**Tech Stack:** Python 3.12, FastAPI, Prisma/Postgres, pytest.

**Spec:** `docs/superpowers/specs/2026-09-13-provider-billing-ingestion-design.md`

**Depends on:** `docs/superpowers/plans/2026-09-13-provider-billing-ingestion.md` (Phase 1, complete)

## Global Constraints

Everything in the Phase 1 plan's Global Constraints still applies. In addition:

- **Neither connector can be verified against a live provider on this machine.** Both `ANTHROPIC_API_KEY` and `OPENAI_API_KEY` in `.env` are empty placeholders, and these endpoints need *organisation admin* keys, which are a further step beyond an ordinary API key. Every response fixture in this plan is copied from the providers' published API reference and must be treated as the contract until a real key proves otherwise.
- **Units differ between the two providers and getting one wrong is a 100x error.** Anthropic reports `amount` in *cents* as a decimal string, where `"123.45"` means $1.23. OpenAI reports `amount.value` in *dollars* as a float. Both must land in the fact table as dollars.
- **Timestamps differ.** Anthropic takes and returns RFC 3339 strings. OpenAI takes and returns Unix seconds.
- Costs stay `Decimal` in memory and text in the column, per the Phase 1 deviation note.

---

## What day grain can and cannot answer

Worth stating before the tasks, because it bounds what these connectors are for.

The gateway serves many teams through one provider credential. Anthropic and OpenAI report against *their* key or workspace, not our teams, so a day-grain fact cannot be split back to a team. Per-team attribution stays with the gateway's own numbers.

What this does answer, and what makes it worth building: for one credential on one day, the provider charged X and we recorded Y. A persistent gap where theirs exceeds ours is traffic that never came through the gateway. That is the escaped-spend discovery from the design, and day grain is enough for it.

---

## File Structure

| File | Responsibility |
|---|---|
| `litellm/provider_billing/anthropic.py` | Anthropic cost report connector |
| `litellm/provider_billing/openai.py` | OpenAI costs connector |
| `litellm/provider_billing/startup.py` | Register all three connectors |
| `litellm/proxy/management_endpoints/provider_reconciliation.py` | Day-grain mode plus the probe endpoint |
| `litellm/types/proxy/management_endpoints/team_endpoints.py` | Response models for both additions |

---

### Task 1: The Anthropic connector

**Files:**
- Create: `litellm/provider_billing/anthropic.py`
- Test: `tests/test_litellm/provider_billing/test_anthropic_connector.py`

**Interfaces:**
- Consumes: `ProviderUsageFact`, `Fetched`, `NotConfigured`, `FetchFailed` from Phase 1
- Produces: `AnthropicBillingConnector(http_client_factory)` with `provider = "anthropic"`
- Fact key format: `anthropic:{YYYY-MM-DD}:{model or "unattributed"}`
- Endpoint: `GET https://api.anthropic.com/v1/organizations/cost_report`
- Headers: `x-api-key`, `anthropic-version: 2023-06-01`
- Params: `starting_at`, `ending_at` (RFC 3339), `bucket_width=1d`, `group_by[]=description`, `limit=31`, `page`

One bucket carries many results, one per model and token type, so the connector sums them
per model to produce one fact per model per day. Token-type detail is dropped deliberately:
the comparable unit against our own spend is the day's charge for a model.

- [ ] **Step 1: Write the failing test**

```python
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

NOW = datetime(2026, 9, 13, 12, 0, tzinfo=timezone.utc)
CREDENTIAL = {"api_key": "sk-ant-admin01-test"}


def _http(*payloads: dict, status: int = 200) -> MagicMock:
    responses = []
    for payload in payloads:
        response = MagicMock()
        response.status_code = status
        response.json = MagicMock(return_value=payload)
        responses.append(response)
    client = MagicMock()
    client.get = AsyncMock(side_effect=responses if len(responses) > 1 else responses * 1)
    return client


def _bucket(*results: dict, start: str = "2026-09-12T00:00:00Z", end: str = "2026-09-13T00:00:00Z") -> dict:
    return {"starting_at": start, "ending_at": end, "results": list(results)}


def _result(amount: str, model: str | None = "claude-opus-5", **extra: object) -> dict:
    return {
        "amount": amount,
        "currency": "USD",
        "model": model,
        "workspace_id": None,
        "cost_type": "tokens",
        "token_type": "uncached_input_tokens",
        **extra,
    }


async def _fetch(client: MagicMock, credential_values=None):
    from litellm.provider_billing.anthropic import AnthropicBillingConnector

    return await AnthropicBillingConnector(http_client_factory=lambda: client).fetch(
        since=NOW - timedelta(days=2),
        until=NOW,
        credential_name="acme-anthropic",
        credential_values=CREDENTIAL if credential_values is None else credential_values,
    )


@pytest.mark.asyncio
async def test_the_amount_is_cents_and_must_reach_the_table_as_dollars():
    """Anthropic documents amount in lowest currency units: "123.45" means $1.23. Storing
    it verbatim would overstate every customer's Anthropic spend by a factor of one
    hundred, in the table whose whole purpose is to be the accurate one."""
    from litellm.types.proxy.provider_billing import Fetched

    result = await _fetch(_http({"data": [_bucket(_result("123.45"))], "has_more": False, "next_page": None}))

    assert isinstance(result, Fetched)
    assert result.facts[0].billed_cost == Decimal("1.2345")


@pytest.mark.asyncio
async def test_one_fact_per_model_per_day_summing_the_token_types():
    """A bucket carries a row per token type. The comparable unit against our own spend is
    the day's charge for a model, so they are summed rather than stored separately."""
    from litellm.types.proxy.provider_billing import Fetched

    result = await _fetch(
        _http(
            {
                "data": [
                    _bucket(
                        _result("100", token_type="uncached_input_tokens"),
                        _result("50", token_type="output_tokens"),
                        _result("25", model="claude-haiku-4-5"),
                    )
                ],
                "has_more": False,
                "next_page": None,
            }
        )
    )

    assert isinstance(result, Fetched)
    by_model = {f.model: f.billed_cost for f in result.facts}
    assert by_model["claude-opus-5"] == Decimal("1.50")
    assert by_model["claude-haiku-4-5"] == Decimal("0.25")


@pytest.mark.asyncio
async def test_the_fact_key_is_stable_so_a_refetch_overwrites():
    """Every run re-reads the last day. Without a key that is identical across runs the
    same day's cost would be inserted again on every tick."""
    from litellm.types.proxy.provider_billing import Fetched

    payload = {"data": [_bucket(_result("100"))], "has_more": False, "next_page": None}
    first = await _fetch(_http(payload))
    second = await _fetch(_http(payload))

    assert isinstance(first, Fetched) and isinstance(second, Fetched)
    assert first.facts[0].fact_key == second.facts[0].fact_key == "anthropic:2026-09-12:claude-opus-5"


@pytest.mark.asyncio
async def test_the_bucket_start_is_the_day_the_cost_belongs_to():
    """Stamping the fetch time instead would file yesterday's charges under today and
    make every daily comparison off by one."""
    from litellm.types.proxy.provider_billing import Fetched

    result = await _fetch(_http({"data": [_bucket(_result("100"))], "has_more": False, "next_page": None}))

    assert isinstance(result, Fetched)
    assert result.facts[0].bucket_start.date().isoformat() == "2026-09-12"


@pytest.mark.asyncio
async def test_every_page_is_followed():
    """limit caps a page at 31 buckets. Reading only the first page would silently drop
    history on any window longer than that."""
    from litellm.types.proxy.provider_billing import Fetched

    client = _http(
        {"data": [_bucket(_result("100"))], "has_more": True, "next_page": "page_2"},
        {"data": [_bucket(_result("200"), start="2026-09-11T00:00:00Z", end="2026-09-12T00:00:00Z")],
         "has_more": False, "next_page": None},
    )
    result = await _fetch(client)

    assert isinstance(result, Fetched)
    assert len(result.facts) == 2
    assert client.get.await_args_list[1].kwargs["params"]["page"] == "page_2"


@pytest.mark.asyncio
async def test_a_cost_with_no_model_is_still_recorded():
    """Web search and code execution charges carry no model. Dropping them would
    understate the bill by exactly the amount hardest to explain later."""
    from litellm.types.proxy.provider_billing import Fetched

    result = await _fetch(
        _http({"data": [_bucket(_result("500", model=None, cost_type="web_search"))],
               "has_more": False, "next_page": None})
    )

    assert isinstance(result, Fetched)
    assert result.facts[0].billed_cost == Decimal("5.00")
    assert result.facts[0].fact_key == "anthropic:2026-09-12:unattributed"


@pytest.mark.asyncio
async def test_a_missing_credential_is_reported_not_raised():
    from litellm.types.proxy.provider_billing import NotConfigured

    assert isinstance(await _fetch(_http({}), credential_values={}), NotConfigured)


@pytest.mark.asyncio
async def test_a_rate_limit_is_retryable_and_a_bad_key_is_not():
    from litellm.types.proxy.provider_billing import FetchFailed

    limited = await _fetch(_http({}, status=429))
    refused = await _fetch(_http({}, status=401))

    assert isinstance(limited, FetchFailed) and limited.retryable is True
    assert isinstance(refused, FetchFailed) and refused.retryable is False


@pytest.mark.asyncio
async def test_the_admin_key_goes_in_the_anthropic_header_not_a_bearer_token():
    """Anthropic authenticates with x-api-key. A Bearer header returns 401 and would look
    like a revoked key rather than a coding mistake."""
    client = _http({"data": [], "has_more": False, "next_page": None})
    await _fetch(client)

    headers = client.get.await_args.kwargs["headers"]
    assert headers["x-api-key"] == "sk-ant-admin01-test"
    assert headers["anthropic-version"] == "2023-06-01"
    assert "Authorization" not in headers


@pytest.mark.asyncio
async def test_an_empty_window_is_a_successful_empty_run():
    from litellm.types.proxy.provider_billing import Fetched

    result = await _fetch(_http({"data": [], "has_more": False, "next_page": None}))

    assert isinstance(result, Fetched)
    assert result.facts == ()
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_litellm/provider_billing/test_anthropic_connector.py -q -p no:randomly`
Expected: FAIL, `ModuleNotFoundError`

- [ ] **Step 3: Write the connector**

```python
"""What Anthropic says our usage cost.

Day grain: Anthropic reports daily aggregates against its own workspace and key, not our
teams, so a fact here cannot be split back to a team. What it answers is whether the
provider's charge for a day matches what this gateway recorded for it.

Two traps live in this response and both are silent. `amount` is in cents as a decimal
string, so "123.45" is $1.23. And a bucket carries one row per token type, so the rows have
to be summed per model or the same day's cost lands several times.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Final

from litellm.types.proxy.provider_billing import (
    Fetched,
    FetchFailed,
    FetchResult,
    NotConfigured,
    ProviderUsageFact,
)

COST_REPORT_URL: Final = "https://api.anthropic.com/v1/organizations/cost_report"

ANTHROPIC_VERSION: Final = "2023-06-01"

MAX_BUCKETS_PER_PAGE: Final = 31
"""Anthropic's documented maximum for daily buckets."""

MAX_PAGES_PER_RUN: Final = 12
"""A stop so a paging bug cannot spin against the provider forever."""

_CENTS_PER_DOLLAR: Final = Decimal(100)

UNATTRIBUTED: Final = "unattributed"
"""Web search and code execution charges carry no model."""


def _decimal(value: object) -> Decimal | None:
    if not isinstance(value, (int, float, str)):
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def _day(bucket: Mapping[str, object]) -> datetime | None:
    raw: Final = bucket.get("starting_at")
    if not isinstance(raw, str):
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


class AnthropicBillingConnector:
    def __init__(self, http_client_factory: Callable[[], Any]) -> None:  # any-ok: untyped httpx wrapper
        self._http_client_factory = http_client_factory

    @property
    def provider(self) -> str:
        return "anthropic"

    async def fetch(
        self,
        *,
        since: datetime,
        until: datetime,
        credential_name: str,
        credential_values: Mapping[str, str],
    ) -> FetchResult:
        api_key: Final = credential_values.get("api_key")
        if not api_key:
            return NotConfigured(reason=f"credential {credential_name} carries no api_key")

        client: Final = self._http_client_factory()
        headers: Final = {"x-api-key": api_key, "anthropic-version": ANTHROPIC_VERSION}
        params: dict[str, object] = {  # mutable-ok: the page cursor advances across requests
            "starting_at": since.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "ending_at": until.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "bucket_width": "1d",
            "group_by[]": "description",
            "limit": MAX_BUCKETS_PER_PAGE,
        }

        facts: list[ProviderUsageFact] = []  # mutable-ok: accumulated across pages
        for _ in range(MAX_PAGES_PER_RUN):
            response = await client.get(COST_REPORT_URL, params=dict(params), headers=headers)
            status = getattr(response, "status_code", 0)
            if status == 429:
                return FetchFailed(reason="anthropic rate limited this key", retryable=True)
            if status in (401, 403):
                return FetchFailed(reason=f"anthropic refused credential {credential_name}", retryable=False)
            if status != 200:
                return FetchFailed(reason=f"anthropic returned {status}", retryable=True)

            payload = response.json()
            if not isinstance(payload, Mapping):
                return FetchFailed(reason="anthropic returned a body that is not an object", retryable=True)

            buckets = payload.get("data")
            facts.extend(_facts_from(buckets, credential_name) if isinstance(buckets, Sequence) else ())

            next_page = payload.get("next_page")
            if not payload.get("has_more") or not isinstance(next_page, str):
                break
            params["page"] = next_page

        return Fetched(facts=tuple(facts), watermark=until)


def _facts_from(buckets: Sequence[object], credential_name: str) -> tuple[ProviderUsageFact, ...]:
    """One fact per model per day, summing the token-type rows within a bucket."""
    facts: list[ProviderUsageFact] = []  # mutable-ok: built per bucket
    for bucket in buckets:
        if not isinstance(bucket, Mapping):
            continue
        day = _day(bucket)
        results = bucket.get("results")
        if day is None or not isinstance(results, Sequence):
            continue

        per_model: dict[str, Decimal] = defaultdict(Decimal)  # mutable-ok: accumulator
        for item in results:
            if not isinstance(item, Mapping):
                continue
            cents = _decimal(item.get("amount"))
            if cents is None:
                continue
            model = item.get("model")
            per_model[model if isinstance(model, str) else UNATTRIBUTED] += cents / _CENTS_PER_DOLLAR

        facts.extend(
            ProviderUsageFact(
                fact_key=f"anthropic:{day.date().isoformat()}:{model}",
                provider="anthropic",
                credential_name=credential_name,
                grain="day",
                bucket_start=day,
                evidence="reconciled",
                billed_cost=dollars,
                model=None if model == UNATTRIBUTED else model,
            )
            for model, dollars in sorted(per_model.items())
        )
    return tuple(facts)
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_litellm/provider_billing/test_anthropic_connector.py -q -p no:randomly`
Expected: `10 passed`

- [ ] **Step 5: Prove the cents conversion has teeth**

Change `cents / _CENTS_PER_DOLLAR` to `cents`, re-run, confirm
`test_the_amount_is_cents_and_must_reach_the_table_as_dollars` FAILS, then restore it.

- [ ] **Step 6: Commit**

```bash
git add litellm/provider_billing/anthropic.py tests/test_litellm/provider_billing/test_anthropic_connector.py
git commit -m "feat(billing): read what Anthropic says our usage cost"
```

---

### Task 2: The OpenAI connector

**Files:**
- Create: `litellm/provider_billing/openai.py`
- Test: `tests/test_litellm/provider_billing/test_openai_connector.py`

**Interfaces:**
- Consumes: the same Phase 1 types
- Produces: `OpenAIBillingConnector(http_client_factory)` with `provider = "openai"`
- Fact key format: `openai:{YYYY-MM-DD}:{line_item or "unattributed"}`
- Endpoint: `GET https://api.openai.com/v1/organization/costs`
- Headers: `Authorization: Bearer <admin key>`
- Params: `start_time`, `end_time` (Unix seconds), `bucket_width=1d`, `group_by[]=line_item`, `limit`, `page`

Deliberately different from Anthropic in three ways the response forces: dollars not cents,
Unix seconds not RFC 3339, and `amount.value` nested rather than flat.

- [ ] **Step 1: Write the failing test**

```python
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

NOW = datetime(2026, 9, 13, 12, 0, tzinfo=timezone.utc)
CREDENTIAL = {"api_key": "sk-admin-test"}
DAY_START = int(datetime(2026, 9, 12, tzinfo=timezone.utc).timestamp())


def _http(*payloads: dict, status: int = 200) -> MagicMock:
    responses = []
    for payload in payloads:
        response = MagicMock()
        response.status_code = status
        response.json = MagicMock(return_value=payload)
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


async def _fetch(client: MagicMock, credential_values=None):
    from litellm.provider_billing.openai import OpenAIBillingConnector

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
    from litellm.types.proxy.provider_billing import Fetched

    result = await _fetch(_http({"object": "page", "data": [_bucket(_result(0.06))], "has_more": False,
                                 "next_page": None}))

    assert isinstance(result, Fetched)
    assert result.facts[0].billed_cost == Decimal("0.06")


@pytest.mark.asyncio
async def test_a_float_amount_keeps_its_digits():
    """json gives a float. Decimal(float) carries the binary approximation; going through
    str does not."""
    from litellm.types.proxy.provider_billing import Fetched

    result = await _fetch(_http({"object": "page", "data": [_bucket(_result(0.1))], "has_more": False,
                                 "next_page": None}))

    assert isinstance(result, Fetched)
    assert result.facts[0].billed_cost == Decimal("0.1")


@pytest.mark.asyncio
async def test_the_unix_bucket_becomes_the_day_the_cost_belongs_to():
    from litellm.types.proxy.provider_billing import Fetched

    result = await _fetch(_http({"object": "page", "data": [_bucket(_result(1.0))], "has_more": False,
                                 "next_page": None}))

    assert isinstance(result, Fetched)
    assert result.facts[0].bucket_start.date().isoformat() == "2026-09-12"


@pytest.mark.asyncio
async def test_the_window_is_sent_as_unix_seconds():
    """OpenAI rejects RFC 3339 here, where Anthropic requires it."""
    client = _http({"object": "page", "data": [], "has_more": False, "next_page": None})
    await _fetch(client)

    params = client.get.await_args.kwargs["params"]
    assert isinstance(params["start_time"], int)
    assert isinstance(params["end_time"], int)


@pytest.mark.asyncio
async def test_line_items_are_kept_separate_within_a_day():
    from litellm.types.proxy.provider_billing import Fetched

    result = await _fetch(
        _http({"object": "page",
               "data": [_bucket(_result(0.06, "gpt-4o-mini, input"), _result(0.02, "gpt-4o-mini, output"))],
               "has_more": False, "next_page": None})
    )

    assert isinstance(result, Fetched)
    assert {f.model for f in result.facts} == {"gpt-4o-mini, input", "gpt-4o-mini, output"}


@pytest.mark.asyncio
async def test_the_fact_key_is_stable_so_a_refetch_overwrites():
    from litellm.types.proxy.provider_billing import Fetched

    payload = {"object": "page", "data": [_bucket(_result(1.0))], "has_more": False, "next_page": None}
    first = await _fetch(_http(payload))
    second = await _fetch(_http(payload))

    assert isinstance(first, Fetched) and isinstance(second, Fetched)
    assert first.facts[0].fact_key == second.facts[0].fact_key


@pytest.mark.asyncio
async def test_every_page_is_followed():
    from litellm.types.proxy.provider_billing import Fetched

    client = _http(
        {"object": "page", "data": [_bucket(_result(1.0))], "has_more": True, "next_page": "page_2"},
        {"object": "page", "data": [_bucket(_result(2.0), start=DAY_START - 86400)], "has_more": False,
         "next_page": None},
    )
    result = await _fetch(client)

    assert isinstance(result, Fetched)
    assert len(result.facts) == 2


@pytest.mark.asyncio
async def test_the_admin_key_goes_in_a_bearer_header():
    client = _http({"object": "page", "data": [], "has_more": False, "next_page": None})
    await _fetch(client)

    assert client.get.await_args.kwargs["headers"]["Authorization"] == "Bearer sk-admin-test"


@pytest.mark.asyncio
async def test_a_missing_credential_is_reported_not_raised():
    from litellm.types.proxy.provider_billing import NotConfigured

    assert isinstance(await _fetch(_http({}), credential_values={}), NotConfigured)


@pytest.mark.asyncio
async def test_a_rate_limit_is_retryable_and_a_bad_key_is_not():
    from litellm.types.proxy.provider_billing import FetchFailed

    limited = await _fetch(_http({}, status=429))
    refused = await _fetch(_http({}, status=401))

    assert isinstance(limited, FetchFailed) and limited.retryable is True
    assert isinstance(refused, FetchFailed) and refused.retryable is False
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_litellm/provider_billing/test_openai_connector.py -q -p no:randomly`
Expected: FAIL, `ModuleNotFoundError`

- [ ] **Step 3: Write the connector**

```python
"""What OpenAI says our usage cost.

Day grain, like Anthropic, and for the same reason: OpenAI reports against its own project
and key rather than our teams.

Three things differ from Anthropic and each is a silent trap. The amount is already in
dollars, not cents. The window is Unix seconds, not RFC 3339. And the amount is nested
under `amount.value` rather than flat.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Final

from litellm.types.proxy.provider_billing import (
    Fetched,
    FetchFailed,
    FetchResult,
    NotConfigured,
    ProviderUsageFact,
)

COSTS_URL: Final = "https://api.openai.com/v1/organization/costs"

MAX_BUCKETS_PER_PAGE: Final = 31

MAX_PAGES_PER_RUN: Final = 12

UNATTRIBUTED: Final = "unattributed"


def _decimal(value: object) -> Decimal | None:
    if not isinstance(value, (int, float, str)):
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def _day(bucket: Mapping[str, object]) -> datetime | None:
    raw: Final = bucket.get("start_time")
    if not isinstance(raw, (int, float)):
        return None
    return datetime.fromtimestamp(int(raw), tz=timezone.utc)


class OpenAIBillingConnector:
    def __init__(self, http_client_factory: Callable[[], Any]) -> None:  # any-ok: untyped httpx wrapper
        self._http_client_factory = http_client_factory

    @property
    def provider(self) -> str:
        return "openai"

    async def fetch(
        self,
        *,
        since: datetime,
        until: datetime,
        credential_name: str,
        credential_values: Mapping[str, str],
    ) -> FetchResult:
        api_key: Final = credential_values.get("api_key")
        if not api_key:
            return NotConfigured(reason=f"credential {credential_name} carries no api_key")

        client: Final = self._http_client_factory()
        headers: Final = {"Authorization": f"Bearer {api_key}"}
        params: dict[str, object] = {  # mutable-ok: the page cursor advances across requests
            "start_time": int(since.timestamp()),
            "end_time": int(until.timestamp()),
            "bucket_width": "1d",
            "group_by[]": "line_item",
            "limit": MAX_BUCKETS_PER_PAGE,
        }

        facts: list[ProviderUsageFact] = []  # mutable-ok: accumulated across pages
        for _ in range(MAX_PAGES_PER_RUN):
            response = await client.get(COSTS_URL, params=dict(params), headers=headers)
            status = getattr(response, "status_code", 0)
            if status == 429:
                return FetchFailed(reason="openai rate limited this key", retryable=True)
            if status in (401, 403):
                return FetchFailed(reason=f"openai refused credential {credential_name}", retryable=False)
            if status != 200:
                return FetchFailed(reason=f"openai returned {status}", retryable=True)

            payload = response.json()
            if not isinstance(payload, Mapping):
                return FetchFailed(reason="openai returned a body that is not an object", retryable=True)

            buckets = payload.get("data")
            facts.extend(_facts_from(buckets, credential_name) if isinstance(buckets, Sequence) else ())

            next_page = payload.get("next_page")
            if not payload.get("has_more") or not isinstance(next_page, str):
                break
            params["page"] = next_page

        return Fetched(facts=tuple(facts), watermark=until)


def _facts_from(buckets: Sequence[object], credential_name: str) -> tuple[ProviderUsageFact, ...]:
    facts: list[ProviderUsageFact] = []  # mutable-ok: built per bucket
    for bucket in buckets:
        if not isinstance(bucket, Mapping):
            continue
        day = _day(bucket)
        results = bucket.get("results")
        if day is None or not isinstance(results, Sequence):
            continue

        for item in results:
            if not isinstance(item, Mapping):
                continue
            amount = item.get("amount")
            dollars = _decimal(amount.get("value")) if isinstance(amount, Mapping) else None
            if dollars is None:
                continue
            raw_line_item = item.get("line_item")
            line_item = raw_line_item if isinstance(raw_line_item, str) else UNATTRIBUTED
            facts.append(
                ProviderUsageFact(
                    fact_key=f"openai:{day.date().isoformat()}:{line_item}",
                    provider="openai",
                    credential_name=credential_name,
                    grain="day",
                    bucket_start=day,
                    evidence="reconciled",
                    billed_cost=dollars,
                    model=None if line_item == UNATTRIBUTED else line_item,
                )
            )
    return tuple(facts)
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_litellm/provider_billing/test_openai_connector.py -q -p no:randomly`
Expected: `10 passed`

- [ ] **Step 5: Prove the two unit handlings cannot be swapped**

Add `cents / Decimal(100)` to the OpenAI connector, re-run, confirm
`test_the_amount_is_already_dollars_and_is_not_scaled` FAILS, then restore.

- [ ] **Step 6: Commit**

```bash
git add litellm/provider_billing/openai.py tests/test_litellm/provider_billing/test_openai_connector.py
git commit -m "feat(billing): read what OpenAI says our usage cost"
```

---

### Task 3: Register both, and a probe so they can be verified on arrival

**Files:**
- Modify: `litellm/provider_billing/startup.py`
- Modify: `litellm/proxy/management_endpoints/provider_reconciliation.py`
- Modify: `litellm/types/proxy/management_endpoints/team_endpoints.py`
- Test: `tests/test_litellm/provider_billing/test_startup.py`
- Test: `tests/test_litellm/proxy/management_endpoints/test_provider_reconciliation.py` (extend)

**Interfaces:**
- Produces: `register_billing_connectors(prisma_client)` replacing the OpenRouter-only function;
  `POST /provider/billing/probe?provider=<name>` returning `BillingProbeResponse` with
  `provider`, `outcome` (`fetched` | `not_configured` | `failed` | `no_connector`),
  `facts_found`, `sample_cost`, `detail`

Neither connector can be verified here, so the probe exists to make verification one command
on the day a key arrives, rather than a log-reading exercise. It runs one fetch and reports
the tagged union verbatim without writing anything.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_litellm/provider_billing/test_startup.py`:

```python
from __future__ import annotations

from unittest.mock import MagicMock


def test_every_shipped_connector_is_registered():
    """A connector that exists but is never registered is dead code that looks like a
    feature. The registry is what the runner iterates."""
    from litellm.provider_billing.connector import clear_registry_for_tests, registered_connectors
    from litellm.provider_billing.startup import register_billing_connectors

    clear_registry_for_tests()
    register_billing_connectors(prisma_client=MagicMock())

    assert {c.provider for c in registered_connectors()} == {"openrouter", "anthropic", "openai"}
    clear_registry_for_tests()


def test_registering_twice_is_harmless():
    """A worker that restarts its scheduler calls this again, and the registry refuses
    duplicates by design. Startup must not die on the second call."""
    from litellm.provider_billing.connector import clear_registry_for_tests, registered_connectors
    from litellm.provider_billing.startup import register_billing_connectors

    clear_registry_for_tests()
    register_billing_connectors(prisma_client=MagicMock())
    register_billing_connectors(prisma_client=MagicMock())

    assert len(registered_connectors()) == 3
    clear_registry_for_tests()
```

Append to `tests/test_litellm/proxy/management_endpoints/test_provider_reconciliation.py`:

```python
@pytest.mark.asyncio
async def test_the_probe_reports_a_working_connector_without_writing_anything():
    """Neither Anthropic nor OpenAI can be verified on a machine with no admin key. The
    probe is how the first real key gets checked in one command."""
    from datetime import datetime, timezone

    from litellm.proxy.management_endpoints.provider_reconciliation import provider_billing_probe
    from litellm.types.proxy.provider_billing import Fetched, ProviderUsageFact

    fact = ProviderUsageFact(
        fact_key="anthropic:2026-09-12:claude-opus-5",
        provider="anthropic",
        credential_name="acme",
        grain="day",
        bucket_start=datetime.now(timezone.utc),
        evidence="reconciled",
        billed_cost=Decimal("1.25"),
    )

    class _Connector:
        provider = "anthropic"

        async def fetch(self, **_: object):
            return Fetched(facts=(fact,), watermark=datetime.now(timezone.utc))

    async def creds(_provider: str):
        return ("acme", {"api_key": "sk-ant-admin01-x"})

    result = await provider_billing_probe(
        provider="anthropic",
        user_api_key_dict=ADMIN,
        _connectors=(_Connector(),),
        _credentials_for=creds,
    )

    assert result.outcome == "fetched"
    assert result.facts_found == 1
    assert result.sample_cost == "1.25"


@pytest.mark.asyncio
async def test_the_probe_names_a_missing_credential_rather_than_failing():
    from litellm.proxy.management_endpoints.provider_reconciliation import provider_billing_probe

    class _Connector:
        provider = "anthropic"

        async def fetch(self, **_: object):
            raise AssertionError("must not be called without a credential")

    async def no_creds(_provider: str):
        return None

    result = await provider_billing_probe(
        provider="anthropic",
        user_api_key_dict=ADMIN,
        _connectors=(_Connector(),),
        _credentials_for=no_creds,
    )

    assert result.outcome == "not_configured"


@pytest.mark.asyncio
async def test_the_probe_says_so_when_no_connector_exists_for_a_provider():
    from litellm.proxy.management_endpoints.provider_reconciliation import provider_billing_probe

    result = await provider_billing_probe(
        provider="bedrock",
        user_api_key_dict=ADMIN,
        _connectors=(),
        _credentials_for=lambda _p: None,
    )

    assert result.outcome == "no_connector"


@pytest.mark.asyncio
async def test_only_an_admin_may_probe():
    from fastapi import HTTPException

    from litellm.proxy.management_endpoints.provider_reconciliation import provider_billing_probe

    member = UserAPIKeyAuth(user_role=LitellmUserRoles.INTERNAL_USER, api_key="sk-u", user_id="u")
    with pytest.raises(HTTPException) as exc:
        await provider_billing_probe(
            provider="anthropic", user_api_key_dict=member, _connectors=(), _credentials_for=lambda _p: None
        )

    assert exc.value.status_code == 403
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_litellm/provider_billing/test_startup.py tests/test_litellm/proxy/management_endpoints/test_provider_reconciliation.py -q -p no:randomly`
Expected: FAIL on the new tests

- [ ] **Step 3: Replace the startup registration**

Rewrite `litellm/provider_billing/startup.py`:

```python
"""Registering the connectors this build ships with.

Separate from the connectors themselves so importing one does not register it, which would
make the registry depend on import order and break the duplicate-registration guard.
"""

from __future__ import annotations

from typing import Any, Final

from litellm._logging import verbose_proxy_logger


def register_billing_connectors(*, prisma_client: Any) -> None:  # any-ok: untyped runtime wrapper
    """Idempotent: a worker that restarts its scheduler must not fail on a second call."""
    from litellm.llms.custom_httpx.http_handler import get_async_httpx_client
    from litellm.provider_billing.anthropic import AnthropicBillingConnector
    from litellm.provider_billing.connector import register_connector, registered_connectors
    from litellm.provider_billing.openai import OpenAIBillingConnector
    from litellm.provider_billing.openrouter import (
        OpenRouterBillingConnector,
        build_unpriced_openrouter_lookup,
    )
    from litellm.types.llms.custom_http import httpxSpecialProvider

    def http() -> Any:  # any-ok: the proxy's httpx wrapper is untyped
        return get_async_httpx_client(llm_provider=httpxSpecialProvider.LoggingCallback)

    already: Final = {connector.provider for connector in registered_connectors()}
    candidates: Final = (
        OpenRouterBillingConnector(
            unpriced_request_ids=build_unpriced_openrouter_lookup(prisma_client),
            http_client_factory=http,
        ),
        AnthropicBillingConnector(http_client_factory=http),
        OpenAIBillingConnector(http_client_factory=http),
    )

    for connector in candidates:
        if connector.provider not in already:
            register_connector(connector)
            verbose_proxy_logger.debug("registered the %s billing connector", connector.provider)
```

- [ ] **Step 4: Update the call site**

In `litellm/proxy/proxy_server.py`, change the import and the call:

```python
from litellm.provider_billing.startup import register_billing_connectors
```

```python
        register_billing_connectors(prisma_client=prisma_client)
```

- [ ] **Step 5: Add the probe response model**

Append to `litellm/types/proxy/management_endpoints/team_endpoints.py`:

```python
class BillingProbeResponse(BaseModel):
    """One on-demand fetch from a provider's billing API, reported without storing anything"""

    provider: str
    outcome: str
    """fetched, not_configured, failed, or no_connector"""

    facts_found: int
    sample_cost: str | None
    detail: str | None
```

- [ ] **Step 6: Add the probe endpoint**

Append to `litellm/proxy/management_endpoints/provider_reconciliation.py`:

```python
@router.post(
    "/provider/billing/probe",
    tags=["provider billing"],
    dependencies=[Depends(user_api_key_auth)],
    response_model=BillingProbeResponse,
)
async def provider_billing_probe(
    provider: str = fastapi.Query(description="Which provider's billing API to try"),
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
    _connectors: Sequence[BillingConnector] | None = None,
    _credentials_for: Callable[[str], Awaitable[tuple[str, Mapping[str, str]] | None]] | None = None,
) -> BillingProbeResponse:
    """Run one fetch and report what came back, storing nothing.

    Anthropic and OpenAI could not be verified against a live provider when they were
    written, because this deployment had no organisation admin key. This turns that
    verification into one command on the day a key arrives.
    """
    from litellm.proxy.proxy_server import prisma_client

    if user_api_key_dict.user_role != LitellmUserRoles.PROXY_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "Only a proxy admin may probe a provider's billing API."},
        )

    connectors: Final = registered_connectors() if _connectors is None else _connectors
    connector: Final = next((c for c in connectors if c.provider == provider), None)
    if connector is None:
        return BillingProbeResponse(
            provider=provider, outcome="no_connector", facts_found=0, sample_cost=None,
            detail="This build ships no billing connector for that provider.",
        )

    lookup: Final = (
        _credentials_for
        if _credentials_for is not None
        else build_billing_credential_lookup(prisma_client=prisma_client)
    )
    credential: Final = await lookup(provider)
    if credential is None:
        return BillingProbeResponse(
            provider=provider, outcome="not_configured", facts_found=0, sample_cost=None,
            detail=(
                "No stored credential is marked for this provider. Create one with "
                'credential_info {"purpose": "billing_ingestion", "provider": "%s"}.' % provider
            ),
        )
    credential_name, credential_values = credential

    now: Final = datetime.now(timezone.utc)
    result: Final = await connector.fetch(
        since=now - LOOKBACK, until=now, credential_name=credential_name, credential_values=credential_values
    )

    match result:
        case Fetched(facts=facts):
            return BillingProbeResponse(
                provider=provider, outcome="fetched", facts_found=len(facts),
                sample_cost=_plain(facts[0].billed_cost) if facts else None,
                detail=None if facts else "The provider answered but reported nothing in this window.",
            )
        case NotConfigured(reason=reason):
            return BillingProbeResponse(
                provider=provider, outcome="not_configured", facts_found=0, sample_cost=None, detail=reason
            )
        case FetchFailed(reason=reason, retryable=retryable):
            return BillingProbeResponse(
                provider=provider, outcome="failed", facts_found=0, sample_cost=None,
                detail=f"{reason} (retryable={retryable})",
            )
```

Add the imports this needs at the top of the same file:

```python
from collections.abc import Awaitable, Callable, Mapping, Sequence
from datetime import datetime, timezone

from litellm.provider_billing.connector import BillingConnector, registered_connectors
from litellm.provider_billing.runner import LOOKBACK
from litellm.provider_billing.scheduled import build_billing_credential_lookup
from litellm.types.proxy.management_endpoints.team_endpoints import BillingProbeResponse
from litellm.types.proxy.provider_billing import Fetched, FetchFailed, NotConfigured
```

- [ ] **Step 7: Extract the credential lookup so the probe and the job share it**

In `litellm/provider_billing/scheduled.py`, lift the inner `credentials_for` out of
`build_provider_billing_job` into a module-level function, and have the job call it:

```python
def build_billing_credential_lookup(
    *, prisma_client: Any  # any-ok: untyped runtime wrapper
) -> Callable[[str], Awaitable[tuple[str, Mapping[str, str]] | None]]:
    """The stored credential marked for reading a provider's bill.

    Rows come through CredentialsRepository, which that module documents as the only place
    that talks to its table. Values come through CredentialAccessor rather than off the
    row, so the decryption this needs is the same code path the request router uses.
    """

    async def credentials_for(provider: str) -> tuple[str, Mapping[str, str]] | None:
        from litellm.litellm_core_utils.credential_accessor import CredentialAccessor
        from litellm.repositories.credentials_repository import CredentialsRepository

        rows = await CredentialsRepository(prisma_client).find_all()
        for row in rows:
            info = getattr(row, "credential_info", None)
            if not isinstance(info, Mapping):
                continue
            if info.get("purpose") != "billing_ingestion" or info.get("provider") != provider:
                continue
            name = str(getattr(row, "credential_name", ""))
            values = CredentialAccessor.get_credential_values(name)
            if values:
                return (name, {key: str(value) for key, value in values.items()})
        return None

    return credentials_for
```

- [ ] **Step 8: Run every suite**

Run:
```bash
.venv/Scripts/python.exe -m pytest tests/test_litellm/provider_billing/ tests/test_litellm/proxy/management_endpoints/test_provider_reconciliation.py -q -p no:randomly --timeout=300
```
Expected: all pass.

- [ ] **Step 9: Prove the wiring against the running proxy**

```bash
bash ~/.claude/scripts/litellm-dev-up.sh

# Every connector registered, and the two new ones honestly report no credential
for P in openrouter anthropic openai bedrock; do
  echo -n "$P -> "
  curl -s -X POST -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
    "http://127.0.0.1:4001/provider/billing/probe?provider=$P" \
    | python -c "import sys,json; d=json.load(sys.stdin); print(d['outcome'], '|', d.get('detail'))"
done
```

Expected: `openrouter -> fetched`, `anthropic -> not_configured`, `openai -> not_configured`,
`bedrock -> no_connector`. That proves registration, credential lookup, and the probe path
for all three connectors without a provider key. It does **not** prove either new connector
parses a real response; only a real admin key can.

- [ ] **Step 10: Commit**

```bash
git add -A
git commit -m "feat(billing): register the Anthropic and OpenAI connectors, and a probe to verify them"
```

---

### Task 4: Day-grain reconciliation

**Files:**
- Modify: `litellm/proxy/management_endpoints/provider_reconciliation.py`
- Modify: `litellm/types/proxy/management_endpoints/team_endpoints.py`
- Test: `tests/test_litellm/proxy/management_endpoints/test_daily_reconciliation.py`

**Interfaces:**
- Produces: `GET /provider/reconciliation/daily?provider=<name>&days=<n>` returning
  `DailyReconciliationResponse` with `rows: list[DailyReconciliationRow]`, `our_total`,
  `their_total`, `delta`, `days_provider_charged_more`
- `DailyReconciliationRow`: `day`, `our_cost`, `their_cost`, `delta`, `escaped_spend`

`escaped_spend` is true when the provider charged more than we recorded for that day. That
is the discovery the design named: spend on the customer's own provider account that never
came through this gateway.

- [ ] **Step 1: Write the failing test**

```python
from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from litellm.proxy._types import LitellmUserRoles, UserAPIKeyAuth

ADMIN = UserAPIKeyAuth(user_role=LitellmUserRoles.PROXY_ADMIN, api_key="sk-admin", user_id="admin")


def _row(day: str, ours: str | None, theirs: str | None) -> dict:
    return {
        "day": day,
        "our_cost": None if ours is None else Decimal(ours),
        "their_cost": None if theirs is None else Decimal(theirs),
    }


async def _call(rows: list[dict], caller: UserAPIKeyAuth = ADMIN):
    from litellm.proxy.management_endpoints.provider_reconciliation import daily_reconciliation

    client = MagicMock()
    client.db.query_raw = AsyncMock(return_value=rows)
    with patch("litellm.proxy.proxy_server.prisma_client", client):
        return await daily_reconciliation(provider="anthropic", days=7, user_api_key_dict=caller)


@pytest.mark.asyncio
async def test_a_day_the_provider_charged_more_is_flagged_as_escaped_spend():
    """The discovery no gateway can make on its own. If Anthropic billed more than we
    recorded, the difference is traffic that never came through us, and a customer who
    bought a gateway for control needs to know it is leaking."""
    result = await _call([_row("2026-09-12", "10.00", "14.00")])

    assert result.rows[0].escaped_spend is True
    assert result.rows[0].delta == "-4.00"
    assert result.days_provider_charged_more == 1


@pytest.mark.asyncio
async def test_a_day_we_recorded_more_is_not_escaped_spend():
    """Our estimate being high is a pricing problem, not a leak. Calling both the same
    thing would cry wolf on every stale price entry."""
    result = await _call([_row("2026-09-12", "14.00", "10.00")])

    assert result.rows[0].escaped_spend is False
    assert result.days_provider_charged_more == 0


@pytest.mark.asyncio
async def test_a_day_the_provider_has_not_reported_is_not_flagged():
    """Cloud bills land a day or two late. Flagging every recent day as a leak would make
    the signal useless."""
    result = await _call([_row("2026-09-13", "5.00", None)])

    assert result.rows[0].escaped_spend is False
    assert result.rows[0].their_cost is None
    assert result.rows[0].delta is None


@pytest.mark.asyncio
async def test_a_day_only_the_provider_reported_is_entirely_escaped_spend():
    """Nothing came through the gateway that day and the provider still charged. That is
    the strongest form of the signal and must not be dropped for having no gateway row."""
    result = await _call([_row("2026-09-12", None, "9.00")])

    assert result.rows[0].escaped_spend is True
    assert result.rows[0].our_cost == "0"
    assert result.rows[0].their_cost == "9.00"


@pytest.mark.asyncio
async def test_totals_are_fixed_point_strings():
    result = await _call([_row("2026-09-12", "0.0000030", "0.0000025")])

    assert "E" not in result.delta
    assert isinstance(result.our_total, str)


@pytest.mark.asyncio
async def test_only_an_admin_may_read_it():
    from fastapi import HTTPException

    member = UserAPIKeyAuth(user_role=LitellmUserRoles.INTERNAL_USER, api_key="sk-u", user_id="u")
    with pytest.raises(HTTPException) as exc:
        await _call([], caller=member)

    assert exc.value.status_code == 403
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_litellm/proxy/management_endpoints/test_daily_reconciliation.py -q -p no:randomly`
Expected: FAIL, `ImportError: cannot import name 'daily_reconciliation'`

- [ ] **Step 3: Add the response models**

Append to `litellm/types/proxy/management_endpoints/team_endpoints.py`:

```python
class DailyReconciliationRow(BaseModel):
    """One day, charged twice"""

    day: str
    our_cost: str
    their_cost: str | None
    delta: str | None
    escaped_spend: bool
    """True when the provider charged more than this gateway recorded, meaning traffic
    reached the provider without passing through here."""


class DailyReconciliationResponse(BaseModel):
    """Daily totals from a provider that reports aggregates rather than single requests"""

    provider: str
    rows: list[DailyReconciliationRow]
    our_total: str
    their_total: str
    delta: str
    days_provider_charged_more: int
```

- [ ] **Step 4: Add the endpoint**

Append to `litellm/proxy/management_endpoints/provider_reconciliation.py`:

```python
_DAILY_SQL: Final = """
WITH ours AS (
    SELECT date_trunc('day', s."startTime") AS day, SUM(s.spend)::numeric AS our_cost
      FROM "LiteLLM_SpendLogs" s
     WHERE s.custom_llm_provider = $1
       AND s."startTime" >= NOW() - ($2 || ' days')::interval
     GROUP BY 1
), theirs AS (
    SELECT date_trunc('day', f.bucket_start) AS day, SUM(f.billed_cost::numeric) AS their_cost
      FROM "LiteLLM_ProviderUsageFact" f
     WHERE f.provider = $1
       AND f.grain = 'day'
       AND f.bucket_start >= NOW() - ($2 || ' days')::interval
     GROUP BY 1
)
SELECT to_char(COALESCE(ours.day, theirs.day), 'YYYY-MM-DD') AS day,
       ours.our_cost,
       theirs.their_cost
  FROM ours FULL OUTER JOIN theirs ON ours.day = theirs.day
 ORDER BY 1 DESC
"""


@router.get(
    "/provider/reconciliation/daily",
    tags=["provider billing"],
    dependencies=[Depends(user_api_key_auth)],
    response_model=DailyReconciliationResponse,
)
async def daily_reconciliation(
    provider: str = fastapi.Query(description="Which provider to reconcile, for example anthropic"),
    days: int = fastapi.Query(default=7, ge=1, le=31),
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
) -> DailyReconciliationResponse:
    """Daily totals for a provider that reports aggregates rather than single requests.

    A full outer join, because a day the provider charged for and the gateway never saw is
    the single most valuable row here: it is spend that bypassed this gateway entirely.
    """
    from litellm.proxy.proxy_server import prisma_client

    if user_api_key_dict.user_role != LitellmUserRoles.PROXY_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "Only a proxy admin may read cross-team provider reconciliation."},
        )
    if prisma_client is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": CommonProxyErrors.db_not_connected_error.value},
        )

    raw: Final[Sequence[Mapping[str, object]]] = await prisma_client.db.query_raw(_DAILY_SQL, provider, str(days))

    days_seen: Final = tuple(
        (
            str(row.get("day") or ""),
            _decimal(row.get("our_cost")) or Decimal(0),
            _decimal(row.get("their_cost")),
        )
        for row in raw
    )

    our_total: Final = sum((ours for _, ours, _ in days_seen), Decimal(0))
    their_total: Final = sum((theirs for *_, theirs in days_seen if theirs is not None), Decimal(0))

    return DailyReconciliationResponse(
        provider=provider,
        rows=[
            DailyReconciliationRow(
                day=day,
                our_cost=_plain(ours),
                their_cost=None if theirs is None else _plain(theirs),
                delta=None if theirs is None else _plain(ours - theirs),
                escaped_spend=theirs is not None and theirs > ours,
            )
            for day, ours, theirs in days_seen
        ],
        our_total=_plain(our_total),
        their_total=_plain(their_total),
        delta=_plain(our_total - their_total),
        days_provider_charged_more=sum(1 for _, ours, theirs in days_seen if theirs is not None and theirs > ours),
    )
```

- [ ] **Step 5: Run to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_litellm/proxy/management_endpoints/test_daily_reconciliation.py -q -p no:randomly`
Expected: `6 passed`

- [ ] **Step 6: Prove the escaped-spend flag has teeth**

Change `theirs > ours` to `theirs >= ours`, re-run, confirm
`test_a_day_we_recorded_more_is_not_escaped_spend` still passes but
`test_a_day_the_provider_has_not_reported_is_not_flagged` behaviour is unchanged; then
change it to `False` and confirm
`test_a_day_the_provider_charged_more_is_flagged_as_escaped_spend` FAILS. Restore.

- [ ] **Step 7: Verify the SQL against the live database**

The daily SQL has never run. Execute it directly before trusting the endpoint:

```bash
docker exec -i tokeniq_db psql -U llmproxy -d litellm <<'SQL'
WITH ours AS (
    SELECT date_trunc('day', s."startTime") AS day, SUM(s.spend)::numeric AS our_cost
      FROM "LiteLLM_SpendLogs" s
     WHERE s.custom_llm_provider = 'openrouter'
       AND s."startTime" >= NOW() - ('31' || ' days')::interval
     GROUP BY 1
), theirs AS (
    SELECT date_trunc('day', f.bucket_start) AS day, SUM(f.billed_cost::numeric) AS their_cost
      FROM "LiteLLM_ProviderUsageFact" f
     WHERE f.provider = 'openrouter' AND f.grain = 'day'
       AND f.bucket_start >= NOW() - ('31' || ' days')::interval
     GROUP BY 1
)
SELECT to_char(COALESCE(ours.day, theirs.day), 'YYYY-MM-DD') AS day, ours.our_cost, theirs.their_cost
  FROM ours FULL OUTER JOIN theirs ON ours.day = theirs.day ORDER BY 1 DESC;
SQL
```

Expected: rows with `our_cost` populated and `their_cost` null, since every OpenRouter fact
is request grain. That is correct and proves the grain filter works.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat(billing): compare a provider's daily charge against what we recorded"
```

---

## Self-review notes

**Spec coverage.** Plan 2 of the design's five is delivered: both LLM-native connectors,
the day-grain join the design's table names for them, and honest handling of the fact that
neither can be verified here.

**Deliberately not covered.** No UI, per the design's plan 4. No per-team attribution from
these connectors, because the providers report against their own key and workspace rather
than our teams, which the plan states rather than papering over.

**Type consistency.** `BillingProbeResponse`, `DailyReconciliationRow` and
`DailyReconciliationResponse` are defined in Task 3 and Task 4 and used only after.
`build_billing_credential_lookup` is introduced in Task 3 Step 7 and consumed by the probe
in Step 6 of the same task; the extraction must land before the endpoint runs.

**The honest gap.** Task 3 Step 9 proves registration and credential handling for all three
connectors. It does not prove that either new connector parses a real provider response.
Every fixture in Tasks 1 and 2 is transcribed from published API reference documentation.
The first real admin key should be pointed at the probe before anyone trusts a number from
these two.
