# Blueprint step 1: the Data Sources page and the connect flow

**Goal:** the one page the blueprint puts every incoming source on, and the dialog that adds one.

**Source:** `docs/product/token-iq-product-blueprint.html`, the `{k:'ds',g:'Data'}` page model and the
`TIQ_MODALS.connect` dialog. Build step 1 of its section 13, which the blueprint marks "designed"
rather than built. Section 12 of `docs/plans/2026-10-04-independent-codebase.md` says to treat the
blueprint as a specification and follow that build order.

**Where this sits:** step 0, the codebase programme, is done. Step 2, the quick fixes, is done bar
its dialog, which was deferred *to here* because there is no connect surface to put it in and
nothing mints an external ID per connection. Step 3 onward depends on the truth layer, not on this.

This is also phase 9's fourth consolidation row, the one `docs/status.md` recorded as "phase 5A's
rebuild rather than a rename". Same work, reached from the other end: seven of today's sidebar
entries become one page with four tabs.

## What the blueprint specifies

One page, `Data › Data Sources`, manage for Org Admin, view for Finance Admin, hidden for everyone
else. Its own words for what it is: "Every place Token IQ gets usage and cost data from, whether it
is arriving, and the records exactly as received." Deliberately not on it: "Spend by team or model.
That is analysis (Cost Explorer)."

| Tab | The blueprint's description | Built from |
|---|---|---|
| Overview | "Can the data be trusted? Health and freshness of every source, invoice coverage, and data quality issues to fix." | `/provider/connections`, `/ledger/invoices`, `/ledger/reconciliation`, plus an issues list that does not exist |
| Accounts | "Every connected account: AI providers, AI tools, agent platforms, cloud billing exports and custom sources... Each row opens its raw records." | `/provider/connections`, `/tool/connections`, `/provider/usage/raw`, `/provider/sync-history` |
| Gateway | "The Token IQ gateway: observed traffic, request log, virtual keys and upstream endpoints." | today's Logs, Virtual Keys, Providers and Models + Endpoints pages |
| Uploads | "Invoices, workspace exports and contracts that have no API, uploaded or forwarded by email." | `POST /ledger/invoices`, and the invoice-forwarding address |

One primary action, `+ Connect account`, opening the connect dialog.

## Facts measured on 11 Oct 2026, in the code

| Piece | What exists | What is missing |
|---|---|---|
| Accounts | `GET /provider/connections`, `GET /tool/connections`, `GET /provider/sync-history`, `GET /provider/usage/raw`, `POST /provider/billing/probe`. The `provider-apis` page already renders connection state, what-we-fetch and sync history; `user-tools` does the same for tools | One table over both kinds, with a row that opens raw records. Agent platforms, cloud billing exports and custom sources have no connector at all |
| Overview | connection health and freshness from `/provider/connections`; invoice coverage from `/ledger/invoices` and `/ledger/reconciliation` | **the data-quality issues list.** The blueprint names four: failing connections, missing invoices, unmatched people, keys without projects. Nothing computes them together |
| Gateway | every part exists as its own page today | nothing, beyond putting them behind one tab without breaking their addresses |
| Uploads | `POST /ledger/invoices` takes an invoice | the forwarding address, and anything that is not an invoice |
| Connect dialog | `TIQ_MODALS.connect` specifies it completely: a vendor catalogue in five categories, four method kinds (`key`, `guided`, `oauth`, `role`), per-field label, type, options, explanation, example and required flag, and a two-tab Setup guide / Configure shape | all of it. Also no endpoint mints an external ID, which the `role` kind needs |

## The rule this work must not break

**A provider figure says how much was spent. A gateway figure says who spent it. They are never
added together.**

This page puts both on one screen for the first time, which is exactly where the rule gets broken by
accident. The Accounts tab lists provider accounts *and* tool accounts; the Gateway tab is the
gateway's own view. A total across the page, or a "total sources" figure that sums a provider's
billed cost with the gateway's attributed cost, is the failure. Each tab reports its own figures and
the page shows no cross-tab total.

## The trap worth the most attention

**Seven entries disappearing from the sidebar is seven addresses a customer may have bookmarked.**

The three merges already done each kept every old address alive: a legacy `?page=` id redirecting to
the right tab, and the old path left as a redirect. This row is larger and two of its seven,
Virtual Keys and Logs, are among the most-visited pages in the product. The same rule applies and is
worth saying before any of it moves: no address stops resolving, and `MIGRATED_PAGES` plus
`TAB_OWNER` carry the mapping, as they do for Organization, Access Control and Settings.

Second trap: the Gateway tab would move Virtual Keys and Logs *out of* a group a customer uses
constantly, to sit behind a tab on a data page. That is what the blueprint says, and it is also the
change most likely to be felt as a regression, so it goes last and alone.

## Global Constraints

- No address stops resolving, and a test says so for each one
- No figure crosses the provider/gateway line, and a test says so
- Every tab's visibility rule lives in one function the sidebar and the page share, as
  `visibleOrganizationTabs` and its two siblings do
- TDD: the failing test first, every time
- Python line length 120, `: Final`, no `Any`, immutable collections, tagged unions and `match`
- Never run the full vitest suite with no path

---

## Task 1: The page, its four tabs, and the Accounts table

- [ ] **Step 1: Write the failing test for the tab visibility rule**

Manage for Org Admin, view for Finance Admin, hidden for every other role, which is the first of
these pages whose access differs by role rather than being admin-only. A view-only role must see the
tabs and none of the actions.

- [ ] **Step 2: The tab shell and the Accounts tab**

Accounts first, because it is the one tab whose backend is complete. One table over
`/provider/connections` and `/tool/connections`, each row opening the raw records that
`/provider/usage/raw` already returns.

- [ ] **Step 3: Keep every address alive**

`provider-apis`, `user-tools` and `llm-provider-credentials` become tabs. Their `?page=` ids and
their paths redirect, and a test covers each.

- [ ] **Step 4: Commit**

---

## Task 2: The Overview tab and the issues list

- [ ] **Step 1: Write the failing test for each issue the blueprint names**

Failing connections, missing invoices, unmatched people, keys without projects. Each is a count with
a link to where it is fixed, and each needs its own test, because an issues list that silently
returns nothing looks identical to a healthy installation.

- [ ] **Step 2: Compute them in one place, not four screens**

- [ ] **Step 3: Invoice coverage, which already has its data**

- [ ] **Step 4: Commit**

---

## Task 3: The connect dialog

- [ ] **Step 1: An endpoint that mints and stores an external ID per connection**

What task 2 of build step 2 was missing. `new_external_id()` exists and nothing calls it.

- [ ] **Step 2: The dialog, from `TIQ_MODALS.connect` rather than from my own design**

Five categories, four method kinds, and the two-tab Setup guide / Configure shape. The `role` kind
is specified field by field in build step 2's plan and is the one to build first, because its
backend is already done and tested.

- [ ] **Step 3: Nothing is saved until the connection test passes**

The blueprint's own words. `POST /provider/billing/probe` is that test and it already exists.

- [ ] **Step 4: Commit**

---

## Task 4: The Uploads tab

- [ ] **Step 1: Invoices, which have an endpoint**
- [ ] **Step 2: The forwarding address**
- [ ] **Step 3: Commit**

---

## Task 5: The Gateway tab, last and alone

- [ ] **Step 1: Decide with the owner whether Virtual Keys and Logs really move**

The blueprint says they do. They are also the most-visited pages in the product, and moving them
behind a tab on a data page is the change most likely to be felt as a regression. Ask before moving,
and record the answer either way: this is the one task here whose cost is not technical.

- [ ] **Step 2: Whatever that answer is, keep every address alive**
- [ ] **Step 3: Commit**

---

## Self-Review

**1. Source coverage**

| Blueprint step 1 item | Task |
|---|---|
| One page with four tabs | Task 1, with Overview in 2, Uploads in 4, Gateway in 5 |
| Raw records for every account | Task 1 step 2 |
| Connect account dialog, Anthropic and OpenAI menus, sign-in buttons, guided keys, Custom source | Task 3 |
| The deferred AWS role dialog from build step 2 | Task 3 step 2 |

**2. What is deliberately not here**

Agent platforms, cloud billing exports and custom sources appear in the blueprint's Accounts tab and
have no connector behind them. Listing a vendor a customer cannot actually connect would be an empty
promise, so the catalogue shows what exists and the rest waits on its connector.

**3. The thing a reviewer should check hardest**

That no figure on this page adds a provider total to a gateway total. It is the first screen to show
both, the counting rule is the one thing in this product that breaks silently, and a page whose job
is "every place data comes from" is the natural place for somebody to add a grand total.

Second hardest: the seven addresses. Six of the seven are pages a customer reaches from a bookmark
or a link in a runbook.
