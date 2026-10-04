# Overview Home Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The screen a customer lands on, answering what they spent, whether the bill was right, how much nobody owns, what to do about it, and how fresh the answer is.

**Architecture:** One endpoint composes the figures from the repositories that already hold them, so the period is consistent across every tile and the counting rule is applied once on the server rather than in each component. The screen is stat tiles and short lists in the pattern the rest of the dashboard already uses, not a new visual language.

**Tech Stack:** Python 3.12, FastAPI, pytest. Dashboard is Next.js with shadcn/Base UI, TanStack Query and vitest.

**Spec:** `docs/superpowers/specs/2026-09-14-token-iq-product-design.md`, the Overview entry under Navigation and Phase 1

## The rule this page must not break

**A provider figure says how much was spent. A gateway figure says who spent it. They are
never added together.**

This is the product's oldest rule and this screen is where breaking it would do the most
damage, because a headline total is the one number a customer repeats to their finance team
without checking. Adding the gateway's figure to the provider's would roughly double it.

So the headline total is what the providers billed, plus tool spend that appears on no
provider bill, plus seat fees. The gateway's own figure never enters it. The gateway's number
appears on this page only as attribution: how much of the provider total we can say who spent.

Claude Code usage billed to an API organisation is already inside the provider total, which is
why tool usage contributes only its `new_money` rows. The repository already enforces that in
SQL; this page must not work around it.

## What the page shows

| Tile | Where it comes from |
|---|---|
| Total spend for the period, and the change against the period before | Provider facts, plus tool `new_money`, plus seats |
| How much of it we can attribute, and how much nobody owns | Gateway spend and unallocated gaps |
| Bill match per provider | The ledger's reconciliation, one row per provider |
| The top few recommendations | The recommendation rules, already ranked |
| How fresh each source is | The most recent sync per provider and tool |

## Global Constraints

- Money is `Decimal` end to end and never passes through `float`. Every summed money column
  leaves Postgres cast `::text`
- The headline total never includes the gateway figure
- A figure the product cannot compute is absent or labelled, never a zero standing in for
  "we do not know"
- A period with no data says so rather than drawing an empty chart
- The page reuses the dashboard's existing stat-tile and card patterns, its chart components
  and its colour tokens. Text wears text tokens, never a series colour
- Status is never colour alone: every state carries a word
- No new sidebar group. The entry, its route and the group list in `leftnav.test.tsx` change
  in one commit
- No `Any` or coarse types, `: Final` on every variable, immutable collections
- Tests check behaviour, not structure, and must fail when the behaviour is mutated
- Python line length 120. TypeScript has no `any`, no tokens in `localStorage`

---

## Task 1: The figures, composed once, without double counting

**Files:**
- Create: `litellm/overview/__init__.py`, `litellm/overview/totals.py`
- Create: `tests/test_litellm/overview/test_totals.py`

- [x] **Step 1: Write the failing tests**

The headline total is provider spend plus tool new money plus seats, and adding the gateway
figure to it is the mutation that must fail. A period with nothing in it reports nothing
rather than zero. The change against the previous period is absent when there is no previous
period, rather than reported as a rise from zero.

- [x] **Step 2: Write the pure function**

Pure, taking the figures as arguments, so the rule can be tested without a database.

- [x] **Step 3: Mutate each rule and confirm a test dies**

- [x] **Step 4: Commit**

---

## Task 2: The endpoint

**Files:**
- Create: `litellm/proxy/management_endpoints/overview.py`
- Create: `litellm/types/proxy/management_endpoints/overview_endpoints.py`
- Create: `tests/test_litellm/proxy/management_endpoints/test_overview.py`

- [x] **Step 1: Write the failing tests**

Admin only. Every amount crosses as a string. The response carries the period it was asked
for. A source that has never synced reports never rather than a date.

- [x] **Step 2: Build it, reading the repositories that already hold each figure**

- [x] **Step 3: Prove it live against the running proxy and real data**

- [x] **Step 4: Commit**

---

## Task 3: The screen

**Files:**
- Modify: `ui/litellm-dashboard/src/components/networking.tsx`
- Create: `ui/litellm-dashboard/src/app/(dashboard)/hooks/overview/useOverview.ts`
- Create: `ui/litellm-dashboard/src/app/(dashboard)/overview/page.tsx` and `_components/`

- [x] **Step 1: Write the failing display tests**

Formatting and labelling on their own, away from a render: an absent figure shows nothing
rather than a zero, a rise and a fall read differently, and the attribution share is a share
of the provider total rather than of anything else.

- [x] **Step 2: Write the failing integration tests**

- [x] **Step 3: Build it in the dashboard's existing patterns**

Stat tiles in the card grid the Combined screens already use. Status carries a word beside any
colour. The recommendation list links to the full screen rather than repeating it.

- [x] **Step 4: Run only the touched tests, regenerate the API types, commit**

---

## Task 4: Make it the landing page

**Files:**
- Modify: `leftnav.tsx`, `migratedPages.ts`, `leftnav.test.tsx`, and wherever the default route is decided

- [x] **Step 1: Write the failing test**

A new HOME group with Overview in it, and the group list updated in the same commit.

- [x] **Step 2: Add the entry, the route and the redirect together**

- [x] **Step 3: Run the touched tests and commit**

---

## Task 5: Record it

**Files:**
- Modify: `docs/superpowers/specs/2026-09-14-token-iq-product-design.md`, `PROJECT.md`

- [x] **Step 1: Record what the headline total includes and, more importantly, what it excludes**

- [x] **Step 2: Record what the page cannot yet show and why**

- [x] **Step 3: Commit**

---

## Self-Review

**1. Spec coverage**

| Spec requirement | Task |
|---|---|
| Total spend across all sources | Tasks 1 and 2 |
| Change against last period | Tasks 1 and 2 |
| Bill match per provider | Task 2 |
| Share unallocated | Tasks 1 and 2 |
| Top recommendations | Task 2 |
| Data freshness | Task 2 |
| It is the page you land on | Task 4 |

**2. Placeholder scan**

No "TBD". What the page cannot show is named in Task 5 rather than left blank.

**3. Type consistency**

One response model, built in Task 2 from the pure totals of Task 1 and read by Task 3, so a
figure cannot be computed one way on the server and another way on the screen.

**4. The thing a reviewer should check hardest**

That the headline total does not include the gateway figure. It is the product's oldest rule,
this is the most prominent number in the product, and the failure is silent: every screen
keeps working and the one figure a customer repeats to their finance team is roughly double
what they actually spent.

---

## Whole-plan review, 2026-09-30

All five tasks are done. The Self-Review said a reviewer should check hardest that the
headline total excludes the gateway figure, and that held: six mutations were applied to the
counting rules and all six were caught, including adding the gateway figure to the total and
taking the unallocated share of the wrong denominator. Checked live too, on real data, where
the total reads the provider figure rather than the provider figure plus the gateway's.

Two decisions worth keeping.

The page has its own queries rather than reusing the existing repositories. Most of those
take a window in days counted back from today, and a landing page cannot have one tile
showing last week beside another showing last month. Five focused queries were a smaller
change than bending five signatures.

A provider's standing has four states rather than a boolean, and one of them is neutral. A
bill larger than the gateway's record and one smaller are different problems, and a provider
read only through its bill is neither: that is a normal way to run, and a permanent amber
badge on a working connection teaches people to ignore the column.

Nothing on this page is a chart. Every figure it shows is a single number or a short list,
and a chart added to fill space would have been worse than a number. The tiles reuse the card
pattern the Combined screens already use, because consistency is most of what makes a product
look considered.

What it cannot yet show: a spend trend over time, which needs the daily series rather than
one period's totals, and any figure from a user tool, since no tool has met a real account.
