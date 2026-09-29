# Provider Readiness Without Accounts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Get every provider connector to the point where connecting a real account is one click and one credential, with everything that can be proven without an account already proven, and everything that cannot stated plainly rather than assumed.

**Architecture:** Each connector stays a pure fetcher that never raises. Two things change. The vendor's base URL becomes an injected value instead of a module constant, so the real connector can be driven against a server we control. Each connector then gains a contract test that runs the real code over a real `httpx` client, asserts the request we send matches what the vendor documents, and replies with payloads copied from the vendor's own published examples. The probe endpoint that already exists gets a button in the product, so verification the day an account arrives is a click rather than a code change.

**Tech Stack:** Python 3.12, FastAPI, `httpx`, Prisma with Postgres, `prisma-client-py` raw queries, pytest. Dashboard is Next.js with shadcn/Base UI, TanStack Query and vitest.

**Spec:** `docs/superpowers/specs/2026-09-14-token-iq-product-design.md`, sections "Provider API ingestion" and "Data sources", Phase 2

## The problem this plan exists to solve

**Six connectors exist. Five have never sent a single HTTP request to the vendor they were written for.**

Their tests pass, and the tests are worthless in one specific way: every one of them replaces the HTTP client with a `MagicMock` that returns a dictionary we typed out ourselves. Nothing in the suite exercises the URL we build, the query parameters we attach, the authentication header we construct, the pagination link we follow, or what we do with a 401, a 429 or a body that is not the shape we expected. A connector can pass every test it has while pointing at the wrong path with the wrong auth scheme.

This is the same lesson this branch has now learned six times. A query that could not execute, a filter that reported zero, an endpoint that returned 500, a reader that rejected every real row, a cursor that failed on page two, a seat that fell outside its own period: every one of them passed a green suite and died on contact with real infrastructure. The only reason OpenRouter works is that it is the one connector that has met a real server.

An account is still the only thing that can settle whether the vendor's real payload matches the vendor's own documentation. Everything upstream of that can be settled now, and this plan settles it.

## What this plan can prove, and what it cannot

| Question | Provable without an account |
|---|---|
| Do we call the path and method the vendor documents | Yes |
| Do we send the auth header in the scheme the vendor documents | Yes |
| Do we send the date range, granularity and paging parameters correctly | Yes |
| Do we follow pagination to the end rather than stopping at page one | Yes |
| Do we parse the vendor's own published sample response correctly | Yes |
| Do we survive 401, 403, 429, 500 and a malformed body without raising | Yes |
| Do we store what we parsed, idempotently, with money intact | Yes, already covered |
| Does the vendor's real response match the vendor's documentation | **No. Only an account settles this** |
| Does the account have the entitlement the endpoint requires | **No. Only an account settles this** |
| Are the real figures right | **No. Only an account settles this** |

The last three stay open, and Task 5 records them in the product doc as open rather than letting a green suite imply otherwise.

## Global Constraints

- Money is `Decimal` end to end and must never pass through `float`
- A connector never raises. Every failure is a value the runner can record
- No real credential, key or token appears in a test, a fixture, a commit or a log. Fixture credentials are obviously fake
- Sample payloads are copied from the vendor's published documentation and the file says which page they came from, so a reader can check them against the vendor rather than trusting us
- The default base URL stays exactly what it is today. Injection adds an override; it never changes where a connector points unless told
- No customer-visible LiteLLM branding, no company or customer names, no secrets, no `eval`, no `shell=True`
- No `Any` or coarse types, every parameter strongly typed, `: Final` on every variable (LIT010), no parameter rebinding (LIT011), immutable collections. `# mutable-ok: <reason>` only as a genuine last resort with a true reason
- Every suppression names its exact rule in brackets with a reason that is actually true. `# type: ignore` is banned
- No comments except genuinely complex business logic, tool-read suppressions, or TODO/FIXME
- Tests must test function, never structure, and must fail when the behaviour is mutated
- Never remove, merge or rename an existing UI tab
- Python max line length 120. TypeScript has no `any`, no tokens in `localStorage`

---

## Task 1: Make the vendor URL something we can point somewhere else

**Files:**
- Modify: `litellm/provider_billing/anthropic.py`, `openai.py`, `openrouter.py`, `azure.py`, `bedrock.py`, `vertex.py`
- Modify: `tests/test_litellm/provider_billing/test_*_connector.py`

- [ ] **Step 1: Write the failing tests**

One test per connector: constructed with no base URL, it calls the vendor's documented host; constructed with one, it calls that instead and changes nothing else about the request.

- [ ] **Step 2: Make the base URL a constructor value defaulting to today's constant**

Not an environment variable and not a global. An injected value, so a test can hold two connectors pointing at different servers at once, and so a customer on a sovereign cloud or behind a corporate proxy has somewhere to put their host without us shipping a fork.

- [ ] **Step 3: Confirm every existing connector test still passes unchanged**

The default must be byte-identical to the current behaviour. If any existing test needed editing to pass, the default moved and that is a defect, not a test problem.

- [ ] **Step 4: Commit**

---

## Task 2: Drive each connector over real HTTP against a server we control

**Files:**
- Create: `tests/test_litellm/provider_billing/contract/__init__.py`
- Create: `tests/test_litellm/provider_billing/contract/conftest.py`
- Create: `tests/test_litellm/provider_billing/contract/payloads/` (one file per vendor, sourced from their docs)
- Create: `tests/test_litellm/provider_billing/contract/test_<provider>_contract.py` for all six

- [ ] **Step 1: Build the harness**

An `httpx.MockTransport` behind a real `httpx.AsyncClient`, so the connector's own client builds the request, serialises the parameters and handles the status code. The harness records every request it received so a test can assert on the path, the query, the headers and the order of the calls.

Chosen over a real socket server deliberately: a real listener adds ports, races and flakes in CI, and buys only TLS and the socket itself, neither of which is where these bugs live. The request the connector builds is identical either way.

- [ ] **Step 2: For each connector, assert the request contract**

Path and method, the date range in the vendor's format, granularity, page size, and the authentication header in the vendor's scheme, which differs per vendor and is exactly the kind of thing that is wrong until a real server rejects it.

- [ ] **Step 3: For each connector, parse the vendor's own sample response**

Payloads copied from the vendor's published documentation, each file naming its source. Not payloads reverse-engineered from our parser, which would only prove the parser agrees with itself.

- [ ] **Step 4: For each connector, walk pagination to the end**

Two pages then a terminator, asserting both pages reach storage. A connector that silently returns page one looks healthy and under-reports spend forever, which is the worst failure this product can have.

- [ ] **Step 5: For each connector, survive every error the vendor can return**

401, 403, 429, 500, a body that is not JSON, and a body that is JSON of the wrong shape. Each must produce a recorded failure with a reason a human can act on, and must never raise.

- [ ] **Step 6: Mutate and confirm the tests have teeth**

For each connector, break the URL, break the auth header, and stop pagination after page one. Every one of the three must kill a test. A mutation that survives means the test is decorative.

- [ ] **Step 7: Commit**

---

## Task 3: Put the connection test in the product

**Files:**
- Modify: `ui/litellm-dashboard/src/components/networking.tsx`
- Create: `ui/litellm-dashboard/src/app/(dashboard)/hooks/providerApis/useBillingProbe.ts`
- Modify: `ui/litellm-dashboard/src/app/(dashboard)/provider-apis/_components/ConnectionTab.tsx`
- Create: `ui/litellm-dashboard/src/app/(dashboard)/provider-apis/_components/probeResult.ts` and its test

- [ ] **Step 1: Write the failing tests**

A Test connection button per stored credential. While it runs it says so. On success it reports what came back. On failure it reports the reason the probe gave, verbatim, never a generic failure message: the whole value of this button is telling someone which of a wrong key, a missing entitlement or a wrong account is the problem.

- [ ] **Step 2: Wire the existing probe endpoint**

`/provider/billing/probe` already exists and is admin-only. Nothing about the backend needs to change; it has simply never been reachable from the product.

- [ ] **Step 3: Run only the touched tests, regenerate the API types, commit**

---

## Task 4: Say which providers have actually met a real account

**Files:**
- Modify: `litellm/provider_billing/connection_state.py`
- Modify: `litellm/proxy/management_endpoints/provider_reconciliation.py`
- Modify: `ui/litellm-dashboard/src/app/(dashboard)/provider-apis/_components/connectionState.ts` and its test

- [ ] **Step 1: Write the failing tests**

A provider that has never had a successful run storing at least one fact is reported as never verified, and says so on the screen. A provider that has is reported as verified, with the date it first was. The distinction is derived from stored runs, never hardcoded.

- [ ] **Step 2: Build it**

Today the doc carries the sentence "five connectors have never run against a real account", which will be wrong the moment one does and nobody remembers to edit it. The product should answer this from its own data.

- [ ] **Step 3: Run the touched tests, then prove it live**

OpenRouter must read as verified, because it has real facts stored. The other five must read as never verified. Both against the live database, not a fixture.

- [ ] **Step 4: Commit**

---

## Task 5: Record what is ready and what only an account can settle

**Files:**
- Modify: `docs/superpowers/specs/2026-09-14-token-iq-product-design.md`

- [ ] **Step 1: Replace the hardcoded connector status with what the product now reports**

- [ ] **Step 2: Record what the contract tests prove, in the words of the table at the top of this plan**

- [ ] **Step 3: Record the three questions that stay open until an account exists**

- [ ] **Step 4: Record the one-click path from a real credential to a verified provider, so the day an account arrives nobody has to rediscover it**

- [ ] **Step 5: Commit**

---

## Self-Review

**1. Spec coverage**

| Spec requirement | Task |
|---|---|
| Six connectors exist and are ready for a real account | Tasks 1 and 2 |
| A customer can tell whether a provider is actually connected | Tasks 3 and 4 |
| The product states its own limits rather than hiding them | Tasks 4 and 5 |
| Sovereign cloud and proxied hosts have somewhere to point | Task 1, as a side effect |

**2. Placeholder scan**

No "TBD" and no "add error handling": Task 2 Step 5 names the six error cases.

**3. Type consistency**

The base URL is one injected string with one default per connector, set in Task 1 and consumed by every contract test in Task 2. The probe response shape already exists and is unchanged; Task 3 only renders it.

**4. The thing a reviewer should check hardest**

That the sample payloads really came from the vendors and were not written to match our parser. A payload reverse-engineered from our own code proves only that the parser agrees with itself, and it would convert this entire plan into theatre while making the suite look twice as strong. Every payload file names its source, and the reviewer should spot-check at least two against the vendor's live documentation.
