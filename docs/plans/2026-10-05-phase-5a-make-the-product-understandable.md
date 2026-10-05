# Phase 5A: make the product understandable

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** a reader who has not seen the product can say, for each screen, what it is telling them
and what they would do next. Every figure a screen presents as a sum reconciles on screen.

**Architecture:** UI only, plus one new read endpoint for names. No change to how any figure is
computed. Where a screen is wrong about what a number means, the fix is the sentence, not the
arithmetic.

**Tech Stack:** Next.js, React, TypeScript, Vitest, Playwright.

**Spec:** `docs/specs/2026-10-04-token-iq-independent-codebase.md`, section 5.6

**Why it runs now, out of order:** the spec puts this after phase 5 so no effort goes into a page
about to be deleted. Phase 5 is blocked on two owner decisions, and none of Usage, Ledger,
Recommendations or Overview appears on the phase 5 delete list, so the reason for the ordering does
not apply to these screens. Phase 5 still runs before phase 6.

## The rule this phase must not break

**A provider figure says how much was spent. A gateway figure says who spent it. They are never
added together.**

This phase is more dangerous to that rule than any phase that touches the arithmetic, because its
whole deliverable is sentences explaining what the figures mean. A screen that computes correctly
and explains wrongly teaches the reader to add the two together themselves. The Combined screens
put a provider total and a gateway total side by side, and the sentence that introduces them is
exactly where "so your total spend is..." gets written by accident.

Every sentence this phase adds about a total must name which of the three sources it came from, and
must not describe a provider figure and a gateway figure as parts of one sum. The headline total is
provider-billed cost, plus tool spend on no provider bill, plus seats, and the gateway's own figure
is attribution that never enters it.

## Facts measured on 5 Oct 2026, in the code

Each of the spec's five complaints was checked rather than taken on trust.

| Complaint | What the code does |
|---|---|
| Usage stacks three rows of tabs | `UsageTabs` gives Combined/Gateway/APIs; Combined then gives Cost Explorer/Source Comparison/Unallocated; Gateway gives cost/models/keys/mcp/endpoints; and `UsagePageView` line 808 uses a fourth `TabsList` as a row-limit selector |
| Two date controls that disagree | `CombinedTabs` holds a days-based `Select` (`combined-date-range`); `UsagePageView` holds a separate from/to `AdvancedDatePicker` in its own `useState`. Both panels are `keepMounted`, so each keeps its own period and switching tab changes the window with no indication |
| Screens lead with controls | `CostExplorerView` renders its dimension `Select` before any figure; `CombinedTabs` renders the date control above the tab content |
| An empty state with no way out | `ledgerDisplay.ts` maps `no_invoice` to the bare string `"No bill entered"`. The form that enters one is `InvoicesView.tsx`, a different tab of `LedgerTabs` |
| Rows labelled with identifiers | `gateway_spend_repository` groups `LiteLLM_DailyTeamSpend` by `team_id`, and `ExplorerSlice.key` carries that id straight through to the row label |

The page model the spec wants extracted lives in `docs/product/token-iq-product-blueprint.html`,
2,670 lines, holding the tabs and sub-tabs, eight roles with per-role access, the five page
templates, the setup dialogs and the help text.

## The traps

**1. Names are a new read, and a chance to leak.** Replacing a team id with a team name means the
usage screens need names for ids. A reader who may see one team's spend must not learn the names of
teams they cannot see. The lookup has to be filtered by the same authorisation the figures are,
not fetched from a general team list in the browser.

**2. Collapsing tabs changes URLs people have bookmarked.** The tab state is in the page, not the
route, for most of these, but `?page=` is used elsewhere in the product. Any tab removed or renamed
needs its old entry point to still land somewhere sensible.

**3. One date control means one period, which changes what each panel shows.** Today each panel
silently uses its own. Unifying them is correct and will change numbers on screen relative to
today. That is the point, and it needs saying in the commit rather than discovering later that a
figure "changed".

**4. `keepMounted` is load-bearing for speed and against correctness.** It is why each panel keeps
stale state. Removing it will refetch on every tab change.

**5. The acceptance is a reader, not a test.** "Can state what it is telling them" cannot be
asserted in Vitest. The per-screen acceptance comes from the extracted page model: each screen
declares what it claims, and a test checks the screen renders that claim. Taste stays out of it.

## Global Constraints

- No change to how any figure is computed. If a screen is wrong, the sentence changes
- Every sentence naming a total says which source it came from
- No new figure is introduced that adds a provider figure to a gateway figure
- Vitest for display logic, Playwright for a walk-through per screen
- Never run the full vitest suite with no path
- Tokens never go in `localStorage`
- Existing tabs are moved or renamed, never removed, without explicit approval

---

## Task 1: Extract the page model from the blueprint

**Files:** `docs/product/token-iq-product-blueprint.html`, new `docs/product/page-model.json`

- [x] **Step 1: Write the extractor and the schema**

Pages, tabs, sub-tabs, per-role access, dialogs and help text, out of the HTML and into committed
JSON. The JSON is the artefact every later task checks itself against, so it is the deliverable,
not a by-product.

- [x] **Step 2: Reconcile it against what the UI actually renders**

The blueprint describes the product as intended. A tab in the JSON that no page renders, or a page
that renders a tab the JSON does not know, is a finding either way: either the UI drifted or the
blueprint did. Record which, per discrepancy, and do not silently make one match the other.

- [x] **Step 3: Commit**

---

## Task 2: One period for Usage

**Files:** `UsageTabs.tsx`, `CombinedTabs.tsx`, `UsagePageView.tsx`

- [x] **Step 1: Write the failing test**

Two panels, one period: switching tab must not change the window. Today it does, and the test
should fail before the change.

- [x] **Step 2: Lift the period to the page**

One control, above the tabs, owned by `UsageTabs` and passed down. The days-based `Select` and the
from/to picker become one thing; from/to is the more expressive, so days becomes a preset on it.

- [x] **Step 3: Say so where the numbers change**

Unifying the period changes what each panel shows relative to today. The commit says which panels
and in which direction.

- [x] **Step 4: Commit**

---

## Task 3: Every screen opens with what it means

**Files:** the Combined, Gateway, APIs, Ledger, Recommendations and Overview views

- [x] **Step 1: Write the sentence for each screen, and the source rule into a test**

One sentence per screen: what the figures are, which of the three sources they came from, what to
do next. The test asserts each screen renders its claim from the page model, and asserts no screen
presents a provider figure and a gateway figure as addends of one total.

That second assertion is the one that matters. It is the counting rule, in the only place this
phase can break it.

- [x] **Step 2: Put the meaning above the controls**

Sentence, then figures, then evidence, then controls. Today the controls come first and the meaning
is in a footnote.

- [x] **Step 3: Commit**

---

## Task 4: Empty states that offer the way out

**Files:** `ledgerDisplay.ts`, `BillReconciliationView.tsx`, and the other empty states

- [x] **Step 1: Find every empty state and what fills it**

`no_invoice` is the known one. Enumerate the rest rather than fixing the one the spec named.

- [x] **Step 2: Give each one the action**

"No bill entered" becomes a sentence and a control that opens the form, in place, rather than
naming a tab the reader has to find.

- [x] **Step 3: Commit**

---

## Task 5: Names instead of identifiers

**Files:** the explorer endpoint and `explorerDisplay.ts`

- [x] **Step 1: Decide where the name comes from, and write the leak test first**

A row grouped by `team_id` needs that team's name. The lookup is filtered by the caller's
authorisation, so a reader limited to one team cannot learn another team's name. The test asserts
exactly that before the feature exists.

- [x] **Step 2: Return the name beside the key, never instead of it**

`ExplorerSlice` keeps `key` and gains a display name. The key stays because it is what a filter or
a link needs, and because a name is not unique.

- [x] **Step 3: Fall back to the identifier rather than hiding the row**

A team deleted since the spend was recorded has no name. Showing nothing loses the money.

- [x] **Step 4: Commit**

---

## Task 6: Walk through it, and the handover

**Files:** `tests/e2e/ui/`, `docs/status.md`

- [x] **Step 1: A Playwright walk per screen**

Open each screen cold and assert the claim is visible before any control is touched, and that the
figures presented as a sum add up on screen.

- [x] **Step 2: Put the open question to the owner**

Whether this phase also replaces the inherited usage dashboard embedded in Usage, which is another
product's interface with its own controls, its own date range and a chat box. Section 7 of the spec
carries it as a decision to make, and it is not mine.

- [x] **Step 3: Record what changed and what each screen now claims**

- [x] **Step 4: Commit**

---

## Self-Review

**1. Spec coverage**

| Spec requirement (5.6) | Task |
|---|---|
| Page model extracted into committed JSON | Task 1 |
| Screens lead with meaning, then figures, then evidence | Task 3 |
| Nested Usage tabs collapsed, date controls reconciled | Task 2 |
| Empty states explain themselves and offer the action | Task 4 |
| Pages open on a source that has data | Task 3 step 2 |
| Identifiers replaced by names | Task 5 |
| Acceptance from the page model, not taste | Task 1, Task 6 |
| Open question on the embedded dashboard put to the owner | Task 6 step 2 |

**2. Placeholder scan**

No "TBD". Each of the spec's five complaints is cited to the file and symbol that causes it.

**3. Type consistency**

`ExplorerSlice` gains a field rather than changing one, so no existing reader of `key` breaks.

**4. The thing a reviewer should check hardest**

The sentences, against the counting rule.

Every other risk in this phase is visible: a tab in the wrong place looks wrong, a missing name
looks wrong, an empty state with no button looks wrong. A sentence that says "your total spend"
over a provider figure and a gateway figure looks *right*, reads well, and teaches the reader to
double-count. It is the one defect in this phase that gets more convincing the better it is
written.

Second hardest: the name lookup in task 5. It is the only new read of data this phase adds, and the
only place it can leak something a reader is not entitled to see.
