# User Tool Connectors Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build every user tool connector the plan calls for, to the same standard the provider connectors now hold, so that the day a customer's tool account exists the work is one credential and one button.

**Architecture:** A tool connector mirrors a billing connector: a pure fetcher that never raises, returning either facts or a named failure. Two shapes come back, because the tools genuinely differ. Claude Code and Cursor report what a named person actually spent, which becomes a tool usage fact. Copilot reports who holds a licence, which becomes a seat in the model Phase 4 already built. Each connector is held to its vendor's documented API by a contract test driven over a real HTTP client.

**Tech Stack:** Python 3.12, FastAPI, `httpx`, Prisma with Postgres, `prisma-client-py` raw queries, pytest. Dashboard is Next.js with shadcn/Base UI, TanStack Query and vitest.

**Spec:** `docs/superpowers/specs/2026-09-14-token-iq-product-design.md`, sections "User tools" and "Data sources", Phase 4

## What the vendors actually publish, checked on 2026-09-29

| Tool | Endpoint | What it gives | Shape |
|---|---|---|---|
| Claude Code | `GET /v1/organizations/usage_report/claude_code` | Per person per day, per model, an estimated cost and token counts, keyed by email address | Usage fact |
| Cursor | `POST /teams/filtered-usage-events` and `POST /teams/spend` | Per event a charged amount in cents with the user's email and model, and a per member spend total | Usage fact |
| GitHub Copilot | `GET /orgs/{org}/copilot/billing/seats` | Who holds a licence, when it was assigned, when they were last active, and the plan type. No cost | Seat |
| Codex and ChatGPT | Nothing published | See below | Deferred |

Each connector's authentication differs and each is easy to get wrong in a way only a real
server rejects: Claude Code takes `X-Api-Key` with a version header, Cursor takes HTTP Basic
with the API key as the username and an empty password, and GitHub takes a bearer token with
`Accept: application/vnd.github+json` and an API version header.

**Codex and ChatGPT are deferred, with a reason rather than an empty file.** No per-user admin
usage endpoint is published for either. What is documented is that Codex signed in with an API
key bills through the OpenAI platform account at standard API rates, which the existing OpenAI
billing connector already collects. Codex on a ChatGPT Business or Enterprise plan is credit
based, and those credits are a subscription cost, which the Seats model already carries. So
the money is not missing from the product; only a per-person split of it is, and inventing an
endpoint for it would be worse than saying so.

## The rule this plan must not break

**Claude Code usage billed to an API organisation is the same money the Anthropic provider
connector already reports.**

Every Claude Code record carries `customer_type`. When it is `api`, that spend appears on the
organisation's Anthropic bill and is already counted by the Anthropic billing connector.
Storing it again as tool usage and adding the two would overstate a customer's Anthropic spend
by exactly the amount their developers ran through Claude Code, which is the single largest
number on the screen for a customer who uses it heavily.

When `customer_type` is `subscription`, the spend sits on a Pro, Team or Enterprise plan and is
genuinely separate money.

So a Claude Code record is stored either way, because knowing who spent it is the whole point,
but it is tagged with whether the amount is already counted elsewhere, and only untagged rows
may be added to a total. This is the same discipline as the counting rule the product already
holds: a provider figure says how much was spent, a gateway figure says who spent it, and they
are never added together.

Cursor is different and does not need the tag: Cursor buys the models itself and bills the
customer, so it appears on no provider bill we read.

## Global Constraints

- Money is `Decimal` end to end and must never pass through `float`. Claude Code and Cursor
  both report cents, so both need scaling and neither may be scaled twice
- A connector never raises. Every failure is a value the runner can record
- No real credential, key or token in a test, a fixture, a commit or a log
- Sample payloads are copied from the vendor's published documentation, and each file names the
  page it came from
- A person is matched to a Token IQ user by email, and a tool row whose email matches nobody is
  reported as unmatched by name rather than being dropped or guessed at
- The hierarchy is teams, projects and users. Never "employees"
- Prisma migrations change schema only, never rewrite rows. All three schema copies stay
  byte-identical. New tables are read and written with raw parameterised SQL, because
  `prisma generate` is blocked on this machine
- No `Any` or coarse types, every parameter strongly typed, `: Final` on every variable
  (LIT010), no parameter rebinding (LIT011), `ReadOnly` on TypedDict fields (LIT012),
  immutable collections
- Every suppression names its exact rule in brackets with a true reason. `# type: ignore` is banned
- No comments except genuinely complex business logic, tool-read suppressions, or TODO/FIXME
- Tests must test function, never structure, and must fail when the behaviour is mutated
- Never remove, merge or rename an existing UI tab
- No customer-visible LiteLLM branding, no company or customer names, no secrets, no `eval`
- Python max line length 120. TypeScript has no `any`, no tokens in `localStorage`

---

## Task 1: A tool usage fact, and the tag that stops it being double counted

**Files:**
- Create: `litellm/types/proxy/tool_usage.py`
- Create: `litellm/tool_usage/__init__.py`, `litellm/tool_usage/connector.py`
- Create: `tests/test_litellm/tool_usage/test_tool_usage_types.py`
- Modify: the three Prisma schema copies, plus a migration

- [ ] **Step 1: Write the failing tests**

A fact carries the tool, the person's email as the tool reported it, the day, the cost, the
currency and whether that cost is already counted on a provider bill. A fact that claims an
amount with no currency is refused at construction, as the recommendation card is.

- [ ] **Step 2: Define the type and the connector protocol**

`ToolUsageFact` and a `ToolConnector` protocol matching `BillingConnector`: same never-raise
contract, same tagged-union result, so the runner that already exists can drive both.

- [ ] **Step 3: Add the table and apply the migration**

Schema only. A unique key per tool, person and day so a refetch overwrites rather than doubles.

- [ ] **Step 4: Run the tests, mutate each guard, commit**

---

## Task 2: The Claude Code connector

**Files:**
- Create: `litellm/tool_usage/claude_code.py`
- Create: `tests/test_litellm/tool_usage/test_claude_code_connector.py`
- Create: `tests/test_litellm/tool_usage/contract/test_claude_code_contract.py`

- [ ] **Step 1: Write the failing contract test**

Driven over a real HTTP client against the example response printed on Anthropic's own
reference page. It pins the path, the `X-Api-Key` and version headers, the single-day
`starting_at`, the page size cap of 1000, following `next_page` to the end, and every error.

- [ ] **Step 2: Write the failing unit tests for the two things most likely to be wrong**

The cost is in minor units, so 186 means one dollar eighty-six and storing it verbatim
overstates by a hundredfold. And a record's `customer_type` decides whether the amount is
already on the Anthropic bill, which is the rule above.

- [ ] **Step 3: Build it**

One request per day, because this endpoint returns a single day per call. An actor may be a
person or an API key, and a row attributed to an API key has no person to bill, so it is kept
with its key name rather than being dropped or attributed to nobody.

- [ ] **Step 4: Mutate and commit**

Drop the minor-unit scaling, invert the already-counted tag, and stop paging. Each must kill a test.

---

## Task 3: The Cursor connector

**Files:**
- Create: `litellm/tool_usage/cursor.py`
- Create: `tests/test_litellm/tool_usage/test_cursor_connector.py`
- Create: `tests/test_litellm/tool_usage/contract/test_cursor_contract.py`

- [ ] **Step 1: Write the failing contract test**

Cursor authenticates with HTTP Basic, the API key as the username and an empty password, which
is unlike every other connector here and is wrong until a real server rejects it. The window is
epoch milliseconds, capped at 30 days per call, and the endpoint is a POST with a JSON body.

- [ ] **Step 2: Write the failing unit tests**

Charged amounts are cents. Events are per request, so a day's cost for a person is the sum of
their events that day, and an event with no email belongs to nobody and is reported as such.

- [ ] **Step 3: Build it, respecting the rate limit**

Sixty requests a minute on usage events, and thirty days maximum per call, so a longer window
is split rather than asked for in one go.

- [ ] **Step 4: Mutate and commit**

---

## Task 4: The Copilot connector, which reports seats rather than usage

**Files:**
- Create: `litellm/tool_usage/copilot.py`
- Create: `tests/test_litellm/tool_usage/test_copilot_connector.py`
- Create: `tests/test_litellm/tool_usage/contract/test_copilot_contract.py`

- [ ] **Step 1: Write the failing tests**

Copilot publishes who holds a licence, not what they spent, so this connector produces seats
into the model Phase 4 already built rather than usage facts. A seat's cost is the plan price,
which only the customer knows, so the connector reports the holder and the plan type and leaves
the amount to be set once rather than inventing one.

- [ ] **Step 2: Build it**

Bearer token, `Accept: application/vnd.github+json` and the API version header. Page through
`per_page` up to its maximum of 100.

- [ ] **Step 3: Record what last activity does and does not mean**

`last_activity_at` is null unless the person enabled telemetry in their IDE, so an empty value
is not evidence that a seat is unused. Recommending someone lose a licence on that basis would
be wrong, which is exactly why the unused seats recommendation stays deferred.

- [ ] **Step 4: Mutate and commit**

---

## Task 5: Register, schedule and store

**Files:**
- Create: `litellm/repositories/tool_usage_fact_repository.py`
- Create: `litellm/tool_usage/runner.py`, `litellm/tool_usage/startup.py`
- Modify: `litellm/provider_billing/credential_purpose.py` for a tool purpose
- Create: the matching tests

- [ ] **Step 1: Write the failing tests**

Storage is idempotent on tool, person and day. One tool failing does not stop the others. A
credential marked for tool ingestion is never usable to send traffic.

- [ ] **Step 2: Build it, reusing the provider runner's shape**

Same scheduling, same single-replica guard, same sync-run history, so the Sync History tab
works for tools with no new machinery.

- [ ] **Step 3: Prove it live against the running proxy with no credentials configured**

Every tool must report not configured, cleanly, and no run may raise. That is the state a
customer without accounts is in, and it has to be correct.

- [ ] **Step 4: Commit**

---

## Task 6: The User Tools data source page

**Files:**
- Create: `litellm/proxy/management_endpoints/tool_connections.py`
- Create: `ui/litellm-dashboard/src/app/(dashboard)/user-tools/` with the page and its components
- Modify: `leftnav.tsx`, `migratedPages.ts`, `leftnav.test.tsx` in one commit

- [ ] **Step 1: Write the failing tests**

One tab per tool with Connection, What We Fetch and Sync History, mirroring Provider APIs. The
same Test connection button, the same never-run-against-a-real-account badge derived from
stored rows, and the same rule that a failure shows the tool's own words.

- [ ] **Step 2: Build it, reusing the provider components where they already fit**

- [ ] **Step 3: Say on the page what each tool can and cannot tell us**

Copilot reports no cost. Claude Code on an API account is already counted on the Anthropic
bill. Codex publishes nothing. A customer reading this page should learn that without asking.

- [ ] **Step 4: Run the touched tests only, regenerate the API types, commit**

---

## Task 7: Record what is built and what is not

**Files:**
- Modify: `docs/superpowers/specs/2026-09-14-token-iq-product-design.md`, `PROJECT.md`

- [ ] **Step 1: Replace the user tools status with what is actually built**

- [ ] **Step 2: Record the double counting rule and how it is enforced**

- [ ] **Step 3: Record why Codex and ChatGPT are deferred, and where that money is already counted**

- [ ] **Step 4: Say plainly that Phase 4's test is still not met, and what would meet it**

- [ ] **Step 5: Commit**

---

## Self-Review

**1. Spec coverage**

| Spec requirement | Task |
|---|---|
| Claude Code connector | 2 |
| Copilot connector | 4 |
| Cursor connector | 3 |
| ChatGPT and Codex | Deferred with a recorded reason, Task 7 |
| User Tools data source page, one tab per tool | 6 |
| A person's total cost includes their tool usage | 1 and 5 store it; the Users screen already sums seats |
| Tools tab on a user | Out of scope: it displays what a tool reported, and nothing reports yet |

**2. Placeholder scan**

No "TBD". Every deferral names its reason and where the money is instead.

**3. Type consistency**

`ToolUsageFact` is defined once in Task 1 and produced by Tasks 2 and 3. Copilot produces the
existing `Seat` rather than a fourth shape. The `ToolConnector` protocol matches
`BillingConnector` exactly, so Task 5 reuses the provider runner's shape.

**4. The thing a reviewer should check hardest**

That Claude Code spend on an API account cannot reach a total twice. The tag is easy to set and
easy to ignore, and the failure is silent: every screen keeps working and one large number is
quietly wrong. The reviewer should confirm the tag is set from `customer_type` and not from
anything else, and that no sum anywhere adds a tagged row.
