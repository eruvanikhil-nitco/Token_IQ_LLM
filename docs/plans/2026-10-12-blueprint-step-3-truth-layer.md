# Blueprint step 3: the truth layer and Pricing & Rates

**Goal:** one cost line per day, owner and meter, de-duplicated across sources, priced at the
customer's own rates, in one currency they chose. Everything after this step reads it.

**Source:** `docs/product/token-iq-product-blueprint.html`, the middle layer of section 01 and
build step 3 of section 13: "A standard cost-line table, de-duplication rules, effective rates and
currency. Everything later depends on this." Marked "backend first", and the blueprint is explicit
that it is a backend job rather than a screen.

**Where this sits:** build steps 0, 1 and 2 are done. Step 4 (app shell, roles, Cost Explorer),
step 5 (recommendations v2), step 7 (reconciliation and month-end close) and step 8 (budgets and
forecasts) all read cost lines, so each of them inherits whatever this step gets wrong.

## What the blueprint specifies

The middle layer, in its own words: "One cost line per day × owner × meter", de-duplicated across
sources, owner assigned by rule, evidence grade attached, priced at the client's real rates. Not a
tab. The layer above it, analysis, "always works from the combined, de-duplicated data, never from
one source alone". The layer below, Data Sources, never shows spend by team or model.

Pricing & Rates is the screen half, and the blueprint names its job in passing rather than in a
page model: the invoice dialog's currency field says "Invoice currency; converted using Pricing &
Rates", and section 12's label table maps today's Cost Tracking onto `Administration › Pricing &
Rates`.

## Facts measured on 12 Oct 2026, in the code and in the dev database

| Piece | What exists | What is missing |
|---|---|---|
| Cost facts | `LiteLLM_ProviderUsageFact`: day or request, provider, credential, model, meter, `billed_cost` as exact digits, currency, tokens, `evidence`, and a unique `fact_key` that makes a re-fetch idempotent | nothing per fact; the gap is that no two sources are ever read together |
| Tool facts | `LiteLLM_ToolUsageFact`: day, tool, person, cost, and `basis` of `new_money` or `already_on_a_provider_bill` | nothing per fact |
| Seats | `LiteLLM_UserSeat`: one flat amount per person per period | nothing |
| The combined read | four separate compositions: `token_iq/api/ledger.py` reads provider facts, `token_iq/overview/totals.py` sums pre-summed sources, `token_iq/api/combined_usage.py` compares provider against gateway, `token_iq/api/provider_usage.py` totals one provider | **one shape and one composition.** Four readings of the same question is how the counting rule eventually breaks: it only has to be forgotten once |
| Owner | `LiteLLM_AttributionRule`, matched on `cloud_account`, applied at read time in the ledger | a rule that can match anything else: a virtual key, a cloud tag, a user, a request header. The blueprint's allocation rules name five match kinds |
| Evidence | three grades in the type: `reconciled`, `priced`, `allocated` | two of the three. Every connector writes `reconciled`, and the dev database holds 50 facts, all `reconciled`, totalling 0.00780515. Nothing writes `priced` or `allocated`, so the grade is decoration today |
| Prices | `token_iq/pricing/data/model_prices.json` plus an append-only `price_history.jsonl` with `price_on(model, field, when)`, so a closed month re-prices at the rate that applied | the customer's own rates. A negotiated discount, a committed-use rate or a private price list has nowhere to be recorded |
| Currency | every row carries one, totals are reported per currency, and reconciliation refuses to compare across currencies rather than converting | a rate the customer entered, so one reporting currency is possible without inventing a rate |
| Pricing & Rates | the Cost Tracking page exists under its old name | the page the label table names, and anywhere to put rates |

## The rule this work must not break

**A provider figure says how much was spent. A gateway figure says who spent it. They are never
added together.**

This step is where that rule stops being a convention and becomes a type. Today it is written down
in `token_iq/overview/totals.py` and respected separately by each of the four compositions. One
composition means one place it can be broken, and a shape that carries the gateway figure
deliberately beside the total rather than inside it, as `Sources` already does.

## The trap worth the most attention

**A stored cost-line table is a second source of truth.**

The blueprint says "table", and a materialised table is the obvious reading. It also drifts: facts
arrive late, a connector re-fetches, a rate is corrected, an attribution rule changes, and every one
of those makes the stored line wrong in a way that still looks like a figure. The fix is a
backfill, which is the operation most likely to be got wrong under time pressure.

So this plan composes the cost line from the facts rather than storing it, behind one function with
one shape, and records what would change that: a measured slow read on a real customer's volume.
Materialising later is then an implementation change behind an interface, not a rewrite of every
caller. The dev database holds 50 facts; nothing here has measured a volume that needs a table.

## Global Constraints

- No figure crosses the provider/gateway line, and a test says so for every composition
- Every amount stays exact digits end to end, never a float, and tests assert the digits
- No rate is ever invented. A conversion or a discount exists only if a customer recorded it,
  with its period and where it came from
- A grade that nothing measures says so, as `Unmeasurable` does on the Overview tab, rather than
  borrowing a zero
- Prisma migrations change schema only, never rewrite rows
- TDD: the failing test first, every time
- Python line length 120, `: Final`, no `Any`, immutable collections, tagged unions and `match`
- Never run the full vitest suite with no path

---

## Task 1: The cost line, as one shape and one composition

- [x] **Step 1: Write the failing test for the counting rule at the composition boundary**

One function takes what each source reported and returns cost lines plus the totals that may be
read off them. The test that matters asserts a gateway figure never reaches a total, and that a tool
row already on a provider bill never adds to one.

- [x] **Step 2: `token_iq/truth/cost_line.py`, pure, no database**

One cost line per day, owner and meter, with its evidence grade, its currency and its source. Built
from provider facts, tool facts and seats, tested without a database, as `overview/data_quality.py`
and `ledger/reconciliation.py` are.

- [x] **Step 3: Move the ledger onto it, so there is one composition rather than two**

The ledger is the closest thing to a truth layer today and the only screen that already shows
evidence and owner per line. It reads the new shape, and its live figures do not move.

- [x] **Step 4: Commit**

### What task 1 found

**The counting rule is now a type rather than a convention.** Every line is either `Spend`, which a
total may add, or `WhoSpent`, which says who spent money counted somewhere else and can never reach
one. `money_of` matches over the two exhaustively, so a third kind added later is a type error here
instead of a line quietly left out of, or quietly added to, every total in the product. That is the
difference between the rule being written down, which it was, and being unbreakable.

**A line nobody asserted has no evidence grade, and that had to reach the wire.** The three grades
are the provider's own vocabulary: it asserted dollars, it asserted tokens and we applied rates, or
only our own gateway records cover it. A seat is a figure a person read off a contract, so claiming
any of them would be a claim about evidence that does not exist. A fourth grade would have put a
meaningless empty bucket in the per-provider summary, which already hardcodes the three. So the
grade is nullable, the Ledger screen says "entered" with a sentence explaining it, and nothing
defaults silently.

**The truth layer takes a narrower provider fact than the connectors write.** `ProviderUsageFact`
carries tokens, request ids and the raw payload, which belong to the write and to the raw-records
view. The money needs day, provider, account, model, meter, grade, currency and amount, so that is
what `ProviderCostFact` is, and the ledger's repository returns it. Building the write shape here
would have meant filling fields this read never looked at with None, which is a lie the type system
cannot catch.

**One name for one thing, even where the screen word differs.** The composed line calls its account
`credential_name`, the name the fact table, the attribution rules and the connect flow all use,
rather than the nicer-reading `account`. Two names for one thing is how a join eventually goes
wrong, and the UI can relabel it without the backend holding two words for it.

**Moving the ledger renamed a helper into a route.** `ledger_lines` was already the name of the
route handler, so the composition helper shadowed it and three tests started failing with
"coroutine object is not subscriptable". Caught in a minute by tests, but worth saying: in a module
where the handlers are plain functions, a helper named after the thing it serves collides with it.

**Live, the figures did not move.** Fifty lines, a page summing to 0.00780515, and a period total of
0.00780515, the same as before the move, with every line's owner and grade as it was.

---

## Task 2: De-duplication, with each rule named

- [x] **Step 1: A test per rule, because each one hides a different double count**

Four rules, and they are not variations of one: a re-fetched fact (`fact_key`, already enforced by
the database), a tool row whose money is already on a provider bill (`basis`), two provider accounts
covering the same spend, and the provider total against the gateway's own. The last one is the
counting rule and belongs to task 1; the third has nothing enforcing it today.

- [x] **Step 2: `token_iq/truth/dedup.py`, and a decision record for the third rule**

Two credentials reading one account is a real configuration: a customer connects a management
account and a member account, or re-connects after a key rotation without removing the old
connection. Whatever the rule is, it has to be stated and visible, because the symptom is a bill
that reads double and still reconciles against nothing.

- [x] **Step 3: Commit**

### What task 2 found

**Three of the four rules were already enforced, in three different places, and none of them said
so.** A re-fetched fact is stopped by a unique `fact_key` in the database. Tool money already on a
provider bill, and a gateway figure against a provider's, are both stopped by the cost line's type
from task 1. Naming all four in one place is most of this task's value: the next person to add a
source needs to know which rules already cover it and which do not.

**The fourth cannot be detected properly, and that is a fact about the providers.** No connector
learns the provider's own account identifier, so two credentials reading one AWS account look
exactly like two credentials reading two separate accounts. A development account beside a
production account is ordinary, so there is no safe inference from the credentials alone.

**What is distinguishable is the figure.** The same amount, to every digit, for one day, model,
meter and currency, under two account names, is one account read twice. Zero is excluded, because
two accounts reporting nothing against a model is the commonest figure a provider publishes, and
pairing those would put a row on the list for every unused model in an estate.

**Nothing is dropped, which is decision 0024.** The costs are asymmetric and only one direction is
visible. A wrong suspicion costs a reader one look at their provider console. A wrong deletion
halves a bill, and nothing downstream can tell: reconciliation would report the invoice as larger
than the ledger and blame the provider, while every figure still added up internally. Nobody
questions a number that went down.

**It surfaces where the product already asks a person to act**, as a fifth data-quality issue on
Data Sources > Overview, counted and pointing at the Accounts tab. Proved live by inserting a
second credential's copy of two real facts: the issue went to 2 and the things-to-fix count from 3
to 4, then both back when the rows were removed, with the fact table as it was.

**Found on the way: the dev database had run out of connections.** "FATAL: sorry, too many clients
already" after a day of restarts, which showed up as the new query returning a 500 while the
proxy's own readiness check still said healthy, because that check answers on a connection it
already holds. A brand-new query failing while everything else works is the pool, not the query.

---

## Task 3: Effective rates, which makes the `priced` grade real

- [ ] **Step 1: Where a customer's own rate is recorded**

A negotiated discount, a committed-use rate or a private price list, per provider and optionally
per model, with the period it applies to and where it came from. A rate with no period cannot
re-price a closed month, which is the whole reason `price_history` exists.

- [ ] **Step 2: Pricing gateway traffic at those rates, as `priced` evidence**

Today a request the gateway observed and no provider has billed yet contributes nothing to any
figure. Priced at the customer's rate it becomes a cost line graded `priced`, which is the
blueprint's "estimated cost has been observed by the gateway but not yet billed", and which is
replaced by the provider's own figure when it arrives.

- [ ] **Step 3: Commit**

---

## Task 4: Currency, without inventing a rate

- [ ] **Step 1: A recorded rate per currency pair and period**

Entered by an admin, with its source, like an invoice. Reconciliation's current refusal to convert
stays exactly as it is for a pair nobody recorded.

- [ ] **Step 2: One reporting currency, with the conversion stated**

A converted figure says it was converted, at which rate and when, beside the figure. A total that
mixes currencies silently is worse than one that refuses.

- [ ] **Step 3: Commit**

---

## Task 5: The Pricing & Rates page

- [ ] **Step 1: Cost Tracking becomes Pricing & Rates, keeping its address alive**

The rename section 12's label table asks for, by the same rule as every other merge: the legacy
`?page=` id and the old path both keep resolving, and a test covers each.

- [ ] **Step 2: The rates and the currency rates on it, read-only for a finance admin**

- [ ] **Step 3: Commit**

---

## Self-Review

**1. Source coverage**

| Build step 3 item | Task |
|---|---|
| A standard cost-line table | Task 1, composed rather than stored, with the reason and what would change it |
| De-duplication rules | Task 2, one rule at a time |
| Effective rates | Task 3 |
| Currency | Task 4 |
| Pricing & Rates | Task 5 |

**2. What is deliberately not here**

The five match kinds the blueprint's allocation rules name. Owner assignment today matches only a
provider credential, and widening it is a page of its own in Administration (Cost Allocation) with
its own rule ordering and preview. It belongs with that page rather than inside the truth layer,
and the cost line carries whatever owner the rules produce either way.

**3. The thing a reviewer should check hardest**

That no composition adds a gateway figure to a provider figure, and that the one composition is
genuinely the only one: a second reading left behind in another module is the same bug this task
exists to remove, just further away.

Second hardest: that every amount is still exact digits after passing through a rate. A discount
applied as a float is a figure that reconciles to the penny in testing and drifts on a real bill.
