# Attribution Rules and Unallocated Spend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every dollar a provider billed that the gateway never saw an owner, or say plainly that it has none.

**Architecture:** The provider says how much was spent and the gateway says who spent it. Subtracting the two per provider, account and day leaves a gap: spend that bypassed the gateway. A stored rule maps a provider account or a provider API key to a team, project or user, and the gap inherits that owner. A gap no rule matches is reported as unallocated rather than hidden or spread around. The matching is a pure function over rows so it can be tested without a database, and the SQL does the summing so the cost of the screen does not grow with the customer's billing history.

**Tech Stack:** Python 3.12, FastAPI, Prisma with Postgres, `prisma-client-py` raw queries, pytest. Dashboard is Next.js with shadcn/Base UI, TanStack Query and vitest.

**Spec:** `docs/superpowers/specs/2026-09-14-token-iq-product-design.md`, sections "The counting rule", "Key screens / Usage", and the Attribution Rules entry under ORGANISATION in "Full sidebar"

## Global Constraints

- The Combined view never adds the gateway figure and the provider figure together. For each provider and day, the provider's figure says how much was spent and the gateway's figure says who spent it
- Whatever the provider charged beyond what the gateway recorded is spend that bypassed the gateway. It gets its own line, assigned to a team, project or user through attribution rules, or shown as unallocated when no rule matches
- Every figure carries its source, an evidence level (`reconciled`, `priced` or `allocated`) and a freshness marker. A day that has not settled is labelled "not settled yet" rather than shown as a gap
- The hierarchy is teams, projects and users. Never "employees"
- Money is `Decimal` end to end and must never pass through `float`. In raw SQL every summed money column must be cast `::text` before it leaves Postgres, because `prisma-client-py` decodes a bare `numeric` as a float. `SUM(f.billed_cost::numeric)::text` is the pattern already used in `litellm/repositories/provider_usage_fact_repository.py:27`
- A `SUM` over a `bigint` column decodes as a float too. Cast it `::bigint` and read it through a helper that tolerates an integral float
- No customer-visible LiteLLM branding, and no company or customer names anywhere in code, commits or docs
- Never copy or adapt LiteLLM enterprise code (`enterprise/`, `litellm_enterprise`)
- Prisma migrations change schema only. No `UPDATE`, `DELETE`, `MERGE` or `INSERT ... SELECT`
- No `Any` or coarse types, every parameter strongly typed, `: Final` on every variable (LIT010), `ReadOnly[...]` on every TypedDict field (LIT012), no parameter rebinding (LIT011), immutable collections. `# mutable-ok: <reason>` only as a true last resort with a reason that is actually true
- Every lint or type suppression names its exact rule in brackets and carries a real reason. `# type: ignore` is banned
- No comments except genuinely complex business logic, tool-read suppressions, or TODO/FIXME with a strong reason
- Tests must test function, never structure, and must fail when the behaviour is mutated. Test bodies are executable assertions, never prose or a docstring
- Python max line length 120. TypeScript has no `any`, and no tokens in `localStorage`
- Never run the full dashboard vitest suite with no path
- Python is always `C:\Users\NikhilEruva\litellm\.venv\Scripts\python.exe`
- Conventional-commits messages, no Claude attribution or `Co-Authored-By` trailer

---

### Task 1: Make the existing daily reconciliation exact

**Why first:** everything in this plan subtracts the gateway figure from the provider figure. `litellm/proxy/management_endpoints/provider_reconciliation.py:249` sums `billed_cost` as a bare `numeric`, which `prisma-client-py` hands back as a float, so the figure this plan builds on is already inexact before any gap is computed. This is the same defect that was fixed in the Azure connector on the previous branch. Fixing it here means the gap is a difference of two exact numbers rather than a difference of two approximations.

**Files:**
- Modify: `litellm/proxy/management_endpoints/provider_reconciliation.py` (`_SQL` and `_DAILY_SQL`)
- Test: `tests/test_litellm/proxy/management_endpoints/test_provider_reconciliation.py`

**Interfaces:**
- Consumes: nothing
- Produces: `/provider/reconciliation/daily` and `/provider/reconciliation` returning exact amounts. Later tasks reuse the `::text` pattern, not these functions

- [ ] **Step 1: Write the failing test**

```python
async def test_daily_totals_keep_every_digit_the_provider_billed():
    db = FakeDb(rows=[{"day": "2026-09-19", "our_cost": "0.1", "their_cost": "0.30000000000000004"}])
    captured = await run_daily_reconciliation(db=db, provider="openai", days=7)
    assert captured.days[0].their_cost == Decimal("0.30000000000000004")
    assert "numeric)::text" in db.last_sql
    assert "SUM(f.billed_cost::numeric) AS" not in db.last_sql
```

- [ ] **Step 2: Run it and watch it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_litellm/proxy/management_endpoints/test_provider_reconciliation.py -v -k exact`
Expected: FAIL, because the SQL still selects a bare `numeric`

- [ ] **Step 3: Cast every summed money column to text**

In both `_SQL` and `_DAILY_SQL`, change each summed money expression so the value leaves Postgres as text:

```sql
SELECT to_char(COALESCE(ours.day, theirs.day), 'YYYY-MM-DD') AS day,
       ours.our_cost,
       theirs.their_cost
```

becomes a query whose two CTEs end in `::text`:

```sql
), theirs AS (
    SELECT date_trunc('day', f.bucket_start) AS day, SUM(f.billed_cost::numeric)::text AS their_cost
```

and the gateway side likewise: `SUM(s.spend)::numeric::text AS our_cost`. Keep the `ORDER BY` on the numeric expression, not on the text, so ordering stays numeric rather than lexicographic.

- [ ] **Step 4: Run the test and the file's existing tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_litellm/proxy/management_endpoints/test_provider_reconciliation.py -v`
Expected: PASS

- [ ] **Step 5: Prove it against the live proxy**

The proxy runs only via `~/.claude/scripts/litellm-dev-up.sh` on port 4001 with dev key `sk-1234`.

```bash
curl -s -H "Authorization: Bearer sk-1234" \
  "http://localhost:4001/provider/reconciliation/daily?provider=openrouter&days=7"
```

Expected: every cost is a quoted digit string, and the total matches `/provider/usage/summary?provider=openrouter&days=7`

- [ ] **Step 6: Commit**

```bash
git add litellm/proxy/management_endpoints/provider_reconciliation.py tests/test_litellm/proxy/management_endpoints/test_provider_reconciliation.py
git commit -m "fix(billing): keep reconciliation totals exact instead of decoding them as floats"
```

---

### Task 2: Store attribution rules

**Files:**
- Create: `litellm-proxy-extras/litellm_proxy_extras/migrations/20260920000000_attribution_rule/migration.sql`
- Modify: `schema.prisma`, `litellm/proxy/schema.prisma`, `litellm-proxy-extras/litellm_proxy_extras/schema.prisma`
- Create: `litellm/types/proxy/attribution.py`
- Create: `litellm/repositories/attribution_rule_repository.py`
- Test: `tests/test_litellm/repositories/test_attribution_rule_repository.py`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `MatchType = Literal["provider_api_key", "cloud_account"]`
  - `OwnerType = Literal["team", "project", "user"]`
  - `@dataclass(frozen=True, slots=True) class AttributionRule: rule_id: str; provider: str; match_type: MatchType; match_value: str; owner_type: OwnerType; owner_id: str; note: str | None`
  - `AttributionRuleRepository(db)` with `async def all(self) -> tuple[AttributionRule, ...]`, `async def upsert(self, rule: AttributionRule) -> AttributionRule`, `async def delete(self, rule_id: str) -> bool`

- [ ] **Step 1: Write the failing repository test**

```python
async def test_a_rule_round_trips_with_its_owner_and_match():
    repo = AttributionRuleRepository(FakeDb())
    stored = await repo.upsert(
        AttributionRule(
            rule_id="r1", provider="openai", match_type="cloud_account",
            match_value="finance-openai", owner_type="team", owner_id="t-7", note=None,
        )
    )
    assert stored.match_value == "finance-openai"
    assert (await repo.all())[0].owner_id == "t-7"


async def test_a_row_with_an_unknown_match_type_is_dropped_rather_than_guessed():
    repo = AttributionRuleRepository(FakeDb(rows=[{"rule_id": "r1", "provider": "openai",
        "match_type": "telepathy", "match_value": "x", "owner_type": "team", "owner_id": "t"}]))
    assert await repo.all() == ()
```

- [ ] **Step 2: Run it and watch it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_litellm/repositories/test_attribution_rule_repository.py -v`
Expected: FAIL with "No module named 'litellm.repositories.attribution_rule_repository'"

- [ ] **Step 3: Add the model to all three prisma schemas**

```prisma
// One rule mapping a provider account or a provider API key to the team, project or user
// that owns the spend it produced. Read by the unallocated gap calculation.
model LiteLLM_AttributionRule {
    rule_id     String   @id @default(uuid())
    provider    String
    match_type  String   // provider_api_key | cloud_account
    match_value String
    owner_type  String   // team | project | user
    owner_id    String
    note        String?
    created_at  DateTime @default(now())
    updated_at  DateTime @updatedAt

    @@unique([provider, match_type, match_value])
    @@index([provider])
}
```

The unique constraint is what makes matching unambiguous: one account cannot belong to two owners, so no priority or tie-break rule is needed anywhere in this plan.

- [ ] **Step 4: Write the migration**

`migration.sql`, schema only, no data rewrite:

```sql
CREATE TABLE "LiteLLM_AttributionRule" (
    "rule_id" TEXT NOT NULL,
    "provider" TEXT NOT NULL,
    "match_type" TEXT NOT NULL,
    "match_value" TEXT NOT NULL,
    "owner_type" TEXT NOT NULL,
    "owner_id" TEXT NOT NULL,
    "note" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,
    CONSTRAINT "LiteLLM_AttributionRule_pkey" PRIMARY KEY ("rule_id")
);

CREATE UNIQUE INDEX "LiteLLM_AttributionRule_provider_match_type_match_value_key"
    ON "LiteLLM_AttributionRule"("provider", "match_type", "match_value");

CREATE INDEX "LiteLLM_AttributionRule_provider_idx"
    ON "LiteLLM_AttributionRule"("provider");
```

- [ ] **Step 5: Write the types**

`litellm/types/proxy/attribution.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

MatchType = Literal["provider_api_key", "cloud_account"]
"""provider_api_key: the provider's own key id, which request-grain facts carry.
cloud_account: the stored credential a day-grain fact was fetched with."""

OwnerType = Literal["team", "project", "user"]


@dataclass(frozen=True, slots=True)
class AttributionRule:
    rule_id: str
    provider: str
    match_type: MatchType
    match_value: str
    owner_type: OwnerType
    owner_id: str
    note: str | None = None
```

- [ ] **Step 6: Write the repository**

Follow `litellm/repositories/provider_sync_run_repository.py` for the constructor shape and the row-reading helpers. A row whose `match_type` or `owner_type` is not in the literal is dropped, the same way `_fact_or_none` drops an unreadable fact, because a rule with a meaning nobody can name must not silently own someone's money.

- [ ] **Step 7: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_litellm/repositories/test_attribution_rule_repository.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add schema.prisma litellm/proxy/schema.prisma litellm-proxy-extras/litellm_proxy_extras/schema.prisma litellm-proxy-extras/litellm_proxy_extras/migrations/20260920000000_attribution_rule litellm/types/proxy/attribution.py litellm/repositories/attribution_rule_repository.py tests/test_litellm/repositories/test_attribution_rule_repository.py
git commit -m "feat(attribution): store rules mapping provider accounts and keys to owners"
```

---

### Task 3: Decide who owns a gap

**Files:**
- Create: `litellm/attribution/gap_owner.py`
- Create: `litellm/attribution/__init__.py`
- Test: `tests/test_litellm/attribution/test_gap_owner.py`

**Interfaces:**
- Consumes: `AttributionRule`, `MatchType`, `OwnerType` from `litellm/types/proxy/attribution.py`
- Produces:
  - `@dataclass(frozen=True, slots=True) class GapRow: provider: str; credential_name: str; provider_api_key_id: str | None; day: datetime; provider_cost: Decimal; gateway_cost: Decimal`
  - `@dataclass(frozen=True, slots=True) class AttributedGap: row: GapRow; gap: Decimal; owner_type: OwnerType | None; owner_id: str | None; rule_id: str | None; state: GapState`
  - `GapState = Literal["owned", "unallocated", "matched", "not_settled"]`
  - `def attribute(rows: Sequence[GapRow], rules: Sequence[AttributionRule], *, settled_before: datetime) -> tuple[AttributedGap, ...]`

This is a pure function with no database and no clock of its own, so every rule below is testable directly.

- [ ] **Step 1: Write the failing tests**

```python
def test_a_key_rule_beats_an_account_rule_for_the_same_gap():
    row = GapRow(provider="openai", credential_name="acct", provider_api_key_id="key-1",
                 day=DAY, provider_cost=Decimal("10"), gateway_cost=Decimal("4"))
    rules = (
        AttributionRule("r-acct", "openai", "cloud_account", "acct", "team", "t-1"),
        AttributionRule("r-key", "openai", "provider_api_key", "key-1", "project", "p-9"),
    )
    result = attribute((row,), rules, settled_before=SETTLED)
    assert result[0].owner_id == "p-9"
    assert result[0].gap == Decimal("6")


def test_a_gap_no_rule_matches_is_unallocated_not_zero():
    row = GapRow("openai", "acct", None, DAY, Decimal("10"), Decimal("4"))
    result = attribute((row,), (), settled_before=SETTLED)
    assert result[0].state == "unallocated"
    assert result[0].owner_id is None
    assert result[0].gap == Decimal("6")


def test_a_day_the_provider_has_not_settled_is_not_reported_as_a_gap():
    row = GapRow("openai", "acct", None, UNSETTLED_DAY, Decimal("0"), Decimal("4"))
    result = attribute((row,), (), settled_before=SETTLED)
    assert result[0].state == "not_settled"


def test_the_gateway_recording_more_than_the_provider_billed_is_never_a_negative_gap():
    row = GapRow("openai", "acct", None, DAY, Decimal("3"), Decimal("4"))
    result = attribute((row,), (), settled_before=SETTLED)
    assert result[0].state == "matched"
    assert result[0].gap == Decimal("0")


def test_a_rule_for_another_provider_never_matches():
    row = GapRow("openai", "acct", None, DAY, Decimal("10"), Decimal("4"))
    rules = (AttributionRule("r", "anthropic", "cloud_account", "acct", "team", "t-1"),)
    assert attribute((row,), rules, settled_before=SETTLED)[0].state == "unallocated"


def test_money_never_passes_through_a_float():
    row = GapRow("openai", "acct", None, DAY, Decimal("0.30000000000000004"), Decimal("0.1"))
    assert attribute((row,), (), settled_before=SETTLED)[0].gap == Decimal("0.20000000000000004")
```

- [ ] **Step 2: Run them and watch them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_litellm/attribution/test_gap_owner.py -v`
Expected: FAIL with "No module named 'litellm.attribution'"

- [ ] **Step 3: Write the matcher**

```python
def _match(row: GapRow, rules: Sequence[AttributionRule]) -> AttributionRule | None:
    """The provider's own key id wins over the account it sits in, because it is the
    narrower statement about who spent the money."""
    by_key: Final = next(
        (
            rule
            for rule in rules
            if rule.provider == row.provider
            and rule.match_type == "provider_api_key"
            and row.provider_api_key_id is not None
            and rule.match_value == row.provider_api_key_id
        ),
        None,
    )
    if by_key is not None:
        return by_key
    return next(
        (
            rule
            for rule in rules
            if rule.provider == row.provider
            and rule.match_type == "cloud_account"
            and rule.match_value == row.credential_name
        ),
        None,
    )
```

- [ ] **Step 4: Write `attribute`**

The order of the checks is the whole behaviour, so keep it explicit: an unsettled day is reported as unsettled before any arithmetic, a non-positive gap is `matched` with a gap of exactly `Decimal(0)` rather than a negative number, and only a positive gap on a settled day is looked up against the rules.

- [ ] **Step 5: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_litellm/attribution/test_gap_owner.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add litellm/attribution tests/test_litellm/attribution
git commit -m "feat(attribution): decide who owns spend that bypassed the gateway"
```

---

### Task 4: Compute the gap rows in SQL

**Files:**
- Create: `litellm/repositories/gap_repository.py`
- Test: `tests/test_litellm/repositories/test_gap_repository.py`

**Interfaces:**
- Consumes: `GapRow` from `litellm/attribution/gap_owner.py`
- Produces: `GapRepository(db)` with `async def rows(self, *, provider: str, days: int) -> tuple[GapRow, ...]`

- [ ] **Step 1: Write the failing test**

```python
async def test_gap_rows_come_back_as_exact_decimals():
    db = FakeDb(rows=[{
        "provider": "openai", "credential_name": "acct", "provider_api_key_id": None,
        "day": "2026-09-19", "provider_cost": "0.30000000000000004", "gateway_cost": "0.1",
    }])
    rows = await GapRepository(db).rows(provider="openai", days=7)
    assert rows[0].provider_cost == Decimal("0.30000000000000004")
    assert "::text" in db.last_sql


async def test_a_provider_day_the_gateway_never_saw_still_produces_a_row():
    db = FakeDb(rows=[{"provider": "openai", "credential_name": "acct", "provider_api_key_id": None,
                       "day": "2026-09-19", "provider_cost": "5", "gateway_cost": None}])
    rows = await GapRepository(db).rows(provider="openai", days=7)
    assert rows[0].gateway_cost == Decimal(0)


async def test_a_row_with_an_unreadable_cost_is_dropped_rather_than_zeroed():
    db = FakeDb(rows=[{"provider": "openai", "credential_name": "acct", "provider_api_key_id": None,
                       "day": "2026-09-19", "provider_cost": "not a number", "gateway_cost": "1"}])
    assert await GapRepository(db).rows(provider="openai", days=7) == ()
```

- [ ] **Step 2: Run them and watch them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_litellm/repositories/test_gap_repository.py -v`
Expected: FAIL with "No module named 'litellm.repositories.gap_repository'"

- [ ] **Step 3: Write the SQL**

```sql
WITH theirs AS (
    SELECT f.provider,
           f.credential_name,
           f.provider_api_key_id,
           date_trunc('day', f.bucket_start)   AS day,
           SUM(f.billed_cost::numeric)::text   AS provider_cost
      FROM "LiteLLM_ProviderUsageFact" f
     WHERE f.provider = $1
       AND f.bucket_start >= NOW() - ($2 || ' days')::interval
     GROUP BY 1, 2, 3, 4
), ours AS (
    SELECT date_trunc('day', s."startTime") AS day,
           SUM(s.spend)::numeric::text      AS gateway_cost
      FROM "LiteLLM_SpendLogs" s
     WHERE s.custom_llm_provider = $1
       AND s."startTime" >= NOW() - ($2 || ' days')::interval
     GROUP BY 1
)
SELECT theirs.provider,
       theirs.credential_name,
       theirs.provider_api_key_id,
       to_char(theirs.day, 'YYYY-MM-DD') AS day,
       theirs.provider_cost,
       ours.gateway_cost
  FROM theirs LEFT JOIN ours ON theirs.day = ours.day
 ORDER BY theirs.day DESC, theirs.credential_name
```

The gateway side is grouped by day alone, because a gateway spend log records the virtual key that made the call and not the provider account the provider later billed. Attributing the gateway figure to an account would be inventing a link the data does not contain. Say that in the module docstring.

- [ ] **Step 4: Write the row reader**

Reuse the shape of `_fact_or_none` in `litellm/repositories/provider_usage_fact_repository.py`: a row missing a readable cost is dropped, and `gateway_cost` absent means the gateway saw nothing that day, which is `Decimal(0)` rather than a dropped row.

- [ ] **Step 5: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_litellm/repositories/test_gap_repository.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add litellm/repositories/gap_repository.py tests/test_litellm/repositories/test_gap_repository.py
git commit -m "feat(attribution): read per-account daily gaps between provider and gateway"
```

---

### Task 5: Serve the rules and the unallocated list

**Files:**
- Create: `litellm/proxy/management_endpoints/attribution.py`
- Modify: `litellm/proxy/proxy_server.py` (register the router next to the other provider billing routers)
- Test: `tests/test_litellm/proxy/management_endpoints/test_attribution.py`

**Interfaces:**
- Consumes: `AttributionRuleRepository`, `GapRepository`, `attribute`
- Produces these routes, all admin only, matching how `provider_connections.py` guards with `LitellmUserRoles.PROXY_ADMIN`:
  - `GET  /attribution/rules` -> `{"rules": [...]}`
  - `POST /attribution/rules` -> the stored rule
  - `DELETE /attribution/rules/{rule_id}` -> `{"deleted": true}`
  - `GET  /attribution/unallocated?provider=<p>&days=<n>` -> `{"provider", "days", "total_unallocated", "total_owned", "lines": [...]}`

- [ ] **Step 1: Write the failing endpoint tests**

```python
async def test_unallocated_totals_are_exact_strings_not_numbers():
    body = await get_unallocated(provider="openai", days=7, gaps=(GAP_10_MINUS_4,), rules=())
    assert body["total_unallocated"] == "6"
    assert isinstance(body["total_unallocated"], str)


async def test_an_owned_gap_is_not_counted_as_unallocated():
    body = await get_unallocated(provider="openai", days=7, gaps=(GAP_10_MINUS_4,), rules=(ACCT_RULE,))
    assert body["total_unallocated"] == "0"
    assert body["total_owned"] == "6"


async def test_a_non_admin_cannot_read_another_team_s_unallocated_spend():
    with pytest.raises(HTTPException) as caught:
        await get_unallocated(provider="openai", days=7, role=LitellmUserRoles.INTERNAL_USER)
    assert caught.value.status_code == 403


async def test_creating_a_rule_for_an_unknown_owner_type_is_refused():
    with pytest.raises(HTTPException) as caught:
        await post_rule({"provider": "openai", "match_type": "cloud_account",
                         "match_value": "a", "owner_type": "departmnet", "owner_id": "x"})
    assert caught.value.status_code == 400
```

- [ ] **Step 2: Run them and watch them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_litellm/proxy/management_endpoints/test_attribution.py -v`
Expected: FAIL with "No module named 'litellm.proxy.management_endpoints.attribution'"

- [ ] **Step 3: Write the response models and the routes**

Model the response with Pydantic so the amounts serialise as strings, the way `ProviderUsageSummaryResponse` in `provider_usage.py` already does. Validate the POST body with a Pydantic model whose `match_type` and `owner_type` are the `Literal` types from Task 2, so an unknown value is a 400 from validation rather than a row nobody can read later.

- [ ] **Step 4: Register the router**

Follow exactly how `provider_connections.router` is included in `litellm/proxy/proxy_server.py`.

- [ ] **Step 5: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_litellm/proxy/management_endpoints/test_attribution.py -v`
Expected: PASS

- [ ] **Step 6: Prove it against the live proxy**

```bash
curl -s -X POST -H "Authorization: Bearer sk-1234" -H "Content-Type: application/json" \
  http://localhost:4001/attribution/rules \
  -d '{"provider":"openrouter","match_type":"cloud_account","match_value":"tq_openrouter","owner_type":"team","owner_id":"demo-team"}'

curl -s -H "Authorization: Bearer sk-1234" \
  "http://localhost:4001/attribution/unallocated?provider=openrouter&days=7"
```

Expected: the rule comes back with a `rule_id`, and the unallocated response moves that provider's gap out of `total_unallocated` and into `total_owned`. Delete the rule afterwards and confirm it moves back.

- [ ] **Step 7: Commit**

```bash
git add litellm/proxy/management_endpoints/attribution.py litellm/proxy/proxy_server.py tests/test_litellm/proxy/management_endpoints/test_attribution.py
git commit -m "feat(attribution): serve attribution rules and unallocated spend"
```

---

### Task 6: The Attribution Rules screen

**Files:**
- Create: `ui/litellm-dashboard/src/app/(dashboard)/attribution/page.tsx`
- Create: `ui/litellm-dashboard/src/app/(dashboard)/attribution/_components/AttributionTabs.tsx`
- Create: `ui/litellm-dashboard/src/app/(dashboard)/attribution/_components/RuleTable.tsx`
- Create: `ui/litellm-dashboard/src/app/(dashboard)/attribution/_components/UnmatchedPanel.tsx`
- Create: `ui/litellm-dashboard/src/app/(dashboard)/hooks/attribution/useAttributionRules.ts`
- Create: `ui/litellm-dashboard/src/app/(dashboard)/hooks/attribution/useUnallocated.ts`
- Modify: `ui/litellm-dashboard/src/components/networking.ts` (four calls plus their response types)
- Modify: `ui/litellm-dashboard/src/components/leftnav.tsx` (add Attribution Rules under ORGANISATION)
- Test: `ui/litellm-dashboard/src/app/(dashboard)/attribution/_components/AttributionTabs.integration.test.tsx`

**Interfaces:**
- Consumes: the four routes from Task 5
- Produces: the sidebar entry `Attribution Rules` under ORGANISATION, with tabs `Provider Keys`, `Cloud Accounts` and `Unmatched`

Tool Logins is the fourth tab in the spec and belongs to Phase 4, when user tools exist. Do not add a disabled or empty tab for it: an empty tab that does nothing is a promise the product cannot keep yet.

- [ ] **Step 1: Write the failing integration test**

```tsx
it("shows an unmatched gap as money with no owner rather than as zero", async () => {
  server.use(unallocatedHandler({ total_unallocated: "6", lines: [UNOWNED_LINE] }));
  render(<AttributionTabs />);
  await userEvent.click(screen.getByRole("tab", { name: /unmatched/i }));
  expect(await screen.findByText("$6.00")).toBeInTheDocument();
  expect(screen.getByText(/no rule matches/i)).toBeInTheDocument();
});

it("keeps the chosen provider when moving between tabs", async () => {
  render(<AttributionTabs />);
  fireEvent.change(screen.getByLabelText(/provider/i), { target: { value: "anthropic" } });
  await userEvent.click(screen.getByRole("tab", { name: /cloud accounts/i }));
  await userEvent.click(screen.getByRole("tab", { name: /provider keys/i }));
  expect(screen.getByLabelText(/provider/i)).toHaveValue("anthropic");
});
```

- [ ] **Step 2: Run it and watch it fail**

Run: `cd ui/litellm-dashboard && npx vitest run src/app/\(dashboard\)/attribution`
Expected: FAIL, the module does not exist

- [ ] **Step 3: Build the tabs**

Base UI `Tabs` unmounts an inactive panel unless `keepMounted` is set, which silently resets the provider filter on a tab round-trip. `ui/litellm-dashboard/src/app/(dashboard)/usage/_components/UsageTabs.tsx` already carries `keepMounted` with a comment explaining exactly this; follow it.

- [ ] **Step 4: Add the sidebar entry**

Add `Attribution Rules` under ORGANISATION in `leftnav.tsx`, after Budgets, matching the spec's sidebar. Do not remove, merge or rename any existing entry.

- [ ] **Step 5: Run the touched tests only**

Run: `cd ui/litellm-dashboard && npx vitest run src/app/\(dashboard\)/attribution`
Expected: PASS. Never run the whole suite with no path.

- [ ] **Step 6: Regenerate the API types**

Run: `cd ui/litellm-dashboard && npm run gen:api`, then commit the regenerated `src/lib/http/schema.d.ts`. Never hand-edit it.

- [ ] **Step 7: Commit**

```bash
git add ui/litellm-dashboard/src
git commit -m "feat(attribution): add the attribution rules screen"
```

---

### Task 7: Say what is built and what is not

**Files:**
- Modify: `docs/superpowers/specs/2026-09-14-token-iq-product-design.md`

- [ ] **Step 1: Update the status table**

In "Where the product stands", add a row or extend the existing Provider API ingestion row to say that attribution rules and unallocated spend exist, that a rule maps a provider account or provider API key to a team, project or user, and that Tool Logins is not built because user tools are not built.

- [ ] **Step 2: Record the honest limit**

Say plainly that the gateway side of the gap is grouped by day only, because a gateway spend log names the virtual key and not the provider account, so a customer with several accounts on one provider sees the gap per account only on the provider's side. Do not imply a precision the data does not support.

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/specs/2026-09-14-token-iq-product-design.md
git commit -m "docs: record attribution rules as built and name the gateway grouping limit"
```

---

## Self-Review

**1. Spec coverage**

| Spec requirement | Task |
|---|---|
| Gap is provider figure minus gateway figure, never a sum | Tasks 3 and 4 |
| The gap gets its own line assigned through attribution rules | Tasks 2, 3 and 5 |
| Unallocated when no rule matches | Tasks 3, 5 and 6 |
| A day that has not settled is labelled, not shown as a gap | Task 3, `not_settled` |
| Every figure carries its source and evidence level | Task 4 keeps `provider_cost` and `gateway_cost` separate on every row, so the source of each is never lost |
| Attribution Rules screen with Provider Keys, Cloud Accounts, Unmatched | Task 6 |
| Tool Logins tab | Deliberately not built. Phase 4, when user tools exist |
| Teams, projects and users, never "employees" | `OwnerType` in Task 2 |

**2. Placeholder scan**

No "TBD", no "add error handling", no "similar to Task N". Every code step carries the code. Task 6's two tests are written out rather than described.

**3. Type consistency**

- `MatchType` and `OwnerType` are defined once in Task 2 and imported by Tasks 3 and 5
- `AttributionRule` has the same seven fields in Tasks 2, 3 and 5
- `GapRow` is produced by Task 4 and consumed by Task 3, with the same six fields in both
- `attribute(rows, rules, *, settled_before)` has one signature, used in Tasks 3 and 5
- The provider slug is the same string everywhere: the connector's `provider` property, the fact's `provider` column, and the rule's `provider` column

**4. Known gap accepted on purpose**

The gateway spend log does not record which provider account served a request, so the gateway half of every gap is per day rather than per account. For a customer with one account per provider, which is the common case, the gap is exact. For a customer with several accounts on one provider, the per-account split is the provider's view only. Task 7 requires this to be written down rather than left for someone to discover from a wrong number.
