# Usage / APIs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Read back the provider usage facts this product already stores, as a Summary of what each provider charged and a Raw Data view of exactly what each provider sent

**Architecture:** Three layers. The store gains two bounded read paths: one that aggregates a window of facts in SQL, and one that pages raw rows newest first. The read layer adds two proxy-admin endpoints over those, alongside a per-provider coverage summary computed from the data rather than asserted. The dashboard's Usage page gains a tab layer, its existing content becoming Gateway, and a new APIs tab with a provider picker and Summary and Raw Data views per provider.

**Tech Stack:** Python 3.12, FastAPI, Prisma/Postgres raw SQL for aggregation, pytest; Next.js 15, TypeScript, shadcn/Base UI primitives, TanStack Query, vitest with Testing Library

**Spec:** `docs/superpowers/specs/2026-09-15-cost-platform-reference.md` (the Usage / APIs section) and `docs/superpowers/specs/2026-09-14-token-iq-product-design.md` (the agreed Usage tree)

## Global Constraints

- All work goes on the existing branch `litellm_token_iq`. Never touch `main`, never create a branch or worktree per task
- Do not add `Co-Authored-By` or any Claude attribution to commit messages. This has been slipped in six times on the previous plan and once cost a git history rewrite
- Never copy or adapt code from `enterprise/` or `litellm_enterprise`, including anything in history before `728daee2d8`
- No customer or company names anywhere. Publicly known providers (OpenAI, Anthropic, AWS Bedrock, OpenRouter) are fine
- No customer-visible LiteLLM branding in new dashboard copy
- Python runs only through `C:/Users/NikhilEruva/litellm/.venv/Scripts/python.exe`. Never the system Python 3.14
- Python max line length is 120
- No comments except: genuinely complex business logic, a lint/type suppression naming its exact rule in brackets WITH a reason, or a TODO/FIXME with a strong reason. Docstrings are expected and are not comments
- Every suppression names its exact rule in brackets and carries a reason. A rule code with no reason is itself a violation (LIT004) that fails the budget gate. `# type: ignore` is banned (LIT009)
- LIT001/LIT002: no mutable collections in annotations or construction. LIT010: `: Final` on locals. LIT011: never rebind or mutate a parameter
- Fully typed. No `Any`, no bare `dict`, no `dict[str, Any]`, except at an untyped runtime boundary using the existing `# any-ok: <reason>` pattern
- No `any` in TypeScript. Prefer a union over a coarse `string` where the set is known
- Never remove, rename or reorder an existing UI tab or sidebar entry. Moving existing content into a new tab is permitted and is what Task 5 does
- Dashboard: never run the full vitest suite; pass explicit paths. Never put tokens in `localStorage`
- The lint budget gates crash on this Windows box because `scripts/gate_slot_lock.py` imports `fcntl` unconditionally. Implementers must not run them; the controller verifies the budget
- Run tests in the FOREGROUND. Do not background a test run and wait on it
- `src/lib/http/schema.d.ts` is generated. After changing a route or response model, regenerate with: `LITELLM_PYTHON="C:/Users/NikhilEruva/litellm/.venv/Scripts/python.exe" PYTHONUTF8=1 PYTHONPATH="C:/Users/NikhilEruva/litellm" npm run gen:api`
- Human-facing text: no emojis, no em dashes, prose over bullets, no trailing period on a paragraph
- Conventional commits

## What the stored data actually supports, and what it does not

This is the plan's central constraint. `LiteLLM_ProviderUsageFact` holds: `provider`, `credential_name`, `grain`, `bucket_start`, `evidence`, `provider_request_id`, `provider_api_key_id`, `model`, `billed_cost`, `billing_currency`, `input_tokens`, `output_tokens`, `cached_input_tokens`, `cache_write_tokens`, `raw`, `fetched_at`.

So these breakdowns are honest and are built: by model, by token type (input, output, cache read, cache write), by account (`credential_name`), by the provider's own key id where it sends one, and by evidence level.

These appear in the reference research but are NOT in the stored data, and are therefore NOT built: service tier, region, model maker, and per-user attribution. None of the four connectors parses them today. A column showing blanks would imply we lost something we never had.

Rather than hardcoding claims about which provider reports what, Task 8 computes coverage from the window's own rows and says plainly which fields that provider did not populate. That stays true as connectors change.

On settling windows, only Bedrock has a verified constant (`SETTLING_HOURS: Final = 48` in `litellm/provider_billing/bedrock.py`). Task 1 carries that through honestly and says the window is unknown for the others rather than inventing one.

---

## File Structure

**Backend, created**

| File | Responsibility |
|---|---|
| `litellm/provider_billing/usage_summary.py` | Pure shaping of aggregate rows into a summary, no I/O |
| `litellm/proxy/management_endpoints/provider_usage.py` | `GET /provider/usage/summary` and `GET /provider/usage/raw` |

**Backend, modified**

| File | Change |
|---|---|
| `litellm/provider_billing/fetch_profile.py` | `settling_note` on `FetchProfile` |
| `litellm/repositories/provider_usage_fact_repository.py` | `summary_rows`, `token_totals`, `recent_facts` |
| `litellm/types/proxy/management_endpoints/team_endpoints.py` | Response models |
| `litellm/proxy/proxy_server.py` | Register the router |

**Dashboard, created**

| File | Responsibility |
|---|---|
| `src/app/(dashboard)/usage/_components/UsageTabs.tsx` | Gateway and APIs tab shell |
| `src/app/(dashboard)/usage/_components/apis/ProviderUsagePanel.tsx` | Provider picker, Summary and Raw Data tabs |
| `src/app/(dashboard)/usage/_components/apis/UsageSummaryView.tsx` | The breakdowns |
| `src/app/(dashboard)/usage/_components/apis/RawDataView.tsx` | Paged raw rows and the provider payload |
| `src/app/(dashboard)/usage/_components/apis/CoverageNote.tsx` | What this provider did not report |
| `src/app/(dashboard)/hooks/providerUsage/useProviderUsageSummary.ts` | Query for the summary |
| `src/app/(dashboard)/hooks/providerUsage/useProviderUsageRaw.ts` | Paged query for raw rows |

**Dashboard, modified**

| File | Change |
|---|---|
| `src/app/(dashboard)/usage/page.tsx` | Render the tab shell around existing content |
| `src/components/networking.tsx` | `providerUsageSummaryCall`, `providerUsageRawCall`, wire types |

---

### Task 1: Say how long a provider's figures keep moving

**Why:** the reference research is explicit that recent figures change after the fact, and that a cost screen must say so. We know this precisely for one provider and not at all for the others. Saying nothing invites someone to treat yesterday's number as final; inventing a window is worse.

**Files:**
- Modify: `litellm/provider_billing/fetch_profile.py`
- Test: `tests/test_litellm/provider_billing/test_fetch_profile.py`

**Interfaces:**
- Consumes: `FetchProfile` and `FETCH_PROFILES` as they exist
- Produces: `FetchProfile.settling_note: str`, present on all four profiles

- [ ] **Step 1: Write the failing test**

Append to `tests/test_litellm/provider_billing/test_fetch_profile.py`:

```python
def test_every_profile_says_whether_its_figures_still_move():
    """A cost screen that does not say a number is still settling invites someone to
    treat it as final. Every provider must state something, even if that something is
    that we do not know."""
    from litellm.provider_billing.fetch_profile import FETCH_PROFILES

    for provider, profile in FETCH_PROFILES.items():
        assert profile.settling_note, f"{provider} has no settling_note"


def test_bedrocks_settling_note_matches_the_constant_that_drives_it():
    """The 48 hour cutoff is real code, not a claim. If someone changes the constant the
    text must move with it, or the screen starts lying."""
    from litellm.provider_billing.bedrock import SETTLING_HOURS
    from litellm.provider_billing.fetch_profile import FETCH_PROFILES

    assert str(SETTLING_HOURS) in FETCH_PROFILES["bedrock"].settling_note


def test_providers_without_a_verified_window_say_so_rather_than_inventing_one():
    from litellm.provider_billing.fetch_profile import FETCH_PROFILES

    for provider in ("openai", "anthropic", "openrouter"):
        note = FETCH_PROFILES[provider].settling_note.lower()
        assert "not" in note or "unknown" in note
```

- [ ] **Step 2: Run it and watch it fail**

```bash
C:/Users/NikhilEruva/litellm/.venv/Scripts/python.exe -m pytest tests/test_litellm/provider_billing/test_fetch_profile.py -v
```

Expected: FAIL with `AttributeError: 'FetchProfile' object has no attribute 'settling_note'`

- [ ] **Step 3: Add the field**

In `litellm/provider_billing/fetch_profile.py`, add `settling_note: str` to the `FetchProfile` dataclass after `history_note`, and a parameter to the `_profile` helper so each provider supplies its own. Import `SETTLING_HOURS` from `litellm.provider_billing.bedrock` and build Bedrock's note from it rather than typing 48 again.

Use these exact notes:

```python
_NO_VERIFIED_SETTLING: Final = (
    "How long this provider keeps adjusting recent figures has not been verified against "
    "a real account, so treat the most recent days as provisional."
)
```

Bedrock's note must contain the constant, for example:

```python
f"Cost Explorer settles over about {SETTLING_HOURS} hours, so the most recent day is "
"deliberately not read until it stops moving."
```

The other three take `_NO_VERIFIED_SETTLING`.

If importing `SETTLING_HOURS` from `bedrock.py` creates a circular import, move the constant into `fetch_profile.py` and import it from there in `bedrock.py` instead. It must exist in exactly one place: a settling window that disagrees with the cutoff actually applied is a lie to the customer.

- [ ] **Step 4: Run it and watch it pass**

```bash
C:/Users/NikhilEruva/litellm/.venv/Scripts/python.exe -m pytest tests/test_litellm/provider_billing/test_fetch_profile.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add litellm/provider_billing/fetch_profile.py tests/test_litellm/provider_billing/test_fetch_profile.py
git commit -m "feat(billing): say how long each provider keeps adjusting its figures"
```

---

### Task 2: Aggregate a window of facts without reading them all

**Why:** the Summary needs totals by model, by account and by token type over a window. The facts table grows on every scheduler tick, so this must aggregate in the database. Pulling rows into Python to sum them would eventually take the database down while someone is looking at a dashboard.

**Files:**
- Modify: `litellm/repositories/provider_usage_fact_repository.py`
- Test: `tests/test_litellm/repositories/test_provider_usage_fact_repository.py`

**Interfaces:**
- Consumes: the existing `ProviderUsageFactRepository(prisma_client)` and its `_table` property
- Produces:
  - `async def summary_rows(self, *, provider: str, days: int) -> tuple[SummaryRow, ...]`
  - `async def token_totals(self, *, provider: str, days: int) -> TokenTotals`
  - both defined as frozen slotted dataclasses in `litellm/types/proxy/provider_billing.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_litellm/repositories/test_provider_usage_fact_repository.py`:

```python
@pytest.mark.asyncio
async def test_summary_rows_aggregate_in_sql_and_are_bounded_by_the_window():
    """This table grows on every scheduler tick. Summing in Python would mean reading the
    whole history to render one screen."""
    from litellm.repositories.provider_usage_fact_repository import ProviderUsageFactRepository

    client = MagicMock()
    client.db.query_raw = AsyncMock(return_value=[])

    await ProviderUsageFactRepository(client).summary_rows(provider="openai", days=30)

    sql, *params = client.db.query_raw.await_args.args
    assert "group by" in sql.lower()
    assert "sum(" in sql.lower()
    assert params[0] == "openai"
    assert params[1] == "30"


@pytest.mark.asyncio
async def test_summary_rows_carry_model_account_cost_and_request_count():
    from litellm.repositories.provider_usage_fact_repository import ProviderUsageFactRepository

    client = MagicMock()
    client.db.query_raw = AsyncMock(
        return_value=[
            {
                "model": "gpt-4o",
                "credential_name": "prod",
                "evidence": "reconciled",
                "billed_cost": Decimal("12.5"),
                "facts": 3,
            }
        ]
    )

    rows = await ProviderUsageFactRepository(client).summary_rows(provider="openai", days=7)

    assert rows[0].model == "gpt-4o"
    assert rows[0].credential_name == "prod"
    assert rows[0].evidence == "reconciled"
    assert rows[0].billed_cost == Decimal("12.5")
    assert rows[0].facts == 3


@pytest.mark.asyncio
async def test_a_row_we_cannot_read_is_dropped_rather_than_guessed():
    """A malformed aggregate row must not become a zero-cost line that silently understates
    the bill."""
    from litellm.repositories.provider_usage_fact_repository import ProviderUsageFactRepository

    client = MagicMock()
    client.db.query_raw = AsyncMock(return_value=[{"model": "gpt-4o", "billed_cost": "not-a-number"}])

    assert await ProviderUsageFactRepository(client).summary_rows(provider="openai", days=7) == ()


@pytest.mark.asyncio
async def test_token_totals_sum_each_token_type_separately():
    """Input, output, cache read and cache write are priced differently. Collapsing them
    into one number hides the thing a reader is looking for."""
    from litellm.repositories.provider_usage_fact_repository import ProviderUsageFactRepository

    client = MagicMock()
    client.db.query_raw = AsyncMock(
        return_value=[{"input": 100, "output": 20, "cached_input": 5, "cache_write": 2}]
    )

    totals = await ProviderUsageFactRepository(client).token_totals(provider="openai", days=7)

    assert (totals.input_tokens, totals.output_tokens) == (100, 20)
    assert (totals.cached_input_tokens, totals.cache_write_tokens) == (5, 2)
```

Add any of `Decimal`, `MagicMock`, `AsyncMock`, `pytest` the file does not already import.

- [ ] **Step 2: Run it and watch it fail**

```bash
C:/Users/NikhilEruva/litellm/.venv/Scripts/python.exe -m pytest tests/test_litellm/repositories/test_provider_usage_fact_repository.py -v
```

Expected: FAIL with `AttributeError: 'ProviderUsageFactRepository' object has no attribute 'summary_rows'`

- [ ] **Step 3: Add the types**

In `litellm/types/proxy/provider_billing.py`, after `ProviderSyncRun`:

```python
@dataclass(frozen=True, slots=True)
class SummaryRow:
    model: str | None
    credential_name: str
    evidence: EvidenceLevel
    billed_cost: Decimal
    facts: int


@dataclass(frozen=True, slots=True)
class TokenTotals:
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int
    cache_write_tokens: int
```

- [ ] **Step 4: Add the queries**

In `litellm/repositories/provider_usage_fact_repository.py`, add two module-level SQL constants and two methods. `billed_cost` is TEXT, so every arithmetic use must cast:

```python
_SUMMARY_SQL: Final = """
SELECT f.model,
       f.credential_name,
       f.evidence,
       SUM(f.billed_cost::numeric) AS billed_cost,
       COUNT(*)                    AS facts
  FROM "LiteLLM_ProviderUsageFact" f
 WHERE f.provider = $1
   AND f.bucket_start >= NOW() - ($2 || ' days')::interval
 GROUP BY f.model, f.credential_name, f.evidence
 ORDER BY 4 DESC
"""

_TOKENS_SQL: Final = """
SELECT COALESCE(SUM(f.input_tokens), 0)        AS input,
       COALESCE(SUM(f.output_tokens), 0)       AS output,
       COALESCE(SUM(f.cached_input_tokens), 0) AS cached_input,
       COALESCE(SUM(f.cache_write_tokens), 0)  AS cache_write
  FROM "LiteLLM_ProviderUsageFact" f
 WHERE f.provider = $1
   AND f.bucket_start >= NOW() - ($2 || ' days')::interval
"""
```

Both methods pass `days` as `str(days)` to match the existing interval-casting pattern already used in `litellm/proxy/management_endpoints/provider_reconciliation.py`. Drop any row whose cost cannot be read as a Decimal, following the `_run_or_none` shape already used in `litellm/repositories/provider_sync_run_repository.py`: return `None` for an unreadable row and filter those out, rather than substituting a zero.

- [ ] **Step 5: Run it and watch it pass**

```bash
C:/Users/NikhilEruva/litellm/.venv/Scripts/python.exe -m pytest tests/test_litellm/repositories/test_provider_usage_fact_repository.py -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add litellm/repositories/provider_usage_fact_repository.py litellm/types/proxy/provider_billing.py tests/test_litellm/repositories/test_provider_usage_fact_repository.py
git commit -m "feat(billing): aggregate provider usage facts in the database"
```

---

### Task 3: Shape the aggregates into a summary

**Why:** the endpoint should not hold the arithmetic that decides what a customer is told their AI spend was. Keeping it pure means every branch can be read and tested on its own, the same reason `connection_state.py` exists.

**Files:**
- Create: `litellm/provider_billing/usage_summary.py`
- Test: `tests/test_litellm/provider_billing/test_usage_summary.py`

**Interfaces:**
- Consumes: `SummaryRow`, `TokenTotals`, `EvidenceLevel` from `litellm/types/proxy/provider_billing.py`
- Produces:
  - `build_usage_summary(rows: Sequence[SummaryRow], tokens: TokenTotals) -> UsageSummary`
  - `UsageSummary` with `total_cost: Decimal`, `by_model: tuple[ModelSpend, ...]`, `by_account: tuple[AccountSpend, ...]`, `by_evidence: Mapping[EvidenceLevel, Decimal]`, `tokens: TokenTotals`, `facts: int`

- [ ] **Step 1: Write the failing test**

Create `tests/test_litellm/provider_billing/test_usage_summary.py`:

```python
from __future__ import annotations

from decimal import Decimal

from litellm.types.proxy.provider_billing import SummaryRow, TokenTotals

TOKENS = TokenTotals(input_tokens=100, output_tokens=20, cached_input_tokens=5, cache_write_tokens=2)


def _row(model, account="prod", evidence="reconciled", cost="1", facts=1) -> SummaryRow:
    return SummaryRow(
        model=model,
        credential_name=account,
        evidence=evidence,
        billed_cost=Decimal(cost),
        facts=facts,
    )


def test_spend_by_model_is_summed_across_accounts_and_ordered_by_cost():
    from litellm.provider_billing.usage_summary import build_usage_summary

    summary = build_usage_summary(
        (_row("gpt-4o", "prod", cost="2"), _row("gpt-4o", "staging", cost="3"), _row("o3", cost="4")),
        TOKENS,
    )

    assert [(m.model, m.billed_cost) for m in summary.by_model] == [
        ("gpt-4o", Decimal("5")),
        ("o3", Decimal("4")),
    ]


def test_spend_by_account_is_summed_across_models():
    """A company running two accounts needs to see which one is spending, which is the
    whole reason several accounts per provider are read separately."""
    from litellm.provider_billing.usage_summary import build_usage_summary

    summary = build_usage_summary(
        (_row("gpt-4o", "prod", cost="2"), _row("o3", "prod", cost="3"), _row("o3", "staging", cost="1")),
        TOKENS,
    )

    assert [(a.credential_name, a.billed_cost) for a in summary.by_account] == [
        ("prod", Decimal("5")),
        ("staging", Decimal("1")),
    ]


def test_a_row_with_no_model_is_kept_and_labelled_rather_than_dropped():
    """Web search and code execution charges carry no model. Dropping them would make the
    breakdown add up to less than the bill."""
    from litellm.provider_billing.usage_summary import build_usage_summary

    summary = build_usage_summary((_row(None, cost="7"),), TOKENS)

    assert summary.by_model[0].model is None
    assert summary.total_cost == Decimal("7")


def test_the_total_equals_the_sum_of_the_parts():
    """If the headline figure and the breakdown disagree, a reader cannot trust either."""
    from litellm.provider_billing.usage_summary import build_usage_summary

    summary = build_usage_summary(
        (_row("gpt-4o", cost="2"), _row("o3", cost="3"), _row(None, cost="1")), TOKENS
    )

    assert summary.total_cost == Decimal("6")
    assert sum(m.billed_cost for m in summary.by_model) == summary.total_cost
    assert sum(a.billed_cost for a in summary.by_account) == summary.total_cost


def test_evidence_is_split_so_a_reader_knows_what_the_provider_actually_asserted():
    """reconciled means the provider asserted dollars. allocated means only our own gateway
    events exist. Showing one number for both would overstate how much of this is confirmed."""
    from litellm.provider_billing.usage_summary import build_usage_summary

    summary = build_usage_summary(
        (_row("gpt-4o", evidence="reconciled", cost="4"), _row("o3", evidence="allocated", cost="1")),
        TOKENS,
    )

    assert summary.by_evidence["reconciled"] == Decimal("4")
    assert summary.by_evidence["allocated"] == Decimal("1")


def test_an_empty_window_summarises_to_zero_rather_than_failing():
    from litellm.provider_billing.usage_summary import build_usage_summary

    summary = build_usage_summary((), TokenTotals(0, 0, 0, 0))

    assert summary.total_cost == Decimal(0)
    assert summary.by_model == ()
    assert summary.facts == 0
```

- [ ] **Step 2: Run it and watch it fail**

```bash
C:/Users/NikhilEruva/litellm/.venv/Scripts/python.exe -m pytest tests/test_litellm/provider_billing/test_usage_summary.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'litellm.provider_billing.usage_summary'`

- [ ] **Step 3: Write the summariser**

Create `litellm/provider_billing/usage_summary.py`. Build every collection in one shot with comprehensions; do not seed an empty dict and mutate it. Group with `collections.Counter` or a comprehension over `sorted`, then freeze with `tuple()` and `MappingProxyType()`. Define `ModelSpend` and `AccountSpend` as frozen slotted dataclasses in this module, since nothing outside it constructs them.

The module docstring should say why the split by evidence matters: a reader needs to know which figures the provider asserted and which we derived.

- [ ] **Step 4: Run it and watch it pass**

```bash
C:/Users/NikhilEruva/litellm/.venv/Scripts/python.exe -m pytest tests/test_litellm/provider_billing/test_usage_summary.py -v
```

Expected: PASS, seven tests

- [ ] **Step 5: Commit**

```bash
git add litellm/provider_billing/usage_summary.py tests/test_litellm/provider_billing/test_usage_summary.py
git commit -m "feat(billing): shape provider usage aggregates into a summary"
```

---

### Task 4: Serve the summary

**Files:**
- Create: `litellm/proxy/management_endpoints/provider_usage.py`
- Modify: `litellm/types/proxy/management_endpoints/team_endpoints.py`
- Modify: `litellm/proxy/proxy_server.py`
- Test: `tests/test_litellm/proxy/management_endpoints/test_provider_usage.py`

**Interfaces:**
- Consumes: `build_usage_summary`, `summary_rows`, `token_totals`, `FETCH_PROFILES`
- Produces: `GET /provider/usage/summary?provider=<slug>&days=<n>`, proxy-admin only

- [ ] **Step 1: Write the failing tests**

Create `tests/test_litellm/proxy/management_endpoints/test_provider_usage.py` with four tests, following the shape already used in `tests/test_litellm/proxy/management_endpoints/test_provider_connections.py` (read that file first and reuse its ADMIN/NON_ADMIN fixtures and patching approach):

```python
@pytest.mark.asyncio
async def test_only_an_admin_may_read_provider_usage():
    """This exposes what every account in the deployment spent. A non-admin reaching it
    leaks financial data across teams."""


@pytest.mark.asyncio
async def test_usage_without_a_database_answers_500_not_a_crash():
    ...


@pytest.mark.asyncio
async def test_an_unknown_provider_is_refused_rather_than_answering_an_empty_summary():
    """An empty summary for a typo'd provider reads as 'you spent nothing', which is a
    different and much worse message than 'no such provider'."""


@pytest.mark.asyncio
async def test_the_response_carries_the_settling_note_so_recent_figures_are_not_read_as_final():
    ...
```

Write each body out fully against the route, asserting status codes and response fields. Do not leave the docstrings alone as the test.

- [ ] **Step 2: Run them and watch them fail**

```bash
C:/Users/NikhilEruva/litellm/.venv/Scripts/python.exe -m pytest tests/test_litellm/proxy/management_endpoints/test_provider_usage.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Add the response models**

In `litellm/types/proxy/management_endpoints/team_endpoints.py`, after the provider connection models. Costs cross as strings holding exact digits, matching `ReconciliationRow` in the same file; token counts are integers. Type `evidence` with the existing `EvidenceLevel` Literal rather than `str`:

```python
class ProviderModelSpend(BaseModel):
    model: str | None
    billed_cost: str


class ProviderAccountSpend(BaseModel):
    credential_name: str
    billed_cost: str


class ProviderTokenTotals(BaseModel):
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int
    cache_write_tokens: int


class ProviderUsageSummaryResponse(BaseModel):
    provider: str
    display_name: str
    days: int
    total_cost: str
    facts: int
    by_model: tuple[ProviderModelSpend, ...]
    by_account: tuple[ProviderAccountSpend, ...]
    by_evidence: Mapping[EvidenceLevel, str]
    tokens: ProviderTokenTotals
    grain: UsageGrain
    delay_note: str
    settling_note: str
```

Use `tuple[...]` not `list[...]`: three `list` fields on the previous plan's response models broke the LIT001 budget and had to be changed.

- [ ] **Step 4: Write the endpoint**

Create `litellm/proxy/management_endpoints/provider_usage.py`. Guard admin access and a missing `prisma_client` exactly as `provider_connections.py` does. Refuse an unknown provider with 404 and a message naming the valid slugs. Bound `days` with `fastapi.Query(default=30, ge=1, le=90)`.

Register the router in `litellm/proxy/proxy_server.py` beside `provider_connections_router`.

- [ ] **Step 5: Run the tests and watch them pass**

```bash
C:/Users/NikhilEruva/litellm/.venv/Scripts/python.exe -m pytest tests/test_litellm/proxy/management_endpoints/test_provider_usage.py tests/test_litellm/provider_billing/ -v
```

Expected: PASS

- [ ] **Step 6: Prove it against the running proxy**

```bash
~/.claude/scripts/litellm-dev-up.sh
curl -s -H "Authorization: Bearer sk-1234" "http://localhost:4001/provider/usage/summary?provider=openrouter&days=30"
curl -s -o /dev/null -w "%{http_code}\n" "http://localhost:4001/provider/usage/summary?provider=openrouter"
```

Expected: a summary for openrouter, and 401 without credentials.

- [ ] **Step 7: Regenerate the dashboard types and commit**

```bash
cd ui/litellm-dashboard
LITELLM_PYTHON="C:/Users/NikhilEruva/litellm/.venv/Scripts/python.exe" PYTHONUTF8=1 PYTHONPATH="C:/Users/NikhilEruva/litellm" npm run gen:api
cd ../..
git add litellm tests/test_litellm ui/litellm-dashboard/src/lib/http/schema.d.ts
git commit -m "feat(billing): serve a usage summary per provider"
```

---

### Task 5: Serve the raw rows

**Why:** the reference research says Raw Data keeps every provider field. We store the provider's own payload on every fact, and nothing reads it back yet. That was the entire point of storing it.

**Files:**
- Modify: `litellm/repositories/provider_usage_fact_repository.py`
- Modify: `litellm/proxy/management_endpoints/provider_usage.py`
- Modify: `litellm/types/proxy/management_endpoints/team_endpoints.py`
- Test: `tests/test_litellm/repositories/test_provider_usage_fact_repository.py`
- Test: `tests/test_litellm/proxy/management_endpoints/test_provider_usage.py`

**Interfaces:**
- Consumes: the repository and endpoint from Tasks 2 and 4
- Produces:
  - `async def recent_facts(self, *, provider: str, limit: int, before: datetime | None) -> tuple[ProviderUsageFact, ...]`
  - `GET /provider/usage/raw?provider=<slug>&limit=<n>&before=<iso>`

- [ ] **Step 1: Write the failing repository test**

```python
@pytest.mark.asyncio
async def test_recent_facts_are_bounded_ordered_newest_first_in_the_database():
    """Rendered on every page of the Raw Data view against a table that grows on every
    tick. An unbounded or Python-sorted read would eventually take the database down."""
    from litellm.repositories.provider_usage_fact_repository import ProviderUsageFactRepository

    table = MagicMock()
    table.find_many = AsyncMock(return_value=[])
    client = MagicMock()
    client.db.litellm_providerusagefact = table

    await ProviderUsageFactRepository(client).recent_facts(provider="openai", limit=50, before=None)

    call = table.find_many.await_args.kwargs
    assert call["where"] == {"provider": "openai"}
    assert call["order"] == {"bucket_start": "desc"}
    assert call["take"] == 50


@pytest.mark.asyncio
async def test_paging_asks_only_for_rows_older_than_the_cursor():
    """Offset paging re-reads everything before the page. This table is append-heavy, so a
    keyset cursor is the difference between a fast page ten and a slow one."""
    from litellm.repositories.provider_usage_fact_repository import ProviderUsageFactRepository

    table = MagicMock()
    table.find_many = AsyncMock(return_value=[])
    client = MagicMock()
    client.db.litellm_providerusagefact = table
    cursor = datetime(2026, 9, 15, tzinfo=timezone.utc)

    await ProviderUsageFactRepository(client).recent_facts(provider="openai", limit=10, before=cursor)

    assert table.find_many.await_args.kwargs["where"] == {
        "provider": "openai",
        "bucket_start": {"lt": cursor},
    }
```

- [ ] **Step 2: Run them and watch them fail, then implement**

```bash
C:/Users/NikhilEruva/litellm/.venv/Scripts/python.exe -m pytest tests/test_litellm/repositories/test_provider_usage_fact_repository.py -v
```

Implement `recent_facts` mapping rows to `ProviderUsageFact`, dropping any row that cannot be read rather than substituting defaults, following the `_run_or_none` shape in `provider_sync_run_repository.py`. Carry `raw` through unchanged: it is the whole point of this view.

- [ ] **Step 3: Add the response model**

```python
class ProviderRawFact(BaseModel):
    bucket_start: str
    grain: UsageGrain
    evidence: EvidenceLevel
    credential_name: str
    model: str | None
    provider_request_id: str | None
    provider_api_key_id: str | None
    billed_cost: str
    billing_currency: str
    input_tokens: int | None
    output_tokens: int | None
    cached_input_tokens: int | None
    cache_write_tokens: int | None
    raw: Mapping[str, object] | None
    fetched_at: str


class ProviderUsageRawResponse(BaseModel):
    provider: str
    rows: tuple[ProviderRawFact, ...]
    next_before: str | None
```

`next_before` is the `bucket_start` of the last row, or `None` when the page was not full. That is the cursor the client sends back.

- [ ] **Step 4: Add the route, test, and prove it live**

Add `GET /provider/usage/raw` to `provider_usage.py` with the same admin and database guards, `limit` bounded by `fastapi.Query(default=50, ge=1, le=200)`. Add route tests for the 403 and 500 paths matching Task 4's, plus one asserting `next_before` is `None` on a short page and set on a full one.

```bash
curl -s -H "Authorization: Bearer sk-1234" "http://localhost:4001/provider/usage/raw?provider=openrouter&limit=5"
```

- [ ] **Step 5: Regenerate types and commit**

```bash
cd ui/litellm-dashboard
LITELLM_PYTHON="C:/Users/NikhilEruva/litellm/.venv/Scripts/python.exe" PYTHONUTF8=1 PYTHONPATH="C:/Users/NikhilEruva/litellm" npm run gen:api
cd ../..
git add litellm tests/test_litellm ui/litellm-dashboard/src/lib/http/schema.d.ts
git commit -m "feat(billing): serve the provider's own payload as raw usage rows"
```

---

### Task 6: Give the Usage page a tab layer

**Why:** the agreed tree has Usage carrying Gateway, APIs and Combined. Today the page is only the gateway view. This adds the shell so APIs has somewhere to live.

**This task MOVES existing content, it does not remove it.** Everything the Usage page renders today must appear unchanged under a Gateway tab, which opens by default. Nothing is deleted, renamed or reordered. Combined is Phase 3 and is NOT added, not even disabled: a dead tab teaches people the product is unfinished.

**Files:**
- Create: `ui/litellm-dashboard/src/app/(dashboard)/usage/_components/UsageTabs.tsx`
- Create: `ui/litellm-dashboard/src/app/(dashboard)/usage/_components/UsageTabs.test.tsx`
- Modify: `ui/litellm-dashboard/src/app/(dashboard)/usage/page.tsx`

**Interfaces:**
- Produces: `UsageTabs` taking `gateway: React.ReactNode` and `apis: React.ReactNode`

- [ ] **Step 1: Write the failing test**

```tsx
describe("UsageTabs", () => {
  it("opens on Gateway so today's view is what a returning user still sees first", () => {
    render(<UsageTabs gateway={<p>gateway content</p>} apis={<p>apis content</p>} />);
    expect(screen.getByText("gateway content")).toBeInTheDocument();
  });

  it("shows the APIs view when that tab is chosen", async () => {
    const user = userEvent.setup();
    render(<UsageTabs gateway={<p>gateway content</p>} apis={<p>apis content</p>} />);
    await user.click(screen.getByRole("tab", { name: "APIs" }));
    expect(await screen.findByText("apis content")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run it, watch it fail, then build the shell**

```bash
cd ui/litellm-dashboard
npx vitest run "src/app/(dashboard)/usage/_components/UsageTabs.test.tsx"
```

Build `UsageTabs` with the `Tabs` primitives from `@/components/ui/tabs`, defaulting to `gateway`. Then change `usage/page.tsx` to render the existing content as the `gateway` prop. Pass a placeholder for `apis` in this task only; Task 7 replaces it.

- [ ] **Step 3: Confirm nothing was lost**

```bash
cd ui/litellm-dashboard
npx vitest run "src/app/(dashboard)/usage"
git diff --stat "src/app/(dashboard)/usage/page.tsx"
```

Read the diff. Every component the page rendered before must still be rendered. If anything was dropped, restore it.

- [ ] **Step 4: Commit**

```bash
git add "ui/litellm-dashboard/src/app/(dashboard)/usage"
git commit -m "feat(ui): give the Usage page Gateway and APIs tabs"
```

---

### Task 7: The APIs tab

**Files:**
- Create: `src/app/(dashboard)/usage/_components/apis/ProviderUsagePanel.tsx` and its test
- Create: `src/app/(dashboard)/usage/_components/apis/UsageSummaryView.tsx` and its test
- Create: `src/app/(dashboard)/hooks/providerUsage/useProviderUsageSummary.ts`
- Modify: `src/components/networking.tsx`, `src/app/(dashboard)/usage/page.tsx`

**Interfaces:**
- Consumes: `GET /provider/usage/summary` from Task 4
- Produces: `providerUsageSummaryCall`, wire types declared in `networking.tsx` with hooks importing them, and `useProviderUsageSummary(provider, days)`

Declare the wire types in `networking.tsx` and have the hook import them, NOT the reverse: a networking module importing from an app-route hook is a backwards dependency. This was corrected on the previous plan; do not reintroduce it.

- [ ] **Step 1: Write the failing tests**

Cover: a provider picker listing only providers this build can read (OpenAI, Anthropic, Amazon Bedrock, OpenRouter); Summary showing total spend, spend by model, spend by account and the four token types; the settling note rendered so recent figures are not read as final; and an empty window showing a meaningful message rather than a zero-filled table.

Assert on values a user can perceive and pin the substantive copy, not just a keyword. An assertion loose enough to pass against reversed copy is a defect.

- [ ] **Step 2: Build it**

The picker's provider list comes from the summary endpoint's own vocabulary, not a hardcoded array, so Azure and Vertex appear automatically when their connectors land.

- [ ] **Step 3: Run the tests, then commit**

```bash
cd ui/litellm-dashboard
npx vitest run "src/app/(dashboard)/usage"
```

```bash
git commit -m "feat(ui): add the APIs tab with a per-provider usage summary"
```

---

### Task 8: Raw Data, and saying what a provider did not report

**Why:** this closes the loop on stored payloads, and it is where the plan keeps its promise about honesty. The reference research lists dimensions we do not have. Rather than hardcoding claims per provider, compute coverage from the rows in the window and say which fields that provider did not populate. That stays true as connectors change.

**Files:**
- Create: `src/app/(dashboard)/usage/_components/apis/RawDataView.tsx` and its test
- Create: `src/app/(dashboard)/usage/_components/apis/CoverageNote.tsx` and its test
- Create: `src/app/(dashboard)/usage/_components/apis/coverage.ts` and its test
- Create: `src/app/(dashboard)/hooks/providerUsage/useProviderUsageRaw.ts`
- Modify: `src/components/networking.tsx`, `ProviderUsagePanel.tsx`

**Interfaces:**
- Consumes: `GET /provider/usage/raw` from Task 5
- Produces: `fieldsNotReported(rows: readonly ProviderRawFact[]): readonly string[]` in `coverage.ts`

- [ ] **Step 1: Write the failing coverage tests**

```ts
describe("fieldsNotReported", () => {
  it("names a field no row in the window populated", () => {
    expect(fieldsNotReported([row({ provider_api_key_id: null })])).toContain("API key");
  });

  it("does not name a field some row did populate", () => {
    expect(fieldsNotReported([row({ provider_api_key_id: null }), row({ provider_api_key_id: "k" })]))
      .not.toContain("API key");
  });

  it("says nothing at all for an empty window rather than claiming everything is missing", () => {
    // An empty window means we have no evidence either way. Listing every field as
    // unreported would tell a customer their provider is broken when nothing has synced.
    expect(fieldsNotReported([])).toEqual([]);
  });
});
```

- [ ] **Step 2: Build coverage, the Raw Data table and the note**

Raw Data shows one row per fact with its stored fields, and lets a row expand to reveal the provider's own payload verbatim. The coverage note reads as a plain sentence naming the fields this provider did not send in this window, with a line saying that service tier, region and per-user attribution are not collected by this build at all, so nobody reads their absence as data loss.

- [ ] **Step 3: Run the tests, prove it in the browser, commit**

```bash
cd ui/litellm-dashboard
npx vitest run "src/app/(dashboard)/usage"
```

Then open `http://localhost:4001/ui/?page=new_usage`, choose APIs, and check both views against a provider with stored facts.

```bash
git commit -m "feat(ui): add Raw Data and say what each provider did not report"
```

---

## Self-Review

**Spec coverage**

| Reference spec requirement | Where |
|---|---|
| Summary adds breakdowns by token type next to spend by model | Tasks 3 and 7 |
| Breakdown by key or workspace | Partly. By account (`credential_name`) in Tasks 3 and 7. The provider's own key id is shown per row in Raw Data, Task 8, but is null for every current connector, so it is not a summary axis |
| Breakdown by service tier | NOT BUILT, and deliberately. Not stored, not parsed by any connector. Task 8 states its absence on screen |
| By user where the provider supplies it | NOT BUILT. None of the four provider endpoints supplies it. Task 8 states this |
| Detail level and delay note | Task 4 carries `grain` and `delay_note` through; Task 7 renders them |
| How many recent days may still change, per provider | Task 1, honestly: derived from the real constant for Bedrock, stated as unverified for the other three |
| Raw Data keeps every provider field | Tasks 5 and 8 |
| Raw Data adds the normalised dimensions and the data source | Partly. Source (provider, account, evidence) yes. The full normalised dimension set needs model maker, region and service tier, none of which exist yet; that belongs with Usage / Combined in Phase 3 |

**Gaps accepted on purpose:** service tier, region, model maker and per-user attribution all require new ingestion work in the connectors. Inventing columns for them would be the dishonesty this plan exists to avoid. Usage / Combined, and the Azure and Vertex connectors, remain Phase 2 and 3 work.

**Type consistency**

- `SummaryRow` and `TokenTotals` are defined in Task 2 and consumed with those field names in Task 3
- `build_usage_summary(rows, tokens) -> UsageSummary` is defined in Task 3 and called that way in Task 4
- `recent_facts(*, provider, limit, before)` is defined in Task 5 and used by its own route
- The endpoint field names in Tasks 4 and 5 match the TypeScript consumed in Tasks 7 and 8 one for one
- `EvidenceLevel` and `UsageGrain` are the existing Literals from `litellm/types/proxy/provider_billing.py`, not re-declared
