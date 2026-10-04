# Provider Connections Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn provider billing ingestion from a silent background job into a connection a customer can see, trust and run more than one account against, and give it a home in the sidebar under Data Sources > Provider APIs

**Architecture:** Three layers, built bottom up. The store gains a sync-run table so every fetch attempt leaves a record, and provider facts finally keep the payload the provider sent. The ingestion layer stops assuming one account per provider: the credential lookup returns every billing credential for a provider, the runner drives each one separately, and the fact key carries the credential so two accounts cannot overwrite each other. The read layer adds two endpoints, one deriving a connection state per account from the sync history and one listing that history, and the dashboard renders them as one tab per provider with Connection, What We Fetch and Sync History inside

**Tech Stack:** Python 3.12, FastAPI, Prisma (prisma-client-py) on Postgres, pytest; Next.js 15, TypeScript, shadcn/Base UI primitives, react-hook-form, TanStack Query, vitest with Testing Library

**Spec:** `docs/superpowers/specs/2026-09-15-cost-platform-reference.md` (the four connection states, What We Fetch, Sync History) and `docs/superpowers/specs/2026-09-14-token-iq-product-design.md` (the agreed sidebar tree and the provider table)

## Global Constraints

- All work goes on the existing branch `litellm_token_iq`. Never touch `main`, never create a branch per task
- Do not add `Co-Authored-By: Claude` or any Claude attribution to commit messages. No `claude/` prefix, no `/` in branch names
- Never copy or adapt code from `enterprise/` or `litellm_enterprise`, including anything in history before `728daee2d8`
- No customer or company names anywhere in code, commits or docs. Publicly known providers (OpenAI, Anthropic, AWS Bedrock, OpenRouter) are fine because we support them generally
- No customer-visible LiteLLM branding in new dashboard copy
- Python runs only through `C:/Users/NikhilEruva/litellm/.venv/Scripts/python.exe`. Never the system Python 3.14
- Python max line length is 120
- No comments unless they explain genuinely complex business logic, or are a lint/type suppression with its rule in brackets and a reason, or a TODO/FIXME with a strong reason. Module and function docstrings are not comments and are expected
- Every lint or type suppression names its exact rule in brackets with a reason, e.g. `# noqa: BLE001  # <reason>`. `# type: ignore` is banned (LIT009)
- LIT001/LIT002: no mutable collections in annotations or construction. Build in one shot with comprehensions wrapped in `tuple()` / `MappingProxyType()` / `frozenset()`. `# mutable-ok: <reason>` is a genuine last resort. The repo budget has roughly five violations of headroom, so a task that needs more than one is doing it wrong
- LIT010: annotate every local with `: Final`. LIT011: never rebind or mutate a parameter
- LIT012: qualify every TypedDict field with `ReadOnly[...]`
- Fully typed. No `Any`, no bare `dict`, no `dict[str, Any]`. When a runtime collaborator is untyped (prisma client, httpx wrapper), validate at the caller with Pydantic or annotate the single boundary parameter with `Any` plus `# any-ok: <reason>`, matching what `litellm/provider_billing/scheduled.py` already does
- Prisma migrations change schema only. No `UPDATE`, `DELETE`, `MERGE` or `INSERT ... SELECT`. `tests/code_coverage_tests/check_migrations_no_data_rewrites.py` enforces this
- Backend tests live in `tests/test_litellm/` mirroring `litellm/`. Extend the mapped test file for a change to existing code; create a new one only for a new module
- Dashboard tests: never run the full vitest suite. Pass explicit paths. Never put tokens in `localStorage`
- `src/lib/http/schema.d.ts` is generated. After changing a backend route or response model the dashboard consumes, regenerate it. On this box the generator defaults to `python3` and fails, so run: `LITELLM_PYTHON="C:/Users/NikhilEruva/litellm/.venv/Scripts/python.exe" PYTHONUTF8=1 PYTHONPATH="C:/Users/NikhilEruva/litellm" npm run gen:api`
- Never remove or merge an existing UI tab or sidebar entry. This plan only adds one
- Human-facing text (commits, docs, UI copy): no emojis, no em dashes, no "not X, it's Y", prose over bullets, no trailing period on a paragraph
- Conventional commits for every commit message
- Run the proxy only with `~/.claude/scripts/litellm-dev-up.sh` (port 4001, dev key `sk-1234`). After adding a model to `schema.prisma`, re-run `python -m prisma generate --schema=schema.prisma` with `.venv/Scripts` on PATH, or every ORM read of the new model 500s

---

## File Structure

**Backend, created**

| File | Responsibility |
|---|---|
| `litellm/repositories/provider_sync_run_repository.py` | The only place that talks to `LiteLLM_ProviderSyncRun` |
| `litellm/provider_billing/connection_state.py` | Pure rules turning a credential plus its last sync run into one of the four states |
| `litellm/provider_billing/fetch_profile.py` | What we fetch per provider: endpoint, grain, cadence, window, and honest notes on delay and history |
| `litellm/proxy/management_endpoints/provider_connections.py` | `GET /provider/connections` and `GET /provider/sync-history` |
| `litellm-proxy-extras/litellm_proxy_extras/migrations/20260916000000_provider_sync_run/migration.sql` | Creates the sync-run table |

**Backend, modified**

| File | Change |
|---|---|
| `litellm/types/proxy/provider_billing.py` | `BillingCredential`, `SyncOutcome`, `ProviderSyncRun` |
| `litellm/repositories/provider_usage_fact_repository.py` | Persist `raw`; add `counts_by_credential` |
| `litellm/provider_billing/openai.py`, `anthropic.py`, `bedrock.py`, `openrouter.py` | Carry the provider's own payload into `raw`; put the credential in the fact key for the three day-grain providers |
| `litellm/provider_billing/runner.py` | Loop over every credential for a provider, and record each attempt |
| `litellm/provider_billing/scheduled.py` | Credential lookup returns every billing credential for a provider |
| `litellm/proxy/management_endpoints/provider_reconciliation.py` | Probe follows the new lookup shape |
| `litellm/proxy/proxy_server.py` | Register the new router |
| `schema.prisma` | The `LiteLLM_ProviderSyncRun` model |

**Dashboard, created**

| File | Responsibility |
|---|---|
| `src/components/add_model/providerFieldDefaults.ts` | Which declared provider defaults still need seeding into form state |
| `src/app/(dashboard)/provider-apis/page.tsx` | Route shell |
| `src/app/(dashboard)/provider-apis/_components/ProviderApisPanel.tsx` | One tab per provider |
| `src/app/(dashboard)/provider-apis/_components/ConnectionTab.tsx` | State, accounts, read-only badge |
| `src/app/(dashboard)/provider-apis/_components/WhatWeFetchTab.tsx` | Endpoint, grain, cadence, window, notes |
| `src/app/(dashboard)/provider-apis/_components/SyncHistoryTab.tsx` | Recent runs |
| `src/app/(dashboard)/hooks/providerApis/useProviderConnections.ts` | Query for `/provider/connections` |
| `src/app/(dashboard)/hooks/providerApis/useProviderSyncHistory.ts` | Query for `/provider/sync-history` |

**Dashboard, modified**

| File | Change |
|---|---|
| `src/components/add_model/provider_specific_fields.tsx` | Seed declared defaults into form state so they are saved |
| `src/components/networking.tsx` | `providerConnectionsCall`, `providerSyncHistoryCall` |
| `src/components/leftnav.tsx` | Provider APIs entry in DATA SOURCES |
| `src/components/page_metadata.ts`, `src/utils/migratedPages.ts` | Register the page |

---

### Task 1: Keep the payload the provider sent

**Why:** the Raw Data tab in Usage / APIs is meant to show every provider field. `LiteLLM_ProviderUsageFact.raw` exists in the schema and in the database, and nothing has ever written to it, so today the provider's own line item is thrown away the moment it is parsed. Nothing downstream can be built until the column is filled

**Files:**
- Modify: `litellm/repositories/provider_usage_fact_repository.py:11-29`
- Modify: `litellm/provider_billing/openai.py:52-83`
- Modify: `litellm/provider_billing/anthropic.py:63-97`
- Modify: `litellm/provider_billing/bedrock.py:47-99`
- Modify: `litellm/provider_billing/openrouter.py:117-131`
- Test: `tests/test_litellm/repositories/test_provider_usage_fact_repository.py`
- Test: `tests/test_litellm/provider_billing/test_openai_connector.py`
- Test: `tests/test_litellm/provider_billing/test_anthropic_connector.py`
- Test: `tests/test_litellm/provider_billing/test_bedrock_connector.py`
- Test: `tests/test_litellm/provider_billing/test_openrouter_connector.py`

**Interfaces:**
- Consumes: `ProviderUsageFact` from `litellm/types/proxy/provider_billing.py`, which already declares `raw: Mapping[str, object] | None = None`
- Produces: every fact written by every connector carries `raw`, and `ProviderUsageFactRepository.upsert_many` persists it to the `raw` JSONB column

- [ ] **Step 1: Write the failing repository test**

Append to `tests/test_litellm/repositories/test_provider_usage_fact_repository.py`:

```python
@pytest.mark.asyncio
async def test_the_providers_own_payload_is_written_to_the_raw_column():
    """Raw Data shows the provider's fields verbatim. A fact whose payload was dropped at
    parse time can never be shown, and the provider will not serve that day again."""
    from litellm.repositories.provider_usage_fact_repository import ProviderUsageFactRepository

    table = MagicMock()
    table.upsert = AsyncMock()
    client = MagicMock()
    client.db.litellm_providerusagefact = table

    fact = ProviderUsageFact(
        fact_key="openai:acct:2026-09-15:gpt-4o",
        provider="openai",
        credential_name="acct",
        grain="day",
        bucket_start=datetime(2026, 9, 15, tzinfo=timezone.utc),
        evidence="reconciled",
        billed_cost=Decimal("1.25"),
        raw={"line_item": "gpt-4o", "amount": {"value": 1.25, "currency": "usd"}},
    )

    await ProviderUsageFactRepository(client).upsert_many([fact])

    written = table.upsert.await_args.kwargs["data"]["create"]
    assert written["raw"] == {"line_item": "gpt-4o", "amount": {"value": 1.25, "currency": "usd"}}
```

Add whatever of `MagicMock`, `AsyncMock`, `datetime`, `timezone`, `Decimal`, `pytest` and `ProviderUsageFact` the file does not already import.

- [ ] **Step 2: Run it and watch it fail**

```bash
C:/Users/NikhilEruva/litellm/.venv/Scripts/python.exe -m pytest tests/test_litellm/repositories/test_provider_usage_fact_repository.py -v
```

Expected: FAIL with `KeyError: 'raw'`

- [ ] **Step 3: Persist the column**

In `litellm/repositories/provider_usage_fact_repository.py`, add one entry to the mapping returned by `_row`, directly after `"cache_write_tokens"`:

```python
        "raw": None if fact.raw is None else dict(fact.raw),
    }
```

Prisma takes a plain dict for a `Json?` field. `dict(...)` copies the connector's mapping so nothing downstream can mutate what was written.

- [ ] **Step 4: Run it and watch it pass**

```bash
C:/Users/NikhilEruva/litellm/.venv/Scripts/python.exe -m pytest tests/test_litellm/repositories/test_provider_usage_fact_repository.py -v
```

Expected: PASS

- [ ] **Step 5: Write the four failing connector tests**

Append one to each connector's test file. OpenAI, in `tests/test_litellm/provider_billing/test_openai_connector.py`:

```python
def test_each_fact_keeps_the_result_openai_sent():
    from litellm.provider_billing.openai import _facts_from

    facts = _facts_from(
        [
            {
                "start_time": 1789344000,
                "results": [{"line_item": "gpt-4o", "amount": {"value": 1.25, "currency": "usd"}}],
            }
        ],
        "acct",
    )

    assert facts[0].raw == {"line_item": "gpt-4o", "amount": {"value": 1.25, "currency": "usd"}}
```

Anthropic, in `tests/test_litellm/provider_billing/test_anthropic_connector.py`. Anthropic sums several token-type rows into one fact per model, so the fact keeps every row that fed it:

```python
def test_each_fact_keeps_every_anthropic_row_that_fed_it():
    from litellm.provider_billing.anthropic import _facts_from

    facts = _facts_from(
        [
            {
                "starting_at": "2026-09-15T00:00:00Z",
                "results": [
                    {"model": "claude-sonnet-4", "amount": "100", "token_type": "input"},
                    {"model": "claude-sonnet-4", "amount": "200", "token_type": "output"},
                ],
            }
        ],
        "acct",
    )

    assert facts[0].raw == {
        "starting_at": "2026-09-15T00:00:00Z",
        "results": [
            {"model": "claude-sonnet-4", "amount": "100", "token_type": "input"},
            {"model": "claude-sonnet-4", "amount": "200", "token_type": "output"},
        ],
    }
```

Bedrock, in `tests/test_litellm/provider_billing/test_bedrock_connector.py`:

```python
def test_each_fact_keeps_the_cost_explorer_group_it_came_from():
    from datetime import datetime, timezone

    from litellm.provider_billing.bedrock import _facts_from

    group = {"Keys": ["USE1-BedrockTokens"], "Metrics": {"UnblendedCost": {"Amount": "3.50", "Unit": "USD"}}}
    facts = _facts_from(
        [{"TimePeriod": {"Start": "2026-09-14"}, "Groups": [group]}],
        "acct",
        datetime(2026, 9, 16, tzinfo=timezone.utc),
    )

    assert facts[0].raw == group
```

OpenRouter, in `tests/test_litellm/provider_billing/test_openrouter_connector.py`. This connector builds facts inside `fetch`, so drive it the way the existing tests in that file already drive it, and assert on the resulting fact:

```python
@pytest.mark.asyncio
async def test_each_fact_keeps_the_generation_body_openrouter_sent():
    from litellm.provider_billing.openrouter import OpenRouterBillingConnector

    body = {"id": "gen-1", "total_cost": "0.004", "model": "openai/gpt-4o"}
    response = MagicMock()
    response.status_code = 200
    response.json = MagicMock(return_value={"data": body})
    client = MagicMock()
    client.get = AsyncMock(return_value=response)

    async def unpriced():
        return ("gen-1",)

    result = await OpenRouterBillingConnector(
        unpriced_request_ids=unpriced, http_client_factory=lambda: client
    ).fetch(
        since=datetime(2026, 9, 15, tzinfo=timezone.utc),
        until=datetime(2026, 9, 16, tzinfo=timezone.utc),
        credential_name="acct",
        credential_values={"api_key": "k"},
    )

    assert result.facts[0].raw == body
```

- [ ] **Step 6: Run the four and watch them fail**

```bash
C:/Users/NikhilEruva/litellm/.venv/Scripts/python.exe -m pytest tests/test_litellm/provider_billing/test_openai_connector.py tests/test_litellm/provider_billing/test_anthropic_connector.py tests/test_litellm/provider_billing/test_bedrock_connector.py tests/test_litellm/provider_billing/test_openrouter_connector.py -v
```

Expected: four FAILs, each `assert None == {...}`

- [ ] **Step 7: Carry the payload through each connector**

OpenAI, `litellm/provider_billing/openai.py`, inside the `facts.append(ProviderUsageFact(...))` call, add one argument after `model=`:

```python
                    raw=dict(item),
```

Anthropic, `litellm/provider_billing/anthropic.py`. The per-model accumulator currently keeps only the running total, so it must also keep the rows. Replace the `per_model` accumulator and the `facts.extend(...)` generator in `_facts_from` with:

```python
        per_model: dict[str, Decimal] = defaultdict(Decimal)  # mutable-ok: accumulator per bucket
        rows_for: dict[str, list[Mapping[str, object]]] = defaultdict(list)  # mutable-ok: accumulator per bucket
        for item in results:
            if not isinstance(item, Mapping):
                continue
            cents = _decimal(item.get("amount"))
            if cents is None:
                continue
            model = item.get("model")
            key = model if isinstance(model, str) else UNATTRIBUTED
            per_model[key] += cents / _CENTS_PER_DOLLAR
            rows_for[key].append(dict(item))

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
                raw={"starting_at": bucket.get("starting_at"), "results": list(rows_for[model])},
            )
            for model, dollars in sorted(per_model.items())
        )
```

Bedrock, `litellm/provider_billing/bedrock.py`. `_amounts_in` currently discards the group it read the amount from, so widen its tuple to three elements. Replace its two `return` statements:

```python
        return tuple(
            (
                keys[0] if isinstance(keys := group.get("Keys"), Sequence) and keys and isinstance(keys[0], str)
                else UNGROUPED,
                metric.get("Amount"),
                dict(group),
            )
            for group in groups
            if isinstance(group, Mapping)
            and isinstance(metrics := group.get("Metrics"), Mapping)
            and isinstance(metric := metrics.get(METRIC), Mapping)
        )

    total: Final = period.get("Total")
    if isinstance(total, Mapping) and isinstance(metric := total.get(METRIC), Mapping):
        return ((UNGROUPED, metric.get("Amount"), dict(total)),)
    return ()
```

and update `_facts_from` to unpack and store it:

```python
            for usage_type, raw, group in _amounts_in(period)
            if (amount := decimal_or_none(raw)) is not None
```

with `raw=group,` added to the `ProviderUsageFact(...)` construction after `model=`. Adjust `_amounts_in`'s return annotation to match the widened tuple.

OpenRouter, `litellm/provider_billing/openrouter.py`, in the `facts.append(ProviderUsageFact(...))` call, add after `output_tokens=`:

```python
                    raw=dict(data),
```

- [ ] **Step 8: Run the four and watch them pass**

```bash
C:/Users/NikhilEruva/litellm/.venv/Scripts/python.exe -m pytest tests/test_litellm/provider_billing/ tests/test_litellm/repositories/test_provider_usage_fact_repository.py -v
```

Expected: PASS, with no regressions in the rest of `tests/test_litellm/provider_billing/`

- [ ] **Step 9: Commit**

```bash
git add litellm/provider_billing litellm/repositories/provider_usage_fact_repository.py tests/test_litellm/provider_billing tests/test_litellm/repositories/test_provider_usage_fact_repository.py
git commit -m "feat(billing): keep the payload each provider sent on every usage fact"
```

---

### Task 2: Several accounts per provider

**Why:** a company that runs two OpenAI organisations, or one Bedrock account per environment, has two billing credentials for the same provider. Today `build_billing_credential_lookup` returns the first match and the rest are silently ignored, and worse, the OpenAI, Anthropic and Bedrock fact keys carry no credential, so if the runner ever did read a second account the two would overwrite each other row for row and the total would be wrong with no error anywhere

OpenRouter's key stays `openrouter:{generation_id}` on purpose. A generation id is unique across OpenRouter, so it cannot collide between accounts, and it is the only provider with real stored rows on any deployment. Changing its key would leave those rows orphaned under the old format and double-count them in the daily reconciliation, which no migration is allowed to clean up

**Files:**
- Modify: `litellm/types/proxy/provider_billing.py`
- Modify: `litellm/provider_billing/scheduled.py:55-89`, `92-118`
- Modify: `litellm/provider_billing/runner.py:32-75`
- Modify: `litellm/provider_billing/openai.py:73`, `anthropic.py:86`, `bedrock.py:87`
- Modify: `litellm/proxy/management_endpoints/provider_reconciliation.py:140-230`
- Modify: `litellm/types/proxy/management_endpoints/team_endpoints.py:200-209`
- Test: `tests/test_litellm/provider_billing/test_runner.py`
- Test: `tests/test_litellm/provider_billing/test_scheduled_registration.py`
- Test: `tests/test_litellm/provider_billing/test_openai_connector.py`

**Interfaces:**
- Consumes: `ProviderUsageFact`, `Fetched`, `NotConfigured`, `FetchFailed` from `litellm/types/proxy/provider_billing.py`
- Produces:
  - `BillingCredential(name: str, values: Mapping[str, str])`, a frozen slotted dataclass in `litellm/types/proxy/provider_billing.py`
  - `build_billing_credentials_lookup(*, prisma_client: Any) -> Callable[[str], Awaitable[tuple[BillingCredential, ...]]]` in `litellm/provider_billing/scheduled.py`, replacing `build_billing_credential_lookup`
  - `run_ingestion(*, repository: ProviderUsageFactRepository, connectors: Sequence[BillingConnector], credentials_for: Callable[[str], Awaitable[tuple[BillingCredential, ...]]], now: datetime) -> IngestionReport`, same `IngestionReport(written, skipped, failed)` shape

- [ ] **Step 1: Write the failing runner test**

Replace the `_creds` helper in `tests/test_litellm/provider_billing/test_runner.py` with one that answers with a tuple, and update `_run`'s default:

```python
from litellm.types.proxy.provider_billing import BillingCredential


async def _creds(_provider: str) -> tuple[BillingCredential, ...]:
    return (BillingCredential(name="c", values={"api_key": "k"}),)
```

The `no_creds` helper inside `test_a_provider_with_no_credential_is_skipped_quietly` returns `()` instead of `None`, and its annotation becomes `tuple[BillingCredential, ...]`.

Then append the new case:

```python
@pytest.mark.asyncio
async def test_every_account_for_a_provider_is_fetched_separately():
    """A company with two OpenAI organisations has two billing credentials. Reading only the
    first silently halves their reported bill, and nothing in the product would say so."""
    seen: list[str] = []

    class _Recording(_Connector):
        async def fetch(self, *, credential_name: str, **_: object):
            seen.append(credential_name)
            return Fetched(facts=(_fact(),), watermark=NOW)

    async def two(_provider: str) -> tuple[BillingCredential, ...]:
        return (
            BillingCredential(name="prod", values={"api_key": "k1"}),
            BillingCredential(name="staging", values={"api_key": "k2"}),
        )

    report = await _run((_Recording("openai", None),), two)

    assert seen == ["prod", "staging"]
    assert report.written == 2


@pytest.mark.asyncio
async def test_one_account_failing_does_not_stop_the_others_on_the_same_provider():
    async def two(_provider: str) -> tuple[BillingCredential, ...]:
        return (
            BillingCredential(name="broken", values={"api_key": "k1"}),
            BillingCredential(name="fine", values={"api_key": "k2"}),
        )

    class _PerCredential(_Connector):
        async def fetch(self, *, credential_name: str, **_: object):
            if credential_name == "broken":
                return FetchFailed(reason="401", retryable=False)
            return Fetched(facts=(_fact(),), watermark=NOW)

    report = await _run((_PerCredential("openai", None),), two)

    assert report.written == 1
    assert report.failed == ("openai",)
```

- [ ] **Step 2: Write the failing fact-key test**

Append to `tests/test_litellm/provider_billing/test_openai_connector.py`:

```python
def test_two_openai_accounts_do_not_share_a_fact_key():
    """fact_key is the upsert key. Without the credential in it, the second account's row for
    a day overwrites the first account's row for that day and the total silently halves."""
    from litellm.provider_billing.openai import _facts_from

    bucket = [
        {
            "start_time": 1789344000,
            "results": [{"line_item": "gpt-4o", "amount": {"value": 1.25, "currency": "usd"}}],
        }
    ]

    prod = _facts_from(bucket, "prod")
    staging = _facts_from(bucket, "staging")

    assert prod[0].fact_key != staging[0].fact_key
```

- [ ] **Step 3: Run both and watch them fail**

```bash
C:/Users/NikhilEruva/litellm/.venv/Scripts/python.exe -m pytest tests/test_litellm/provider_billing/test_runner.py tests/test_litellm/provider_billing/test_openai_connector.py -v
```

Expected: the runner cases FAIL with `AttributeError` or `TypeError` on the tuple credential, and the fact-key case FAILs with `assert 'openai:2026-09-15:gpt-4o' != 'openai:2026-09-15:gpt-4o'`

- [ ] **Step 4: Add the credential type**

In `litellm/types/proxy/provider_billing.py`, after the `ProviderUsageFact` dataclass:

```python
@dataclass(frozen=True, slots=True)
class BillingCredential:
    """One stored credential a connector may read a provider's bill with."""

    name: str
    values: Mapping[str, str]
```

- [ ] **Step 5: Return every matching credential**

In `litellm/provider_billing/scheduled.py`, replace `build_billing_credential_lookup` with:

```python
def build_billing_credentials_lookup(
    *, prisma_client: Any  # any-ok: PrismaClient is an untyped runtime wrapper
) -> Callable[[str], Awaitable[tuple[BillingCredential, ...]]]:
    """Every stored credential marked for reading a provider's bill.

    Rows come through CredentialsRepository, which that module documents as the only place
    that talks to its table. Values come through CredentialAccessor rather than off the row,
    so the decryption this needs is the same code path the request router uses.
    """

    async def credentials_for(provider: str) -> tuple[BillingCredential, ...]:
        from litellm.litellm_core_utils.credential_accessor import CredentialAccessor
        from litellm.repositories.credentials_repository import CredentialsRepository

        rows: Final = await CredentialsRepository(prisma_client).find_all()
        return tuple(
            BillingCredential(name=name, values={key: str(value) for key, value in values.items()})
            for row in rows
            if isinstance(info := getattr(row, "credential_info", None), Mapping)
            and is_billing_credential(info)
            and info.get("provider") == provider
            and (name := str(getattr(row, "credential_name", "")))
            and (values := CredentialAccessor.get_credential_values(name))
        )

    return credentials_for
```

Add `BillingCredential` to the imports from `litellm.types.proxy.provider_billing`. In `build_provider_billing_job`, change `build_billing_credential_lookup(...)` to `build_billing_credentials_lookup(...)`.

- [ ] **Step 6: Drive every credential from the runner**

In `litellm/provider_billing/runner.py`, replace the body of the `for connector in connectors:` loop:

```python
    for connector in connectors:
        credentials = await credentials_for(connector.provider)
        if not credentials:
            skipped.append(connector.provider)
            continue

        for credential in credentials:
            try:
                result = await connector.fetch(
                    since=now - LOOKBACK,
                    until=now,
                    credential_name=credential.name,
                    credential_values=credential.values,
                )
            except Exception as exc:  # noqa: BLE001  # a connector bug must not end the run for other accounts
                verbose_proxy_logger.exception("billing connector %s raised: %s", connector.provider, exc)
                failed.append(connector.provider)
                continue

            match result:
                case Fetched(facts=facts):
                    written += await repository.upsert_many(facts)
                case NotConfigured(reason=reason):
                    verbose_proxy_logger.debug(
                        "billing connector %s skipped %s: %s", connector.provider, credential.name, reason
                    )
                    skipped.append(connector.provider)
                case FetchFailed(reason=reason, retryable=retryable):
                    verbose_proxy_logger.warning(
                        "billing connector %s failed for %s (retryable=%s): %s",
                        connector.provider,
                        credential.name,
                        retryable,
                        reason,
                    )
                    failed.append(connector.provider)
```

Change the `credentials_for` parameter annotation to `Callable[[str], Awaitable[tuple[BillingCredential, ...]]]` and import `BillingCredential`. `skipped` and `failed` may now repeat a provider when several of its accounts fail, which is what the caller wants to see; dedupe only in the report if a later reader needs it, not here.

- [ ] **Step 7: Put the credential in the three day-grain fact keys**

`litellm/provider_billing/openai.py:73`:

```python
                    fact_key=f"openai:{credential_name}:{day.date().isoformat()}:{line_item}",
```

`litellm/provider_billing/anthropic.py:86`:

```python
                fact_key=f"anthropic:{credential_name}:{day.date().isoformat()}:{model}",
```

`litellm/provider_billing/bedrock.py:87`:

```python
                fact_key=f"bedrock:{credential_name}:{day.date().isoformat()}:{usage_type}",
```

Leave `openrouter.py:119` exactly as it is, for the reason in this task's Why.

- [ ] **Step 8: Follow the new shape in the probe**

In `litellm/proxy/management_endpoints/provider_reconciliation.py`, `run_billing_probe` takes `credentials_for: Callable[[str], Awaitable[tuple[BillingCredential, ...]]]`. Replace its credential block:

```python
    credentials: Final = await credentials_for(provider)
    if not credentials:
        return BillingProbeResponse(
            provider=provider,
            credential_name=None,
            outcome="not_configured",
            facts_found=0,
            sample_cost=None,
            detail=(
                "No stored credential is marked for this provider. Create one whose "
                f'credential_info is {{"purpose": "billing_ingestion", "provider": "{provider}"}}.'
            ),
        )
    credential: Final = credentials[0]
```

and use `credential.name` / `credential.values` in the `connector.fetch(...)` call. Every `BillingProbeResponse(...)` in the function gains `credential_name=`: `None` for the `no_connector` and the no-credential branches, `credential.name` for the three result branches. Import `BillingCredential` and drop the `Mapping` import if it is now unused. The route body changes `build_billing_credential_lookup` to `build_billing_credentials_lookup`.

In `litellm/types/proxy/management_endpoints/team_endpoints.py`, add one field to `BillingProbeResponse` after `provider`:

```python
    credential_name: str | None
    """Which stored credential was tried, when one was found"""
```

- [ ] **Step 9: Run the suite and watch it pass**

```bash
C:/Users/NikhilEruva/litellm/.venv/Scripts/python.exe -m pytest tests/test_litellm/provider_billing/ tests/test_litellm/proxy/management_endpoints/test_provider_reconciliation.py tests/test_litellm/proxy/management_endpoints/test_daily_reconciliation.py -v
```

Expected: PASS. If a test still calls `build_billing_credential_lookup` or returns a bare tuple from `credentials_for`, update the test to the new shape rather than keeping a compatibility alias in the source.

- [ ] **Step 10: Commit**

```bash
git add litellm tests/test_litellm
git commit -m "feat(billing): read every billing account a provider has, not just the first"
```

---

### Task 3: A table that records every sync attempt

**Why:** Sync History and the Needs attention state both need to know what happened on the last run and why. Nothing is stored today, so a failing key is invisible until someone notices the totals are stale

**Files:**
- Modify: `schema.prisma` (after the `LiteLLM_ProviderUsageFact` model, which ends at line 72)
- Create: `litellm-proxy-extras/litellm_proxy_extras/migrations/20260916000000_provider_sync_run/migration.sql`
- Modify: `litellm/types/proxy/provider_billing.py`
- Create: `litellm/repositories/provider_sync_run_repository.py`
- Test: `tests/test_litellm/repositories/test_provider_sync_run_repository.py`

**Interfaces:**
- Consumes: nothing from earlier tasks beyond `BillingCredential` existing in the same types module
- Produces:
  - `SyncOutcome = Literal["fetched", "not_configured", "failed"]` and `ProviderSyncRun` in `litellm/types/proxy/provider_billing.py`
  - `ProviderSyncRunRepository(prisma_client: object)` with `async def record(self, run: ProviderSyncRun) -> None` and `async def recent(self, *, provider: str | None = None, limit: int = 50) -> tuple[ProviderSyncRun, ...]`

- [ ] **Step 1: Write the failing repository test**

Create `tests/test_litellm/repositories/test_provider_sync_run_repository.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from litellm.types.proxy.provider_billing import ProviderSyncRun

STARTED = datetime(2026, 9, 16, 9, 0, tzinfo=timezone.utc)
FINISHED = datetime(2026, 9, 16, 9, 0, 4, tzinfo=timezone.utc)


def _run(outcome: str = "fetched") -> ProviderSyncRun:
    return ProviderSyncRun(
        provider="openai",
        credential_name="prod",
        started_at=STARTED,
        finished_at=FINISHED,
        outcome=outcome,
        facts_written=3,
        window_start=datetime(2026, 9, 15, 9, 0, tzinfo=timezone.utc),
        window_end=STARTED,
        detail=None,
    )


def _client() -> tuple[MagicMock, MagicMock]:
    table = MagicMock()
    table.create = AsyncMock()
    table.find_many = AsyncMock(return_value=[])
    client = MagicMock()
    client.db.litellm_providersyncrun = table
    return client, table


@pytest.mark.asyncio
async def test_a_run_is_written_with_its_outcome_and_window():
    from litellm.repositories.provider_sync_run_repository import ProviderSyncRunRepository

    client, table = _client()

    await ProviderSyncRunRepository(client).record(_run(outcome="failed"))

    written = table.create.await_args.kwargs["data"]
    assert written["provider"] == "openai"
    assert written["credential_name"] == "prod"
    assert written["outcome"] == "failed"
    assert written["facts_written"] == 3
    assert written["window_end"] == STARTED


@pytest.mark.asyncio
async def test_recent_runs_come_back_newest_first_and_bounded():
    """Sync History reads this on every page load and the table grows on every tick, so an
    unbounded newest-last read would page through a year of rows to show ten."""
    from litellm.repositories.provider_sync_run_repository import ProviderSyncRunRepository

    client, table = _client()

    await ProviderSyncRunRepository(client).recent(provider="openai", limit=10)

    call = table.find_many.await_args.kwargs
    assert call["where"] == {"provider": "openai"}
    assert call["order"] == {"started_at": "desc"}
    assert call["take"] == 10


@pytest.mark.asyncio
async def test_recent_without_a_provider_reads_every_provider():
    from litellm.repositories.provider_sync_run_repository import ProviderSyncRunRepository

    client, table = _client()

    await ProviderSyncRunRepository(client).recent(limit=200)

    assert table.find_many.await_args.kwargs["where"] == {}


@pytest.mark.asyncio
async def test_a_row_missing_its_outcome_is_dropped_rather_than_guessed():
    """Reporting an unreadable row as healthy would tell a customer their key works when we
    have no idea whether it does."""
    from litellm.repositories.provider_sync_run_repository import ProviderSyncRunRepository

    client, table = _client()
    table.find_many = AsyncMock(
        return_value=[
            SimpleNamespace(
                provider="openai",
                credential_name="prod",
                started_at=STARTED,
                finished_at=FINISHED,
                outcome="nonsense",
                facts_written=0,
                window_start=STARTED,
                window_end=FINISHED,
                detail=None,
            )
        ]
    )

    assert await ProviderSyncRunRepository(client).recent(provider="openai") == ()
```

- [ ] **Step 2: Run it and watch it fail**

```bash
C:/Users/NikhilEruva/litellm/.venv/Scripts/python.exe -m pytest tests/test_litellm/repositories/test_provider_sync_run_repository.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'litellm.repositories.provider_sync_run_repository'`

- [ ] **Step 3: Add the types**

In `litellm/types/proxy/provider_billing.py`, after `BillingCredential`:

```python
SyncOutcome = Literal["fetched", "not_configured", "failed"]
"""fetched: the provider answered and whatever it returned was stored.
not_configured: the credential cannot be used, for example it carries no api_key.
failed: the provider refused, rate limited, or the connector raised."""


@dataclass(frozen=True, slots=True)
class ProviderSyncRun:
    provider: str
    credential_name: str
    started_at: datetime
    finished_at: datetime
    outcome: SyncOutcome
    facts_written: int
    window_start: datetime
    window_end: datetime
    detail: str | None = None
```

- [ ] **Step 4: Add the schema model**

In `schema.prisma`, after the closing brace of `LiteLLM_ProviderUsageFact`:

```prisma
// One record per provider fetch attempt, per account. Sync History reads it, and the
// newest row per account decides whether that connection is healthy or needs attention.
model LiteLLM_ProviderSyncRun {
    id              String   @id @default(uuid())
    provider        String
    credential_name String
    started_at      DateTime
    finished_at     DateTime
    outcome         String   // fetched | not_configured | failed
    facts_written   Int      @default(0)
    window_start    DateTime
    window_end      DateTime
    detail          String?

    @@index([provider, started_at])
    @@index([credential_name, started_at])
}
```

- [ ] **Step 5: Add the migration**

Create `litellm-proxy-extras/litellm_proxy_extras/migrations/20260916000000_provider_sync_run/migration.sql`:

```sql
-- One record per provider fetch attempt, per account. Create-only: the ingestion job appends
-- rows at runtime, so this migration never touches data.
CREATE TABLE IF NOT EXISTS "LiteLLM_ProviderSyncRun" (
    "id"              TEXT PRIMARY KEY,
    "provider"        TEXT NOT NULL,
    "credential_name" TEXT NOT NULL,
    "started_at"      TIMESTAMP(3) NOT NULL,
    "finished_at"     TIMESTAMP(3) NOT NULL,
    "outcome"         TEXT NOT NULL,
    "facts_written"   INTEGER NOT NULL DEFAULT 0,
    "window_start"    TIMESTAMP(3) NOT NULL,
    "window_end"      TIMESTAMP(3) NOT NULL,
    "detail"          TEXT
);

CREATE INDEX IF NOT EXISTS "LiteLLM_ProviderSyncRun_provider_started_idx"
    ON "LiteLLM_ProviderSyncRun"("provider", "started_at");
CREATE INDEX IF NOT EXISTS "LiteLLM_ProviderSyncRun_credential_started_idx"
    ON "LiteLLM_ProviderSyncRun"("credential_name", "started_at");
```

- [ ] **Step 6: Write the repository**

Create `litellm/repositories/provider_sync_run_repository.py`:

```python
"""Persistence for provider fetch attempts.

A row is written whether the fetch worked or not: a connection that has been failing for a
day is the single thing this table exists to make visible.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Final, get_args
from uuid import uuid4

from litellm.types.proxy.provider_billing import ProviderSyncRun, SyncOutcome

_OUTCOMES: Final[frozenset[str]] = frozenset(get_args(SyncOutcome))


def _run_or_none(row: object) -> ProviderSyncRun | None:
    """A row we cannot read is dropped rather than guessed at.

    Reporting an unreadable row as a success would tell a customer their key works when we
    have no evidence either way.
    """
    outcome: Final = getattr(row, "outcome", None)
    if outcome not in _OUTCOMES:
        return None
    times: Final = tuple(
        getattr(row, name, None) for name in ("started_at", "finished_at", "window_start", "window_end")
    )
    if not all(isinstance(value, datetime) for value in times):
        return None
    started, finished, window_start, window_end = times
    provider: Final = getattr(row, "provider", None)
    credential_name: Final = getattr(row, "credential_name", None)
    if not isinstance(provider, str) or not isinstance(credential_name, str):
        return None
    detail: Final = getattr(row, "detail", None)
    return ProviderSyncRun(
        provider=provider,
        credential_name=credential_name,
        started_at=started,  # pyright: ignore[reportArgumentType]  # checked by the isinstance sweep above
        finished_at=finished,  # pyright: ignore[reportArgumentType]  # checked by the isinstance sweep above
        outcome=outcome,
        facts_written=written if isinstance(written := getattr(row, "facts_written", 0), int) else 0,
        window_start=window_start,  # pyright: ignore[reportArgumentType]  # checked by the isinstance sweep above
        window_end=window_end,  # pyright: ignore[reportArgumentType]  # checked by the isinstance sweep above
        detail=detail if isinstance(detail, str) else None,
    )


class ProviderSyncRunRepository:
    def __init__(self, prisma_client: object) -> None:
        self._prisma_client = prisma_client

    @property
    def _table(self) -> Any:  # any-ok: PrismaClient is an untyped runtime wrapper
        return self._prisma_client.db.litellm_providersyncrun  # pyright: ignore[reportAttributeAccessIssue]

    async def record(self, run: ProviderSyncRun) -> None:
        await self._table.create(
            data={
                "id": str(uuid4()),
                "provider": run.provider,
                "credential_name": run.credential_name,
                "started_at": run.started_at,
                "finished_at": run.finished_at,
                "outcome": run.outcome,
                "facts_written": run.facts_written,
                "window_start": run.window_start,
                "window_end": run.window_end,
                "detail": run.detail,
            }
        )

    async def recent(self, *, provider: str | None = None, limit: int = 50) -> tuple[ProviderSyncRun, ...]:
        """The newest attempts, newest first. Bounded: this table grows on every tick."""
        rows: Final = await self._table.find_many(
            where={} if provider is None else {"provider": provider},
            order={"started_at": "desc"},
            take=limit,
        )
        return tuple(run for row in rows if (run := _run_or_none(row)) is not None)
```

If the `pyright: ignore` lines turn out to be unnecessary once the isinstance sweep is written differently, remove them; a suppression that suppresses nothing is worse than none. An accepted alternative is four separate `isinstance` guards returning `None` early, which narrows without any suppression at all, and is preferred if it reads cleanly.

- [ ] **Step 7: Run the tests and watch them pass**

```bash
C:/Users/NikhilEruva/litellm/.venv/Scripts/python.exe -m pytest tests/test_litellm/repositories/test_provider_sync_run_repository.py -v
```

Expected: PASS, four tests

- [ ] **Step 8: Check the migration rule gate**

```bash
C:/Users/NikhilEruva/litellm/.venv/Scripts/python.exe tests/code_coverage_tests/check_migrations_no_data_rewrites.py
```

Expected: exit 0

- [ ] **Step 9: Apply the migration locally and regenerate the client**

```bash
docker exec -i tokeniq_db psql -U llmproxy -d litellm -v ON_ERROR_STOP=1 --single-transaction \
  < litellm-proxy-extras/litellm_proxy_extras/migrations/20260916000000_provider_sync_run/migration.sql
PATH="/c/Users/NikhilEruva/litellm/.venv/Scripts:$PATH" \
  /c/Users/NikhilEruva/litellm/.venv/Scripts/python.exe -m prisma generate --schema=schema.prisma
```

Skipping the generate leaves every ORM read of the new model answering 500 with `'Prisma' object has no attribute 'litellm_providersyncrun'` while raw SQL writes appear to work, which is a confusing failure to debug later.

- [ ] **Step 10: Commit**

```bash
git add schema.prisma litellm-proxy-extras litellm/types/proxy/provider_billing.py litellm/repositories/provider_sync_run_repository.py tests/test_litellm/repositories/test_provider_sync_run_repository.py
git commit -m "feat(billing): record every provider fetch attempt in its own table"
```

---

### Task 4: The runner writes a sync run for every attempt

**Files:**
- Modify: `litellm/provider_billing/runner.py`
- Modify: `litellm/provider_billing/scheduled.py:92-118`
- Test: `tests/test_litellm/provider_billing/test_runner.py`

**Interfaces:**
- Consumes: `ProviderSyncRunRepository.record(run: ProviderSyncRun) -> None` from Task 3; `BillingCredential` and the per-credential loop from Task 2
- Produces: `run_ingestion(*, repository: ProviderUsageFactRepository, sync_runs: ProviderSyncRunRepository, connectors: Sequence[BillingConnector], credentials_for: Callable[[str], Awaitable[tuple[BillingCredential, ...]]], now: datetime) -> IngestionReport`

- [ ] **Step 1: Write the failing tests**

In `tests/test_litellm/provider_billing/test_runner.py`, give `_run` a sync-run double and pass it through:

```python
def _sync_runs() -> MagicMock:
    runs = MagicMock()
    runs.record = AsyncMock()
    return runs


async def _run(connectors, credentials_for=_creds, repo=None, sync_runs=None):
    from litellm.provider_billing.runner import run_ingestion

    return await run_ingestion(
        repository=repo or _repo(),
        sync_runs=sync_runs or _sync_runs(),
        connectors=connectors,
        credentials_for=credentials_for,
        now=NOW,
    )
```

Then append:

```python
@pytest.mark.asyncio
async def test_a_successful_fetch_is_recorded_with_what_it_wrote():
    runs = _sync_runs()

    await _run((_Connector("openai", Fetched(facts=(_fact(),), watermark=NOW)),), sync_runs=runs)

    recorded = runs.record.await_args.args[0]
    assert recorded.provider == "openai"
    assert recorded.credential_name == "c"
    assert recorded.outcome == "fetched"
    assert recorded.facts_written == 1
    assert recorded.window_end == NOW
    assert recorded.detail is None


@pytest.mark.asyncio
async def test_a_refused_key_is_recorded_with_the_reason_the_provider_gave():
    """A customer whose admin key was revoked sees Needs attention with the provider's own
    words. Recording only 'failed' would make them open a support ticket to learn why."""
    runs = _sync_runs()

    await _run((_Connector("openai", FetchFailed(reason="openai refused credential c", retryable=False)),), sync_runs=runs)

    recorded = runs.record.await_args.args[0]
    assert recorded.outcome == "failed"
    assert "refused" in recorded.detail


@pytest.mark.asyncio
async def test_a_connector_that_raises_is_still_recorded_as_a_failed_run():
    """Without this the worst failure, a crashing connector, is the one that leaves no trace
    and shows as a connection that simply stopped updating."""
    runs = _sync_runs()

    await _run((_Connector("openai", RuntimeError("boom")),), sync_runs=runs)

    recorded = runs.record.await_args.args[0]
    assert recorded.outcome == "failed"
    assert "boom" in recorded.detail


@pytest.mark.asyncio
async def test_a_provider_with_no_credential_records_nothing():
    """Not connected is the absence of a connection, not a failing one. A row here would put
    every unconfigured provider permanently in Needs attention."""

    async def none(_provider: str):
        return ()

    runs = _sync_runs()
    await _run((_Connector("openai", Fetched(facts=(), watermark=NOW)),), none, sync_runs=runs)

    runs.record.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_failure_writing_the_run_does_not_lose_the_facts():
    """The history is a convenience. Losing a day of the customer's real cost data because a
    bookkeeping insert failed would be the wrong trade."""
    runs = _sync_runs()
    runs.record = AsyncMock(side_effect=RuntimeError("db down"))

    report = await _run((_Connector("openai", Fetched(facts=(_fact(),), watermark=NOW)),), sync_runs=runs)

    assert report.written == 1
```

- [ ] **Step 2: Run them and watch them fail**

```bash
C:/Users/NikhilEruva/litellm/.venv/Scripts/python.exe -m pytest tests/test_litellm/provider_billing/test_runner.py -v
```

Expected: FAIL with `TypeError: run_ingestion() got an unexpected keyword argument 'sync_runs'`

- [ ] **Step 3: Record each attempt**

In `litellm/provider_billing/runner.py`, add the parameter and a recorder, then call it on each branch. The full inner loop becomes:

```python
        for credential in credentials:
            started = datetime_now()
            try:
                result = await connector.fetch(
                    since=window_start,
                    until=now,
                    credential_name=credential.name,
                    credential_values=credential.values,
                )
            except Exception as exc:  # noqa: BLE001  # a connector bug must not end the run for other accounts
                verbose_proxy_logger.exception("billing connector %s raised: %s", connector.provider, exc)
                failed.append(connector.provider)
                await _record(
                    sync_runs,
                    connector.provider,
                    credential.name,
                    started,
                    now,
                    window_start,
                    "failed",
                    0,
                    f"{type(exc).__name__}: {exc}",
                )
                continue

            match result:
                case Fetched(facts=facts):
                    count = await repository.upsert_many(facts)
                    written += count
                    await _record(
                        sync_runs, connector.provider, credential.name, started, now, window_start,
                        "fetched", count, None,
                    )
                case NotConfigured(reason=reason):
                    verbose_proxy_logger.debug(
                        "billing connector %s skipped %s: %s", connector.provider, credential.name, reason
                    )
                    skipped.append(connector.provider)
                    await _record(
                        sync_runs, connector.provider, credential.name, started, now, window_start,
                        "not_configured", 0, reason,
                    )
                case FetchFailed(reason=reason, retryable=retryable):
                    verbose_proxy_logger.warning(
                        "billing connector %s failed for %s (retryable=%s): %s",
                        connector.provider, credential.name, retryable, reason,
                    )
                    failed.append(connector.provider)
                    await _record(
                        sync_runs, connector.provider, credential.name, started, now, window_start,
                        "failed", 0, reason,
                    )
```

with `window_start: Final = now - LOOKBACK` computed once before the connector loop, `datetime_now` being `lambda: datetime.now(timezone.utc)` written inline as `datetime.now(timezone.utc)`, and the recorder:

```python
async def _record(
    sync_runs: ProviderSyncRunRepository,
    provider: str,
    credential_name: str,
    started_at: datetime,
    finished_at: datetime,
    window_start: datetime,
    outcome: SyncOutcome,
    facts_written: int,
    detail: str | None,
) -> None:
    """The history is a convenience; the facts are the product. A bookkeeping insert that
    fails must not take a day of real cost data with it."""
    try:
        await sync_runs.record(
            ProviderSyncRun(
                provider=provider,
                credential_name=credential_name,
                started_at=started_at,
                finished_at=finished_at,
                outcome=outcome,
                facts_written=facts_written,
                window_start=window_start,
                window_end=finished_at,
                detail=detail,
            )
        )
    except Exception as exc:  # noqa: BLE001  # see docstring: never lose facts over a history row
        verbose_proxy_logger.warning("could not record the %s sync run: %s", provider, exc)
```

Ten positional arguments to `_record` is too many to read. Prefer passing the assembled `ProviderSyncRun` and keeping `_record(sync_runs, run)` at two parameters, building the run at each call site with keyword arguments. Either shape is acceptable as long as every call site is readable and the try/except stays in one place.

Import `datetime`, `timezone`, `ProviderSyncRun`, `SyncOutcome` and `ProviderSyncRunRepository` as needed.

- [ ] **Step 4: Wire it in the job**

In `litellm/provider_billing/scheduled.py`, inside `build_provider_billing_job`, import and construct the repository next to the existing one and pass it through:

```python
    from litellm.repositories.provider_sync_run_repository import ProviderSyncRunRepository

    sync_runs: Final = ProviderSyncRunRepository(prisma_client)
```

and add `sync_runs=sync_runs,` to the `run_ingestion(...)` call inside the lambda.

- [ ] **Step 5: Run the tests and watch them pass**

```bash
C:/Users/NikhilEruva/litellm/.venv/Scripts/python.exe -m pytest tests/test_litellm/provider_billing/ -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add litellm/provider_billing tests/test_litellm/provider_billing
git commit -m "feat(billing): record the outcome of every provider fetch as it happens"
```

---

### Task 5: Connection state and sync history, over HTTP

**Files:**
- Create: `litellm/provider_billing/connection_state.py`
- Create: `litellm/provider_billing/fetch_profile.py`
- Create: `litellm/proxy/management_endpoints/provider_connections.py`
- Modify: `litellm/types/proxy/management_endpoints/team_endpoints.py`
- Modify: `litellm/repositories/provider_usage_fact_repository.py`
- Modify: `litellm/proxy/proxy_server.py:506-508`, `18127`
- Test: `tests/test_litellm/provider_billing/test_connection_state.py`
- Test: `tests/test_litellm/proxy/management_endpoints/test_provider_connections.py`

**Interfaces:**
- Consumes: `ProviderSyncRun`, `SyncOutcome` and `ProviderSyncRunRepository.recent(...)` from Task 3; `build_billing_credentials_lookup` and `BillingCredential` from Task 2; `registered_connectors()` from `litellm/provider_billing/connector.py`; `INTERVAL_SECONDS` from `litellm/provider_billing/scheduled.py`; `LOOKBACK` from `litellm/provider_billing/runner.py`
- Produces:
  - `ConnectionState = Literal["not_connected", "waiting_for_first_data", "healthy", "needs_attention"]`
  - `account_state(*, last_run: ProviderSyncRun | None, facts_stored: int) -> tuple[ConnectionState, str | None]`
  - `provider_state(account_states: Sequence[ConnectionState]) -> ConnectionState`
  - `FETCH_PROFILES: Mapping[str, FetchProfile]` keyed by provider slug
  - `ProviderUsageFactRepository.counts_by_credential(provider: str) -> Mapping[str, int]`
  - `GET /provider/connections` and `GET /provider/sync-history`

- [ ] **Step 1: Write the failing state tests**

Create `tests/test_litellm/provider_billing/test_connection_state.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone

from litellm.types.proxy.provider_billing import ProviderSyncRun

NOW = datetime(2026, 9, 16, 9, 0, tzinfo=timezone.utc)


def _run(outcome: str, detail: str | None = None, facts_written: int = 0) -> ProviderSyncRun:
    return ProviderSyncRun(
        provider="openai",
        credential_name="prod",
        started_at=NOW,
        finished_at=NOW,
        outcome=outcome,
        facts_written=facts_written,
        window_start=NOW,
        window_end=NOW,
        detail=detail,
    )


def test_an_account_that_has_never_synced_is_waiting_not_healthy():
    from litellm.provider_billing.connection_state import account_state

    assert account_state(last_run=None, facts_stored=0) == (
        "waiting_for_first_data",
        "No sync has run for this account yet.",
    )


def test_an_account_whose_last_run_failed_needs_attention_and_says_why():
    """The reason is the whole value of this state. A customer whose admin key was revoked
    should read the provider's own words, not open a ticket to find out."""
    from litellm.provider_billing.connection_state import account_state

    assert account_state(last_run=_run("failed", "openai refused credential prod"), facts_stored=12) == (
        "needs_attention",
        "openai refused credential prod",
    )


def test_a_credential_the_connector_cannot_use_needs_attention():
    from litellm.provider_billing.connection_state import account_state

    state, detail = account_state(last_run=_run("not_configured", "credential prod carries no api_key"), facts_stored=0)

    assert state == "needs_attention"
    assert detail == "credential prod carries no api_key"


def test_a_successful_run_that_has_produced_nothing_yet_is_still_waiting():
    """A provider that has answered but reported no spend is not proof the connection works
    end to end. Calling it healthy would hide a wrong account id until the first invoice."""
    from litellm.provider_billing.connection_state import account_state

    assert account_state(last_run=_run("fetched"), facts_stored=0)[0] == "waiting_for_first_data"


def test_a_successful_run_with_stored_facts_is_healthy():
    from litellm.provider_billing.connection_state import account_state

    assert account_state(last_run=_run("fetched", facts_written=3), facts_stored=3) == ("healthy", None)


def test_a_provider_with_no_accounts_is_not_connected():
    from litellm.provider_billing.connection_state import provider_state

    assert provider_state(()) == "not_connected"


def test_one_broken_account_puts_the_whole_provider_in_needs_attention():
    """Two OpenAI organisations where one key is dead is a half-reported bill. Showing the
    provider as healthy because the other account works is the failure this prevents."""
    from litellm.provider_billing.connection_state import provider_state

    assert provider_state(("healthy", "needs_attention")) == "needs_attention"


def test_a_provider_whose_accounts_are_all_healthy_is_healthy():
    from litellm.provider_billing.connection_state import provider_state

    assert provider_state(("healthy", "healthy")) == "healthy"


def test_a_provider_still_waiting_on_one_account_is_waiting():
    from litellm.provider_billing.connection_state import provider_state

    assert provider_state(("healthy", "waiting_for_first_data")) == "waiting_for_first_data"
```

- [ ] **Step 2: Run them and watch them fail**

```bash
C:/Users/NikhilEruva/litellm/.venv/Scripts/python.exe -m pytest tests/test_litellm/provider_billing/test_connection_state.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'litellm.provider_billing.connection_state'`

- [ ] **Step 3: Write the state rules**

Create `litellm/provider_billing/connection_state.py`:

```python
"""What state a provider connection is in, decided only from evidence we hold.

Kept pure and separate from the endpoint so the rules can be read and tested on their own:
every branch here is something a customer will act on.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final, Literal

from litellm.types.proxy.provider_billing import ProviderSyncRun

ConnectionState = Literal["not_connected", "waiting_for_first_data", "healthy", "needs_attention"]

_NEVER_RUN: Final = "No sync has run for this account yet."

_SEVERITY: Final[tuple[ConnectionState, ...]] = (
    "needs_attention",
    "not_connected",
    "waiting_for_first_data",
    "healthy",
)
"""Worst first. A provider is only as good as its least healthy account."""


def account_state(*, last_run: ProviderSyncRun | None, facts_stored: int) -> tuple[ConnectionState, str | None]:
    """The state of one stored credential against one provider, and why."""
    if last_run is None:
        return ("waiting_for_first_data", _NEVER_RUN)
    if last_run.outcome in ("failed", "not_configured"):
        return ("needs_attention", last_run.detail)
    if facts_stored == 0:
        return (
            "waiting_for_first_data",
            "The provider answered but has reported no cost for this account yet.",
        )
    return ("healthy", None)


def provider_state(account_states: Sequence[ConnectionState]) -> ConnectionState:
    """One state for a provider that may have several accounts."""
    if not account_states:
        return "not_connected"
    return next(state for state in _SEVERITY if state in account_states)
```

- [ ] **Step 4: Run them and watch them pass**

```bash
C:/Users/NikhilEruva/litellm/.venv/Scripts/python.exe -m pytest tests/test_litellm/provider_billing/test_connection_state.py -v
```

Expected: PASS, nine tests

- [ ] **Step 5: Write what we fetch**

Create `litellm/provider_billing/fetch_profile.py`. Every field states something this build actually does or a plainly true property of the provider's endpoint. Nothing here invents a backfill depth or an earliest date we have not verified:

```python
"""What this build reads from each provider, in the words the What We Fetch tab shows.

Deliberately modest: every line describes behaviour that exists in this repository today.
A backfill depth or an earliest available date we have not verified against a real account
would read as a promise, and the first customer to check it would find it wrong.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from litellm.provider_billing.runner import LOOKBACK
from litellm.provider_billing.scheduled import INTERVAL_SECONDS
from litellm.types.proxy.provider_billing import UsageGrain

_NO_BACKFILL: Final = (
    "Each run re-reads the most recent window. There is no first-connection backfill yet, so "
    "cost from before this connection was made is not loaded."
)


@dataclass(frozen=True, slots=True)
class FetchProfile:
    provider: str
    display_name: str
    endpoint: str
    endpoint_url: str
    grain: UsageGrain
    refresh_seconds: int
    window_hours: int
    delay_note: str
    history_note: str


def _profile(
    provider: str, display_name: str, endpoint: str, endpoint_url: str, grain: UsageGrain, delay_note: str
) -> FetchProfile:
    return FetchProfile(
        provider=provider,
        display_name=display_name,
        endpoint=endpoint,
        endpoint_url=endpoint_url,
        grain=grain,
        refresh_seconds=INTERVAL_SECONDS,
        window_hours=int(LOOKBACK.total_seconds() // 3600),
        delay_note=delay_note,
        history_note=_NO_BACKFILL,
    )


FETCH_PROFILES: Final[Mapping[str, FetchProfile]] = MappingProxyType(
    {
        "openai": _profile(
            "openai",
            "OpenAI",
            "Organization Costs",
            "https://api.openai.com/v1/organization/costs",
            "day",
            "OpenAI reports cost by day for the whole organisation, so the finest comparison "
            "against gateway traffic is by model and day. Recent days can still change.",
        ),
        "anthropic": _profile(
            "anthropic",
            "Anthropic",
            "Admin Cost Report",
            "https://api.anthropic.com/v1/organizations/cost_report",
            "day",
            "Anthropic reports cost by day against its own workspace rather than our teams, so "
            "the finest comparison against gateway traffic is by model and day.",
        ),
        "openrouter": _profile(
            "openrouter",
            "OpenRouter",
            "Generation",
            "https://openrouter.ai/api/v1/generation",
            "request",
            "OpenRouter prices each request individually, so every gateway request can be "
            "checked against what OpenRouter charged for it. OpenRouter drops this history "
            "after about 30 days, so the newest requests are read first.",
        ),
        "bedrock": _profile(
            "bedrock",
            "Amazon Bedrock",
            "Cost Explorer",
            "https://ce.us-east-1.amazonaws.com/",
            "day",
            "Cost Explorer reports by day and settles over the following days, so the most "
            "recent day is deliberately not read until it stops moving.",
        ),
    }
)
```

If `INTERVAL_SECONDS` or `LOOKBACK` cannot be imported here without a circular import, move the two constants into this module and import them from here in `runner.py` and `scheduled.py` instead of duplicating the numbers.

- [ ] **Step 6: Count stored facts per account**

Append to `ProviderUsageFactRepository` in `litellm/repositories/provider_usage_fact_repository.py`:

```python
    async def counts_by_credential(self, provider: str) -> Mapping[str, int]:
        """How many facts each account has produced, for deciding whether it has ever worked."""
        rows: Final = await self._table.group_by(
            by=["credential_name"], where={"provider": provider}, count=True
        )
        return MappingProxyType(
            {
                name: count
                for row in rows
                if isinstance(name := _read(row, "credential_name"), str)
                and isinstance(count := _count_of(row), int)
            }
        )
```

with two small readers above the class, since prisma-client-py returns `group_by` rows as dicts rather than models:

```python
def _read(row: object, key: str) -> object:
    return row.get(key) if isinstance(row, Mapping) else getattr(row, key, None)


def _count_of(row: object) -> object:
    counted: Final = _read(row, "_count")
    if isinstance(counted, Mapping):
        return counted.get("credential_name") or counted.get("_all")
    return counted
```

Import `MappingProxyType`. Verify the actual `group_by` result shape against prisma-client-py before finalising; if `group_by` proves awkward, `find_many(where={"provider": provider})` with a Counter over `credential_name` is an acceptable fallback, but only with a `take` bound on it.

- [ ] **Step 7: Write the failing endpoint tests**

Create `tests/test_litellm/proxy/management_endpoints/test_provider_connections.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from litellm.types.proxy.provider_billing import BillingCredential, ProviderSyncRun

NOW = datetime(2026, 9, 16, 9, 0, tzinfo=timezone.utc)


def _run(provider: str, credential_name: str, outcome: str, detail: str | None = None) -> ProviderSyncRun:
    return ProviderSyncRun(
        provider=provider,
        credential_name=credential_name,
        started_at=NOW,
        finished_at=NOW,
        outcome=outcome,
        facts_written=1,
        window_start=NOW,
        window_end=NOW,
        detail=detail,
    )


@pytest.mark.asyncio
async def test_a_provider_with_no_credential_is_reported_not_connected():
    from litellm.proxy.management_endpoints.provider_connections import build_provider_connections

    async def no_credentials(_provider: str) -> tuple[BillingCredential, ...]:
        return ()

    result = await build_provider_connections(
        providers=("openai",),
        credentials_for=no_credentials,
        recent_runs=(),
        fact_counts_for=lambda _provider: {},
    )

    assert result.providers[0].state == "not_connected"
    assert result.providers[0].accounts == []


@pytest.mark.asyncio
async def test_each_account_gets_its_own_row_and_the_worst_one_sets_the_provider_state():
    from litellm.proxy.management_endpoints.provider_connections import build_provider_connections

    async def two(_provider: str) -> tuple[BillingCredential, ...]:
        return (
            BillingCredential(name="prod", values={"api_key": "k1"}),
            BillingCredential(name="staging", values={"api_key": "k2"}),
        )

    result = await build_provider_connections(
        providers=("openai",),
        credentials_for=two,
        recent_runs=(
            _run("openai", "prod", "fetched"),
            _run("openai", "staging", "failed", "openai refused credential staging"),
        ),
        fact_counts_for=lambda _provider: {"prod": 40},
    )

    connection = result.providers[0]
    assert connection.state == "needs_attention"
    assert {account.credential_name: account.state for account in connection.accounts} == {
        "prod": "healthy",
        "staging": "needs_attention",
    }
    assert connection.accounts[1].detail == "openai refused credential staging"


@pytest.mark.asyncio
async def test_only_the_newest_run_for_an_account_decides_its_state():
    """Runs arrive newest first. Letting an older failure win would leave a connection the
    customer already fixed showing as broken until the history rolled over."""
    from litellm.proxy.management_endpoints.provider_connections import build_provider_connections

    async def one(_provider: str) -> tuple[BillingCredential, ...]:
        return (BillingCredential(name="prod", values={"api_key": "k"}),)

    result = await build_provider_connections(
        providers=("openai",),
        credentials_for=one,
        recent_runs=(_run("openai", "prod", "fetched"), _run("openai", "prod", "failed", "was broken")),
        fact_counts_for=lambda _provider: {"prod": 5},
    )

    assert result.providers[0].accounts[0].state == "healthy"


@pytest.mark.asyncio
async def test_every_connection_says_what_it_fetches():
    from litellm.proxy.management_endpoints.provider_connections import build_provider_connections

    async def none(_provider: str) -> tuple[BillingCredential, ...]:
        return ()

    result = await build_provider_connections(
        providers=("openrouter",),
        credentials_for=none,
        recent_runs=(),
        fact_counts_for=lambda _provider: {},
    )

    fetches = result.providers[0].fetches
    assert fetches.grain == "request"
    assert fetches.refresh_seconds == 300
    assert "30 days" in fetches.delay_note
```

- [ ] **Step 8: Run them and watch them fail**

```bash
C:/Users/NikhilEruva/litellm/.venv/Scripts/python.exe -m pytest tests/test_litellm/proxy/management_endpoints/test_provider_connections.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'litellm.proxy.management_endpoints.provider_connections'`

- [ ] **Step 9: Add the response models**

In `litellm/types/proxy/management_endpoints/team_endpoints.py`, after `BillingProbeResponse`:

```python
class ProviderFetchDetail(BaseModel):
    """What this build reads from one provider"""

    endpoint: str
    endpoint_url: str
    grain: str
    """request or day"""

    refresh_seconds: int
    window_hours: int
    delay_note: str
    history_note: str


class ProviderConnectionAccount(BaseModel):
    """One stored billing credential's standing against its provider"""

    credential_name: str
    state: str
    """waiting_for_first_data, healthy, or needs_attention"""

    detail: str | None
    last_sync_at: str | None
    last_outcome: str | None
    facts_stored: int


class ProviderConnection(BaseModel):
    provider: str
    display_name: str
    state: str
    """not_connected, waiting_for_first_data, healthy, or needs_attention"""

    accounts: list[ProviderConnectionAccount]
    fetches: ProviderFetchDetail


class ProviderConnectionsResponse(BaseModel):
    providers: list[ProviderConnection]


class ProviderSyncHistoryRow(BaseModel):
    provider: str
    credential_name: str
    started_at: str
    finished_at: str
    outcome: str
    facts_written: int
    window_start: str
    window_end: str
    detail: str | None


class ProviderSyncHistoryResponse(BaseModel):
    rows: list[ProviderSyncHistoryRow]
```

- [ ] **Step 10: Write the endpoints**

Create `litellm/proxy/management_endpoints/provider_connections.py`:

```python
"""What state each provider connection is in, and what it has been doing.

The assembly is split out of the routes so it can be tested without a database: these are
the two screens a customer looks at when they think their bill is wrong.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Final

import fastapi
from fastapi import APIRouter, Depends, HTTPException, status

from litellm.provider_billing.connection_state import ConnectionState, account_state, provider_state
from litellm.provider_billing.credential_purpose import BILLING_PROVIDERS
from litellm.provider_billing.fetch_profile import FETCH_PROFILES, FetchProfile
from litellm.provider_billing.scheduled import build_billing_credentials_lookup
from litellm.proxy._types import CommonProxyErrors, LitellmUserRoles, UserAPIKeyAuth
from litellm.proxy.auth.user_api_key_auth import user_api_key_auth
from litellm.repositories.provider_sync_run_repository import ProviderSyncRunRepository
from litellm.repositories.provider_usage_fact_repository import ProviderUsageFactRepository
from litellm.types.proxy.management_endpoints.team_endpoints import (
    ProviderConnection,
    ProviderConnectionAccount,
    ProviderConnectionsResponse,
    ProviderFetchDetail,
    ProviderSyncHistoryResponse,
    ProviderSyncHistoryRow,
)
from litellm.types.proxy.provider_billing import BillingCredential, ProviderSyncRun

router: Final = APIRouter()

_RUNS_FOR_STATE: Final = 200
"""Enough recent runs to find the newest one per account across every provider in one read."""

_MAX_HISTORY_ROWS: Final = 200


def _fetch_detail(profile: FetchProfile) -> ProviderFetchDetail:
    return ProviderFetchDetail(
        endpoint=profile.endpoint,
        endpoint_url=profile.endpoint_url,
        grain=profile.grain,
        refresh_seconds=profile.refresh_seconds,
        window_hours=profile.window_hours,
        delay_note=profile.delay_note,
        history_note=profile.history_note,
    )


def _newest_per_account(runs: Sequence[ProviderSyncRun], provider: str) -> Mapping[str, ProviderSyncRun]:
    """Runs arrive newest first, so the first one seen for an account is the one that counts."""
    newest: dict[str, ProviderSyncRun] = {}  # mutable-ok: one pass over an already ordered sequence
    for run in runs:
        if run.provider == provider:
            newest.setdefault(run.credential_name, run)
    return newest


async def build_provider_connections(
    *,
    providers: Sequence[str],
    credentials_for: Callable[[str], Awaitable[tuple[BillingCredential, ...]]],
    recent_runs: Sequence[ProviderSyncRun],
    fact_counts_for: Callable[[str], Mapping[str, int]],
) -> ProviderConnectionsResponse:
    """One row per provider, with one row per stored account inside it."""
    connections: list[ProviderConnection] = []  # mutable-ok: accumulated across awaits in a loop

    for provider in providers:
        profile = FETCH_PROFILES[provider]
        credentials = await credentials_for(provider)
        newest = _newest_per_account(recent_runs, provider)
        counts = fact_counts_for(provider)

        accounts = tuple(
            (credential.name, newest.get(credential.name), account_state(
                last_run=newest.get(credential.name), facts_stored=counts.get(credential.name, 0)
            ))
            for credential in credentials
        )
        states: Final[tuple[ConnectionState, ...]] = tuple(state for _, _, (state, _) in accounts)

        connections.append(
            ProviderConnection(
                provider=provider,
                display_name=profile.display_name,
                state=provider_state(states),
                accounts=[
                    ProviderConnectionAccount(
                        credential_name=name,
                        state=state,
                        detail=detail,
                        last_sync_at=None if run is None else run.finished_at.isoformat(),
                        last_outcome=None if run is None else run.outcome,
                        facts_stored=counts.get(name, 0),
                    )
                    for name, run, (state, detail) in accounts
                ],
                fetches=_fetch_detail(profile),
            )
        )

    return ProviderConnectionsResponse(providers=connections)


def _admin_or_403(user_api_key_dict: UserAPIKeyAuth) -> None:
    if user_api_key_dict.user_role != LitellmUserRoles.PROXY_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "Only a proxy admin may read provider connections."},
        )


@router.get(
    "/provider/connections",
    tags=["provider billing"],
    dependencies=[Depends(user_api_key_auth)],
    response_model=ProviderConnectionsResponse,
)
async def provider_connections(
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
) -> ProviderConnectionsResponse:
    """Every provider this build can read a bill from, and the state of each connection."""
    from litellm.proxy.proxy_server import prisma_client

    _admin_or_403(user_api_key_dict)
    if prisma_client is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": CommonProxyErrors.db_not_connected_error.value},
        )

    facts: Final = ProviderUsageFactRepository(prisma_client)
    counts: Final = {provider: await facts.counts_by_credential(provider) for provider in sorted(BILLING_PROVIDERS)}

    return await build_provider_connections(
        providers=sorted(BILLING_PROVIDERS),
        credentials_for=build_billing_credentials_lookup(prisma_client=prisma_client),
        recent_runs=await ProviderSyncRunRepository(prisma_client).recent(limit=_RUNS_FOR_STATE),
        fact_counts_for=lambda provider: counts[provider],
    )


@router.get(
    "/provider/sync-history",
    tags=["provider billing"],
    dependencies=[Depends(user_api_key_auth)],
    response_model=ProviderSyncHistoryResponse,
)
async def provider_sync_history(
    provider: str = fastapi.Query(description="Which provider's fetch history to read"),
    limit: int = fastapi.Query(default=50, ge=1, le=_MAX_HISTORY_ROWS),
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
) -> ProviderSyncHistoryResponse:
    """Recent fetch attempts for one provider, newest first."""
    from litellm.proxy.proxy_server import prisma_client

    _admin_or_403(user_api_key_dict)
    if prisma_client is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": CommonProxyErrors.db_not_connected_error.value},
        )

    runs: Final = await ProviderSyncRunRepository(prisma_client).recent(provider=provider, limit=limit)

    return ProviderSyncHistoryResponse(
        rows=[
            ProviderSyncHistoryRow(
                provider=run.provider,
                credential_name=run.credential_name,
                started_at=run.started_at.isoformat(),
                finished_at=run.finished_at.isoformat(),
                outcome=run.outcome,
                facts_written=run.facts_written,
                window_start=run.window_start.isoformat(),
                window_end=run.window_end.isoformat(),
                detail=run.detail,
            )
            for run in runs
        ]
    )
```

The `connections` list and the `newest` dict each need a `# mutable-ok:` reason as written. If the budget cannot take two, rewrite `build_provider_connections` as a comprehension over an awaited `dict(zip(providers, await asyncio.gather(...)))` of credentials, which removes the loop entirely; prefer that if the gate complains.

- [ ] **Step 11: Register the router**

In `litellm/proxy/proxy_server.py`, beside the existing provider reconciliation import near line 506:

```python
from litellm.proxy.management_endpoints.provider_connections import (
    router as provider_connections_router,
)
```

and beside `app.include_router(provider_reconciliation_router)` near line 18127:

```python
app.include_router(provider_connections_router)
```

- [ ] **Step 12: Run the tests and watch them pass**

```bash
C:/Users/NikhilEruva/litellm/.venv/Scripts/python.exe -m pytest tests/test_litellm/proxy/management_endpoints/test_provider_connections.py tests/test_litellm/provider_billing/ tests/test_litellm/repositories/ -v
```

Expected: PASS

- [ ] **Step 13: Prove it against the running proxy**

```bash
~/.claude/scripts/litellm-dev-up.sh
curl -s -H "Authorization: Bearer sk-1234" "http://localhost:4001/provider/connections" | head -c 2000
curl -s -H "Authorization: Bearer sk-1234" "http://localhost:4001/provider/sync-history?provider=openrouter&limit=5"
```

Expected: `/provider/connections` lists four providers; the one with a stored billing credential shows an account row and the rest show `not_connected`. Sync history is an empty list until the scheduler has ticked, which takes up to five minutes.

- [ ] **Step 14: Regenerate the dashboard API types**

```bash
cd ui/litellm-dashboard
LITELLM_PYTHON="C:/Users/NikhilEruva/litellm/.venv/Scripts/python.exe" PYTHONUTF8=1 \
  PYTHONPATH="C:/Users/NikhilEruva/litellm" npm run gen:api
```

- [ ] **Step 15: Commit**

```bash
git add litellm tests/test_litellm ui/litellm-dashboard/src/lib/http/schema.d.ts
git commit -m "feat(billing): expose provider connection state and sync history"
```

---

### Task 6: A provider's declared defaults reach the saved credential

**Why:** the proxy publishes a `default_value` for some provider fields, OpenAI's `api_base` among them. The credential form renders those fields but never puts the default into form state, so `buildCredentialPayload` never sees it and the saved credential is missing a value the form implied it had. The admin then either types it by hand or finds out at first use

**Files:**
- Create: `ui/litellm-dashboard/src/components/add_model/providerFieldDefaults.ts`
- Create: `ui/litellm-dashboard/src/components/add_model/providerFieldDefaults.test.ts`
- Modify: `ui/litellm-dashboard/src/components/add_model/provider_specific_fields.tsx:228-248`, and after the `allFields` memo near line 202
- Test: `ui/litellm-dashboard/src/components/model_add/CredentialModal.test.tsx`

**Interfaces:**
- Consumes: the `ProviderCredentialField` interface already declared in `provider_specific_fields.tsx`, which carries `key`, `type` and `defaultValue`
- Produces: `defaultsToSeed(fields: readonly FieldDefault[], currentValues: Readonly<Record<string, unknown>>): ReadonlyArray<[string, string]>` exported from `providerFieldDefaults.ts`, where `FieldDefault = { key: string; defaultValue?: string }`

- [ ] **Step 1: Write the failing unit tests**

Create `ui/litellm-dashboard/src/components/add_model/providerFieldDefaults.test.ts`:

```ts
import { describe, expect, it } from "vitest";

import { defaultsToSeed } from "./providerFieldDefaults";

describe("defaultsToSeed", () => {
  it("seeds a declared default the form has no value for", () => {
    expect(defaultsToSeed([{ key: "api_base", defaultValue: "https://api.openai.com/v1" }], {})).toEqual([
      ["api_base", "https://api.openai.com/v1"],
    ]);
  });

  it("leaves a field the admin already typed into alone", () => {
    // Overwriting a typed value would silently replace a customer's private endpoint with
    // the public one, and the form would look like it accepted what they typed.
    expect(
      defaultsToSeed([{ key: "api_base", defaultValue: "https://api.openai.com/v1" }], {
        api_base: "https://internal.example/v1",
      }),
    ).toEqual([]);
  });

  it("seeds a field the admin cleared back to empty", () => {
    expect(defaultsToSeed([{ key: "api_base", defaultValue: "https://api.openai.com/v1" }], { api_base: "" })).toEqual([
      ["api_base", "https://api.openai.com/v1"],
    ]);
  });

  it("ignores a field that declares no default", () => {
    expect(defaultsToSeed([{ key: "api_key" }], {})).toEqual([]);
  });

  it("returns every field that needs seeding, not only the first", () => {
    expect(
      defaultsToSeed(
        [
          { key: "api_base", defaultValue: "https://api.openai.com/v1" },
          { key: "api_version", defaultValue: "2024-02-01" },
        ],
        {},
      ),
    ).toEqual([
      ["api_base", "https://api.openai.com/v1"],
      ["api_version", "2024-02-01"],
    ]);
  });
});
```

- [ ] **Step 2: Run them and watch them fail**

```bash
cd ui/litellm-dashboard
npx vitest run src/components/add_model/providerFieldDefaults.test.ts
```

Expected: FAIL, cannot resolve `./providerFieldDefaults`

- [ ] **Step 3: Write the helper**

Create `ui/litellm-dashboard/src/components/add_model/providerFieldDefaults.ts`:

```ts
export interface FieldDefault {
  key: string;
  defaultValue?: string;
}

/**
 * Which declared provider defaults still need to be put into form state.
 *
 * The proxy publishes a default_value for some provider fields, OpenAI's api_base among
 * them. Rendering it as placeholder text is not enough: the payload is built from form
 * state, so a default that never lands there is never saved, and the credential is stored
 * without a value the form implied it had.
 */
export const defaultsToSeed = (
  fields: readonly FieldDefault[],
  currentValues: Readonly<Record<string, unknown>>,
): ReadonlyArray<[string, string]> =>
  fields
    .filter((field) => field.defaultValue !== undefined)
    .filter((field) => currentValues[field.key] === undefined || currentValues[field.key] === "")
    .map((field) => [field.key, field.defaultValue as string]);
```

- [ ] **Step 4: Run them and watch them pass**

```bash
cd ui/litellm-dashboard
npx vitest run src/components/add_model/providerFieldDefaults.test.ts
```

Expected: PASS, five tests

- [ ] **Step 5: Write the failing form test**

Append to `ui/litellm-dashboard/src/components/model_add/CredentialModal.test.tsx`, following whatever render helper and provider-fields stub that file already uses. Assert on what is submitted, not on what is rendered:

```tsx
it("saves the provider's declared default when the admin does not change it", async () => {
  // The default is shown as if it were part of the credential. A payload without it stores a
  // credential the form implied was complete, and the admin finds out at first use.
  const onSubmit = vi.fn();
  renderCredentialModal({ onSubmit });

  await chooseProviderWithDefaultApiBase();
  fireEvent.change(screen.getByLabelText(/credential name/i), { target: { value: "acct" } });
  fireEvent.change(screen.getByLabelText(/api key/i), { target: { value: "sk-test" } });
  fireEvent.click(screen.getByRole("button", { name: /add credential/i }));

  await waitFor(() =>
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ api_base: "https://api.openai.com/v1" }),
    ),
  );
});
```

Adapt the helper names, the provider chosen and the submit button's accessible name to that file's existing conventions; the assertion on `api_base` reaching the submitted values is the part that must not change.

- [ ] **Step 6: Run it and watch it fail**

```bash
cd ui/litellm-dashboard
npx vitest run src/components/model_add/CredentialModal.test.tsx
```

Expected: FAIL, the submitted object has no `api_base`

- [ ] **Step 7: Seed the defaults from the component**

In `ui/litellm-dashboard/src/components/add_model/provider_specific_fields.tsx`, import the helper and add one effect directly after the `allFields` memo:

```tsx
  React.useEffect(() => {
    for (const [key, value] of defaultsToSeed(allFields, form.getValues())) {
      form.setValue(key, value);
    }
  }, [allFields, form]);
```

`allFields` is memoized on the selected provider, and `resetCredentialFormOnProviderChange` clears the form before the new provider's fields resolve, so this runs once per provider and never fights a value the admin typed.

With form state now carrying the default, drop the display-only fallback on the select control at line 233 so there is one source of truth:

```tsx
          value={(control.value as string | undefined) ?? null}
```

- [ ] **Step 8: Run the affected tests and watch them pass**

```bash
cd ui/litellm-dashboard
npx vitest run src/components/add_model/providerFieldDefaults.test.ts src/components/model_add/CredentialModal.test.tsx src/components/model_add/credential_form_helpers.test.ts src/components/add_model/AddModelForm.test.tsx
```

Expected: PASS across all four files

- [ ] **Step 9: Commit**

```bash
git add ui/litellm-dashboard/src/components/add_model ui/litellm-dashboard/src/components/model_add
git commit -m "fix(ui): save the provider defaults the credential form shows"
```

---

### Task 7: The Provider APIs page, with the Connection tab

**Files:**
- Modify: `ui/litellm-dashboard/src/components/networking.tsx`
- Create: `ui/litellm-dashboard/src/app/(dashboard)/hooks/providerApis/useProviderConnections.ts`
- Create: `ui/litellm-dashboard/src/app/(dashboard)/provider-apis/page.tsx`
- Create: `ui/litellm-dashboard/src/app/(dashboard)/provider-apis/_components/ProviderApisPanel.tsx`
- Create: `ui/litellm-dashboard/src/app/(dashboard)/provider-apis/_components/ConnectionTab.tsx`
- Create: `ui/litellm-dashboard/src/app/(dashboard)/provider-apis/_components/connectionState.ts`
- Create: `ui/litellm-dashboard/src/app/(dashboard)/provider-apis/_components/connectionState.test.ts`
- Create: `ui/litellm-dashboard/src/app/(dashboard)/provider-apis/_components/ConnectionTab.test.tsx`
- Modify: `ui/litellm-dashboard/src/components/leftnav.tsx:160-171`
- Modify: `ui/litellm-dashboard/src/components/page_metadata.ts:32`
- Modify: `ui/litellm-dashboard/src/utils/migratedPages.ts:23`
- Modify: `ui/litellm-dashboard/src/components/leftnav.test.tsx:175`

**Interfaces:**
- Consumes: `GET /provider/connections` from Task 5, returning `{ providers: [{ provider, display_name, state, accounts: [{ credential_name, state, detail, last_sync_at, last_outcome, facts_stored }], fetches: { endpoint, endpoint_url, grain, refresh_seconds, window_hours, delay_note, history_note } }] }`
- Produces:
  - `providerConnectionsCall(accessToken: string)` in `networking.tsx`
  - `useProviderConnections()` returning a TanStack query of `ProviderConnection[]`
  - `STATE_LABELS` and `stateBadgeVariant(state)` in `connectionState.ts`, reused by Task 8

- [ ] **Step 1: Write the failing state-label tests**

Create `ui/litellm-dashboard/src/app/(dashboard)/provider-apis/_components/connectionState.test.ts`:

```ts
import { describe, expect, it } from "vitest";

import { STATE_LABELS, stateBadgeVariant } from "./connectionState";

describe("connection state presentation", () => {
  it("names every state in plain language", () => {
    expect(STATE_LABELS).toEqual({
      not_connected: "Not connected",
      waiting_for_first_data: "Waiting for first data",
      healthy: "Healthy",
      needs_attention: "Needs attention",
    });
  });

  it("marks only a failing connection as destructive", () => {
    // Colouring 'waiting for first data' like a failure would send admins looking for a
    // problem on a connection that is working exactly as designed.
    expect(stateBadgeVariant("needs_attention")).toBe("destructive");
    expect(stateBadgeVariant("healthy")).toBe("default");
    expect(stateBadgeVariant("waiting_for_first_data")).toBe("secondary");
    expect(stateBadgeVariant("not_connected")).toBe("outline");
  });
});
```

- [ ] **Step 2: Run it and watch it fail**

```bash
cd ui/litellm-dashboard
npx vitest run "src/app/(dashboard)/provider-apis/_components/connectionState.test.ts"
```

Expected: FAIL, cannot resolve `./connectionState`

- [ ] **Step 3: Write the state presentation module**

Create `ui/litellm-dashboard/src/app/(dashboard)/provider-apis/_components/connectionState.ts`:

```ts
export type ConnectionState = "not_connected" | "waiting_for_first_data" | "healthy" | "needs_attention";

export const STATE_LABELS: Record<ConnectionState, string> = {
  not_connected: "Not connected",
  waiting_for_first_data: "Waiting for first data",
  healthy: "Healthy",
  needs_attention: "Needs attention",
};

export const stateBadgeVariant = (state: ConnectionState): "default" | "secondary" | "destructive" | "outline" => {
  switch (state) {
    case "needs_attention":
      return "destructive";
    case "healthy":
      return "default";
    case "waiting_for_first_data":
      return "secondary";
    default:
      return "outline";
  }
};
```

- [ ] **Step 4: Run it and watch it pass**

```bash
cd ui/litellm-dashboard
npx vitest run "src/app/(dashboard)/provider-apis/_components/connectionState.test.ts"
```

Expected: PASS, two tests

- [ ] **Step 5: Add the network call**

In `ui/litellm-dashboard/src/components/networking.tsx`, next to `credentialListCall`:

```ts
export const providerConnectionsCall = async (accessToken: string) => {
  try {
    return await apiClient.get(`/provider/connections`, { accessToken });
  } catch (error) {
    console.error("Failed to read provider connections:", error);
    throw error;
  }
};
```

- [ ] **Step 6: Add the query hook**

Create `ui/litellm-dashboard/src/app/(dashboard)/hooks/providerApis/useProviderConnections.ts`:

```ts
import { useQuery } from "@tanstack/react-query";

import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
import { providerConnectionsCall } from "@/components/networking";
import { all_admin_roles } from "@/utils/roles";
import type { ConnectionState } from "@/app/(dashboard)/provider-apis/_components/connectionState";

export interface ProviderConnectionAccount {
  credential_name: string;
  state: ConnectionState;
  detail: string | null;
  last_sync_at: string | null;
  last_outcome: string | null;
  facts_stored: number;
}

export interface ProviderFetchDetail {
  endpoint: string;
  endpoint_url: string;
  grain: string;
  refresh_seconds: number;
  window_hours: number;
  delay_note: string;
  history_note: string;
}

export interface ProviderConnection {
  provider: string;
  display_name: string;
  state: ConnectionState;
  accounts: ProviderConnectionAccount[];
  fetches: ProviderFetchDetail;
}

export const providerConnectionKeys = {
  all: ["provider-connections"] as const,
};

export const useProviderConnections = () => {
  const { accessToken, userRole } = useAuthorized();

  return useQuery<ProviderConnection[]>({
    queryKey: providerConnectionKeys.all,
    queryFn: async () => (await providerConnectionsCall(accessToken!)).providers,
    enabled: Boolean(accessToken) && all_admin_roles.includes(userRole ?? ""),
  });
};
```

- [ ] **Step 7: Write the failing Connection tab test**

Create `ui/litellm-dashboard/src/app/(dashboard)/provider-apis/_components/ConnectionTab.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import ConnectionTab from "./ConnectionTab";
import type { ProviderConnection } from "@/app/(dashboard)/hooks/providerApis/useProviderConnections";

const connection = (overrides: Partial<ProviderConnection> = {}): ProviderConnection => ({
  provider: "openai",
  display_name: "OpenAI",
  state: "healthy",
  accounts: [
    {
      credential_name: "prod",
      state: "healthy",
      detail: null,
      last_sync_at: "2026-09-16T09:00:00+00:00",
      last_outcome: "fetched",
      facts_stored: 42,
    },
  ],
  fetches: {
    endpoint: "Organization Costs",
    endpoint_url: "https://api.openai.com/v1/organization/costs",
    grain: "day",
    refresh_seconds: 300,
    window_hours: 24,
    delay_note: "Recent days can still change.",
    history_note: "There is no first-connection backfill yet.",
  },
  ...overrides,
});

describe("ConnectionTab", () => {
  it("tells an admin with no credential what to do next", () => {
    render(<ConnectionTab connection={connection({ state: "not_connected", accounts: [] })} />);

    expect(screen.getByText("Not connected")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /llm provider credentials/i })).toHaveAttribute(
      "href",
      expect.stringContaining("llm-provider-credentials"),
    );
  });

  it("shows the provider's own reason on a failing account", () => {
    // Without the reason the customer knows only that something is wrong, which is the state
    // they were already in before this page existed.
    render(
      <ConnectionTab
        connection={connection({
          state: "needs_attention",
          accounts: [
            {
              credential_name: "staging",
              state: "needs_attention",
              detail: "openai refused credential staging",
              last_sync_at: "2026-09-16T09:00:00+00:00",
              last_outcome: "failed",
              facts_stored: 0,
            },
          ],
        })}
      />,
    );

    expect(screen.getByText("openai refused credential staging")).toBeInTheDocument();
  });

  it("lists every account separately", () => {
    render(
      <ConnectionTab
        connection={connection({
          accounts: [
            { credential_name: "prod", state: "healthy", detail: null, last_sync_at: null, last_outcome: null, facts_stored: 42 },
            { credential_name: "staging", state: "healthy", detail: null, last_sync_at: null, last_outcome: null, facts_stored: 7 },
          ],
        })}
      />,
    );

    expect(screen.getByText("prod")).toBeInTheDocument();
    expect(screen.getByText("staging")).toBeInTheDocument();
  });

  it("says the keys are only ever read from", () => {
    render(<ConnectionTab connection={connection()} />);

    expect(screen.getByText(/read-only/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 8: Run it and watch it fail**

```bash
cd ui/litellm-dashboard
npx vitest run "src/app/(dashboard)/provider-apis/_components/ConnectionTab.test.tsx"
```

Expected: FAIL, cannot resolve `./ConnectionTab`

- [ ] **Step 9: Write the Connection tab**

Create `ui/litellm-dashboard/src/app/(dashboard)/provider-apis/_components/ConnectionTab.tsx`:

```tsx
"use client";

import Link from "next/link";

import type { ProviderConnection } from "@/app/(dashboard)/hooks/providerApis/useProviderConnections";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { migratedHref } from "@/utils/migratedPages";
import { STATE_LABELS, stateBadgeVariant } from "./connectionState";

const whenever = (value: string | null): string => (value === null ? "Never" : new Date(value).toLocaleString());

export default function ConnectionTab({ connection }: { connection: ProviderConnection }) {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center gap-3">
        <Badge variant={stateBadgeVariant(connection.state)}>{STATE_LABELS[connection.state]}</Badge>
        <Badge variant="outline">Read-only</Badge>
        <p className="text-sm text-muted-foreground">
          {connection.display_name} keys stored here are only ever used to read cost reports. They cannot send
          traffic or spend money
        </p>
      </div>

      {connection.accounts.length === 0 ? (
        <p className="text-sm">
          No account is connected yet. Add a read-only billing key on{" "}
          <Link href={migratedHref("llm-provider-credentials")} className="text-primary underline-offset-4 hover:underline">
            LLM Provider Credentials
          </Link>{" "}
          and choose Billing access as the purpose
        </p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Account</TableHead>
              <TableHead>State</TableHead>
              <TableHead>Last sync</TableHead>
              <TableHead>Rows stored</TableHead>
              <TableHead>Detail</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {connection.accounts.map((account) => (
              <TableRow key={account.credential_name}>
                <TableCell>{account.credential_name}</TableCell>
                <TableCell>
                  <Badge variant={stateBadgeVariant(account.state)}>{STATE_LABELS[account.state]}</Badge>
                </TableCell>
                <TableCell>{whenever(account.last_sync_at)}</TableCell>
                <TableCell>{account.facts_stored}</TableCell>
                <TableCell className="text-muted-foreground">{account.detail ?? ""}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
```

If `migratedHref` is not the exported helper name in `utils/migratedPages.ts`, use whatever `AddModelForm.tsx:323` already calls, which links to the same page.

- [ ] **Step 10: Run it and watch it pass**

```bash
cd ui/litellm-dashboard
npx vitest run "src/app/(dashboard)/provider-apis/_components/ConnectionTab.test.tsx"
```

Expected: PASS, four tests

- [ ] **Step 11: Write the panel and the route**

Create `ui/litellm-dashboard/src/app/(dashboard)/provider-apis/_components/ProviderApisPanel.tsx`:

```tsx
"use client";

import { useProviderConnections } from "@/app/(dashboard)/hooks/providerApis/useProviderConnections";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import ConnectionTab from "./ConnectionTab";
import { STATE_LABELS, stateBadgeVariant } from "./connectionState";

export default function ProviderApisPanel() {
  const { data: connections, isLoading, error } = useProviderConnections();

  if (isLoading) {
    return <p className="text-sm">Loading provider connections...</p>;
  }
  if (error) {
    return <p className="text-sm text-destructive">Could not read provider connections</p>;
  }
  if (!connections || connections.length === 0) {
    return <p className="text-sm">This build reads no provider billing APIs</p>;
  }

  return (
    <Tabs defaultValue={connections[0].provider}>
      <TabsList>
        {connections.map((connection) => (
          <TabsTrigger key={connection.provider} value={connection.provider}>
            <span className="flex items-center gap-2">
              {connection.display_name}
              <Badge variant={stateBadgeVariant(connection.state)}>{STATE_LABELS[connection.state]}</Badge>
            </span>
          </TabsTrigger>
        ))}
      </TabsList>
      {connections.map((connection) => (
        <TabsContent key={connection.provider} value={connection.provider} className="pt-6">
          <ConnectionTab connection={connection} />
        </TabsContent>
      ))}
    </Tabs>
  );
}
```

Create `ui/litellm-dashboard/src/app/(dashboard)/provider-apis/page.tsx`:

```tsx
"use client";

import { Plug } from "lucide-react";

import { PageHeader } from "@/components/shared/PageHeader";
import ProviderApisPanel from "./_components/ProviderApisPanel";

export default function ProviderApisPage() {
  return (
    <main className="flex h-full flex-col gap-6 p-8">
      <PageHeader
        icon={<Plug />}
        title="Provider APIs"
        subtitle="What each provider reports that your accounts cost, and whether we can still read it."
      />
      <ProviderApisPanel />
    </main>
  );
}
```

- [ ] **Step 12: Put it in the sidebar**

In `ui/litellm-dashboard/src/components/leftnav.tsx`, add a first item to the DATA SOURCES group, above LLM Provider Credentials, and import `Plug` from `lucide-react` alongside the existing icon imports:

```tsx
      {
        key: "provider-apis",
        page: "provider-apis",
        label: "Provider APIs",
        icon: <Plug {...ICON} />,
        roles: all_admin_roles,
      },
```

In `ui/litellm-dashboard/src/utils/migratedPages.ts`, beside the credentials entry:

```ts
  "provider-apis": "provider-apis",
```

In `ui/litellm-dashboard/src/components/page_metadata.ts`, beside the credentials entry:

```ts
  "provider-apis": "See what each provider reports your accounts cost, and whether the connection is healthy",
```

In `ui/litellm-dashboard/src/components/leftnav.test.tsx:175`, the DATA SOURCES expectation becomes:

```ts
      "DATA SOURCES": ["provider-apis", "llm-provider-credentials"],
```

- [ ] **Step 13: Run the affected tests**

```bash
cd ui/litellm-dashboard
npx vitest run "src/app/(dashboard)/provider-apis" src/components/leftnav.test.tsx src/components/page_utils.test.ts
```

Expected: PASS. `page_utils.test.ts` asserts that every navigable page has a description, so a missing `page_metadata.ts` entry fails there rather than in the sidebar test.

- [ ] **Step 14: Commit**

```bash
git add ui/litellm-dashboard/src
git commit -m "feat(ui): add a Provider APIs page showing each connection's state"
```

---

### Task 8: What We Fetch and Sync History

**Files:**
- Modify: `ui/litellm-dashboard/src/components/networking.tsx`
- Create: `ui/litellm-dashboard/src/app/(dashboard)/hooks/providerApis/useProviderSyncHistory.ts`
- Create: `ui/litellm-dashboard/src/app/(dashboard)/provider-apis/_components/WhatWeFetchTab.tsx`
- Create: `ui/litellm-dashboard/src/app/(dashboard)/provider-apis/_components/WhatWeFetchTab.test.tsx`
- Create: `ui/litellm-dashboard/src/app/(dashboard)/provider-apis/_components/SyncHistoryTab.tsx`
- Create: `ui/litellm-dashboard/src/app/(dashboard)/provider-apis/_components/SyncHistoryTab.test.tsx`
- Create: `ui/litellm-dashboard/src/app/(dashboard)/provider-apis/_components/fetchCadence.ts`
- Create: `ui/litellm-dashboard/src/app/(dashboard)/provider-apis/_components/fetchCadence.test.ts`
- Modify: `ui/litellm-dashboard/src/app/(dashboard)/provider-apis/_components/ProviderApisPanel.tsx`

**Interfaces:**
- Consumes: `ProviderConnection` and `ProviderFetchDetail` from Task 7's hook; `GET /provider/sync-history?provider=&limit=` from Task 5, returning `{ rows: [{ provider, credential_name, started_at, finished_at, outcome, facts_written, window_start, window_end, detail }] }`; `STATE_LABELS` and `stateBadgeVariant` from Task 7
- Produces: `describeCadence(seconds: number): string` and `describeWindow(hours: number): string` in `fetchCadence.ts`; `useProviderSyncHistory(provider: string)` returning a query of `ProviderSyncHistoryRow[]`

- [ ] **Step 1: Write the failing cadence tests**

Create `ui/litellm-dashboard/src/app/(dashboard)/provider-apis/_components/fetchCadence.test.ts`:

```ts
import { describe, expect, it } from "vitest";

import { describeCadence, describeWindow } from "./fetchCadence";

describe("describeCadence", () => {
  it("reads five minutes as minutes, not three hundred seconds", () => {
    expect(describeCadence(300)).toBe("Every 5 minutes");
  });

  it("reads an hour as an hour", () => {
    expect(describeCadence(3600)).toBe("Every hour");
  });

  it("reads a sub-minute cadence in seconds", () => {
    expect(describeCadence(45)).toBe("Every 45 seconds");
  });
});

describe("describeWindow", () => {
  it("reads twenty four hours as a day", () => {
    expect(describeWindow(24)).toBe("The last 1 day");
  });

  it("reads a part day in hours", () => {
    expect(describeWindow(6)).toBe("The last 6 hours");
  });
});
```

- [ ] **Step 2: Run them and watch them fail**

```bash
cd ui/litellm-dashboard
npx vitest run "src/app/(dashboard)/provider-apis/_components/fetchCadence.test.ts"
```

Expected: FAIL, cannot resolve `./fetchCadence`

- [ ] **Step 3: Write the cadence helpers**

Create `ui/litellm-dashboard/src/app/(dashboard)/provider-apis/_components/fetchCadence.ts`:

```ts
const plural = (count: number, unit: string): string => `${count} ${unit}${count === 1 ? "" : "s"}`;

export const describeCadence = (seconds: number): string => {
  if (seconds >= 3600) {
    const hours = Math.round(seconds / 3600);
    return hours === 1 ? "Every hour" : `Every ${plural(hours, "hour")}`;
  }
  if (seconds >= 60) {
    return `Every ${plural(Math.round(seconds / 60), "minute")}`;
  }
  return `Every ${plural(seconds, "second")}`;
};

export const describeWindow = (hours: number): string =>
  hours >= 24 ? `The last ${plural(Math.round(hours / 24), "day")}` : `The last ${plural(hours, "hour")}`;
```

- [ ] **Step 4: Run them and watch them pass**

```bash
cd ui/litellm-dashboard
npx vitest run "src/app/(dashboard)/provider-apis/_components/fetchCadence.test.ts"
```

Expected: PASS, five tests

- [ ] **Step 5: Write the failing What We Fetch test**

Create `ui/litellm-dashboard/src/app/(dashboard)/provider-apis/_components/WhatWeFetchTab.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import WhatWeFetchTab from "./WhatWeFetchTab";

const fetches = {
  endpoint: "Organization Costs",
  endpoint_url: "https://api.openai.com/v1/organization/costs",
  grain: "day",
  refresh_seconds: 300,
  window_hours: 24,
  delay_note: "Recent days can still change.",
  history_note: "There is no first-connection backfill yet.",
};

describe("WhatWeFetchTab", () => {
  it("says which endpoint is read and how often", () => {
    render(<WhatWeFetchTab fetches={fetches} />);

    expect(screen.getByText("Organization Costs")).toBeInTheDocument();
    expect(screen.getByText("Every 5 minutes")).toBeInTheDocument();
  });

  it("says how fine the data is, because that limits what can be compared", () => {
    // A customer who reads 'per day' here will not go looking for a per-request breakdown
    // that this provider cannot give.
    render(<WhatWeFetchTab fetches={fetches} />);

    expect(screen.getByText("Per day")).toBeInTheDocument();
  });

  it("repeats the provider's own caveats about delay and history", () => {
    render(<WhatWeFetchTab fetches={fetches} />);

    expect(screen.getByText("Recent days can still change.")).toBeInTheDocument();
    expect(screen.getByText("There is no first-connection backfill yet.")).toBeInTheDocument();
  });
});
```

- [ ] **Step 6: Run it and watch it fail**

```bash
cd ui/litellm-dashboard
npx vitest run "src/app/(dashboard)/provider-apis/_components/WhatWeFetchTab.test.tsx"
```

Expected: FAIL, cannot resolve `./WhatWeFetchTab`

- [ ] **Step 7: Write the What We Fetch tab**

Create `ui/litellm-dashboard/src/app/(dashboard)/provider-apis/_components/WhatWeFetchTab.tsx`:

```tsx
"use client";

import type { ProviderFetchDetail } from "@/app/(dashboard)/hooks/providerApis/useProviderConnections";
import { Table, TableBody, TableCell, TableRow } from "@/components/ui/table";
import { describeCadence, describeWindow } from "./fetchCadence";

export default function WhatWeFetchTab({ fetches }: { fetches: ProviderFetchDetail }) {
  const rows: ReadonlyArray<readonly [string, string]> = [
    ["Endpoint", fetches.endpoint],
    ["Address", fetches.endpoint_url],
    ["Detail level", fetches.grain === "request" ? "Per request" : "Per day"],
    ["Refresh", describeCadence(fetches.refresh_seconds)],
    ["Window read each time", describeWindow(fetches.window_hours)],
  ];

  return (
    <div className="flex flex-col gap-6">
      <Table>
        <TableBody>
          {rows.map(([label, value]) => (
            <TableRow key={label}>
              <TableCell className="w-56 font-medium">{label}</TableCell>
              <TableCell>{value}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <div className="flex flex-col gap-2 text-sm text-muted-foreground">
        <p>{fetches.delay_note}</p>
        <p>{fetches.history_note}</p>
      </div>
    </div>
  );
}
```

- [ ] **Step 8: Write the failing Sync History test**

Create `ui/litellm-dashboard/src/app/(dashboard)/provider-apis/_components/SyncHistoryTab.test.tsx`. Stub the hook at the module boundary so the component renders without a network:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const useProviderSyncHistory = vi.fn();
vi.mock("@/app/(dashboard)/hooks/providerApis/useProviderSyncHistory", () => ({ useProviderSyncHistory }));

import SyncHistoryTab from "./SyncHistoryTab";

const row = (overrides: Record<string, unknown> = {}) => ({
  provider: "openai",
  credential_name: "prod",
  started_at: "2026-09-16T09:00:00+00:00",
  finished_at: "2026-09-16T09:00:04+00:00",
  outcome: "fetched",
  facts_written: 12,
  window_start: "2026-09-15T09:00:00+00:00",
  window_end: "2026-09-16T09:00:00+00:00",
  detail: null,
  ...overrides,
});

describe("SyncHistoryTab", () => {
  it("says nothing has run yet rather than showing an empty table", () => {
    useProviderSyncHistory.mockReturnValue({ data: [], isLoading: false, error: null });

    render(<SyncHistoryTab provider="openai" />);

    expect(screen.getByText(/no sync has run yet/i)).toBeInTheDocument();
  });

  it("shows how many rows a run brought back", () => {
    useProviderSyncHistory.mockReturnValue({ data: [row()], isLoading: false, error: null });

    render(<SyncHistoryTab provider="openai" />);

    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByText("prod")).toBeInTheDocument();
  });

  it("shows the reason a run failed", () => {
    // A history that records only 'failed' leaves the customer exactly as stuck as before.
    useProviderSyncHistory.mockReturnValue({
      data: [row({ outcome: "failed", facts_written: 0, detail: "openai refused credential prod" })],
      isLoading: false,
      error: null,
    });

    render(<SyncHistoryTab provider="openai" />);

    expect(screen.getByText("openai refused credential prod")).toBeInTheDocument();
  });
});
```

- [ ] **Step 9: Run both and watch them fail**

```bash
cd ui/litellm-dashboard
npx vitest run "src/app/(dashboard)/provider-apis/_components/WhatWeFetchTab.test.tsx" "src/app/(dashboard)/provider-apis/_components/SyncHistoryTab.test.tsx"
```

Expected: FAIL, neither component resolves

- [ ] **Step 10: Add the history call and hook**

In `ui/litellm-dashboard/src/components/networking.tsx`, next to `providerConnectionsCall`:

```ts
export const providerSyncHistoryCall = async (accessToken: string, provider: string, limit: number) => {
  try {
    return await apiClient.get(`/provider/sync-history?provider=${encodeURIComponent(provider)}&limit=${limit}`, {
      accessToken,
    });
  } catch (error) {
    console.error("Failed to read provider sync history:", error);
    throw error;
  }
};
```

Create `ui/litellm-dashboard/src/app/(dashboard)/hooks/providerApis/useProviderSyncHistory.ts`:

```ts
import { useQuery } from "@tanstack/react-query";

import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
import { providerSyncHistoryCall } from "@/components/networking";
import { all_admin_roles } from "@/utils/roles";

export const SYNC_HISTORY_ROWS = 50;

export interface ProviderSyncHistoryRow {
  provider: string;
  credential_name: string;
  started_at: string;
  finished_at: string;
  outcome: string;
  facts_written: number;
  window_start: string;
  window_end: string;
  detail: string | null;
}

export const useProviderSyncHistory = (provider: string) => {
  const { accessToken, userRole } = useAuthorized();

  return useQuery<ProviderSyncHistoryRow[]>({
    queryKey: ["provider-sync-history", provider],
    queryFn: async () => (await providerSyncHistoryCall(accessToken!, provider, SYNC_HISTORY_ROWS)).rows,
    enabled: Boolean(accessToken && provider) && all_admin_roles.includes(userRole ?? ""),
  });
};
```

- [ ] **Step 11: Write the Sync History tab**

Create `ui/litellm-dashboard/src/app/(dashboard)/provider-apis/_components/SyncHistoryTab.tsx`:

```tsx
"use client";

import { useProviderSyncHistory } from "@/app/(dashboard)/hooks/providerApis/useProviderSyncHistory";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

const OUTCOME_LABELS: Record<string, string> = {
  fetched: "Fetched",
  not_configured: "Cannot be used",
  failed: "Failed",
};

const outcomeVariant = (outcome: string): "default" | "secondary" | "destructive" =>
  outcome === "fetched" ? "default" : outcome === "not_configured" ? "secondary" : "destructive";

export default function SyncHistoryTab({ provider }: { provider: string }) {
  const { data: rows, isLoading, error } = useProviderSyncHistory(provider);

  if (isLoading) {
    return <p className="text-sm">Loading sync history...</p>;
  }
  if (error) {
    return <p className="text-sm text-destructive">Could not read the sync history</p>;
  }
  if (!rows || rows.length === 0) {
    return <p className="text-sm">No sync has run yet for this provider</p>;
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Started</TableHead>
          <TableHead>Account</TableHead>
          <TableHead>Outcome</TableHead>
          <TableHead>Rows</TableHead>
          <TableHead>Detail</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row) => (
          <TableRow key={`${row.credential_name}-${row.started_at}`}>
            <TableCell>{new Date(row.started_at).toLocaleString()}</TableCell>
            <TableCell>{row.credential_name}</TableCell>
            <TableCell>
              <Badge variant={outcomeVariant(row.outcome)}>{OUTCOME_LABELS[row.outcome] ?? row.outcome}</Badge>
            </TableCell>
            <TableCell>{row.facts_written}</TableCell>
            <TableCell className="text-muted-foreground">{row.detail ?? ""}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
```

- [ ] **Step 12: Put the three tabs inside each provider**

In `ui/litellm-dashboard/src/app/(dashboard)/provider-apis/_components/ProviderApisPanel.tsx`, replace the body of each provider's `TabsContent` with an inner `Tabs`:

```tsx
        <TabsContent key={connection.provider} value={connection.provider} className="pt-6">
          <Tabs defaultValue="connection">
            <TabsList>
              <TabsTrigger value="connection">Connection</TabsTrigger>
              <TabsTrigger value="what-we-fetch">What We Fetch</TabsTrigger>
              <TabsTrigger value="sync-history">Sync History</TabsTrigger>
            </TabsList>
            <TabsContent value="connection" className="pt-6">
              <ConnectionTab connection={connection} />
            </TabsContent>
            <TabsContent value="what-we-fetch" className="pt-6">
              <WhatWeFetchTab fetches={connection.fetches} />
            </TabsContent>
            <TabsContent value="sync-history" className="pt-6">
              <SyncHistoryTab provider={connection.provider} />
            </TabsContent>
          </Tabs>
        </TabsContent>
```

with `WhatWeFetchTab` and `SyncHistoryTab` imported at the top.

- [ ] **Step 13: Run every dashboard test this plan touched**

```bash
cd ui/litellm-dashboard
npx vitest run "src/app/(dashboard)/provider-apis" src/components/leftnav.test.tsx src/components/page_utils.test.ts src/components/add_model/providerFieldDefaults.test.ts src/components/model_add/CredentialModal.test.tsx
npx tsc --noEmit
npx eslint "src/app/(dashboard)/provider-apis" src/components/add_model/providerFieldDefaults.ts
```

Expected: tests PASS, no type errors, no new lint findings

- [ ] **Step 14: Prove it in the browser**

```bash
~/.claude/scripts/litellm-dev-up.sh
```

Then open `http://localhost:4001/ui/?page=provider-apis`, sign in as the admin, and check that: the DATA SOURCES group lists Provider APIs above LLM Provider Credentials; every provider tab carries a state badge; the provider with a stored billing credential shows its account and a Read-only badge; What We Fetch names the endpoint and says Every 5 minutes; Sync History says no sync has run yet until the scheduler ticks, then lists a run.

- [ ] **Step 15: Commit and push**

```bash
git add ui/litellm-dashboard/src
git commit -m "feat(ui): add What We Fetch and Sync History to Provider APIs"
git push origin litellm_token_iq
```

---

## Self-Review

**Spec coverage against `2026-09-15-cost-platform-reference.md`, Data Sources / Provider APIs section**

| Spec requirement | Where |
|---|---|
| Four connection states: Not connected, Waiting for first data, Healthy, Needs attention with the reason | Task 5 `connection_state.py`, Task 7 `ConnectionTab` |
| Read-only badge | Task 7, ConnectionTab, with a test asserting it |
| Key type checked before saving | Already shipped in `litellm/provider_billing/credential_purpose.py`; no task needed |
| What We Fetch: endpoint, refresh cadence, typical delay, history loaded on first connection | Task 5 `fetch_profile.py`, Task 8 `WhatWeFetchTab`. The history line says plainly that no backfill exists yet rather than claiming a depth we have not built |
| Sync History shows each daily fetch | Tasks 3, 4, 5, 8. The first-backfill progress the spec also mentions has nothing to show until a backfill exists, so it is deliberately out of scope here |
| A vendor may need two connections, developer platform under Provider APIs and business product under User Tools | Out of scope. User Tools is a later phase, and nothing here forecloses it: a second connection is just another billing credential with its own provider slug |
| Every cost row records its data source | Partly. `ProviderUsageFact` already carries `provider` and `credential_name`, and Task 1 adds the provider's own payload. The normalised dimension set belongs to Usage / APIs, which is the next plan |

**Gaps accepted on purpose**

First-connection backfill, the normalised dimension set, and the Raw Data table itself are all Usage / APIs work. This plan stops at making the connection visible and the raw payload durable, which is what the next plan needs from it.

**Placeholder scan:** every step carries the code or the exact command. Three steps name a judgement the implementer must make rather than a value to fill in, and each states the decision rule and an acceptable alternative: the `pyright: ignore` lines in Task 3 Step 6, the `_record` argument shape in Task 4 Step 3, and the `group_by` result shape in Task 5 Step 6.

**Type consistency check**

- `BillingCredential(name, values)` is defined in Task 2 Step 4 and used with those field names in Tasks 2, 4 and 5
- `credentials_for` returns `tuple[BillingCredential, ...]` in Tasks 2, 4 and 5, never `| None`
- `ProviderSyncRun` is defined in Task 3 Step 3 and constructed with the same nine fields in Tasks 4 and 5 and in both repository tests
- `ProviderSyncRunRepository.recent(*, provider=None, limit=50)` is defined in Task 3 and called that way in Task 5, once with `provider=` and once without
- `account_state` and `provider_state` keep the signatures from Task 5 Step 3 in the endpoint of Step 10
- The endpoint field names `state`, `detail`, `last_sync_at`, `last_outcome`, `facts_stored` and `fetches` match one to one between the Pydantic models in Task 5 Step 9, the TypeScript interfaces in Task 7 Step 6, and every dashboard test fixture in Tasks 7 and 8
- `ConnectionState` has the same four members in Python (Task 5) and TypeScript (Task 7)
