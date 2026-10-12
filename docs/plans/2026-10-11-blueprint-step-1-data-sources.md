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

- [x] **Step 1: Write the failing test for the tab visibility rule**

Manage for Org Admin, view for Finance Admin, hidden for every other role, which is the first of
these pages whose access differs by role rather than being admin-only. A view-only role must see the
tabs and none of the actions.

- [x] **Step 2: The tab shell and the Accounts tab**

Accounts first, because it is the one tab whose backend is complete. One table over
`/provider/connections` and `/tool/connections`, each row opening the raw records that
`/provider/usage/raw` already returns.

- [x] **Step 3: Keep every address alive**

`provider-apis`, `user-tools` and `llm-provider-credentials` become tabs. Their `?page=` ids and
their paths redirect, and a test covers each.

- [x] **Step 4: Commit**

---

### What task 1 found

**LLM Provider Credentials is not an account, and nearly got merged as one.** The label table
lists it among the seven entries folding into Data Sources, so the obvious reading is that it
belongs on Accounts. It does not: those are *forwarding* credentials, and the blueprint puts them
on the Gateway tab under "upstream endpoints". Separating billing from forwarding credentials
was the whole of build step 2's first task, so folding them back into one list would have undone
it. It stays where it is until task 5, and a sidebar test records why.

So this merge is two entries, not three. Both legacy ids point at `data-sources/accounts` rather
than the page root, so they keep landing on the tab they were on once the Overview tab arrives and
takes first position.

**The two endpoints disagree about the record count.** A provider account calls it `facts_stored`
and a tool account `rows_stored`. The row names it `records_stored`, for what it means, and the
adapter normalises both at the boundary so neither endpoint's spelling reaches the table.

**The no-account row earned itself on the live proxy.** Five of the six providers and all three
tools come back with no accounts; openrouter has one, `needs_attention`, holding 50 facts. Without
a row for a supported-but-unconnected source the tab would show that single openrouter row and
nothing else, which reads as "one source, looks fine" rather than "five providers are telling you
nothing". With it, the tab is nine rows and the five silent ones are the answer.

I first read this off a truncated print of the first four providers and wrote that every provider
was unconnected. It is not: openrouter is connected and its row carries a working raw-records
link, which is also what proves that half of the tab end to end.

**Two connection states in my fixtures did not exist.** `failing` and `not_configured` are not in
the set, which is `not_connected`, `waiting_for_first_data`, `healthy`, `needs_attention`. A
fixture built on values that cannot occur tests a shape that does not exist.

## Task 2: The Overview tab and the issues list

- [x] **Step 1: Write the failing test for each issue the blueprint names**

Failing connections, missing invoices, unmatched people, keys without projects. Each is a count with
a link to where it is fixed, and each needs its own test, because an issues list that silently
returns nothing looks identical to a healthy installation.

Done, and the plan was wrong about one of the four. Unmatched people cannot be counted at all: it
needs directory sync, which section 12 lists as its own Must and which nothing here implements. So
an issue's state is a tagged union, `Measured | Unmeasurable`, rather than an integer. A zero means
looked at and found none, and a question nobody has looked at must not borrow that number, because
on the tab asking whether the data can be trusted a zero reads as reassurance.

- [x] **Step 2: Compute them in one place, not four screens**

`token_iq/overview/data_quality.py` holds the rule and takes the facts rather than fetching them, so
it is tested without a database. `/data-quality` composes one period, gathering the connection states
itself through the same builder and run window as the connections endpoint rather than letting the
browser supply them.

- [x] **Step 3: Invoice coverage, which already has its data**

As a fraction, which needed a denominator the repository did not have: `providers_billing` counts the
providers that billed inside the period, starting from the same population as the missing count so
the two are a fraction of each other. Coverage is its own tagged union too, because "0 of 0" reads as
perfect coverage or as total failure depending on the card, and a period nobody billed in is neither.

- [x] **Step 4: Commit**

Both coverage states and all four issue states are proved against the live proxy, not only in tests.

---

## Task 3: The connect dialog

- [x] **Step 1: An endpoint that mints and stores an external ID per connection**

What task 2 of build step 2 was missing. `new_external_id()` exists and nothing calls it.

Done. `POST /provider/connections/external-id` mints once per connection and returns the same
value every time afterwards, because the primary key of the new table is the connection itself.

- [x] **Step 2: The dialog, from `TIQ_MODALS.connect` rather than from my own design**

Five categories, four method kinds, and the two-tab Setup guide / Configure shape. The `role` kind
is specified field by field in build step 2's plan and is the one to build first, because its
backend is already done and tested.

- [x] **Step 3: Nothing is saved until the connection test passes**

The blueprint's own words. `POST /provider/billing/probe` is that test and it already exists.

Enforced on the server rather than in the dialog. `POST /provider/connections` tests the
credential being offered and writes it only when the probe came back `fetched`, so the promise
holds for any client instead of only for this one.

- [x] **Step 4: Commit**

---

### What task 3 found

**The external ID had to become idempotent, not just stored.** The plan said mint and store. What
a browser actually does is open the dialog, leave for AWS, come back, and sometimes reload on the
way. Minting on each read would hand out a second value for a connection whose role already
trusts the first, and AWS answers that with an AccessDenied that names nothing. So the table's
primary key is the pair (provider, account name), the mint reads before it writes, and a write
that collides reads the winner rather than minting again. A collision that then reads back
nothing raises, because treating it as an empty store is the one path that issues a second value.

**The account name has to be fixed once an ID has been issued.** It is half the key, so renaming
afterwards silently starts a different connection and leaves the role the customer already
created pointing at nothing. The dialog locks the field and says why.

**The probe could not be reused as it stood.** `run_billing_probe` looks up the stored credential
for a provider, so a connect flow that called it would test the previous connection and report a
brand new key as working. It already takes its credentials through an injected lookup, so the
candidate is handed to it directly, and a test says the candidate's own values reach the
connector.

**A fetch that found nothing is a pass.** The probe answers `fetched` with zero rows for an
account that simply has no spend in the window, which is the normal state of an account connected
today. Requiring a figure would make a quiet account impossible to connect.

**Credential values needed a server-side allowlist.** The dialog posts a field map, and without
one a caller could put `api_base` on a billing credential and point a connector somewhere other
than the provider. `BILLING_CREDENTIAL_FIELDS` names what each provider's credential may carry,
and `external_id` is deliberately absent from bedrock's set so a value sent by a caller is
dropped rather than honoured.

**Two departures from the mockup, both about not promising what this build cannot do.** A category
with no connector keeps its place and shows no tiles, because dropping it leaves "where do I
connect Copilot?" unanswered while a tile leads to a form whose save cannot succeed. And a method
the blueprint recommends but this build has not got, which is every sign-in, is shown as a tab
marked "Not built yet" with the reason, rather than hidden: hidden, the dialog silently
recommends the least safe option left.

**The template became a download.** The mockup's step one is "Launch template in AWS", which
needs the template hosted at a URL this product does not have. `GET
/provider/connections/bedrock-role-template` serves the file that ships, so step one can be
followed, and a test asserts it is that file byte for byte rather than a copy the trust-policy
test is no longer guarding. The template's other parameter, the AWS principal this installation
runs as, is not discoverable here: nothing configures it. The dialog says where it comes from, and
reading it from `sts:GetCallerIdentity` is the obvious follow-up.

**A read-only view is not a database row, and twice it reached one.** `MappingProxyType` is the
house default for a fixed mapping and it is not JSON serialisable, so both places a mapping left
this module turned into a 500. First every refusal: FastAPI runs an `HTTPException` detail
through `json.dumps`, so each 400 arrived as "Internal server error" with the reason gone, which
is the worst possible answer to a form field being wrong. `data_quality.py` had the same bug from
two commits earlier, unnoticed because its refusal paths had never been curled. Then the credential
row: prisma serialises it the same way, so the first connection whose live test actually passed
came back as a 500 with nothing stored. Asserting a status code never catches either, because
nothing in a unit test serialises the payload, so both now go through `json.dumps` in a test.

**A stale `--reload` worker cost half an hour.** Two live checks reported empty credential values
while the same code passed in process. The worker was serving an older module. Same family as the
`--reload` watches config, not code finding from the Overview tab: when a live result contradicts
an in-process one, suspect the process before the code.

**Three stale paths from the phase 6 rename, found on the way in.** `scripts/prisma_generate_if_needed.py`
and `scripts/type_check_gate.py` both pointed at `litellm/proxy/schema.prisma`, which has not
existed since phase 6. The first would crash on `read_bytes`; the second guards its read with
`if path.exists()`, so it had quietly stopped fingerprinting the schema and a schema change no
longer invalidated the typecheck cache. `npm run gen:api` also needs `LITELLM_PYTHON` set on this
box, because it defaults to `python3`.

---

## Task 4: The Uploads tab

- [x] **Step 1: Invoices, which have an endpoint**
- [x] **Step 2: The forwarding address**
- [x] **Step 3: Commit**

### What task 4 found

**An entered bill was not the bill reconciliation looked up.** The endpoint that stores a bill
parsed its period end as a bare date, so September ended at midnight on the thirtieth, while every
read of a period widens the same date to the last instant of that day. `for_period` matches a
period exactly, so the month then reported "No bill entered for this period yet" with the bill
sitting in the table. Both calls succeed and both responses render the period as 2026-09-30, which
is why nothing noticed. The coverage query fails the same way, through `period_end > bucket_start`:
a provider whose whole month was entered still counted as missing one, because the final day fell
outside its own invoice. One function now builds the stored bill, so the write and the read cannot
disagree, and the live round trip went from `no_invoice` to a real comparison.

**The rows worth having are the bills nobody entered.** A missing bill is invisible everywhere
else: reconciliation reports no bill rather than a difference, and the Overview tab's coverage
figure says how many are missing without saying which. So the missing-invoice query returns names
rather than a count, the count becomes the length of that list, and both tabs are answered by one
statement rather than two that eventually disagree about one provider.

**A missing row carries no total, and not a zero.** There is no bill, so the only figure available
would be the ledger's own, and a figure Token IQ worked out printed in an invoice column is how a
provider total and an attribution total get added together by accident. The same reason the
Accounts tab totals records and not money.

**A provider can be missing a bill and have one at the same time.** It billed since the last bill
was entered. Collapsing the two rows would drop whichever was judged the duplicate, so both are
listed, and the live check shows exactly that: OpenRouter recorded for October and still missing
one for the days before it.

**A forwarding address that cannot receive mail is its own state.** Shown as though it worked, a
typo sends a finance team's bills nowhere and nothing says so until a month-end close has nothing
to reconcile against; folded into "not configured", the same typo reads as nobody having tried and
the next administrator sets it a second time instead of fixing it. All three states were checked
against a running proxy, because an environment-driven setting is exactly where in-process tests
prove nothing.

**Even a working address is said to be a mailbox a person reads.** Nothing here opens mail or
parses an attachment. An address presented as automatic would have a customer forwarding bills for
a month and then asking why none of them arrived.

**The dialog asks for the figures instead of pretending to read them.** The blueprint's modal takes
a PDF or CSV and confirms its parsed lines before saving. There is no parser and no document store,
so a file field would leave a customer believing their bill had been understood. The month is one
field rather than two dates for the reason above: a period assembled by hand is a bill that fails
to cover the last day of its own month.

**An adjustment entered the wrong way round does not fail.** It moves the unexplained remainder by
twice the amount and blames the provider for it. The sign is explained per kind and a contradicting
sign is a note rather than a refusal, because a reversed credit is real.

**Entering a bill is now in two places.** The Ledger page's Invoices tab has had an inline form
since the ledger work, and the blueprint puts this on Data Sources > Uploads, which is also what
Invoice Reconciliation's own "not here" line says. Nothing was removed, because removing a tab
needs asking first. Worth consolidating: the Ledger tab should point here.

**Bills entered before the period fix sit at a midnight end.** Re-entering that month now writes a
second row rather than correcting the first, because the upsert's conflict target is the exact
period. Two bills for one month would double the invoiced figure. Only two dev rows existed and
both were removed; a fresh installation cannot reach it, and a check for two bills covering one
month would be the honest guard if one ever ships.

---

## Task 5: The Gateway tab, last and alone

- [x] **Step 1: Decide with the owner whether Virtual Keys and Logs really move**

The blueprint says they do. They are also the most-visited pages in the product, and moving them
behind a tab on a data page is the change most likely to be felt as a regression. Ask before moving,
and record the answer either way: this is the one task here whose cost is not technical.

**Asked on 12 Oct 2026. The answer was yes, they move.** So they are views of the Gateway tab for
anyone who can open Data Sources, and the sidebar no longer lists them for that viewer.

- [x] **Step 2: Whatever that answer is, keep every address alive**
- [x] **Step 3: Commit**

### What task 5 found

**The move cannot apply to everyone, because the page it moves into is admin-only.** Data Sources is
manage for Org Admin, view for Finance Admin and hidden for every other role, which is the rule task
1 built. The request log and virtual keys have no role restriction at all: a team member reads their
own keys and their own requests there. Moving them unconditionally would take the two screens a
non-admin uses most and leave nothing in their place, which is not a navigation change but a loss of
access. So `gatewayPagesMovedFor` is one function the sidebar asks: the entry disappears exactly
when the tab that replaced it appears, and both routes keep serving the page either way. The
blueprint's own answer for those roles is My Team and My Usage, which are build step 4.

**Views, not tabs.** The blueprint's navigation rule is that a page has sub-tabs and a sub-tab never
has its own tabs, and it writes this tab's own address as `/data-sources/gateway?view=upstreams`. So
the three screens are a `?view=` switcher rather than a second tab strip, which also keeps a link to
one of them a link to what the reader was looking at. An unknown value opens the first view rather
than a blank tab, because a stale bookmark would otherwise be indistinguishable from an outage.

**The request log is the flat panel, not the Logs page.** That page carries four tabs of its own, so
folding it in whole would have been three levels deep. Its other three, the audit log, deleted keys
and deleted teams, record what administrators did rather than what the gateway observed, so they
stay on Logs and the view says where they are. Nothing was removed and nothing is unreachable.

**Providers and Models + Endpoints stay pages, and the view links to them.** Both carry their own
tab strips, Models + Endpoints nine of them, and they are gateway configuration rather than a place
data arrives from. Upstreams is what the blueprint actually describes on this tab: the credential the
gateway forwards with, which is the panel LLM Provider Credentials was.

**LLM Provider Credentials is the one entry that moved outright.** It is admin-only already, so there
is no role carve-out to make: its sidebar entry is gone, `/llm-provider-credentials` redirects to the
upstreams view, and the three places in the product that linked to it now link to the view directly
rather than through a redirect.

**No traffic summary.** The blueprint lists "observed traffic" first and every figure available for
it is either money, which would put a gateway total on the same page as provider bills, or a repeat
of what the Overview page already says. The request log is the honest answer to what the gateway
observed, so it is the view the tab opens on.

**Seven entries are now one page.** Provider APIs and User Tools as Accounts, LLM Provider
Credentials as Upstreams, the request log and virtual keys as the other two views, and Providers and
Models + Endpoints linked from Upstreams rather than absorbed. Every one of the seven addresses still
resolves, and a test covers each.

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
