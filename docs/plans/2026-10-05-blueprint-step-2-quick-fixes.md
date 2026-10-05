# Blueprint step 2: the quick fixes

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** the three fixes the blueprint marks "small, do first", done properly rather than quickly.

**Source:** `docs/product/token-iq-product-blueprint.html` section 13, build step 2, and the
"Three code fixes" entry in its section 12. Read through section 12 of
`docs/plans/2026-10-04-independent-codebase.md`, which says to treat the blueprint as a
specification and follow its build order.

**Where this sits:** build step 0 is phases 0 to 4 of the codebase programme, which are done.
Step 1, the Data Sources page and connect flow, is marked "designed" rather than built. Step 2 is
marked "small, do first", so it runs now. Step 3 onward depends on the truth layer.

## One of the three is already done

Blueprint section 12 lists three code fixes. The third is "41 Token IQ test files run in no CI
job; phase 4 of the codebase plan adds them". **Phase 4 closed that**:
`assert_ci_coverage.py` exits 0, 2,602 test files and 10 Dockerfiles each invoked by a job or
carrying an allowlist entry. Nothing to do here beyond not undoing it.

The build-order entry for step 2 names three items, which are the two remaining code fixes plus the
credential split. Those are the three tasks below.

## Facts measured on 5 Oct 2026, in the code

| Fix | What exists | What is missing |
|---|---|---|
| Split billing and forwarding credentials | `token_iq/connectors/billing/credential_purpose.py` has the `billing_ingestion` marker, per-provider required fields and admin-key prefix checks. A separate `provider-apis` page exists | **Nothing filters billing credentials out of the model-credential list.** `BILLING_PURPOSE` appears in the connector, the reconciliation endpoint and the scheduler, and in no credential endpoint or UI panel |
| Bedrock IAM role | `token_iq/connectors/billing/bedrock.py` reads `aws_access_key_id` and `aws_secret_access_key` at lines 120 and 171, and `_BEDROCK_REQUIRED` demands both | No `role_arn`, no `external_id`, no STS assume-role anywhere in the connector |
| Split the OpenAI line item | `token_iq/connectors/billing/openai.py` line 73 sets `model=line_item`, so "gpt-4.1…, input" and "web search tool calls" land in `model`. Line 111 groups the request by `line_item` | `ProviderUsageFact` has no `meter` field. `LiteLLM_ProviderUsageFact` has no `meter` column, in any of the three `schema.prisma` copies |

## The rule this work must not break

**A provider figure says how much was spent. A gateway figure says who spent it. They are never
added together.**

Fix 3 touches a provider figure's shape, not its value. Splitting `model` must leave every
`billed_cost` and every total identical. What changes is how rows group: today "gpt-4.1, input" and
"gpt-4.1, output" are two distinct `model` values, and after the split both are `gpt-4.1` with
different meters. Any screen or rule that groups by model will show fewer, larger rows. The money
must be the same to the digit, and a test has to say so.

## The trap worth the most attention

**Rows already stored keep the combined string, and a migration may not rewrite them.**

Prisma migrations apply at proxy boot before it serves traffic, so a migration must change schema
only: no `UPDATE`, no `DELETE`, no `INSERT ... SELECT`, enforced by
`tests/code_coverage_tests/check_migrations_no_data_rewrites.py`. So the column arrives empty and
every existing row keeps `model = "gpt-4.1, input"` with `meter = NULL`, while new rows get the
split. The same model then appears under two spellings and any grouping double-counts it as two
things.

The way out is not a data migration. **The connector is idempotent on `fact_key`**, which is
`openai:{credential}:{day}:{line_item}`, so re-running the sync over a period rewrites those exact
rows with the split applied. That gives two requirements:

- `fact_key` must keep using the **raw line item**, unsplit. If the key changes, re-ingestion
  inserts new rows beside the old ones instead of replacing them, and the period doubles
- the plan needs a documented re-ingestion step, and a way to tell a half-migrated table from a
  finished one, because a row with `meter = NULL` is ambiguous between "not re-ingested yet" and
  "a line item with no meter part"

## Global Constraints

- Migrations change schema only. All three `schema.prisma` copies stay byte-identical
- `billed_cost` and every total are unchanged by all three fixes, and a test proves it
- No secret is logged, echoed or returned. A credential is never shown back after it is stored
- TDD: the failing test first, every time
- Python line length 120, `: Final`, no `Any`, immutable collections, tagged unions and `match`
- Never run the full vitest suite with no path

---

## Task 1: Keep billing credentials off the model-credential list

**Files:** `litellm/proxy/credential_endpoints/`, `token_iq/policy/credential_access.py`, the UI
credentials panel

- [x] **Step 1: Write the failing test**

A credential stored with `purpose: billing_ingestion` must not appear in the list the model
credential pages read, and must still appear in the list the provider-billing pages read. Both
halves, because a filter that hides it from everything breaks the connect flow.

- [x] **Step 2: Filter in the API, not the browser**

The marker is on `credential_info`. The endpoint decides, so a client that ignores the filter
cannot list them anyway. A browser-side filter leaves the keys in the response and is a disclosure,
not a tidy-up.

- [x] **Step 3: Check what a billing credential discloses when it is listed**

An admin key's name and provider are not secret, but its presence on a model page invites someone
to attach it to a deployment, which is the thing `BILLING_PROVIDERS` exists to prevent. Record what
the list returns for one.

- [x] **Step 4: Commit**

### What task 1 found

The split was further along than the blueprint implies. `billing_ingestion`, the per-provider
required fields, the admin-key prefix checks and the never-return-values rule were all in place.
Only the list was missing, and it was returning the row with its values emptied rather than leaving
it out.

**The server-side half already held.** `model_management_endpoints` refuses to attach a billing
credential to a deployment, and re-checks even when the credential name is unchanged, in case it was
repurposed for billing after being attached. So this change is the organisational half of a defence
that was already there, which is a better position than the blueprint's wording suggests.

Three tests rather than one, because the obvious filter is wrong in two ways: it must not hide the
credential from `by_name`, which the connect flow reads to show a connection's state, and it must not
treat a missing `purpose` key as billing, which would empty the list most of the product depends on.

### One thing left alone

`CredentialsTable` renders a Purpose column with "Billing access (read-only)", which was the interim
way of telling the two kinds apart in one table. With the list filtered it will only ever show "Model
access" from live data. Removing a column is a UI change that needs approval, so it stays, and this
records that it is now vestigial.

---

## Task 2: Bedrock signs in with a role, not a long-lived key

**Files:** `token_iq/connectors/billing/bedrock.py`, `credential_purpose.py`, the connect dialog

- [ ] **Step 1: Write the failing test**

Given a credential carrying `role_arn` and `external_id`, the connector assumes that role and uses
the temporary credentials it returns. Given one carrying only access keys, it still works, because
an installation that already connected must not break on upgrade.

- [ ] **Step 2: Assume the role, with the external id**

The external id is the point: without it, anyone who learns the role ARN can ask AWS to assume it
from their own account. With it, the customer's role trusts Token IQ's principal only when the
matching external id is presented.

- [ ] **Step 3: Make `_BEDROCK_REQUIRED` accept either shape**

Today it demands both access keys, so a role-only credential fails validation before it is tried.
Either shape is valid; neither being present is not.

- [ ] **Step 4: Build the dialog the blueprint specifies, not one of my own**

`TIQ_MODALS.connect.variants.aws` specifies this completely, and an earlier draft of this plan
reduced it to "say which one to use". It is not a pair of text fields. Read from the blueprint at
line 2439 and from the `kind==='role'` renderer at line 2593:

| Variant | Recommended | Shape |
|---|---|---|
| `role` "IAM role" | **yes** | three numbered steps, a read-only **External ID (generated for you)** with a Copy button, a **"Launch template in AWS"** button, then one text field **Role ARN** placeholder `arn:aws:iam::123456789012:role/token-iq-read-only` |
| `keys` "Access keys" | no | Access key ID (text, "Long-lived key. Not recommended.") and Secret access key (password), with help: only if a cross-account role cannot be allowed, use an IAM user with Cost Explorer read-only, rotate every 90 days |

The reassurance copy is specified too: "Nothing secret is stored. Token IQ asks AWS for short-lived
access each time it syncs. Your security team can see and delete the role whenever they like." And:
"Today the Bedrock connector uses long-lived access keys. This replaces them."

Three consequences the one-line step missed:

- **the external ID is generated by Token IQ, not typed by the customer.** It has to be generated
  once per connection and stored, because the role's trust policy is written against that exact
  value and a regenerated id locks the connection out. The example is `tiq-7f3a9c21-kore`, so the
  shape is a `tiq-` prefix, a random component and an installation identifier. **The example's
  suffix is a customer name and must not reach the code**
- **there is a CloudFormation template to launch**, which creates a read-only role trusted only by
  Token IQ with that external id. That template is an artefact this task has to produce, not just a
  button
- **"short-lived access each time it syncs"** is the AssumeRole call in step 2, so the dialog's
  promise and the connector's behaviour are the same requirement seen from two ends

- [ ] **Step 5: Check the provider key, which differs between the two**

The blueprint keys this variant `aws`; `BILLING_PROVIDERS` calls the provider `bedrock`. Whichever
wins, one of the two documents is wrong and this is where it gets reconciled rather than papered
over with a mapping nobody can find later.

- [ ] **Step 6: Commit**

---

## Task 3: Split the OpenAI line item into model and meter

**Files:** `token_iq/types/provider_billing.py`, three `schema.prisma`, a migration,
`token_iq/connectors/billing/openai.py`, `provider_usage_fact_repository.py`

- [ ] **Step 1: Write the failing test for the split itself**

"gpt-4.1-2026-04-14, input" becomes model `gpt-4.1-2026-04-14` and meter `input`. "web search tool
calls" has no model, so model is `None` and meter is the whole string: a tool call is a meter
against no model, and putting it in `model` is what makes the model list unreadable today.

Table-driven, from the line-item shapes OpenAI actually returns, including one that is only a model
with no meter part and one that is neither.

- [ ] **Step 2: Add the field and the column**

`meter: str | None` on `ProviderUsageFact`, a nullable `meter` column on
`LiteLLM_ProviderUsageFact`, and the same change byte-identically in all three `schema.prisma`
copies. Schema only: the column arrives empty and no row is touched.

- [ ] **Step 3: Keep `fact_key` on the raw line item**

It is what makes re-ingestion replace a row rather than add one beside it. A test asserts the key
for a given day and line item is unchanged by this task, because that is the hinge the whole
migration path hangs on.

- [ ] **Step 4: Prove the money did not move**

The same fixture through the old and new code: identical `billed_cost` per row, identical total,
and the set of `(model, meter)` pairs accounting for exactly the rows the old `model` values did.

- [ ] **Step 5: Write down how a deployment finishes the change**

Re-ingest the periods that matter rather than migrating data. The plan states how far back, and how
to tell a row that has not been re-ingested from a line item that genuinely has no meter. Without
that second part, `meter IS NULL` means two different things and no screen can group safely.

- [ ] **Step 6: Commit**

---

## Task 4: Prove it against a running proxy, and hand over

**Files:** `docs/status.md`

- [ ] **Step 1: Curl the real thing**

A live proxy on localhost, a real OpenAI admin key from `.env`, one real sync, and the stored rows
shown with model and meter separated. Commands and output, not a test run, because the proof is
what the customer would see.

- [ ] **Step 2: Record what changed, and what a deployment must do**

- [ ] **Step 3: Commit**

---

## Self-Review

**1. Source coverage**

| Blueprint step 2 item | Task |
|---|---|
| Split billing and forwarding credentials | Task 1 |
| Bedrock IAM role | Task 2 |
| Split OpenAI line items into model and meter | Task 3 |
| 41 test files in no CI job (section 12's third code fix) | Already done in phase 4 |

**2. Placeholder scan**

No "TBD". Every claim about the current state cites the file and line it was read from.

**3. Type consistency**

`ProviderUsageFact` gains an optional field, so no existing reader breaks. `_BEDROCK_REQUIRED`
changes from a tuple of required names to a choice between two shapes, which is a tagged union and
should be written as one rather than as two `if` branches.

**4. The thing a reviewer should check hardest**

`fact_key`, in task 3 step 3.

Everything else in task 3 is visible: a bad split shows up as a wrong model name. If `fact_key`
changes, re-ingestion stops replacing rows and starts adding them, and the period's cost doubles
while every row in it looks individually correct. It is the one change here that produces a wrong
number rather than a wrong label, and the counting rule is what it breaks.

Second hardest: task 2's fallback. An installation that already connected with access keys must
keep working, and a test that only covers the role path would let the upgrade break every existing
Bedrock connection.
