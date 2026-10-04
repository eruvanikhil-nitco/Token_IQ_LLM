# API Documentation Branding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop the API a customer reads from naming LiteLLM, linking to LiteLLM's documentation, or showing a stranger's email address.

**Architecture:** No behaviour changes. Every fix is prose in an endpoint docstring or a Pydantic `description=`, both of which FastAPI renders into `/openapi.json`, the `/docs` page and the dashboard's own API Reference screen. A gate reads the generated schema rather than the source, because the schema is what a customer sees and is the only place that catches prose arriving from a docstring, a field, an example and a title alike.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, pytest

**Spec:** `docs/superpowers/specs/2026-09-14-token-iq-product-design.md`, Phase 0

## Why this plan exists when Phase 0 already had two

Both earlier Phase 0 plans are finished, though nobody ticked their boxes. Verified on
2026-09-30: the Token IQ plan module exists and `/health/license` reports it, the LiteLLM
licence client and the metering package are gone, the Dockerfiles no longer copy the deleted
enterprise folder and a gate keeps it that way, the Logs page Audit Logs tab renders the
working audit trail, and the audit endpoint refuses anyone who is not a proxy admin.

The existing branding gate passes, and it is not wrong; it is narrow. It inspects string
literals assigned to `detail`, `message`, `exceeded_message`, `event_message` or an `"error"`
key, which is exactly the set of *error messages* it was written for. Documentation prose was
never in scope.

Measured against the live proxy on 2026-09-30, `/openapi.json` contains:

| Leak | Count | Where |
|---|---|---|
| The word LiteLLM | 274 | 131 endpoint descriptions, 21 field descriptions, the rest schema names |
| `docs.litellm.ai` links | 125, across 37 distinct URLs | endpoint descriptions |
| `berri.ai` addresses | 10 | example values in descriptions |

A customer opening API Reference reads all of it.

## The decision this plan does not take

Roughly 110 schema references and 32 schema titles are class names such as `LiteLLMKeyType`
and `SearchToolLiteLLMParams`. Renaming them is a different kind of change from rewriting
prose: it alters the public schema, regenerates the dashboard's `schema.d.ts`, and breaks any
client that generated types from an earlier version.

So this plan rewrites prose only, and records the naming question as open. Prose is what a
human actually reads, it carries every link and every stranger's address, and it can be fixed
today with no risk to a client.

## Global Constraints

- Prose only. No endpoint changes its path, parameters, status codes or behaviour
- No invented URLs. Token IQ's public documentation address is not decided, so a link to
  LiteLLM's docs is removed and the sentence explaining the feature is kept or rewritten to
  stand on its own. A dead link to a page we have not written would be worse than none
- No real person's address anywhere a customer can read. Example addresses use `example.com`
- Nothing is copied or adapted from LiteLLM enterprise code
- The gate reads the generated schema, not the source, because that is what a customer sees
- Existing exemptions stay exempt for their stated reasons: sample code a customer copies and
  edits, and the site URL defaults that need an address nobody has chosen
- New code annotates variables `Final` and carries no comments beyond genuinely complex logic
- Python line length 120. Tests check behaviour, not structure

---

## Task 1: A gate that reads what the customer reads

**Files:**
- Create: `tests/code_coverage_tests/check_openapi_docs_do_not_name_litellm.py`

- [x] **Step 1: Write the check, and watch it fail against today's schema**

It builds the FastAPI app, generates the schema, walks every `description`, `title`, `summary`
and example string, and fails naming each offender. Building the app rather than reading a
saved file means the gate cannot go stale.

- [x] **Step 2: Record the count it starts from**

The first run states the number. That number only ever goes down, which is what makes the
gate a ratchet rather than a wish.

- [x] **Step 3: Commit the gate, failing, with the count in the message**

---

## Task 2: Endpoint descriptions stop naming LiteLLM and stop linking to its docs

**Files:**
- Modify: the endpoint docstrings the gate names

- [x] **Step 1: Replace the product name**

An endpoint that says what LiteLLM does says what Token IQ does, or more often says what the
endpoint does without naming a product at all, which reads better anyway.

- [x] **Step 2: Remove every `docs.litellm.ai` link, keeping the explanation**

Thirty-seven distinct URLs. Where the link carried the whole explanation, the sentence is
rewritten so it stands alone, because a customer following a link to a competitor's
documentation is worse than a customer reading one clear sentence.

- [x] **Step 3: Run the gate and the proxy's own test suite**

The suite matters here: several tests assert on endpoint descriptions.

- [x] **Step 4: Commit**

---

## Task 3: Field descriptions and examples

**Files:**
- Modify: the Pydantic `description=` strings the gate names, and the example values

- [x] **Step 1: Replace the product name in field descriptions**

- [x] **Step 2: Replace every example address with one at `example.com`**

Ten of them are real addresses belonging to people at another company. Showing a stranger's
address to our customers as an example is a mistake regardless of branding.

- [x] **Step 3: Run the gate and the touched tests, then commit**

---

## Task 4: The last message that describes someone else's packaging

**Files:**
- Modify: `litellm/proxy/_types.py`

- [x] **Step 1: Rewrite `missing_enterprise_package_docker`**

It currently reads "This uses the enterprise folder - only available on the Docker image",
which describes LiteLLM's packaging model rather than ours. The enterprise folder does not
exist in this product.

- [x] **Step 2: Run the touched tests and commit**

---

## Task 5: Say where Phase 0 actually stands

**Files:**
- Modify: `docs/superpowers/specs/2026-09-14-token-iq-product-design.md`, `PROJECT.md`, and the
  two earlier Phase 0 plans

- [x] **Step 1: Mark the two earlier Phase 0 plans complete, with what was verified and when**

- [x] **Step 2: Record the schema naming question as open, with the tradeoff**

- [x] **Step 3: State what is left in Phase 0 after this plan**

The deployment pipeline, which waits on the choice of cloud provider and is the only thing
between this product and a customer installation.

- [x] **Step 4: Commit**

---

## Self-Review

**1. Spec coverage**

| Spec requirement | Task |
|---|---|
| Rebranding of remaining customer-visible LiteLLM text | Tasks 2, 3 and 4 |
| Token IQ plan system replacing the licence key | Already done, verified in Task 5 |
| Audit Logs tab on the working trail, admin only | Already done, verified in Task 5 |
| Images build from a clean checkout | Already done, verified in Task 5 |
| Deployment pipeline | Out of scope: waits on the cloud provider choice |

**2. Placeholder scan**

No "TBD". The one thing deliberately not done, renaming schema classes, has its reason and its
tradeoff written down.

**3. Type consistency**

No types change. The gate returns an exit code and a list of offenders, nothing else.

**4. The thing a reviewer should check hardest**

That no link was replaced with an invented Token IQ URL. A dead link in a customer's API
reference is worse than the honest absence of one, and it is the easiest thing to do by
accident while removing thirty-seven of them.

---

## Whole-plan review, 2026-09-30

All five tasks are done and both branding gates pass. The API documentation went from 328
offending pieces of prose to none.

Three things went wrong on the way and each is worth keeping, because each would have shipped
silently.

The first rewrite collapsed runs of spaces as a tidy-up, which destroyed the indentation that
FastAPI renders as a code block. The second ate the newline after a removed link, merging two
bullet lines into one. The third, and the worst, re-emitted each docstring from its parsed
value, which joined every line of every curl example: Python consumes a backslash-newline
continuation before `ast` ever hands the value over, so the round trip was lossy. The fix was
to edit the raw source between the quotes and never the parsed value. All three were caught by
reading the diff rather than by a test, which is the argument for reading diffs.

The gate itself needed four rounds of narrowing before it described only what it claims to
cover. It started by flagging auto-generated titles, then database tables, then header names
and dotted setting names, then a quoted default value. Each exclusion is now a named test,
because an exclusion slightly too broad makes a gate pass on an empty set and look like
success.

The largest single discovery was that a third of the schema does not come from live source at
all. Lazily-loaded features serve their documentation from a committed snapshot file, so the
source can be clean while the customer still reads the old text. Regenerating that snapshot is
part of the work, and anyone changing an endpoint description in a lazy feature has to do it.

Phase 0 now has one item left, the deployment pipeline, and it waits on a decision rather than
on any code.
