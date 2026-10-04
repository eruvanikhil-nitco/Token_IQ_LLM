# Recommendations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the data the product already holds into a short list of things worth doing, each with the evidence behind it and an honest figure attached.

**Architecture:** A recommendation is a pure function over data already collected. Each rule reads a narrow slice, decides whether it has something to say, and returns a card carrying what it noticed, the evidence, a figure, who should act and how confident the figure is. A registry runs every rule; nothing is stored except an admin's decision to mark a card done or dismissed. Rules are pure so each one can be tested against fixed inputs, and the registry is the only thing that touches a database.

**Tech Stack:** Python 3.12, FastAPI, Prisma with Postgres, `prisma-client-py` raw queries, pytest. Dashboard is Next.js with shadcn/Base UI, TanStack Query and vitest.

**Spec:** `docs/superpowers/specs/2026-09-14-token-iq-product-design.md`, section "Recommendations" and Phase 5

## The rule this plan exists to protect

**A figure on a card is only called a saving when acting would actually reduce spend.**

The spec asks for "the estimated monthly saving". Most of what these rules find is not a saving. Spend that escaped the gateway is money already being spent that would become visible, not money returned. Concentration on one provider is a risk, not a cost. Calling either a saving would put a number in front of a finance team that does not survive them asking one question, and it would discredit every other card on the screen.

So every card carries an amount **and** what kind of amount it is: money that could stop being spent, money already spent that nobody is watching, or no figure at all. A rule with nothing honest to quantify says so and still earns its place, because "you are entirely dependent on one provider" is worth reading without a number attached.

## Scope, decided before any code

Four rules, chosen because the data already holds real evidence for them. Measured on the live database on 2026-09-29.

| Rule | Evidence available | Kind of figure |
|---|---|---|
| Spend reached a provider without passing through the gateway | The attribution engine already produces this per account per day; `0.00774700` on 2026-09-15 | Money already spent and unwatched, never called a saving |
| Money spent on requests that failed | `LiteLLM_DailyTeamSpend` holds 94 failed of 156 requests | Money that could stop being spent |
| Every provider dollar goes through one provider | Provider facts hold one provider at 100% | No figure. A risk, not a cost |
| A budget no longer matches what is actually spent | Two budgets exist, and spend per team is known | No figure. Acting changes a limit, not spend |

**Deferred, each with a reason Task 6 records.** Unused seats to reclaim needs tool usage to know a seat is unused, and a person with no gateway traffic may still be using the tool daily; recommending someone lose their licence on that basis would be wrong. A cheaper model that performs well enough needs a judgment about output quality that cost data cannot make, and a swap made on price alone can quietly degrade a customer's product. Committed pricing needs contract terms nobody has given us. Caching that is available but unused needs to know caching *is* available for that model and provider, which the data does not say, and the existing Cost Optimization page already covers caching as a deep dive.

## Global Constraints

- Money is `Decimal` end to end and must never pass through `float`. Every summed money column leaves Postgres cast `::text`
- A figure is never called a saving unless acting would reduce spend. Every card states which kind of figure it carries
- A card with no honest figure shows no figure, rather than a zero or an invented estimate
- Every card carries the evidence it was derived from, in numbers a reader can check against the other screens
- The hierarchy is teams, projects and users. Never "employees"
- Never remove, merge or rename an existing UI tab. The existing Cost Optimization page stays exactly as it is
- Prisma migrations change schema only. All three schema copies stay byte-identical; CI diffs them
- Repositories use raw parameterised SQL. A period end given as a date covers that whole day, and the last instant is `.999` not `.999999`, because these columns are `TIMESTAMP(3)` and Postgres rounds a microsecond value up on insert
- Raw queries return timestamps as ISO strings, not `datetime`. Any reader that requires a `datetime` will reject every real row while passing every fake-backed test
- No `Any` or coarse types, every parameter strongly typed, `: Final` on every variable (LIT010), no parameter rebinding (LIT011), immutable collections. `# mutable-ok: <reason>` only as a genuine last resort with a true reason
- Every suppression names its exact rule in brackets with a reason that is actually true. `# type: ignore` is banned
- No comments except genuinely complex business logic, tool-read suppressions, or TODO/FIXME. Never add a constant or export whose only purpose is to carry a comment
- Tests must test function, never structure, and must fail when the behaviour is mutated
- No customer-visible LiteLLM branding, no company or customer names, no secrets, no `eval`, no `shell=True`
- Python max line length 120. TypeScript has no `any`, no tokens in `localStorage`
- Never run the full dashboard vitest suite with no path. Never run `python -m pytest`; use `.venv/Scripts/python.exe -c "import pytest,sys; sys.exit(pytest.main([...]))"`
- Python is always `C:\Users\NikhilEruva\litellm\.venv\Scripts\python.exe`. The proxy starts only with `bash ~/.claude/scripts/litellm-dev-up.sh`
- `PATH="/c/Users/NikhilEruva/litellm/.venv/Scripts:$PATH" npm run gen:api` after any route change
- A new sidebar entry, its route in `migratedPages.ts`, and the group list in `leftnav.test.tsx` change in the same commit
- `keepMounted` is for panels holding typed input. A read-only panel must not use it, or it fetches on every page visit whether or not anyone opens the tab
- Run the type gate as its own command, never chained to a commit with `&&`: a failing gate must stop the commit
- Conventional-commits messages, no Claude attribution or `Co-Authored-By` trailer

---

### Task 1: The shape of a recommendation

**Files:**
- Create: `litellm/types/proxy/recommendation.py`
- Create: `litellm/recommendations/__init__.py`
- Create: `litellm/recommendations/registry.py`
- Test: `tests/test_litellm/recommendations/test_registry.py`

**Interfaces:**
- Produces:
  - `RecommendationKind = Literal["business", "technical"]`
  - `FigureKind = Literal["could_stop_spending", "already_spent_unwatched", "none"]`
  - `@dataclass(frozen=True, slots=True) class Evidence: label: str; value: str`
  - `@dataclass(frozen=True, slots=True) class Recommendation: rule_id: str; kind: RecommendationKind; title: str; noticed: str; evidence: tuple[Evidence, ...]; figure: Decimal | None; figure_kind: FigureKind; currency: str | None; who_should_act: str`
  - `@dataclass(frozen=True, slots=True) class RuleInput: ...` carrying every slice the rules read, so a rule takes data rather than a database
  - `def evaluate(rule_input: RuleInput) -> tuple[Recommendation, ...]`

`figure` and `figure_kind` travel together and neither is optional in the sense the other is: a
card with `figure_kind` of `none` must have `figure` of `None`, and a card with a figure must say
which kind it is. Task 1 enforces that in one place so no rule can get it wrong.

- [x] **Step 1: Write the failing tests**

```python
def test_a_card_with_no_honest_figure_carries_no_number() -> None:
    card = Recommendation(
        rule_id="r", kind="business", title="t", noticed="n", evidence=(),
        figure=None, figure_kind="none", currency=None, who_should_act="an admin",
    )
    assert card.figure is None


def test_a_figure_must_say_what_kind_of_figure_it_is() -> None:
    with pytest.raises(ValueError):
        Recommendation(
            rule_id="r", kind="business", title="t", noticed="n", evidence=(),
            figure=Decimal("10"), figure_kind="none", currency="USD", who_should_act="an admin",
        )


def test_a_card_claiming_no_figure_may_not_smuggle_one_in() -> None:
    with pytest.raises(ValueError):
        Recommendation(
            rule_id="r", kind="business", title="t", noticed="n", evidence=(),
            figure=None, figure_kind="could_stop_spending", currency="USD", who_should_act="an admin",
        )


def test_a_figure_always_names_its_currency() -> None:
    with pytest.raises(ValueError):
        Recommendation(
            rule_id="r", kind="business", title="t", noticed="n", evidence=(),
            figure=Decimal("10"), figure_kind="could_stop_spending", currency=None, who_should_act="an admin",
        )


def test_evaluate_runs_every_rule_and_keeps_the_ones_with_something_to_say() -> None:
    cards = evaluate(EMPTY_INPUT)
    assert all(isinstance(c, Recommendation) for c in cards)


def test_a_rule_with_nothing_to_say_produces_no_card_rather_than_an_empty_one() -> None:
    assert evaluate(EMPTY_INPUT) == ()
```

Validation in `__post_init__` on a frozen dataclass. Raising here is the one place this codebase
throws rather than returning a value, and it is deliberate: these are programming errors inside
our own rules, not failures a caller can act on.

- [x] **Step 2: Run them and watch them fail**

Run: `.venv/Scripts/python.exe -c "import pytest,sys; sys.exit(pytest.main(['-q','tests/test_litellm/recommendations/test_registry.py']))"`
Expected: FAIL with "No module named 'litellm.recommendations'"

- [x] **Step 3: Write the types and an empty registry**

- [x] **Step 4: Run the tests, then mutate each guard and confirm a test dies**

- [x] **Step 5: Commit**

```bash
git add litellm/types/proxy/recommendation.py litellm/recommendations tests/test_litellm/recommendations
git commit -m "feat(recommendations): define a card that cannot claim a figure it does not have"
```

---

### Task 2: Spend that reached a provider without passing through the gateway

**Files:**
- Create: `litellm/recommendations/rules/escaped_spend.py`
- Create: `litellm/recommendations/rules/__init__.py`
- Modify: `litellm/recommendations/registry.py`
- Test: `tests/test_litellm/recommendations/test_escaped_spend.py`

This is the strongest rule, because the engine behind it is already proven against real data.

**It must never call its figure a saving.** The money is already being spent. Bringing it through
the gateway makes it visible and attributable; it does not reduce it. `figure_kind` is
`already_spent_unwatched`, and the card's own words say so.

- [x] **Step 1: Write the failing tests**

```python
def test_it_says_nothing_when_every_difference_is_claimed_or_settled() -> None:
    assert escaped_spend(_input(unallocated=Decimal(0))) is None


def test_it_reports_what_bypassed_the_gateway_with_the_accounts_it_came_from() -> None:
    card = escaped_spend(_input(unallocated=Decimal("0.00774700"), accounts=("openrouter-billing",)))
    assert card is not None
    assert card.figure == Decimal("0.00774700")
    assert any("openrouter-billing" in e.value for e in card.evidence)


def test_it_never_calls_this_a_saving() -> None:
    card = escaped_spend(_input(unallocated=Decimal("0.00774700")))
    assert card is not None
    assert card.figure_kind == "already_spent_unwatched"
    assert "saving" not in card.noticed.lower()
    assert "save" not in card.noticed.lower()


def test_it_says_who_should_act() -> None:
    card = escaped_spend(_input(unallocated=Decimal("1")))
    assert card is not None
    assert card.who_should_act != ""
```

- [x] **Step 2: Run them and watch them fail, then write the rule**

- [x] **Step 3: Register it, run the tests, mutate each branch**

Include a mutation that changes `figure_kind` to `could_stop_spending` and confirm a test dies.

- [x] **Step 4: Commit**

---

### Task 3: Money spent on requests that failed

**Files:**
- Create: `litellm/recommendations/rules/failed_requests.py`
- Modify: `litellm/recommendations/registry.py`
- Test: `tests/test_litellm/recommendations/test_failed_requests.py`

This one genuinely is money that could stop being spent, so `figure_kind` is
`could_stop_spending`.

**Do not invent the figure.** The spend rollup holds a request count and a total spend, not spend
per failed request. Dividing one by the other assumes every request costs the same, which is
false when a failure at the token limit costs far more than a rejected one. So the card reports
the failure count and the share of requests that failed as evidence, and gives a figure only when
the data actually carries cost attributable to failures. If it does not, `figure_kind` is `none`
and the card still earns its place by naming the rate.

- [x] **Step 1: Write the failing tests**

```python
def test_it_says_nothing_when_nothing_failed() -> None:
    assert failed_requests(_input(failed=0, total=100)) is None


def test_it_reports_the_rate_as_evidence_a_reader_can_check() -> None:
    card = failed_requests(_input(failed=94, total=156))
    assert card is not None
    assert any("94" in e.value for e in card.evidence)
    assert any("156" in e.value for e in card.evidence)


def test_it_does_not_invent_a_cost_per_failed_request() -> None:
    card = failed_requests(_input(failed=94, total=156, spend_on_failures=None))
    assert card is not None
    assert card.figure is None
    assert card.figure_kind == "none"


def test_when_the_data_does_carry_the_cost_it_is_money_that_could_stop() -> None:
    card = failed_requests(_input(failed=94, total=156, spend_on_failures=Decimal("1.50")))
    assert card is not None
    assert card.figure == Decimal("1.50")
    assert card.figure_kind == "could_stop_spending"


def test_a_handful_of_failures_in_a_large_month_is_not_worth_a_card() -> None:
    assert failed_requests(_input(failed=1, total=100000)) is None
```

The last test pins a threshold. State the threshold and its reason in the rule, and pick it so a
normal error rate does not produce a card every month; a screen that always shows the same card
teaches people to ignore the screen.

- [x] **Step 2 to 4: as Task 2**

---

### Task 4: Concentration on one provider, and a budget that no longer matches spend

**Files:**
- Create: `litellm/recommendations/rules/provider_concentration.py`
- Create: `litellm/recommendations/rules/stale_budget.py`
- Modify: `litellm/recommendations/registry.py`
- Test: `tests/test_litellm/recommendations/test_provider_concentration.py`
- Test: `tests/test_litellm/recommendations/test_stale_budget.py`

Both carry `figure_kind` of `none`. Concentration is a risk, not a cost, and changing a budget
changes a limit rather than spend. Each still earns a card, because both are things a finance
lead would want to know and neither is visible anywhere else in the product.

- [x] **Step 1: Write the failing tests**

```python
def test_concentration_says_nothing_when_spend_is_spread() -> None:
    assert provider_concentration(_input(by_provider={"openai": Decimal("50"), "anthropic": Decimal("50")})) is None


def test_concentration_names_the_provider_and_the_share() -> None:
    card = provider_concentration(_input(by_provider={"openrouter": Decimal("100")}))
    assert card is not None
    assert "openrouter" in card.noticed
    assert any("100" in e.value for e in card.evidence)


def test_concentration_carries_no_figure_because_it_is_a_risk_not_a_cost() -> None:
    card = provider_concentration(_input(by_provider={"openrouter": Decimal("100")}))
    assert card is not None
    assert card.figure is None
    assert card.figure_kind == "none"


def test_a_budget_matching_its_spend_needs_no_card() -> None:
    assert stale_budget(_input(budgets=((BUDGET_100, Decimal("90")),))) is None


def test_a_budget_far_above_what_is_spent_is_worth_saying() -> None:
    card = stale_budget(_input(budgets=((BUDGET_100, Decimal("2")),)))
    assert card is not None
    assert any("100" in e.value for e in card.evidence)


def test_a_budget_being_exceeded_is_reported_differently_from_one_set_too_high() -> None:
    over = stale_budget(_input(budgets=((BUDGET_100, Decimal("150")),)))
    under = stale_budget(_input(budgets=((BUDGET_100, Decimal("2")),)))
    assert over is not None and under is not None
    assert over.noticed != under.noticed
```

- [x] **Step 2 to 4: as Task 2**

---

### Task 5: Serve the recommendations, and remember what was dismissed

**Files:**
- Create: `litellm-proxy-extras/litellm_proxy_extras/migrations/20261001000000_recommendation_state/migration.sql`
- Modify: `schema.prisma` and both copies
- Create: `litellm/repositories/recommendation_state_repository.py`
- Create: `litellm/proxy/management_endpoints/recommendations.py`
- Create: `litellm/types/proxy/management_endpoints/recommendation_endpoints.py`
- Modify: `litellm/proxy/proxy_server.py`
- Test: `tests/test_litellm/repositories/test_recommendation_state_repository.py`
- Test: `tests/test_litellm/proxy/management_endpoints/test_recommendations.py`

Only the decision is stored, never the card. A card is recomputed from current data every time,
so a dismissed problem that comes back produces a new card rather than staying hidden behind a
decision made last quarter.

```prisma
// An admin's decision about one recommendation. The card itself is never stored: it is
// recomputed from current data, so a problem that returns is seen again.
model LiteLLM_RecommendationState {
    rule_id    String   @id
    state      String   // done | dismissed
    decided_by String?
    decided_at DateTime @default(now())
    note       String?
}
```

**Interfaces:**
- `GET /recommendations?period_start=&period_end=` returning open cards and, separately, the ones marked done or dismissed
- `POST /recommendations/{rule_id}/state` with `done` or `dismissed`
- `DELETE /recommendations/{rule_id}/state` to bring a card back

- [x] **Step 1: Write the failing tests**

```python
def test_every_amount_crosses_as_a_string() -> None:
    body = recommendations_response(cards=(ESCAPED_CARD,), states={})
    assert isinstance(body.open[0].figure, str)


def test_a_card_with_no_figure_sends_null_rather_than_zero() -> None:
    body = recommendations_response(cards=(CONCENTRATION_CARD,), states={})
    assert body.open[0].figure is None
    assert body.open[0].figure_kind == "none"


def test_a_dismissed_card_leaves_the_open_list_but_is_still_reported() -> None:
    body = recommendations_response(cards=(ESCAPED_CARD,), states={"escaped_spend": "dismissed"})
    assert body.open == ()
    assert body.decided[0].rule_id == "escaped_spend"


def test_the_figure_kind_travels_so_a_screen_cannot_call_it_a_saving() -> None:
    body = recommendations_response(cards=(ESCAPED_CARD,), states={})
    assert body.open[0].figure_kind == "already_spent_unwatched"


@pytest.mark.asyncio
async def test_a_non_admin_cannot_read_cross_team_recommendations() -> None:
    with pytest.raises(HTTPException) as caught:
        await recommendations(period_start="2026-09-01", period_end="2026-09-30", user_api_key_dict=MEMBER)
    assert caught.value.status_code == 403
```

- [x] **Step 2: Run them and watch them fail, then build**

- [x] **Step 3: Apply the migration, then prove it live**

```bash
docker exec -i tokeniq_db psql -U llmproxy -d litellm -v ON_ERROR_STOP=1 --single-transaction \
  < litellm-proxy-extras/litellm_proxy_extras/migrations/20261001000000_recommendation_state/migration.sql
bash ~/.claude/scripts/litellm-dev-up.sh
curl -s -H "Authorization: Bearer sk-1234" \
  "http://localhost:4001/recommendations?period_start=2026-09-01&period_end=2026-09-30"
```

Expected: the escaped-spend card carrying `0.00774700` with `already_spent_unwatched`, the
concentration card with a null figure, and the failed-request card. Dismiss one, confirm it moves
lists, bring it back, and put every output in your report.

- [x] **Step 4: Commit**

---

### Task 6: The Recommendations screen

**Files:**
- Create: `ui/litellm-dashboard/src/app/(dashboard)/recommendations/page.tsx`
- Create: `ui/litellm-dashboard/src/app/(dashboard)/recommendations/_components/RecommendationTabs.tsx`
- Create: `ui/litellm-dashboard/src/app/(dashboard)/recommendations/_components/RecommendationCard.tsx`
- Create: `ui/litellm-dashboard/src/app/(dashboard)/recommendations/_components/recommendationDisplay.ts`
- Create: `ui/litellm-dashboard/src/app/(dashboard)/hooks/recommendations/useRecommendations.ts`
- Modify: `ui/litellm-dashboard/src/components/networking.tsx`, `leftnav.tsx`, `leftnav.test.tsx`, `migratedPages.ts`
- Test: `.../RecommendationTabs.integration.test.tsx`, `.../recommendationDisplay.test.ts`

Tabs: `All`, `Business`, `Technical`, `Done & Dismissed`. Add Recommendations to the sidebar
under ANALYTICS, after Ledger.

- [x] **Step 1: Write the failing display tests**

```ts
it("never labels money already being spent as a saving", () => {
  expect(FIGURE_LABEL.already_spent_unwatched).not.toMatch(/saving/i);
  expect(FIGURE_LABEL.could_stop_spending).toMatch(/saving|stop/i);
});

it("shows no amount at all when a card has no honest figure", () => {
  expect(formatFigure(null, "none", null)).toBe("");
});

it("keeps every digit rather than rounding a figure for display", () => {
  expect(formatFigure("0.00774700", "already_spent_unwatched", "USD")).toBe("$0.00774700");
});
```

- [x] **Step 2: Write the failing integration tests**

```tsx
it("shows what was noticed and the evidence behind it", async () => {
  render(<RecommendationTabs />);
  expect(await screen.findByText(/bypassed the gateway/i)).toBeInTheDocument();
  expect(screen.getByText("$0.00774700")).toBeInTheDocument();
});

it("does not present money already being spent as money saved", async () => {
  render(<RecommendationTabs />);
  await screen.findByText("$0.00774700");
  expect(screen.queryByText(/estimated saving/i)).not.toBeInTheDocument();
});

it("shows a card with no figure without an empty amount beside it", async () => {
  render(<RecommendationTabs />);
  expect(await screen.findByText(/one provider/i)).toBeInTheDocument();
  expect(screen.queryByText("$")).not.toBeInTheDocument();
});

it("moves a dismissed card to Done & Dismissed rather than hiding it", async () => {
  const user = userEvent.setup();
  render(<RecommendationTabs />);
  await user.click(await screen.findByRole("button", { name: /dismiss/i }));
  await user.click(screen.getByRole("tab", { name: "Done & Dismissed" }));
  expect(await screen.findByText(/bypassed the gateway/i)).toBeInTheDocument();
});
```

- [x] **Step 3: Build it, run the touched tests only, regenerate the API types, commit**

Read the `dataviz` skill before drawing anything. These are cards, not charts, and a chart here
would most likely be decoration.

---

### Task 7: Say what is built and what is not

**Files:**
- Modify: `docs/superpowers/specs/2026-09-14-token-iq-product-design.md`

- [x] **Step 1: Record the four rules and what kind of figure each carries**

- [x] **Step 2: Record the four deferred rules and why, verbatim from this plan's Scope section**

- [x] **Step 3: Record the figure rule itself**

A figure is only called a saving when acting would reduce spend. Say it in the product doc, not
only in code, because the next person to add a rule will read the doc.

- [x] **Step 4: Say whether Phase 5's test is met**

Phase 5 is done when recommendations show real savings figures from a customer's own data. Say
plainly that two of four rules carry a figure, that one of those figures is money already being
spent rather than a saving, and that the only real data available is one provider's.

- [x] **Step 5: Commit**

---

## Self-Review

**1. Spec coverage**

| Spec requirement | Task |
|---|---|
| Each card states what was noticed, the evidence, a figure and who should act | Task 1, enforced in the type |
| A card can be marked done or dismissed | Task 5 |
| Business recommendations: spend escaping the gateway | Task 2 |
| Business recommendations: concentration on a single provider | Task 4 |
| Business recommendations: budgets that no longer match spend | Task 4 |
| Technical recommendations: money on failed requests | Task 3 |
| Business: unused seats, committed pricing | Deferred with reasons, recorded in Task 6 |
| Technical: cheaper model, caching unused, oversized context | Deferred with reasons, recorded in Task 6 |
| Cost Optimization stays as the technical deep dive | Untouched by this plan |
| Rules evaluated over combined data, not a model's guesses | Tasks 1 to 4, all pure functions |

**2. Placeholder scan**

No "TBD", no "add error handling". Tasks 3 and 4 say "as Task 2" only for the run-mutate-commit
steps, which are identical mechanics, never for the code itself.

**3. Type consistency**

- `Recommendation`, `Evidence`, `FigureKind` are defined once in Task 1 and imported by every rule
- Each rule is `(rule_input: RuleInput) -> Recommendation | None`, one signature, four implementations
- `RuleInput` gains a field per rule as Tasks 2 to 4 land; each task states which field it adds
- `figure_kind` is produced in Tasks 2 to 4, carried through Task 5 and read in Task 6, so it is wired end to end rather than declared and ignored

**4. The thing a reviewer should check hardest**

That no card calls money a saving when it is not. The type refuses the obvious mistake, but the
words on a card are not type-checked: a rule whose `noticed` sentence says "you could save" while
its `figure_kind` says `already_spent_unwatched` would pass every test in Tasks 1 to 5 and still
mislead a finance team. Task 2's third test checks the wording as well as the flag, and the same
check belongs on every rule that carries a figure.

---

## Whole-plan review, 2026-09-29

All seven tasks are built, and the four rules run against the live database rather than against
fixtures alone. On September's data: escaped spend reports `0.00774700` USD as money already being
spent, failed requests reports 103 of 165 at 62.4% with no figure, provider concentration reports
one provider at 100% with no figure, and the stale budget reports a limit of 0.5 against 0.000205
spent. The dismiss, done and undo round trip was exercised end to end against the running proxy.

Three things the review changed rather than noted:

The wording check the Self-Review called the hardest thing to get right was only on two of the
four rules. A card that reads like a saving while carrying no number passes every type check, so
failed requests with no cost attached and both stale budget cards are now held to the same check.

`RecommendationStateRepository.all()` declared it returns known decision states, but the membership
test did not narrow the type, so the declared return type was a promise nothing enforced. It now
validates each state through a `TypeAdapter`. Nothing tested that reader at all, so the docstring
claim that an unrecognised state hides no card was unenforced too; seven tests now cover it, and
the claim was also proved live by writing a `snoozed` row straight into the table and watching the
card stay open.

What this plan does not deliver, stated plainly rather than left to be inferred: only one of the
four rules can ever produce a savings figure, and it does so only when spend attributable to failed
requests is gathered, which `_gather` does not do today because the spend rollup holds a request
count and a total rather than cost per failed request. So Phase 5's test is not met, and the
product doc says so.
