# Usage / Combined Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One screen where a company sees what its providers billed, what its gateway recorded, and who owns the difference, without the two ever being added together.

**Architecture:** The engine already exists. `litellm/repositories/gap_repository.py` produces the per-account daily comparison and `litellm/attribution/gap_owner.py` decides who owns each difference, both proven against real data. This plan widens the comparison from one provider to all of them, adds a grouping of gateway spend by team, project, user, provider or model, and puts three views on a new Combined tab. The arithmetic stays in pure functions and the summing stays in SQL.

**Tech Stack:** Python 3.12, FastAPI, Prisma with Postgres, `prisma-client-py` raw queries, pytest. Dashboard is Next.js with shadcn/Base UI, TanStack Query and vitest.

**Spec:** `docs/superpowers/specs/2026-09-14-token-iq-product-design.md`, sections "The counting rule" and "Key screens / Usage"

## Global Constraints

- The Combined view never adds the gateway figure and the provider figure together. For each provider and day, the provider's figure says how much was spent and the gateway's figure says who spent it
- Whatever the provider charged beyond what the gateway recorded is spend that bypassed the gateway. It is assigned through an attribution rule or shown as unallocated
- A day the provider has not finished billing is labelled "not settled yet", never shown as a gap. A day the provider has reported nothing about is never labelled as agreement
- The hierarchy is teams, projects and users. Never "employees"
- Money is `Decimal` end to end and must never pass through `float`. Every summed money column leaves Postgres cast `::text`, because `prisma-client-py` decodes a bare `numeric` as a float. `SUM(f.billed_cost::numeric)::text` is the established pattern
- Never remove, merge or rename an existing UI tab. Adding one is fine
- No customer-visible LiteLLM branding, and no company or customer names anywhere
- Never copy or adapt LiteLLM enterprise code (`enterprise/`, `litellm_enterprise`)
- No `Any` or coarse types, every parameter strongly typed, `: Final` on every variable (LIT010), `ReadOnly[...]` on TypedDict fields (LIT012), no parameter rebinding (LIT011), immutable collections. `# mutable-ok: <reason>` only as a true last resort with a reason that is actually true
- Every lint or type suppression names its exact rule in brackets and carries a real reason. `# type: ignore` is banned
- No comments except genuinely complex business logic, tool-read suppressions, or TODO/FIXME with a strong reason. A test must not open with a docstring restating its own name
- Tests must test function, never structure, and must fail when the behaviour is mutated
- Python max line length 120. TypeScript has no `any`, and no tokens in `localStorage`
- Never run the full dashboard vitest suite with no path. Never run `python -m pytest`; invoke it as `.venv/Scripts/python.exe -c "import pytest,sys; sys.exit(pytest.main([...]))"`, because the harness refuses the module form intermittently
- Python is always `C:\Users\NikhilEruva\litellm\.venv\Scripts\python.exe`
- The proxy starts only with `bash ~/.claude/scripts/litellm-dev-up.sh` (port 4001, dev key `sk-1234`)
- Conventional-commits messages, no Claude attribution or `Co-Authored-By` trailer

## Scope limits, decided before any code

These are deliberate. Each is written into the product doc by Task 7 rather than left for someone to discover from a wrong number.

- **Cost Explorer colours spend by two sources, not four.** The spec names gateway, outside the gateway, user tools and seat fees. User tools and seats do not exist; they are Phase 4. Build the two that have data and do not render empty categories for the other two, for the same reason the Provider Keys tab was left out of Attribution Rules: a control or a legend entry that can never have a value is worse than an absent one.
- **Project grouping will be empty on installations that have no project spend.** `LiteLLM_DailyProjectSpend` holds 0 rows on this machine while team and user hold 65 each. The grouping must say "no project spend recorded" rather than draw an empty chart that reads as "no spend".
- **The shared filter bar spans the three Combined views only.** The spec asks for one filter bar across Gateway, APIs and Combined. Gateway is inherited LiteLLM code and rewriting its filters is a separate, riskier change. This plan gives Combined its own shared filter state and leaves Gateway untouched.
- **Combined opens by default**, as the spec requires. This changes what a returning user sees first, so Task 5 makes it a deliberate, tested choice rather than an accident.

---

### Task 1: Compare every provider at once

**Files:**
- Modify: `litellm/repositories/gap_repository.py`
- Test: `tests/test_litellm/repositories/test_gap_repository.py`

**Interfaces:**
- Consumes: `GapRow` from `litellm/attribution/gap_owner.py`
- Produces: `GapRepository.rows(*, provider: str | None, days: int) -> tuple[GapRow, ...]`, where `None` means every provider

Source Comparison shows every provider on one screen. Today the query filters to one. Widen it rather than calling it once per provider, which would be six round trips and six chances for one to fail.

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.asyncio
async def test_every_provider_comes_back_when_none_is_asked_for() -> None:
    repo, db = _repo([_row(provider="openai"), _row(provider="anthropic")])
    rows: Final = await repo.rows(provider=None, days=7)
    assert tuple(row.provider for row in rows) == ("openai", "anthropic")
    assert db.last_args == ("7",)


@pytest.mark.asyncio
async def test_asking_for_one_provider_still_binds_it_as_a_parameter() -> None:
    repo, db = _repo([_row()])
    await repo.rows(provider="openai", days=7)
    assert db.last_args == ("openai", "7")


@pytest.mark.asyncio
async def test_the_gateway_side_is_matched_per_provider_not_smeared_across_them() -> None:
    repo, db = _repo([_row()])
    await repo.rows(provider=None, days=7)
    assert "ON theirs.day = ours.day AND theirs.provider = ours.provider" in db.last_sql
```

- [ ] **Step 2: Run them and watch them fail**

Run: `.venv/Scripts/python.exe -c "import pytest,sys; sys.exit(pytest.main(['-q','tests/test_litellm/repositories/test_gap_repository.py']))"`
Expected: FAIL, `rows()` does not accept `provider=None`

- [ ] **Step 3: Add the all-providers query**

Keep the existing single-provider SQL exactly as it is and add a second constant beside it. Do not build SQL by string concatenation on a branch: two whole statements, each readable on its own, is safer than one assembled from fragments and is how the rest of this codebase reads.

The all-providers statement groups the gateway side by provider as well as day, and joins on both:

```sql
), ours AS (
    SELECT s.custom_llm_provider            AS provider,
           date_trunc('day', s."startTime") AS day,
           SUM(s.spend)::numeric::text      AS gateway_cost
      FROM "LiteLLM_SpendLogs" s
     WHERE s.custom_llm_provider <> ''
       AND s."startTime" >= NOW() - ($1 || ' days')::interval
     GROUP BY 1, 2
)
SELECT theirs.provider,
       theirs.credential_name,
       to_char(theirs.day, 'YYYY-MM-DD') AS day,
       theirs.provider_cost,
       ours.gateway_cost
  FROM theirs LEFT JOIN ours
    ON theirs.day = ours.day AND theirs.provider = ours.provider
 ORDER BY theirs.day DESC, theirs.provider, theirs.credential_name
```

The `<> ''` is the same deliberate exclusion the single-provider query makes by binding a real slug: a gateway request that recorded no provider belongs to no provider's comparison, rather than being charged to one at random.

- [ ] **Step 4: Run the tests**

Run: `.venv/Scripts/python.exe -c "import pytest,sys; sys.exit(pytest.main(['-q','tests/test_litellm/repositories/test_gap_repository.py']))"`
Expected: PASS

- [ ] **Step 5: Prove each behaviour by mutation**

Revert each change one at a time and confirm a test fails. Assert your search string occurs exactly once before mutating: a replace that silently matches nothing looks identical to a missing test, and that has already happened twice on this branch.

- [ ] **Step 6: Commit**

```bash
git add litellm/repositories/gap_repository.py tests/test_litellm/repositories/test_gap_repository.py
git commit -m "feat(combined): compare every provider against the gateway in one query"
```

---

### Task 2: Serve the source comparison

**Files:**
- Create: `litellm/proxy/management_endpoints/combined_usage.py`
- Create: `litellm/types/proxy/management_endpoints/combined_endpoints.py`
- Modify: `litellm/proxy/proxy_server.py` (register the router beside `attribution_router`)
- Test: `tests/test_litellm/proxy/management_endpoints/test_combined_usage.py`

**Interfaces:**
- Consumes: `GapRepository.rows(provider=None, days=...)`, `AttributionRuleRepository.all()`, `attribute(...)`
- Produces: `GET /usage/combined/comparison?days=<n>` returning

```python
class ComparisonDay(BaseModel):
    day: str
    provider: str
    display_name: str
    gateway_cost: str
    provider_cost: str | None
    gap: str
    status: Literal["matched", "gap", "not_settled", "no_provider_data"]
    owner_type: OwnerType | None
    owner_id: str | None


class ComparisonResponse(BaseModel):
    days: int
    rows: tuple[ComparisonDay, ...]
    total_gateway: str
    total_provider: str
    total_gap: str
```

The three totals are reported side by side and never summed into one figure. That is the counting rule, and a test enforces it.

- [ ] **Step 1: Write the failing tests**

```python
def test_the_three_totals_are_reported_separately_and_never_added() -> None:
    body: Final = comparison_response(days=7, attributed=(GAP_10_MINUS_4,))
    assert body.total_provider == "10"
    assert body.total_gateway == "4"
    assert body.total_gap == "6"


def test_a_day_the_provider_has_not_settled_contributes_to_no_total() -> None:
    body: Final = comparison_response(days=7, attributed=(UNSETTLED,))
    assert body.total_gap == "0"
    assert body.rows[0].status == "not_settled"


def test_a_day_the_provider_said_nothing_about_is_not_reported_as_matched() -> None:
    body: Final = comparison_response(days=7, attributed=(SILENT,))
    assert body.rows[0].status == "no_provider_data"
    assert body.rows[0].provider_cost is None


def test_every_amount_crosses_as_a_string() -> None:
    body: Final = comparison_response(days=7, attributed=(GAP_10_MINUS_4,))
    assert isinstance(body.total_gap, str)
    assert isinstance(body.rows[0].gateway_cost, str)


@pytest.mark.asyncio
async def test_a_non_admin_cannot_read_another_team_s_comparison() -> None:
    with pytest.raises(HTTPException) as caught:
        await combined_comparison(days=7, user_api_key_dict=MEMBER)
    assert caught.value.status_code == 403
```

- [ ] **Step 2: Run them and watch them fail**

Run: `.venv/Scripts/python.exe -c "import pytest,sys; sys.exit(pytest.main(['-q','tests/test_litellm/proxy/management_endpoints/test_combined_usage.py']))"`
Expected: FAIL with "No module named 'litellm.proxy.management_endpoints.combined_usage'"

- [ ] **Step 3: Write the response shaping**

Follow `litellm/proxy/management_endpoints/attribution.py` exactly: a `_plain` helper so a small `Decimal` never renders as `5E-7`, a `_proxy_error` envelope, an `_admin_or_403` guard, and a `comparison_response(*, days, attributed)` function split out of the route so the shaping is testable without a database.

Map the five `GapState` values onto the four statuses the screen shows: `owned` and `unallocated` both become `gap`, because the screen's status column answers "do the two sources agree", and who owns the difference is a separate column. Carry `owner_type` and `owner_id` through so the row can say so.

`display_name` comes from the same place the connections page reads it, so one provider is never called two things on two screens.

- [ ] **Step 4: Write the route and register the router**

Compute `settled_before` in the route, as `attribution.py` does, so the clock stays at the edge and the arithmetic stays pure.

- [ ] **Step 5: Run the tests**

Expected: PASS

- [ ] **Step 6: Prove it against the live proxy**

```bash
bash ~/.claude/scripts/litellm-dev-up.sh
curl -s -H "Authorization: Bearer sk-1234" "http://localhost:4001/usage/combined/comparison?days=30"
```

Expected: openrouter's real days appear, 2026-09-16 with status `matched`, 2026-09-15 with status `gap` and a gap of `0.00774700`. Put the output in your report.

- [ ] **Step 7: Commit**

```bash
git add litellm/proxy/management_endpoints/combined_usage.py litellm/types/proxy/management_endpoints/combined_endpoints.py litellm/proxy/proxy_server.py tests/test_litellm/proxy/management_endpoints/test_combined_usage.py
git commit -m "feat(combined): serve the per-provider daily source comparison"
```

---

### Task 3: Group gateway spend by the dimension a reader chose

**Files:**
- Create: `litellm/repositories/gateway_spend_repository.py`
- Test: `tests/test_litellm/repositories/test_gateway_spend_repository.py`

**Interfaces:**
- Produces:
  - `ExplorerDimension = Literal["team", "project", "user", "provider", "model"]`
  - `@dataclass(frozen=True, slots=True) class SpendSlice: key: str; label: str; gateway_cost: Decimal`
  - `GatewaySpendRepository(db)` with `async def by_dimension(self, *, dimension: ExplorerDimension, days: int) -> tuple[SpendSlice, ...]`

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.asyncio
async def test_spend_comes_back_as_exact_decimals() -> None:
    repo, db = _repo([{"key": "t-1", "gateway_cost": "0.30000000000000004"}])
    slices: Final = await repo.by_dimension(dimension="team", days=7)
    assert slices[0].gateway_cost == Decimal("0.30000000000000004")
    assert "::text" in db.last_sql


@pytest.mark.asyncio
async def test_each_dimension_reads_the_table_that_actually_holds_it() -> None:
    for dimension, table in (
        ("team", "LiteLLM_DailyTeamSpend"),
        ("project", "LiteLLM_DailyProjectSpend"),
        ("user", "LiteLLM_DailyUserSpend"),
    ):
        repo, db = _repo([{"key": "k", "gateway_cost": "1"}])
        await repo.by_dimension(dimension=dimension, days=7)
        assert table in db.last_sql


@pytest.mark.asyncio
async def test_an_unknown_dimension_cannot_reach_the_database() -> None:
    repo, db = _repo([])
    with pytest.raises(KeyError):
        await repo.by_dimension(dimension="salary", days=7)  # pyright: ignore[reportArgumentType]  # the point of the test
    assert db.last_sql == ""


@pytest.mark.asyncio
async def test_a_row_with_an_unreadable_amount_is_dropped_rather_than_zeroed() -> None:
    repo, _ = _repo([{"key": "t-1", "gateway_cost": "not a number"}])
    assert await repo.by_dimension(dimension="team", days=7) == ()
```

- [ ] **Step 2: Run them and watch them fail**

Expected: FAIL, the module does not exist

- [ ] **Step 3: Write one statement per dimension, chosen from a frozen mapping**

The dimension decides a table and a column, and both are interpolated into SQL. So neither may ever come from the caller as text: hold a `MappingProxyType` from the literal to a complete, fixed SQL statement, and look it up. A dimension that is not a key raises `KeyError` before any query is built, which is what the third test pins. Do not build the statement by formatting a table name into a template, even from a validated value: the lookup is the guard, and it must be impossible to bypass by adding a caller.

Each statement follows the shape already used in `provider_usage_fact_repository.py`:

```sql
SELECT d.team_id                      AS key,
       SUM(d.spend)::numeric::text    AS gateway_cost
  FROM "LiteLLM_DailyTeamSpend" d
 WHERE d.date >= (NOW() - ($1 || ' days')::interval)::date
 GROUP BY 1
 ORDER BY SUM(d.spend)::numeric DESC
```

`provider` and `model` group `LiteLLM_DailyTeamSpend` by `custom_llm_provider` and `model` respectively, since that table carries both and is the one with rows on every installation.

- [ ] **Step 4: Run the tests**

Expected: PASS

- [ ] **Step 5: Prove each behaviour by mutation, asserting each anchor is unique first**

- [ ] **Step 6: Commit**

```bash
git add litellm/repositories/gateway_spend_repository.py tests/test_litellm/repositories/test_gateway_spend_repository.py
git commit -m "feat(combined): group gateway spend by team, project, user, provider or model"
```

---

### Task 4: Serve the cost explorer

**Files:**
- Modify: `litellm/proxy/management_endpoints/combined_usage.py`
- Modify: `litellm/types/proxy/management_endpoints/combined_endpoints.py`
- Test: `tests/test_litellm/proxy/management_endpoints/test_combined_usage.py`

**Interfaces:**
- Produces: `GET /usage/combined/explorer?dimension=<d>&days=<n>` returning

```python
class ExplorerSlice(BaseModel):
    key: str
    label: str
    through_gateway: str
    outside_gateway: str


class ExplorerResponse(BaseModel):
    dimension: ExplorerDimension
    days: int
    slices: tuple[ExplorerSlice, ...]
    total_through_gateway: str
    total_outside_gateway: str
    unattributable_outside_gateway: str
    note: str
```

- [ ] **Step 1: Write the failing tests**

```python
def test_the_two_sources_are_reported_side_by_side_never_summed() -> None:
    body: Final = explorer_response(dimension="team", days=7, slices=(TEAM_SLICE,), owned=(OWNED_GAP,))
    assert body.total_through_gateway == "4"
    assert body.total_outside_gateway == "6"
    assert not hasattr(body, "total")


def test_outside_gateway_spend_lands_on_the_owner_a_rule_assigned() -> None:
    body: Final = explorer_response(dimension="team", days=7, slices=(TEAM_SLICE,), owned=(OWNED_GAP,))
    assert body.slices[0].key == "t-1"
    assert body.slices[0].outside_gateway == "6"


def test_unowned_outside_gateway_spend_is_reported_apart_rather_than_spread() -> None:
    body: Final = explorer_response(dimension="team", days=7, slices=(TEAM_SLICE,), owned=(UNOWNED_GAP,))
    assert body.unattributable_outside_gateway == "6"
    assert body.slices[0].outside_gateway == "0"


def test_a_dimension_with_no_rows_says_so_rather_than_reporting_zero_spend() -> None:
    body: Final = explorer_response(dimension="project", days=7, slices=(), owned=())
    assert body.slices == ()
    assert "no project spend" in body.note.lower()
```

The third test is the one that matters. Spreading unowned spend across teams would balance the totals and be a lie; it has to sit in its own figure with its own name.

- [ ] **Step 2: Run them and watch them fail**

Expected: FAIL, `explorer_response` does not exist

- [ ] **Step 3: Write the combiner and the route**

Outside-gateway spend is attributable only when a rule names an owner AND that owner is of the dimension being grouped by. Grouping by model or provider can never carry outside-gateway spend to a slice, because a rule names a team, project or user and not a model: in those two cases every gap belongs in `unattributable_outside_gateway`, and the note must say why rather than leaving a reader to wonder where it went.

- [ ] **Step 4: Run the tests**

Expected: PASS

- [ ] **Step 5: Prove it against the live proxy**

```bash
for d in team user provider model project; do
  echo "== $d"
  curl -s -H "Authorization: Bearer sk-1234" "http://localhost:4001/usage/combined/explorer?dimension=$d&days=30"
done
```

Expected: `team` and `user` return slices from real rows, `project` returns none with its note, and every amount is a quoted digit string. Put the output in your report.

- [ ] **Step 6: Commit**

```bash
git add litellm/proxy/management_endpoints/combined_usage.py litellm/types/proxy/management_endpoints/combined_endpoints.py tests/test_litellm/proxy/management_endpoints/test_combined_usage.py
git commit -m "feat(combined): serve the cost explorer"
```

---

### Task 5: The Combined tab, with Source Comparison and Unallocated

**Files:**
- Create: `ui/litellm-dashboard/src/app/(dashboard)/usage/_components/combined/CombinedTabs.tsx`
- Create: `ui/litellm-dashboard/src/app/(dashboard)/usage/_components/combined/SourceComparisonView.tsx`
- Create: `ui/litellm-dashboard/src/app/(dashboard)/usage/_components/combined/UnallocatedView.tsx`
- Create: `ui/litellm-dashboard/src/app/(dashboard)/usage/_components/combined/comparisonDisplay.ts`
- Create: `ui/litellm-dashboard/src/app/(dashboard)/hooks/combined/useComparison.ts`
- Modify: `ui/litellm-dashboard/src/app/(dashboard)/usage/_components/UsageTabs.tsx`
- Modify: `ui/litellm-dashboard/src/components/networking.tsx`
- Test: `ui/litellm-dashboard/src/app/(dashboard)/usage/_components/combined/CombinedTabs.integration.test.tsx`
- Test: `ui/litellm-dashboard/src/app/(dashboard)/usage/_components/combined/comparisonDisplay.test.ts`
- Test: `ui/litellm-dashboard/src/app/(dashboard)/usage/_components/UsageTabs.test.tsx`

- [ ] **Step 1: Write the failing display tests**

```ts
describe("status copy", () => {
  it("never tells the reader the two sources agree when the provider said nothing", () => {
    expect(STATUS_LABEL.no_provider_data).not.toMatch(/match/i);
  });

  it("calls a settling day settling rather than a gap", () => {
    expect(STATUS_LABEL.not_settled).toBe("Not settled yet");
  });

  it("keeps every digit rather than rounding for display", () => {
    expect(formatAmount("0.00774700")).toBe("$0.00774700");
  });

  it("shows a dash, never a zero, when the provider reported nothing", () => {
    expect(formatAmount(null)).toBe("—");
  });
});
```

- [ ] **Step 2: Write the failing integration tests**

```tsx
it("opens on Combined, because that is the view that reconciles the sources", () => {
  render(<UsageTabs gateway={<p>gateway content</p>} apis={<p>apis content</p>} combined={<p>combined content</p>} />);
  expect(screen.getByText("combined content")).toBeInTheDocument();
});

it("still reaches the Gateway view, which is unchanged", async () => {
  const user = userEvent.setup();
  render(<UsageTabs gateway={<p>gateway content</p>} apis={<p>apis content</p>} combined={<p>combined content</p>} />);
  await user.click(screen.getByRole("tab", { name: "Gateway" }));
  expect(await screen.findByText("gateway content")).toBeInTheDocument();
});

it("shows a real difference as money, with the account that produced it", async () => {
  server.use(comparisonHandler(COMPARISON_WITH_GAP));
  render(<CombinedTabs />);
  expect(await screen.findByText("$0.00774700")).toBeInTheDocument();
  expect(screen.getByText("Gap")).toBeInTheDocument();
});

it("keeps the chosen date range when moving between the three views", async () => {
  const user = userEvent.setup();
  render(<CombinedTabs />);
  fireEvent.change(screen.getByLabelText("Date range"), { target: { value: "7" } });
  await user.click(screen.getByRole("tab", { name: "Unallocated" }));
  await user.click(screen.getByRole("tab", { name: "Source Comparison" }));
  expect(screen.getByLabelText("Date range")).toHaveValue("7");
});

it("links an unallocated line to the rule that would claim it", async () => {
  server.use(comparisonHandler(COMPARISON_WITH_GAP));
  render(<CombinedTabs />);
  const user = userEvent.setup();
  await user.click(screen.getByRole("tab", { name: "Unallocated" }));
  expect(await screen.findByRole("link", { name: /assign this account/i })).toHaveAttribute(
    "href",
    expect.stringContaining("attribution"),
  );
});
```

- [ ] **Step 3: Run both and watch them fail**

Run: `cd ui/litellm-dashboard && npx vitest run "src/app/(dashboard)/usage"`
Expected: FAIL, the modules do not exist

- [ ] **Step 4: Build the tabs**

`UsageTabs` gains a third panel and its `defaultValue` becomes `combined`. Do not remove or rename Gateway or APIs. Base UI unmounts an inactive panel unless `keepMounted` is set, which silently resets filters on a tab round-trip; `UsageTabs.tsx` already carries that comment on the Gateway panel, so follow it for all three.

`CombinedTabs` owns the shared date range and passes it down, which is what the fourth test pins.

- [ ] **Step 5: Run the touched tests only**

Run: `cd ui/litellm-dashboard && npx vitest run "src/app/(dashboard)/usage"`
Expected: PASS. Never run the whole suite with no path.

- [ ] **Step 6: Regenerate the API types**

Run: `cd ui/litellm-dashboard && PATH="/c/Users/NikhilEruva/litellm/.venv/Scripts:$PATH" npm run gen:api`, then commit the regenerated `src/lib/http/schema.d.ts`. Never hand-edit it. The `PATH` prefix is needed because the generator shells out to `python3`, which resolves to a Microsoft Store stub otherwise.

- [ ] **Step 7: Commit**

```bash
git add ui/litellm-dashboard/src
git commit -m "feat(combined): add the combined tab with source comparison and unallocated"
```

---

### Task 6: The Cost Explorer view

**Files:**
- Create: `ui/litellm-dashboard/src/app/(dashboard)/usage/_components/combined/CostExplorerView.tsx`
- Create: `ui/litellm-dashboard/src/app/(dashboard)/hooks/combined/useExplorer.ts`
- Modify: `ui/litellm-dashboard/src/app/(dashboard)/usage/_components/combined/CombinedTabs.tsx`
- Modify: `ui/litellm-dashboard/src/components/networking.tsx`
- Test: `ui/litellm-dashboard/src/app/(dashboard)/usage/_components/combined/CostExplorerView.integration.test.tsx`

- [ ] **Step 1: Write the failing tests**

```tsx
it("shows the two sources as separate bars, never as one total", async () => {
  server.use(explorerHandler(EXPLORER_TEAM));
  render(<CostExplorerView days={30} />);
  expect(await screen.findByText("Through the gateway")).toBeInTheDocument();
  expect(screen.getByText("Outside the gateway")).toBeInTheDocument();
  expect(screen.queryByText(/^Total spend$/)).not.toBeInTheDocument();
});

it("names unowned outside-gateway spend rather than folding it into a team", async () => {
  server.use(explorerHandler(EXPLORER_WITH_UNOWNED));
  render(<CostExplorerView days={30} />);
  expect(await screen.findByText(/nobody owns/i)).toBeInTheDocument();
});

it("says a dimension has no spend recorded rather than drawing an empty chart", async () => {
  server.use(explorerHandler(EXPLORER_EMPTY_PROJECT));
  render(<CostExplorerView days={30} />);
  const user = userEvent.setup();
  fireEvent.change(screen.getByLabelText("Group by"), { target: { value: "project" } });
  expect(await screen.findByText(/no project spend recorded/i)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run them and watch them fail**

Expected: FAIL, the module does not exist

- [ ] **Step 3: Build the view**

Before writing any chart, read the `dataviz` skill: it covers the colour formula, the accessible palette and the mark specs this project expects. Two series only, gateway and outside-gateway, and they must stay visually distinct in both light and dark themes.

- [ ] **Step 4: Run the touched tests only**

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ui/litellm-dashboard/src
git commit -m "feat(combined): add the cost explorer view"
```

---

### Task 7: Say what is built and what is not

**Files:**
- Modify: `docs/superpowers/specs/2026-09-14-token-iq-product-design.md`

- [ ] **Step 1: Record what exists**

Add Usage / Combined to the "Where the product stands" table: the three views, and that the comparison covers every provider in one query.

- [ ] **Step 2: Record the four scope limits verbatim from this plan's "Scope limits" section**

Cost Explorer colours two sources rather than four because user tools and seats are Phase 4; project grouping is empty where no project spend exists; the shared filter bar spans the Combined views only and Gateway keeps its own; and Combined now opens by default.

- [ ] **Step 3: Record the limit that outlives this plan**

Outside-gateway spend can only reach a team, project or user slice, never a model or provider slice, because an attribution rule names an owner and not a model. Say it plainly so nobody reads a model breakdown as complete.

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/specs/2026-09-14-token-iq-product-design.md
git commit -m "docs: record usage combined as built and name its limits"
```

---

## Self-Review

**1. Spec coverage**

| Spec requirement | Task |
|---|---|
| Combined opens by default | Task 5, with a test |
| Cost Explorer groups by team, project, user, provider, model | Tasks 3, 4 and 6 |
| Cost Explorer coloured by where the money went | Task 6, two sources; the other two named as Phase 4 in Task 7 |
| Source Comparison per provider per day with gateway, provider, gap and status | Tasks 1, 2 and 5 |
| Unallocated lists spend with no owner and links to the rule | Task 5 |
| Filter shared across tabs | Task 5, across the Combined views only; limit recorded in Task 7 |
| The two sources are never added together | Tasks 2 and 4, each with a test that fails if a combined total appears |
| A day not settled is labelled, not shown as a gap | Task 2, inherited from `attribute` |

**2. Placeholder scan**

No "TBD", no "add error handling", no "similar to Task N". Every code step carries its code.

**3. Type consistency**

- `GapRow` and `attribute(...)` are used with the signatures they already have; this plan does not change them
- `ExplorerDimension` is defined once in Task 3 and imported by Task 4
- `GapRepository.rows` gains `provider: str | None` in Task 1 and is called that way in Task 2
- The provider slug is the same string in the connector, the fact, the rule and the comparison

**4. Risk accepted on purpose**

Task 3 interpolates a table name into SQL. It is guarded by a frozen mapping from a closed literal, never by formatting a caller's string, and Task 3's third test pins that an unknown dimension cannot reach the database at all. That guard is the single thing a reviewer should check hardest in this plan.
