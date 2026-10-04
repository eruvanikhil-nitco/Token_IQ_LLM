# Azure and Vertex Billing Connectors Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Read what Azure and Google charge for their model services, completing the six providers Phase 2 promised

**Architecture:** Two more connectors behind the existing contract, each reading its cloud's general billing pipeline rather than an LLM-specific API: the Cost Management query for Azure, the billing export in BigQuery for Google. Neither cloud has a per-model billing endpoint, so both need configuration alongside a credential, and that configuration rides in the encrypted credential values rather than changing the connector contract. Registering a provider then touches five places beyond the connector itself, and this plan treats that as the work rather than an afterthought.

**Tech Stack:** Python 3.12, httpx via the proxy's own client, azure-identity and google-auth (both already installed), pytest; TypeScript for the credential form

**Spec:** `docs/superpowers/specs/2026-09-13-provider-billing-ingestion-design.md`, with the provider table in `docs/superpowers/specs/2026-09-14-token-iq-product-design.md`

**Supersedes:** `docs/superpowers/plans/2026-09-13-cloud-billing-connectors.md`. That plan's Task 1 (`cloud_rows.py`) and Task 2 (Bedrock) are already built and shipped. Its Azure and Vertex tasks are the starting point here but were written before several interfaces existed, and following them literally today would produce two connectors that drop the provider's payload, collide across accounts, and fail the build. Do not read the old plan; this one replaces it.

## Global Constraints

- All work goes on the existing branch `litellm_token_iq`. Never touch `main`, never create a branch or worktree per task
- Do not add `Co-Authored-By` or any Claude attribution to commit messages. This has been slipped in ten times across this work; one cost a git history rewrite and one was caught only after it had been pushed
- Never copy or adapt code from `enterprise/` or `litellm_enterprise`, including anything in history before `728daee2d8`
- No customer or company names anywhere. Azure, AWS, Google Cloud, OpenAI and Anthropic are fine as publicly known vendors
- No customer-visible LiteLLM branding in new dashboard copy
- Python runs only through `C:/Users/NikhilEruva/litellm/.venv/Scripts/python.exe`. Never the system Python 3.14
- Python max line length 120
- No comments except: genuinely complex business logic, a lint/type suppression naming its exact rule in brackets WITH a reason, or a TODO/FIXME with a strong reason. Docstrings are expected and are not comments
- Every suppression names its exact rule in brackets and carries a reason. A rule code with no reason is itself a violation (LIT004) that fails the budget gate. `# type: ignore` is banned (LIT009). `cast(...)` is LIT006 and broke the gate once on this work: narrow properly instead
- LIT001/LIT002: no mutable collections in annotations or construction. LIT010: `: Final` on locals. LIT011: never rebind or mutate a parameter
- Fully typed. No `Any`, no bare `dict`, no `dict[str, Any]`, except at an untyped runtime boundary using the existing `# any-ok: <reason>` pattern
- No `any` in TypeScript
- The lint budget gates crash on this Windows box because `scripts/gate_slot_lock.py` imports `fcntl` unconditionally. Implementers must not run them; the controller verifies the budget
- Run tests in the FOREGROUND. Do not background a test run and wait on it: several agents on this work stalled indefinitely doing exactly that
- Dashboard: never run the full vitest suite; pass explicit paths
- Human-facing text: no emojis, no em dashes, prose over bullets, no trailing period on a paragraph
- Conventional commits

## What already exists, and what a new provider must now satisfy

The original plan predates all of this. A connector written without it would be broken in ways no test would catch.

`litellm/provider_billing/cloud_rows.py` is built and shipped, including `by_column_name(columns, row, name_key="name")`, which pairs a positional row with its column names and returns an empty mapping when the row is shorter than its columns. It exists precisely for Azure's bare `rows` and BigQuery's schema-matched `rows[].f[].v`. Use it; do not read either response by index.

Five things every provider must now satisfy:

1. **The fact key must carry the credential name.** Facts are upserted on `fact_key`. Two accounts for one provider whose keys collide silently overwrite each other day for day, reporting roughly half the true bill with no error anywhere. This was a real bug found and fixed on this branch. The pattern is `f"{provider}:{credential_name}:{day}:{item}"`, as `openai.py:73`, `anthropic.py:104` and `bedrock.py:88` now do.

2. **Every fact must carry `raw`.** It holds the provider's own response for that line and is what the Raw Data screen renders. Storing it was an entire task of an earlier plan and it is now read back.

3. **`FETCH_PROFILES` must gain an entry.** `tests/test_litellm/provider_billing/test_fetch_profile.py` asserts `set(FETCH_PROFILES.keys()) == BILLING_PROVIDERS`. Adding a provider to one and not the other fails the build, which is exactly what that invariant exists to do.

4. **`billing_credential_problem` must know the provider's required fields.** It currently demands an `api_key` for anything that is not bedrock. Azure and Vertex use neither an api_key nor AWS keys, so without this they would be rejected at save time with a message naming a field they do not have.

5. **The dashboard credential form hardcodes its own provider list.** `ui/litellm-dashboard/src/components/model_add/credential_form_helpers.ts` carries `BILLING_PROVIDERS` and per-provider field lists separately from the backend. An admin cannot create a credential for a provider missing from it.

The Provider APIs page and the Usage APIs picker both derive from the backend, so both pick up new providers with no frontend change. That is the payoff of building them that way and should not be undone.

## Honesty constraints specific to this plan

Neither connector can be verified against a real account on this machine: there are no Azure or Google credentials here and no deployment configured for either. Three existing connectors are in the same position. That has three consequences the plan enforces rather than hopes for:

- Every response fixture is transcribed from published API reference, and each test says so in its docstring. A fixture invented to make a test pass is worse than no test, because it encodes a wire format nobody has seen
- Neither provider gets a settling window derived from anything. `fetch_profile.py` already distinguishes Bedrock, whose note derives from the real `SETTLING_HOURS` constant that drives its cutoff, from the three providers whose notes say plainly that the window has not been verified. Azure and Vertex join the second group, and `test_fetch_profile.py` already enforces that those notes contain no digits
- The delivered state is "built, never run against a real account", and the product design table must say so rather than implying coverage

---

## File Structure

**Backend, created**

| File | Responsibility |
|---|---|
| `litellm/provider_billing/azure.py` | The Azure Cost Management connector |
| `litellm/provider_billing/vertex.py` | The BigQuery billing export connector |
| `tests/test_litellm/provider_billing/test_azure_connector.py` | Its tests |
| `tests/test_litellm/provider_billing/test_vertex_connector.py` | Its tests |

**Backend, modified**

| File | Change |
|---|---|
| `litellm/provider_billing/credential_purpose.py` | `BILLING_PROVIDERS` gains two; required-field rules for both |
| `litellm/provider_billing/fetch_profile.py` | A `FetchProfile` each |
| `litellm/provider_billing/startup.py` | Register both connectors |
| `docs/superpowers/specs/2026-09-14-token-iq-product-design.md` | The provider table's status column |

**Dashboard, modified**

| File | Change |
|---|---|
| `src/components/model_add/credential_form_helpers.ts` | The provider list and their field sets |

---

### Task 1: Let the system accept an Azure or Vertex billing credential

**Why first:** until `BILLING_PROVIDERS` knows these two, a credential for either cannot be saved, the connectors have nothing to read, and there is no way to exercise anything end to end. This task also makes the build fail loudly until the profiles exist, which is the invariant doing its job.

**Files:**
- Modify: `litellm/provider_billing/credential_purpose.py`
- Modify: `litellm/provider_billing/fetch_profile.py`
- Test: `tests/test_litellm/provider_billing/test_credential_purpose.py`
- Test: `tests/test_litellm/provider_billing/test_fetch_profile.py`

**Interfaces:**
- Consumes: `BILLING_PROVIDERS`, `billing_credential_problem(credential_info, credential_values, *, require_keys)`, `FetchProfile`, `FETCH_PROFILES`, `_NO_VERIFIED_SETTLING` as they stand
- Produces: `BILLING_PROVIDERS` containing `azure` and `vertex_ai`; `FETCH_PROFILES` with an entry for each; `billing_credential_problem` naming the right fields for both

- [ ] **Step 1: Write the failing credential tests**

Append to `tests/test_litellm/provider_billing/test_credential_purpose.py`:

```python
def test_an_azure_billing_credential_needs_its_subscription_not_an_api_key():
    """Azure authenticates with a directory token and identifies the account by
    subscription. Demanding an api_key would reject a correct credential and name a field
    the admin does not have."""
    from litellm.provider_billing.credential_purpose import billing_credential_problem

    info = {"purpose": "billing_ingestion", "provider": "azure"}

    assert billing_credential_problem(info, {"subscription_id": "sub-123"}, require_keys=True) is None

    problem = billing_credential_problem(info, {}, require_keys=True)
    assert problem is not None
    assert "subscription_id" in problem
    assert "api_key" not in problem


def test_a_vertex_billing_credential_needs_its_project_and_export_table():
    """Google publishes no billing API for this. The only source is a detailed billing
    export the customer enables into BigQuery, so both the project and the table are
    required and neither has a sensible default."""
    from litellm.provider_billing.credential_purpose import billing_credential_problem

    info = {"purpose": "billing_ingestion", "provider": "vertex_ai"}
    complete = {"billing_project_id": "proj-1", "billing_export_table": "billing.gcp_export"}

    assert billing_credential_problem(info, complete, require_keys=True) is None

    problem = billing_credential_problem(info, {"billing_project_id": "proj-1"}, require_keys=True)
    assert problem is not None
    assert "billing_export_table" in problem


def test_neither_cloud_provider_is_asked_for_an_api_key_it_does_not_use():
    """The default branch demands an api_key for anything that is not bedrock. Adding a
    provider without teaching this function about it rejects every credential for it."""
    from litellm.provider_billing.credential_purpose import billing_credential_problem

    for provider, values in (
        ("azure", {"subscription_id": "sub-123"}),
        ("vertex_ai", {"billing_project_id": "p", "billing_export_table": "t"}),
    ):
        info = {"purpose": "billing_ingestion", "provider": provider}
        assert billing_credential_problem(info, values, require_keys=True) is None


def test_require_keys_false_still_accepts_an_incomplete_cloud_credential():
    """A PATCH that changes only the description must not be refused for fields it never
    touched. This is the same allowance the other providers already get."""
    from litellm.provider_billing.credential_purpose import billing_credential_problem

    info = {"purpose": "billing_ingestion", "provider": "azure"}

    assert billing_credential_problem(info, {}, require_keys=False) is None
```

- [ ] **Step 2: Run them and watch them fail**

```bash
C:/Users/NikhilEruva/litellm/.venv/Scripts/python.exe -m pytest tests/test_litellm/provider_billing/test_credential_purpose.py -v
```

Expected: FAIL, because `azure` and `vertex_ai` are not in `BILLING_PROVIDERS` so the provider check rejects them first.

- [ ] **Step 3: Teach credential_purpose about both**

In `litellm/provider_billing/credential_purpose.py`, add both slugs to `BILLING_PROVIDERS`, and add their required-field rules beside the existing `_BEDROCK_REQUIRED`:

```python
_AZURE_REQUIRED: Final = ("subscription_id",)
_VERTEX_REQUIRED: Final = ("billing_project_id", "billing_export_table")
```

Rather than adding two more `if provider == ...` branches to `billing_credential_problem`, express the whole rule as one mapping from provider to its required fields, so a future provider is a data change rather than a code change:

```python
_REQUIRED_FIELDS: Final = MappingProxyType(
    {"bedrock": _BEDROCK_REQUIRED, "azure": _AZURE_REQUIRED, "vertex_ai": _VERTEX_REQUIRED}
)
```

Keep the existing api_key path and its admin-key-prefix check for the providers that have no entry in that mapping. Do not lose the prefix check: it is what stops an ordinary OpenAI or Anthropic key being saved as a billing key and failing every sync later with a 401.

- [ ] **Step 4: Run them and watch them pass**

```bash
C:/Users/NikhilEruva/litellm/.venv/Scripts/python.exe -m pytest tests/test_litellm/provider_billing/test_credential_purpose.py -v
```

- [ ] **Step 5: Watch the invariant test fail, which is the point**

```bash
C:/Users/NikhilEruva/litellm/.venv/Scripts/python.exe -m pytest tests/test_litellm/provider_billing/test_fetch_profile.py -v
```

Expected: FAIL on `test_every_billing_provider_has_a_fetch_profile`, because `FETCH_PROFILES` now has four keys against six providers. Record this in your report: this is the build-time failure that invariant was added to produce, and seeing it fire is evidence it works.

- [ ] **Step 6: Add both fetch profiles**

In `litellm/provider_billing/fetch_profile.py`, add an entry for each, following the existing `_profile(...)` helper. Both take `_NO_VERIFIED_SETTLING` for their settling note, because no window has been verified for either.

Azure: endpoint name `Cost Management query`, address `https://management.azure.com/`, grain `day`. Its delay note must say only what is true, for example that Azure reports cloud cost by day for the whole subscription rather than per model, so the finest comparison against gateway traffic is by service and day, and that recent days can still change.

Vertex: endpoint name `BigQuery billing export`, address `https://bigquery.googleapis.com/`, grain `day`. Its delay note must say that Google publishes no billing API for this, so figures come from a detailed billing export the customer enables into BigQuery, and that the export lands hours behind.

Write both notes in your own words. Do NOT put a number in either settling note: `test_providers_without_a_verified_window_say_so_rather_than_inventing_one` asserts those three notes contain no digits at all, and it will now cover these two.

- [ ] **Step 7: Run the whole provider_billing suite**

```bash
C:/Users/NikhilEruva/litellm/.venv/Scripts/python.exe -m pytest tests/test_litellm/provider_billing/ -v
```

Expected: PASS, including the invariant test now that both halves agree.

- [ ] **Step 8: Commit**

```bash
git add litellm/provider_billing/credential_purpose.py litellm/provider_billing/fetch_profile.py tests/test_litellm/provider_billing
git commit -m "feat(billing): accept azure and vertex billing credentials"
```

---

### Task 2: The Azure connector

**Files:**
- Create: `litellm/provider_billing/azure.py`
- Test: `tests/test_litellm/provider_billing/test_azure_connector.py`

**Interfaces:**
- Consumes: `by_column_name`, `day_from_iso`, `decimal_or_none` from `litellm/provider_billing/cloud_rows.py`; `Fetched`, `FetchFailed`, `NotConfigured`, `FetchResult`, `ProviderUsageFact` from `litellm/types/proxy/provider_billing.py`
- Produces: `AzureBillingConnector(http_client_factory, token_factory)` with `provider = "azure"`, satisfying the `BillingConnector` protocol in `litellm/provider_billing/connector.py`

`token_factory` is `Callable[[Mapping[str, str]], Awaitable[str | None]]`, injected so tests never touch azure-identity and never need a real directory. Returning `None` means no token could be obtained, which is `NotConfigured`, not a failure.

Endpoint: `POST https://management.azure.com/subscriptions/{subscription_id}/providers/Microsoft.CostManagement/query?api-version=2025-03-01`

Credential values: `subscription_id` required; `service_name` optional, defaulting to `Cognitive Services`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_litellm/provider_billing/test_azure_connector.py`. Every fixture below is transcribed from the published Cost Management reference, and the module docstring must say so:

```python
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

    async def token_factory(_values):
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

    async def token_factory(_values):
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
```

- [ ] **Step 2: Run them and watch them fail**

```bash
C:/Users/NikhilEruva/litellm/.venv/Scripts/python.exe -m pytest tests/test_litellm/provider_billing/test_azure_connector.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'litellm.provider_billing.azure'`

- [ ] **Step 3: Write the connector**

Create `litellm/provider_billing/azure.py`, following the shape of `litellm/provider_billing/bedrock.py`, which is the closest existing sibling. Read that file first.

Requirements the tests above pin, stated so you do not have to infer them:

- `provider` returns `"azure"`
- A missing `subscription_id`, or a `token_factory` returning `None`, gives `NotConfigured` with a reason naming what is missing
- Status 429 is `FetchFailed(retryable=True)`; 401 and 403 are `FetchFailed(retryable=False)`; any other non-200 is `FetchFailed(retryable=True)`
- Rows are read with `by_column_name(columns, row)`, never by index. An empty result from it means the row is dropped
- `UsageDate` arrives as `20260917`. Convert it to an ISO date before handing it to `day_from_iso`, or parse it directly; either way an unparseable value drops the row
- The amount goes through `decimal_or_none`; `None` drops the row
- `fact_key` is `f"azure:{credential_name}:{day.date().isoformat()}:{service}"` where `service` is the row's service name, or a constant like `UNGROUPED` when absent
- `raw` is the mapping `by_column_name` returned for that row
- `evidence` is `"reconciled"`, `grain` is `"day"`, `bucket_start` is the parsed day
- Follow `properties.nextLink` until it is absent, with a page cap so a paging bug cannot spin forever. `openai.py` uses `MAX_PAGES_PER_RUN` for the same reason; follow that precedent
- The connector must never raise. The runner contains exceptions anyway, but a connector that raises takes its own run down rather than reporting a failure the sync history can show

Build every collection in one shot with comprehensions wrapped in `tuple()`. Do not seed a list and append in a loop unless there is no alternative, and if there is not, the `# mutable-ok:` reason must say why.

- [ ] **Step 4: Run them and watch them pass**

```bash
C:/Users/NikhilEruva/litellm/.venv/Scripts/python.exe -m pytest tests/test_litellm/provider_billing/test_azure_connector.py -v
```

- [ ] **Step 5: Commit**

```bash
git add litellm/provider_billing/azure.py tests/test_litellm/provider_billing/test_azure_connector.py
git commit -m "feat(billing): read azure model spend from cost management"
```

---

### Task 3: The Vertex connector

**Files:**
- Create: `litellm/provider_billing/vertex.py`
- Test: `tests/test_litellm/provider_billing/test_vertex_connector.py`

**Interfaces:**
- Consumes: `day_from_iso`, `decimal_or_none` from `litellm/provider_billing/cloud_rows.py`; the same result types as Task 2
- Produces: `VertexBillingConnector(http_client_factory, token_factory)` with `provider = "vertex_ai"`

Endpoint: `POST https://bigquery.googleapis.com/bigquery/v2/projects/{billing_project_id}/queries`

Credential values: `billing_project_id` and `billing_export_table` both required; `service_name` optional, defaulting to `Vertex AI`.

BigQuery answers with `rows[].f[].v` matched positionally against `schema.fields`. That is the same hazard `by_column_name` exists for, but the shape differs enough that reading it needs its own small step: extract the `v` values from each row's `f` array first, then pair them with the field names.

**A note on the query:** the billing export table name comes from the customer's configuration, so it cannot be a bound parameter and must be interpolated into the SQL. That is a real injection surface. Validate it against a strict pattern before use, and reject anything that does not match rather than escaping it. A billing export table name is `dataset.table` or `project.dataset.table` with only letters, digits, underscores and dots, so a regexp like `^[A-Za-z0-9_]+(\.[A-Za-z0-9_]+){1,2}$` is both sufficient and safe. Everything else in the query is a bound parameter.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_litellm/provider_billing/test_vertex_connector.py` with a module docstring saying every fixture is transcribed from the published BigQuery REST reference and the documented billing export schema, and that nothing here has run against a real project.

Write out, in full, tests covering:

- a row becoming a fact with the exact cost, asserting `Decimal` equality on a value with more digits than a float holds cleanly, for example `"0.00780515"`
- the fact key carrying the credential name, proven by fetching as two different credential names and asserting the keys differ
- `raw` holding the row's field mapping
- a row whose `f` array is shorter than `schema.fields` being dropped rather than guessed
- fields in a different order still reading correctly
- paging following `pageToken` until absent, with the page cap honoured
- a missing `billing_project_id` giving `NotConfigured`
- a missing `billing_export_table` giving `NotConfigured`
- **a malformed export table name being refused before any request is made**, asserting the http client was never called. Use something like `"billing.export; DROP TABLE x"`. This is the injection guard and it is the most important test in this file
- a token factory returning `None` giving `NotConfigured`
- 403 being `FetchFailed(retryable=False)`, 429 being `FetchFailed(retryable=True)`
- an unparseable day being dropped

Each test body must be written out in full, driving the connector and asserting real values. A docstring or a prose description standing where a test body belongs is a defect.

- [ ] **Step 2: Run them and watch them fail**

```bash
C:/Users/NikhilEruva/litellm/.venv/Scripts/python.exe -m pytest tests/test_litellm/provider_billing/test_vertex_connector.py -v
```

- [ ] **Step 3: Write the connector**

Create `litellm/provider_billing/vertex.py`. Same contract as Azure, with these differences:

- `provider` returns `"vertex_ai"`
- The table name is validated against the pattern above BEFORE the client is constructed or any request is made, and a failure is `NotConfigured` with a reason saying the configured table name is not a valid BigQuery table reference. Do not include the offending value in the message
- The SQL selects the usage day, the service description and the summed cost from the export table, filtered to the service name and the window, with the window and service bound as query parameters
- `fact_key` is `f"vertex_ai:{credential_name}:{day.date().isoformat()}:{sku}"`
- `raw` is the field mapping for that row

- [ ] **Step 4: Run them and watch them pass**

```bash
C:/Users/NikhilEruva/litellm/.venv/Scripts/python.exe -m pytest tests/test_litellm/provider_billing/test_vertex_connector.py -v
```

- [ ] **Step 5: Commit**

```bash
git add litellm/provider_billing/vertex.py tests/test_litellm/provider_billing/test_vertex_connector.py
git commit -m "feat(billing): read vertex model spend from the bigquery billing export"
```

---

### Task 4: Register both, and let an admin create the credentials

**Why these are one task:** registering a connector the dashboard cannot create a credential for is a feature nobody can reach. A reviewer would reject either half alone.

**Files:**
- Modify: `litellm/provider_billing/startup.py`
- Modify: `ui/litellm-dashboard/src/components/model_add/credential_form_helpers.ts`
- Test: `tests/test_litellm/provider_billing/test_startup.py`
- Test: `ui/litellm-dashboard/src/components/model_add/credential_form_helpers.test.ts`

**Interfaces:**
- Consumes: `AzureBillingConnector` and `VertexBillingConnector` from Tasks 2 and 3; `register_billing_connectors(*, prisma_client)` and `registered_connectors()` as they stand
- Produces: six registered connectors; a credential form offering all six

- [ ] **Step 1: Write the failing registration test**

Append to `tests/test_litellm/provider_billing/test_startup.py`:

```python
def test_every_billing_provider_has_a_registered_connector():
    """BILLING_PROVIDERS is what the endpoints and the dashboard enumerate. A provider in
    that set with no connector answers every probe with 'this build ships no connector',
    which reads as a broken deployment rather than a missing feature."""
    from litellm.provider_billing.connector import clear_registry_for_tests, registered_connectors
    from litellm.provider_billing.credential_purpose import BILLING_PROVIDERS
    from litellm.provider_billing.startup import register_billing_connectors

    clear_registry_for_tests()
    register_billing_connectors(prisma_client=MagicMock())

    assert {connector.provider for connector in registered_connectors()} == BILLING_PROVIDERS
```

Add `MagicMock` to the file's imports if it is not already there. Follow the existing tests in that file for how they set up and tear down the registry.

- [ ] **Step 2: Run it and watch it fail**

```bash
C:/Users/NikhilEruva/litellm/.venv/Scripts/python.exe -m pytest tests/test_litellm/provider_billing/test_startup.py -v
```

Expected: FAIL, four registered against six providers.

- [ ] **Step 3: Register both connectors**

In `litellm/provider_billing/startup.py`, add both to the `candidates` tuple alongside the existing four, constructing each with the http client factory already defined there and a token factory.

For the token factories: azure-identity and google-auth are both installed, but neither must be imported at module scope, because `startup.py` is imported on every proxy boot and a missing cloud SDK would then break deployments that use neither. Import inside the factory and return `None` if the import or the token acquisition fails, since `None` is already the "not configured" signal both connectors understand.

- [ ] **Step 4: Run the backend suite**

```bash
C:/Users/NikhilEruva/litellm/.venv/Scripts/python.exe -m pytest tests/test_litellm/provider_billing/ -v
```

- [ ] **Step 5: Write the failing dashboard test**

Append to `ui/litellm-dashboard/src/components/model_add/credential_form_helpers.test.ts`:

```ts
describe("billing providers", () => {
  it("offers every provider this build can read a bill from", () => {
    // The backend enumerates six. A provider missing here cannot have a credential
    // created for it at all, so its connector is unreachable however well it works.
    expect(BILLING_PROVIDERS.map((provider) => provider.value)).toEqual([
      "openai",
      "anthropic",
      "openrouter",
      "bedrock",
      "azure",
      "vertex_ai",
    ]);
  });

  it("asks azure for its subscription rather than an api key", () => {
    const payload = buildCredentialPayload({
      credential_name: "azure-prod",
      purpose: "billing_access",
      billing_provider: "azure",
      subscription_id: "sub-123",
      api_key: "sk-should-not-be-sent",
    });

    expect(payload.credential_values).toEqual({ subscription_id: "sub-123" });
  });

  it("asks vertex for its project and export table", () => {
    const payload = buildCredentialPayload({
      credential_name: "vertex-prod",
      purpose: "billing_access",
      billing_provider: "vertex_ai",
      billing_project_id: "proj-1",
      billing_export_table: "billing.gcp_export",
    });

    expect(payload.credential_values).toEqual({
      billing_project_id: "proj-1",
      billing_export_table: "billing.gcp_export",
    });
  });
});
```

The second test matters beyond field mapping: both purposes share this form, so a serving key typed before switching to billing access must not be submitted as part of a cloud credential.

- [ ] **Step 6: Run it and watch it fail, then implement**

```bash
cd ui/litellm-dashboard
npx vitest run src/components/model_add/credential_form_helpers.test.ts
```

Add both providers to `BILLING_PROVIDERS` with the labels `Azure OpenAI` and `Google Vertex AI`, add their field lists, and extend `buildCredentialPayload` so each provider submits its own fields. The existing shape is a ternary on `provider === "bedrock"`; replace it with a mapping from provider to its field list, so a future provider is a data change. Add every new field to `BILLING_KEY_FIELDS`, which is what the purpose-switch reset uses to clear values between purposes.

- [ ] **Step 7: Run the affected dashboard tests**

```bash
cd ui/litellm-dashboard
npx vitest run src/components/model_add/credential_form_helpers.test.ts src/components/model_add/CredentialModal.test.tsx
```

- [ ] **Step 8: Prove it against the running proxy**

```bash
bash ~/.claude/scripts/litellm-dev-up.sh
curl -s -H "Authorization: Bearer sk-1234" "http://localhost:4001/provider/connections" | head -c 2000
```

Azure and Vertex must both appear, each `not_connected` with no accounts, each carrying the fetch profile Task 1 gave it. Neither can reach `healthy` here, because there are no credentials for either on this machine, and that is the correct state rather than a failure.

Then check the probe reports honestly for a provider with a connector but no credential:

```bash
curl -s -X POST -H "Authorization: Bearer sk-1234" "http://localhost:4001/provider/billing/probe?provider=azure"
```

Expected: `not_configured`, naming what to create. Not `no_connector`, which would mean registration did not take.

- [ ] **Step 9: Commit**

```bash
git add litellm/provider_billing/startup.py tests/test_litellm/provider_billing/test_startup.py ui/litellm-dashboard/src/components/model_add
git commit -m "feat(billing): register the azure and vertex connectors"
```

---

### Task 5: Say plainly what was and was not verified

**Why this is a task and not a footnote:** the product design table currently says Azure and Vertex are "Planned". After this branch they are built but have never run against a real account, which is a different and weaker claim than "works". Three existing connectors are in the same state. A status table that implies coverage nobody has tested is the kind of thing that gets repeated in a conversation with a customer.

**Files:**
- Modify: `docs/superpowers/specs/2026-09-14-token-iq-product-design.md`

- [ ] **Step 1: Update the provider table**

In the "Provider APIs" table, change the Azure OpenAI and Google Vertex rows from `Planned` to the same wording the other unverified connectors carry: built, never run against a real account. Keep each row's "What we read" and "Detail level" columns accurate to what the connector actually does: Azure reads the Cost Management query at day grain, Vertex reads the BigQuery billing export at day grain.

- [ ] **Step 2: Correct the status line above the table**

The "Where the product stands" table has a Provider API ingestion row listing what is built. Update it so the sentence about Azure and Vertex being planned is no longer there, and so it says six connectors exist of which one, OpenRouter, is proven against real traffic and five have never run against a real account.

Do not overstate. "Built" is true; "working" is not established for any of the five.

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/specs/2026-09-14-token-iq-product-design.md
git commit -m "docs: record azure and vertex as built but unverified"
```

---

## Self-Review

**Spec coverage**

| Requirement | Where |
|---|---|
| Azure OpenAI connector, Cost Management query, day grain | Task 2 |
| Google Vertex connector, BigQuery billing export, day grain | Task 3 |
| Both behind the existing connector contract, no contract change | Tasks 2 and 3 |
| Configuration rides in encrypted credential values | Task 1 for validation, Task 4 for the form |
| No new dependencies | Task 4: azure-identity and google-auth are already installed and imported lazily |
| Neither verifiable on this machine | Stated in both test module docstrings and recorded in Task 5 |

**Interfaces this plan must satisfy that the superseded plan did not know about**

| Requirement | Where enforced |
|---|---|
| fact_key carries the credential name | Tasks 2 and 3, each with a two-credential collision test |
| Every fact carries `raw` | Tasks 2 and 3, each with a payload test |
| `FETCH_PROFILES` gains an entry per provider | Task 1, and the existing invariant test fails until it does |
| Settling notes contain no invented number | Task 1, and the existing no-digits test now covers both |
| `billing_credential_problem` knows the required fields | Task 1 |
| The dashboard credential form offers the provider | Task 4 |

**Gaps accepted on purpose:** neither connector can be proven against a real account here, so Task 4's live proof confirms registration and honest "not configured" reporting rather than a successful fetch. The Provider APIs page and the Usage APIs picker both derive from the backend and need no change, which is verified in Task 4 Step 8 rather than assumed.

**Type consistency**

- `AzureBillingConnector(http_client_factory, token_factory)` and `VertexBillingConnector(http_client_factory, token_factory)` take the same two injected collaborators, and both are constructed that way in Task 4
- `token_factory` is `Callable[[Mapping[str, str]], Awaitable[str | None]]` in both, and `None` means `NotConfigured` in both
- The provider slugs are `azure` and `vertex_ai` everywhere: in `BILLING_PROVIDERS`, in `FETCH_PROFILES`, in each connector's `provider` property, in the fact keys, and in the dashboard list
- `by_column_name`, `day_from_iso` and `decimal_or_none` are used with the signatures they already have in `cloud_rows.py`, which this plan does not modify
