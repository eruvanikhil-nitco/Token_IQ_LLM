# Blueprint step 4: the app shell, the eight roles, guidance and Cost Explorer

**Goal:** one scope bar that drives every page, the blueprint's eight roles with their scope
enforced rather than described, a guide on every page, and Cost Explorer reading the truth layer.

**Source:** `docs/product/token-iq-product-blueprint.html`, build step 4 of section 13: "Top bar,
navigation, page templates, the eight roles and scoping, the My Team pages, page guides, Ask Token
IQ, then Cost Explorer." Section 02 for the structure, section 04 for the roles, section 05 for the
help system, and `TIQ_PAGES` for each page's own access rule.

**Where this sits:** build steps 0 to 3 are done. Step 3 gave this step something to read: one
cost line, de-duplicated, priced at the customer's own rates. Step 5 onward (recommendations,
reconciliation, budgets) needs the roles and the scope this step builds, because every one of those
screens shows money that belongs to somebody.

## What the blueprint specifies

Access has two parts and they are not the same thing. The **role** decides which pages and actions
a person has; the **scope**, organisation or one team or only themselves, decides which data they
see. The blueprint is explicit about where scope applies: "every page, tab, export, scheduled
report, assistant answer, API call and MCP query, and in the status bar."

Eight roles: Org Owner, Org Admin, Finance Admin, Org Viewer, Team Lead (Manage), Team Lead
(Read-only), Team Member, Service Account.

One scope bar in the top bar, organisation › team › project plus the period, and "every page
respects it".

A guide on every page: the blueprint gives each page `help` with steps, tips and a document name,
and every setup dialog the two-tab Setup guide / Configure shape that build step 1 already uses.

## Facts measured on 12 Oct 2026, in the code

| Piece | What exists | What is missing |
|---|---|---|
| App shell | sidebar with role-filtered groups, a header with breadcrumb, view switcher, theme toggle and notifications | the scope bar. Nothing in the shell holds a scope or a period |
| The period | `defaultPeriod()` is copy-pasted into `LedgerTabs`, `OverviewPanel` and `RecommendationTabs`, each with its own `useState` pair | one period. **And the three copies disagree**: the ledger's ends on the last day of the month, the other two end today, so the Overview total and the Ledger total describe different periods and a reader comparing them is comparing month-to-date against a whole month |
| Scope | nothing. No page, endpoint or export takes an organisation, team or project scope | all of it |
| Roles | seven values in `GatewayUserRoles` (`proxy_admin`, `proxy_admin_viewer`, `org_admin`, `internal_user`, `internal_user_viewer`, `team`, `customer`) plus UI aliases, and ad-hoc lists in `utils/roles.ts` | the blueprint's eight, which are not a rename of these: Finance Admin, Org Viewer, both Team Lead roles and Service Account have no equivalent, and `customer` has no blueprint equivalent |
| Page access rules | one function per merged page (`dataSourcesAccess`, `visibleSettingsTabs`, `visibleAccessControlTabs`, `visibleOrganizationTabs`) and `roles` lists on sidebar entries | one rule read from one place. `TIQ_PAGES` gives every page an `acc` map and nothing reads it |
| My Team | nothing. Team Home, Members & Access and Projects & Keys do not exist | all three, and they are the only pages a Team Lead starts from |
| Page guides | nothing. No page carries the blueprint's steps, tips or document name | all of it |
| Cost Explorer | the page exists as `new_usage`, labelled Cost Explorer, reading `/usage/combined/explorer` | the blueprint's own shape: scope-driven, by team, model, provider and person, with confirmed against estimated cost |
| Ask Token IQ | nothing | deferred, see below |

## The rule this work must not break

**A provider figure says how much was spent. A gateway figure says who spent it. They are never
added together.**

Cost Explorer is the page the blueprint puts both kinds of answer on, so it is the most likely
place for somebody to produce one chart that sums them. The truth layer already answers this
correctly: `total_of` adds only what is money, and a gateway observation is never money. Cost
Explorer reads that function rather than its own sums.

**And a second rule this step adds:** a scope is not a filter. A Team Lead who can change the URL
to another team's id must get a refusal from the server, not a filtered page from the browser.
Anything less is a filter that looks like security.

## The trap worth the most attention

**Roles are an authorisation change, and authorisation changes fail open.**

Today's seven roles are wired into `user_api_key_auth`, every management endpoint and the sidebar.
The blueprint's eight are a different vocabulary with different powers, and mapping one onto the
other wrongly does not throw: it grants. A Finance Admin who inherits `proxy_admin` because the
mapping defaulted that way can change settings; a Team Lead who inherits `internal_user` sees
nothing and files a bug, which is the safe direction.

So the sequence matters. The new vocabulary arrives first as a reading of what a person already is,
with no new powers anywhere. Scope is enforced server-side next, with a test per endpoint that a
scoped caller is refused another team's data. Only then does the UI start offering the new roles,
and only then is a role grantable.

## Global Constraints

- No role mapping grants a power the underlying role did not already have, and a test says so
- A scope is enforced where the data is read, not where it is displayed, and a test per endpoint
  says so
- One scope bar, one period, read by every page that shows money
- No figure crosses the provider/gateway line, and Cost Explorer reads `total_of` rather than
  summing its own
- Every page's access rule is one function the sidebar and the page share, as the four merged pages
  already do
- TDD: the failing test first, every time
- Never run the full vitest suite with no path

---

## Task 1: One scope bar, and one period

- [x] **Step 1: Write the failing test for the period the three copies disagree about**

The ledger's month ends on the last day; Overview's and Recommendations' end today. One of those is
what a reader means by "this month" and the other is what they mean by "month to date", and the
product currently shows both without saying which is which.

- [x] **Step 2: The scope bar in the shell, holding the period and the scope**

Period first, because it exists in three places and is wrong in two. The scope (organisation, team,
project) is held beside it and read by nothing yet, so the bar does not promise filtering that no
endpoint performs.

- [x] **Step 3: Move the three pages onto it, with their figures unchanged except where they were wrong**

- [x] **Step 4: Commit**

### What task 1 found

The period now lives in the shell, in `_scope/`, and the three copies are gone. `periodFor` names five
choices and each one is a thing a reader actually means, which is the part the copies got wrong by
having only one name for two of them: month to date is what has been spent so far, and the whole
month is what a provider's bill covers.

Removing the pages' own date inputs would have cost a capability, because a month closes long after
it ends and a finance team reconciles September in November. So the bar has a named month, with the
last twelve offered, and every past month the ledger could reach before is still reachable.

Invoice Reconciliation now says so when the period is not a whole month. It was the screen most
damaged by the disagreement: a bill covers the month, so comparing it against part of one reports a
difference the size of the days that have not happened yet, and the screen read that as the provider
overcharging. The warning sits above the figures rather than under them, and a test asserts that
order, because a caveat a reader meets after the number has already done its work.

The scope proper, organisation and team and project, is deliberately not in the bar yet. Task 3
enforces it server-side, and a picker shipped before that would filter in the browser over an
endpoint that returns everything, which is a filter that looks like security.

No live proof for this task. The proxy will not boot on this machine today: Windows Application
Control blocks the prisma query engine binary, `WinError 4551`, so prisma reports "Not connected to
the query engine" and startup exits. It needs an allow rule for that one file. The checks are 124
unit and integration tests over the touched directories plus 5 of 5 mutants killed, and the manual
steps are in `docs/status.md` for when the proxy runs.

---

## Task 2: The eight roles, as a reading of what a person already is

- [x] **Step 1: Write the failing test that no mapping grants a new power**

For each of today's roles, the blueprint role it reads as, and an assertion that the powers of the
result are a subset of the powers it had. This is the test that makes the rest of the task safe.

- [x] **Step 2: One module that answers what a role may do, with the eight names**

`TIQ_MATRIX` is the blueprint's own answer per page and role. The module states it once, the
sidebar and every page read it, and the four existing per-page functions become callers rather than
second opinions.

- [x] **Step 3: Say plainly which of the eight an installation cannot grant yet**

Finance Admin, Org Viewer and both Team Lead roles have no underlying role to grant. A screen that
offered them would be offering an account nobody can sign in as.

- [x] **Step 4: Commit**

### What task 2 found

The eight roles are in `_access/roles.ts`, with the blueprint's matrix as data in its own words
rather than flattened to a level, because "Own team" and "View; upload invoices" say different
things and choosing one word for both is where a reading becomes a guess.

`allowedPages` is defined as an intersection with what the person can already see. That is the
safety property and it is structural rather than careful: a mapping that named a stronger role, or a
matrix row that granted something new, still cannot widen the answer past today's. A role nothing
maps to reads as null and gets nothing, which is the direction an authorisation mistake has to fail
in. 8 of 8 mutants killed, including dropping the intersection and reading a viewer as an admin.

Two of today's roles read as no blueprint role at all. `team` is the identity a JWT caller presents
and `customer` is an end user of somebody else's application: neither is a person who opens Token
IQ, and giving either one a role would invent an account that can sign in.

**The one thing this task does not do, because it is a removal.** Adopting the matrix in the sidebar
would take entries away from two of today's roles, measured on 13 Oct:

| Role | Reads as | Entries the matrix would hide |
|---|---|---|
| `proxy_admin`, `Admin` | Org Owner | none |
| `org_admin` | Org Admin | none |
| `proxy_admin_viewer`, `Admin Viewer` | Org Viewer | Organization, Cost Allocation, Pricing & Rates, Settings, Data Sources, Virtual Keys, Router Settings |
| `internal_user`, `internal_user_viewer` | Team Member | Cost Optimization, Organization |

The blueprint's Org Viewer is read-only over finance rather than over configuration, which is why an
Admin Viewer loses seven entries. Each of those is defensible, and taking a page away from somebody
who has it today needs the owner's say, so `pagesTheBlueprintHides` reports the difference and
nothing acts on it. The four per-page functions keep their own rule until that decision.

Roles & Permissions is a new tab on Access Control rather than a change to an existing one. It
names all eight, says which four cannot be assigned and why, and says what the other four are
assigned as. A screen that listed Finance Admin without that sentence would be offering an account
nobody can sign in as, which a customer finds out after inviting somebody.

---

## Task 3: Scope, enforced where the data is read

- [ ] **Step 1: A test per endpoint that a scoped caller is refused another team's data**

The security task. Every endpoint that returns money takes the scope from the caller's own identity
rather than from a query parameter, and a parameter that disagrees with the identity is a refusal.

- [ ] **Step 2: One function the endpoints share, and a repository that filters where it reads**

- [ ] **Step 3: Commit**

---

## Task 4: A guide on every page

- [ ] **Step 1: The guide surface, from the blueprint's own `help` for each page**
- [ ] **Step 2: Commit**

---

## Task 5: Cost Explorer, on the truth layer

- [ ] **Step 1: Write the failing test that no chart adds a gateway figure to a provider figure**
- [ ] **Step 2: The page the blueprint specifies, scope-driven, reading the truth layer**
- [ ] **Step 3: Commit**

---

## Task 6: The My Team pages

- [ ] **Step 1: Team Home, Members & Access, Projects & Keys, after roles and scope exist**
- [ ] **Step 2: Commit**

---

## Self-Review

**1. Source coverage**

| Build step 4 item | Task |
|---|---|
| Top bar, navigation, page templates | Task 1, plus what the shell already has |
| The eight roles | Task 2 |
| Scoping | Task 3 |
| My Team pages | Task 6 |
| Page guides | Task 4 |
| Cost Explorer | Task 5 |
| Ask Token IQ | deliberately not here, see below |

**2. What is deliberately not here**

Ask Token IQ. Step 4's own sentence lists it, and section 13's step 10 says "Then Ask Token IQ and
the MCP server", so the blueprint contradicts itself. An assistant that answers spend questions has
to answer them from the analysis pages and inside the asker's scope, so it belongs after both exist.
Recorded here rather than silently skipped.

**3. The thing a reviewer should check hardest**

That no role mapping grants a power the underlying role did not have. Authorisation mistakes fail
open: a wrong mapping does not throw, it permits, and the person who notices is the one who should
not have been able to see the page.

Second hardest: that scope is enforced where the data is read. A filtered page over an unfiltered
endpoint is not scope, and the way to tell is to call the endpoint directly with another team's id.
