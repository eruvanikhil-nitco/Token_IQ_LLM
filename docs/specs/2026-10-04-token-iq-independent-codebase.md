# Token IQ: independent codebase, restructure and product clarity

Spec for the whole programme. Each phase below becomes its own plan file under
`docs/plans/`, and each plan breaks into tasks. This document is the shared contract those
plans are written against: it fixes the goal, the verified facts, the scope of each phase and
what "done" means, so no plan has to re-decide any of it

Source: `TOKEN_IQ_RESTRUCTURE (1).md` at the repository root, written by the project owner on
4 Oct 2026. This spec carries that document forward, corrects three factual errors in it, and
adds eleven things it leaves unassigned. Section 4 lists every departure, so the owner can
see exactly where this spec disagrees with theirs

## 1. Goal

Token IQ stops being a fork of LiteLLM and becomes a codebase of its own, carrying no trace
of the name it grew out of except the attribution its licence requires. Along the way the
product stops reading like a database with a web page on it, and starts explaining itself to
the person paying for it

Three outcomes, in priority order:

1. **Legally clean and self-sufficient.** Nothing is downloaded from upstream at runtime, no
   customer-visible string names LiteLLM, and the MIT attribution is correct and permanent
2. **Smaller and owned.** Features Token IQ does not use are gone, and every data file,
   workflow and process that upstream used to maintain has a named owner here
3. **Understandable.** A person who has never seen the product can open any page and learn
   what they spent, whether it is right, and what to do about it

Outcome 3 is the one the owner raised most recently and the one the source document leaves
unassigned. Section 5.7 gives it a phase

## 2. Decisions this programme carries out

Decided by the project owner on 4 Oct 2026. Phase 1 writes them as decision records

1. **Token IQ becomes an independent codebase.** The fork is disconnected and upstream is
   never merged again. This reverses `docs/decisions/0021-client-facing-rebrand.md`, which kept
   `litellm` identifiers specifically so upstream merges stayed possible
2. **No `litellm` name anywhere in the product**, covering package, module, class and
   function names, commands, environment variables, config keys, HTTP headers, metric names,
   database tables, Docker images, folders, UI text and logs. The only exceptions are the
   licence and attribution text, historical decision records and the changelog, and one
   temporary compatibility module that is deleted a release later
3. **The MIT licence obligation is permanent.** LiteLLM is MIT-licensed, so the original
   copyright notice and licence text must stay with the software. `LICENSE` keeps BerriAI's
   copyright line and gains a NITCO line, and a `NOTICE` file states that Token IQ includes
   code derived from LiteLLM. This is legal text, never branding, and no customer sees it in
   the product. It is never deleted
4. **Remove before renaming.** Unused upstream features are deleted before the large rename,
   so no effort is spent renaming code that is about to go
5. **Rename in layers, with one transition release.** Environment variables, config keys,
   request headers and database tables change in stages, so a running installation keeps
   working while its operator moves to the new names

### Target names

| Today | New name |
|---|---|
| Python package `litellm` | `token_iq.gateway` |
| Token IQ modules (`litellm/provider_billing`, `ledger`, and the rest) | `token_iq.<module>` |
| Distribution `litellm` | `token-iq` |
| `litellm-proxy-extras` | `token-iq-migrations`, package `token_iq_migrations` |
| Commands `litellm`, `litellm-proxy`, `lite` | `token-iq`, `token-iq-cli` |
| `LITELLM_*` environment variables | `TOKEN_IQ_*` |
| `litellm_settings`, `litellm_params` | `gateway_settings`, `model_params` |
| `x-litellm-*` headers | `x-token-iq-*` |
| `litellm_*` Prometheus metrics | `token_iq_*` |
| `LiteLLM_*` Prisma models (85) | prefix dropped, then snake_case tables in a later release |
| Redis and cache prefixes | `token_iq…` |
| `LiteLLMRoutes`, `litellm_logging`, `litellm_core_utils` | `GatewayRoutes`, `gateway_logging`, `core_utils` |
| `ui/litellm-dashboard/` | `ui/dashboard/` |
| `tests/test_litellm/` | `tests/gateway/` |

### Naming conventions for everything new

| Where | Convention | Example |
|---|---|---|
| Product name in UI, docs, email | Token IQ, two words | "Token IQ API" |
| Python | `token_iq` package, snake_case modules, `TokenIq…` classes, `TOKEN_IQ_` env vars | `token_iq/connectors/billing/openai.py` |
| UI folders, URLs, CSS, Terraform, headers, images | kebab-case | `src/token-iq/`, `x-token-iq-project` |
| Tests | mirror the package path | `tests/token_iq/connectors/billing/test_openai.py` |
| Specs and plans | `YYYY-MM-DD-kebab-slug.md` | `2026-10-04-token-iq-independent-codebase.md` |
| Decision records | `NNNN-kebab-slug.md` | `0022-independent-codebase.md` |
| API routers | plural resource name, no `_endpoints` suffix | `projects.py` |
| Courier mode | the UI says "Pass-through mode" | |

## 3. Facts, measured on 4 Oct 2026 at commit `353edcc`

Everything in this section was measured, not quoted. Where it disagrees with the source
document, the source document is wrong and section 4 says so

| Fact | Value | How it was measured |
|---|---|---|
| Occurrences of `litellm`, any case | **143,494 across 6,153 files** | `rg -i -c litellm` excluding `node_modules` and the committed UI bundle |
| Prisma models | 85, **all** prefixed `LiteLLM_` | `grep -c "^model LiteLLM_" schema.prisma` |
| Copies of `schema.prisma` in the repo | 3 (root, `litellm/proxy/`, `litellm-proxy-extras/`) | `find . -name schema.prisma` outside the venv |
| Runtime downloads from upstream | 4, at `litellm/__init__.py` lines 417, 421, 425, 429 | read directly |
| Token IQ test files in no CI job | **41** | `.github/scripts/assert_ci_coverage.py` |
| Files authored for Token IQ | 434 | `git log --author --diff-filter=A`, excluding the UI bundle |
| Committed prebuilt UI bundle | **1,016 tracked files** under `litellm/proxy/_experimental/out` | `git ls-files` |

Three defects carried from the source document, all still present:

- 41 Token IQ test files run in no CI job, so `assert_ci_coverage.py` fails
- `provider_billing/openai.py` lines 62 to 73 store the billing `line_item` in the `model`
  field, so a meter name is recorded as if it were a model
- `provider_billing/bedrock.py` lines 120 and 171 require long-lived static access keys

## 4. Where this spec departs from the source document

The owner asked for anything missed to be caught. These are the departures. Three are
corrections, eleven are additions

### 4.1 Corrections

**C1. The rename is a third of the stated size.** The source document says 521,641
occurrences across 5,513 files, taken from `docs/decisions/21`. Measured today it is 143,494
across 6,153 files. The larger figure almost certainly counted `node_modules`. This matters
because a plan sized against a 3.6x overestimate schedules the wrong amount of time and
tempts whoever runs it into shortcuts

**C2. The quality budgets do not key on paths.** Phase 6 of the source document says the
`*-budget.json` files "key on paths" and will need updating when tests move. They do not.
All four key on rule codes (`ANN001`, `LIT001`, `reportAny`, `TQ001`). Moving files does not
break them. What *does* break is covered in A1 below, and the source document misses it

**C3. The two source files carry download suffixes.** They are on disk as
`TOKEN_IQ_RESTRUCTURE (1).md` and `docs/product/tokeniq-blueprint (1).html`, and the
blueprint sits in `docs/Product/` with a capital P, untracked. Spaces and parentheses in
paths break shell scripts, and the folder case will differ between this Windows checkout and
Linux CI. Both files must be renamed and committed in phase 1 before anything references them

### 4.2 Additions

**A1. The quality gates would silently skip the new package.** `scripts/ruff_strict_gate.py`
and `scripts/type_discipline_gate.py` both hardcode `TARGET = "litellm"`, and
`pyrightconfig.json` has `include: ["litellm"]`. The moment phase 3 creates `token_iq/`,
every Token IQ module leaves type checking and both lint budgets, and nothing fails to say
so. The source document remembers pyright and the Makefile but not the two gate scripts.
Phase 3 must add `token_iq` to all four, and must prove it by planting a violation and
watching a gate catch it

**A2. No phase owns making the product understandable.** Section 12 of the source document
says product changes happen "after phase 4" but assigns them no phase, no acceptance
criteria and no place in the ordering. This is the owner's most recent and most strongly
expressed concern. Section 5.7 of this spec makes it phase 5A

**A3. The blueprint is 335KB of HTML and nothing extracts it.** The page model
(`TIQ_PAGES`, `TIQ_MATRIX`, `TIQ_MODALS`) is the actual specification for pages, tabs, roles
and dialogs, and it is trapped inside a `<script>` tag. It must be extracted into committed
JSON that code and tests can read, otherwise every page gets built from somebody squinting at
a mockup

**A4. A bulk codemod destroys git blame.** The repo already keeps `.git-blame-ignore-revs`.
Every mechanical rename commit in phases 6 to 9 must be appended to it in the same commit
that creates it, or the history of 6,000 files becomes unreadable

**A5. The committed UI bundle must be excluded from every codemod and rebuilt after the UI
move.** 1,016 tracked files under `litellm/proxy/_experimental/out` are build output, not
source. A rename pass over them corrupts a build artifact; worse, they are what the proxy
actually serves, so a stale bundle makes correct source look broken. This already happened
once in this repository on 30 Sep. Every rename phase excludes that path, and phase 9 ends
by rebuilding the bundle and committing it

**A6. Deletion authority is split between two phases.** Phase 2 deletes the auto-router
presets, the blog feed and roughly twenty workflows. Phase 5 deletes unused features but only
after the owner approves the phase 0 inventory. So phase 2 deletes things before that
approval exists. Either phase 2's deletions join the inventory, or the spec states plainly
that they are pre-approved. This spec states they are pre-approved, and lists them

**A7. No phase has a rollback.** Only phase 8 step 2 mentions one. Every phase that changes
a running installation needs a stated way back, even if the answer is "revert the pull
request"

**A8. The e2e Playwright suite is unaccounted for.** `tests/e2e/ui/` runs against a live
proxy with its own config, its own `node_modules` and its own `package.json`. Phases 3, 4, 6
and 9 all move things it depends on. It appears in no phase

**A9. The branch strategy contradicts a standing instruction.** The source document asks for
one branch and one pull request per phase. The owner's standing rule is one branch for all
new work, never touching `main`. These cannot both hold. Section 6.1 proposes a resolution
and flags it as an owner decision

**A10. The named owners are never named.** The price owner (6.2), the security advisory
owner (P2) and the provider API owner (P3) are all "named in `docs/status.md`", and nobody is
named. A process with no name attached is not a process

**A11. The two connector defects have no phase.** The OpenAI line-item bug and the Bedrock
static-key requirement appear under "fixes to make along the way" with no phase, no owner and
no ordering. They are real data-correctness bugs: the OpenAI one records a meter name in the
model column, which corrupts every per-model figure for that provider. Section 5.9 gives them
a phase of their own

## 5. The phases

Each becomes one plan file. Acceptance criteria are what the plan's final task verifies

### 5.0 Phase 0: baseline and inventory

No code changes. Establishes the "before" so every later phase can prove it changed nothing
it did not mean to

Deliverables:

- A recorded baseline: Token IQ tests, the full unit suite once, `assert_ci_coverage.py`,
  lint, the UI build and tests, the Docker build. Every test that already fails is written
  down, because those are not ours to fix
- Name counts for occurrences, environment variables, headers and metrics, used as the
  progress measure for phases 6 to 9
- `docs/plans/2026-10-04-feature-usage-inventory.md`: one row per top-level folder in
  `litellm/` and `litellm/proxy/`, saying what it does, whether Token IQ uses it with
  evidence, and a proposal of keep, delete or unsure

Evidence of use means an import chain from a Token IQ module or from a proxy path Token IQ
serves, a config that enables it, or a UI page that calls it. An absence of evidence is
recorded as unsure, never as delete

Acceptance: the baseline is reproducible and the inventory covers every folder with no blanks.
**The owner reviews and approves the inventory before phase 5 runs**

### 5.1 Phase 1: decisions, licence and documentation

Documentation only, no code

Deliverables: decision records `0022-independent-codebase.md` and `0023-remove-litellm-names.md`,
a superseded note on `0021`, the corrected `LICENSE` and the new `NOTICE`, the documentation
moves into `docs/`, a documentation index with a glossary, a rewritten `CLAUDE.md`, and the
two `(1)` files renamed and committed (C3)

The glossary covers observer-only, pass-through mode, virtual key, provider usage fact,
evidence level, attribution and seat, because every one of those appears in the UI and none
is self-explanatory

Acceptance: `rg -n "docs/decisions/|docs|PROJECT\.md"` outside `docs/plans/` and
`docs/decisions/` returns nothing, and no path in the repository contains a space or a
parenthesis

Rollback: revert the pull request. Nothing executable changed

### 5.2 Phase 2: disconnect from upstream

Upstream supplied more than code. It kept data files current, answered runtime downloads,
hosted the documentation that error messages link to, published the image the Helm chart
pulls, and bumped dependencies. Each needs an owner here or deliberate deletion

Four runtime downloads: model prices (which is every price Token IQ uses), the Anthropic
beta-header config, auto-router presets and the LiteLLM blog feed. The first two become
bundled files refreshed by a reviewed job, the last two are deleted with their features

The price pipeline is the substantial piece. Prices must be current within a day, every
change traceable, and a past month re-priceable at the prices of that month. That means a
bundled `data/pricing/model_prices.json` that the runtime reads and never fetches, an
append-only `price_history.jsonl` loaded into a `ModelPriceHistory` table, and a daily job
that opens a pull request sorting upstream's changes into additions that auto-merge, changes
that need a named reviewer, and removals that are marked retired rather than deleted. A
change above 50 percent, a change to zero, or a change to a model seen in recent production
traffic is always flagged

The product then checks its own prices: invoice reconciliation already compares gateway-priced
cost against provider-billed cost, so a model whose variance stays above 2 percent for seven
days raises an alert that its list price may be wrong

Pre-approved deletions (A6): auto-router presets, the blog feed and its UI panel, BerriAI
issue-triage and branch-upkeep workflows, upstream release and publishing workflows, the
install scripts that curl from BerriAI, upstream's own maintenance scripts, and the data
files `cost.json` and `blog_posts.json`

Acceptance: with outbound network blocked except to configured providers, the proxy starts
and prices load from the bundled file, proven by a socket-blocking test and a container run
with restricted networking. The upstream-reference search returns nothing outside the allowed
files. The price job runs once in dry-run and produces a correct pull request against a
fixture

Rollback: revert the pull request. The bundled price file is additive, so reverting restores
the remote fetch

### 5.3 Phase 3: one package for Token IQ's modules

Create `token_iq/` and move Token IQ's own code into it with `git mv`: billing and tool
connectors into `connectors/`, the ledger, attribution, overview, seats and recommendations
modules, eleven repositories, sixteen API routers into `api/`, the proxy hooks, and the types

About 38 import lines across 11 upstream files change, plus 76 test and script files holding
73 `mock.patch` strings. Patch strings are the dangerous ones: they are plain text, so a
missed one does not fail to import, it silently patches nothing and the test passes while
testing less than it claims

If `token_iq/types/team_api_access.py` importing `litellm.proxy._types` creates a cycle,
leave that one file where it is, record it, and let phase 6 resolve it. Do not invent an
abstraction to break the cycle

**This phase must also add `token_iq` to `pyrightconfig.json`, both gate scripts and the
Makefile targets (A1), and prove each one by planting a violation and watching it fail**

Acceptance: the path searches return nothing, `import token_iq` works in a non-editable
install and inside the Docker image, and a planted type error and a planted lint violation
are each caught

Rollback: revert. The moves are pure `git mv` with no behaviour change

### 5.4 Phase 4: tests mirror the package, and CI runs them

Move the Token IQ tests into `tests/token_iq/` mirroring the package, and add a CI shard that
runs them

The subtle part is shared fixtures. Pytest finds fixtures and hook functions by name in a
conftest, so the new conftests must re-export everything from the old ones, including the
autouse isolation fixtures, the `pytest_runtest_setup` and `pytest_runtest_teardown` pair, and
underscore-prefixed names which need explicit imports. A missing re-export does not error, it
removes isolation between tests, which shows up later as a flake nobody can reproduce

Acceptance: `assert_ci_coverage.py` exits 0 for the first time, and `pytest tests/token_iq`
passes with and without `-n 4`, matching the phase 0 baseline

### 5.5 Phase 5: delete what Token IQ does not use

Runs only after the owner approves the phase 0 inventory

Keep: the proxy, auth, virtual keys, teams, users, organizations, budgets, rate limits, spend
tracking, pass-through endpoints, the OpenAI-compatible endpoint, AWS secret management, the
Prisma client and migrations, the UI pages Token IQ shows, and the provider transformations
for supported providers

Delete, subject to the inventory: routing and its load balancing, fallbacks, cooldowns and
response caching, all already switched off by earlier decisions; agents and A2A; MCP;
guardrails and policies if unused; RAG and vector stores; skills, prompt management and
evals; the realtime, video, image, OCR, search and rerank APIs; fine-tuning, sandbox and
compression; provider folders for unsupported providers; playgrounds; the cookbook and
examples; the root `gateway/` and `backend/` entrypoints; unused Terraform; and the Rust
bridge, which is optional and whose removal lets the build backend drop from maturin to
hatchling

One feature per commit, each followed by an import check and the remaining tests. If
something still imports a deleted module, keep the feature and record why. **No Prisma model
or migration is deleted in this phase**; unused tables are phase 8's problem

Acceptance: all phase checks pass and the file-count reduction is recorded

Rollback: each feature is its own commit, so any single deletion can be reverted alone

### 5.6 Phase 5A: make the product understandable

This phase does not exist in the source document (A2). It is added because the owner's
standing complaint is that the pages are data dumps that cannot be understood by walking
through them, and because every later phase is a rename that would otherwise have to be
redone over whatever this phase changes

It runs after phase 5 so no effort goes into a page about to be deleted, and before phase 6
so the rename passes over the final shape of the UI

Deliverables:

- The blueprint's page model extracted from HTML into committed JSON (A3), with the pages,
  tabs, per-role access, dialogs and help text it defines
- Every analytics screen rebuilt to lead with a plain sentence stating what the figures mean
  and what to do about them, then the figures, then the evidence. Today they lead with
  controls and bury the meaning in footnotes
- The nested tab levels on Usage collapsed. It currently stacks three rows of tabs and
  carries two date controls that disagree with each other, so switching tab silently changes
  the period being looked at
- Empty states that explain why they are empty and offer the action that fills them. The
  Ledger's reconciliation tab currently says "no bill entered" and gives no way to enter one,
  while the form that does it sits in a different tab
- Pages that open on a source that has data rather than on an alphabetically first one that
  has none
- Identifiers replaced by names. The cost explorer currently labels rows with raw team UUIDs

Acceptance: a reader who has not seen the product can state, for each screen, what it is
telling them and what they would do next. The figures a screen presents as a sum must
reconcile on screen. Per-screen acceptance comes from the extracted page model, not from
taste

Open question for the owner: whether this phase also replaces the inherited LiteLLM usage
dashboard embedded in Usage, which is a different product's interface with its own controls,
its own date range and a chat box. Section 7 carries this as a decision to make

### 5.7 Phase 6: rename the engine package

A reviewed `docs/plans/rename-map.csv` first, then one scripted libcst pass, then the
remainder by hand. The codemod script is committed

`litellm` becomes `token_iq.gateway` by moving the folder. Subpackages keep their names.
Redundant prefixes drop, so `litellm_core_utils` becomes `core_utils`. Identifiers containing
the name take `Gateway` or `gateway`, except `litellm_params` and `litellm_settings` which
become `model_params` and `gateway_settings`

Environment variables, config keys, headers, metric names, Redis keys and database names are
explicitly **not** touched here. They are phases 7 to 9, because each needs a compatibility
story and the package rename does not

Two traps. Strings that are an external provider's own API field names must be left alone
even when they say litellm, so each string match is reviewed rather than swept. And the
committed UI bundle is excluded from the codemod entirely (A5)

The rename commits are appended to `.git-blame-ignore-revs` (A4)

Acceptance: `rg -n "\blitellm\b" --type py` matches only the names reserved for phases 7 to 9

### 5.8 Phase 7: compatibility for one transition release

A customer's running configuration must survive the upgrade. One module,
`token_iq/gateway/compat.py`, is the only Python file allowed to hold the old names, and it
is deleted a release later

New names are read first; old ones still work and log a deprecation warning once per name.
This covers environment variables, config keys in both the file and the database, and request
headers, where only the new names are sent in responses. About 445 direct `os.getenv` calls
route through one helper instead

`CHANGELOG.md` gains an "Upgrading" section listing every renamed variable, key and header,
generated from the rename map rather than written by hand

Acceptance: one test starts the proxy with an old-style `.env` and `config.yaml` and confirms
it works and warns; a second does the same with new names and confirms no warning

### 5.9 Phase 8: database names, in two releases

**Step 1, this release: code names only, no data change.** Rename the 85 models in all three
`schema.prisma` copies, which must stay byte-identical, and add `@@map` so the real tables are
untouched. Update every Prisma accessor and every raw SQL string naming a table. Rename the
migrations package. **Existing migration folders are never renamed**, because Prisma tracks
them by name in `_prisma_migrations`

**Step 2, a later release, after a backup: the real table names.** One migration renaming
each table to snake_case with its indexes, constraints and sequences, then the `@@map` lines
come out. This needs a runbook covering backup, maintenance window and rollback, a rehearsal
against a copy of a real installation's database, and the owner's approval before merge

This is the only phase that can lose data, so it is the only one with a mandatory rehearsal

### 5.10 Phase 9: everything else that carries the name

Prometheus metrics, which breaks existing dashboards and alerts so they are listed in the
changelog and any in-repo dashboards are updated. Redis and cache prefixes, where in-flight
cache entries are lost harmlessly but any spend or rate-limit counters held in Redis must be
flushed to the database before upgrading. Logger names and OpenTelemetry service names, while
standard `gen_ai.*` attributes stay as they are

The UI folder becomes `ui/dashboard/`, Token IQ pages move into a route group that preserves
their URLs, and a folder is moved whole only when every file in it is Token IQ's. Navigation
labels change to the blueprint's

**This phase ends by rebuilding and committing the UI bundle** (A5), and the e2e Playwright
suite is updated in the same pull request (A8)

### 5.11 Phase 10: keep it clean

`tests/repo/test_no_litellm_name.py` fails if the name appears anywhere outside the licence,
the notice, the changelog, the decision records, the historical plans, the compatibility
module and the upstream price script. It runs in CI and replaces the two existing branding
gates, which are then deleted

A release later: delete `compat.py`, shrink the allowlist, and ship step 2 of phase 8

### 5.12 Phase 11: the two connector defects

Added because the source document leaves them unassigned (A11). Separate pull requests, each
with a regression test that fails before the fix

- **OpenAI line items.** Split the billing `line_item` into a model and a meter, so
  "gpt-4.1-2025-04-14, input" records model `gpt-4.1-2025-04-14` and meter `input`. An item
  with no model gets a null model and the item text as the meter. Existing `fact_key` values
  stay stable, or historical facts are orphaned
- **Bedrock credentials.** Add IAM role with external ID through STS AssumeRole as the
  recommended method, keeping static access keys available but marked not recommended

These can run at any point after phase 4. They are listed last only because they are
independent

## 6. Cross-cutting rules

### 6.1 Branches

The source document asks for one branch and one pull request per phase. The owner's standing
instruction is a single branch for all new work, never touching `main` (A9)

Proposed resolution, for the owner to confirm: keep working on `litellm_token_iq` as the
single long-lived branch, and cut one short-lived branch per phase off it, merging back into
it rather than into `main`. That satisfies reviewability without creating the per-feature
branches the owner rejected. `main` stays stale until phase 2 step 1 fast-forwards it

### 6.2 Moves and renames

Use `git mv` so history follows. Create `__init__.py` in every new package folder including
test folders. Anything larger than a few files is renamed by a reviewed map and an applied
script, not by hand, and the script is committed

After any move, update imports, `mock.patch` and `monkeypatch` strings, `importlib` strings,
CI YAML, the Makefile, Dockerfiles, `pyproject.toml`, `pyrightconfig.json`, the ruff configs,
the gate scripts, Helm, Terraform, doc links and comments citing paths

### 6.3 Behaviour

Behaviour does not change except where a phase says so. No new features during this work,
with the single exception of phase 5A, which exists precisely to change the product surface
and is scoped accordingly

### 6.4 Stop and ask when

A phase would delete a database column or table, a phase would break a running installation's
configuration, or a circular import cannot be resolved by the move itself. Report the
evidence rather than working around it

### 6.5 Checks every phase passes

| Check | Command |
|---|---|
| Python tests for touched areas | `uv run pytest <paths> -q`, matching the phase 0 baseline |
| CI coverage guard | `python .github/scripts/assert_ci_coverage.py` |
| Lint and types | `make lint` |
| Proxy starts | start it, call `/health/liveliness`, open Overview |
| UI | `npm run build && npx vitest run && npm run lint` in the dashboard folder |
| Image | `docker build .`, then the image starts |

### 6.6 Status

After each phase, `docs/status.md` records what changed, what was left and why

## 7. Decisions the owner still has to make

1. **The branch strategy** in 6.1, where the source document and the standing instruction
   conflict
2. **Whether phase 5A replaces the embedded LiteLLM usage dashboard** inside Usage, or leaves
   it until phase 9 renames it in place
3. **Who owns prices, security advisories and provider API changes** (A10). Three names
4. **Whether Helm survives**, given the 30 Sep decision to deploy on AWS ECS with Terraform.
   If it does not, phase 2 deletes it rather than repointing it at a Token IQ registry
5. **The supported provider list**, which decides what phase 5 deletes from `litellm/llms/`.
   Current evidence says at least OpenAI, Azure OpenAI and Azure AI, Anthropic, Bedrock,
   Vertex AI and Gemini, and OpenRouter

## 8. Definition of done

- [ ] Decision records 0022 and 0023 written; `LICENSE` and `NOTICE` satisfy MIT attribution
- [ ] Every dependency-register row closed; no runtime call leaves for upstream, proven with
      networking restricted
- [ ] Prices load from the bundled file; the daily job opens pull requests; additions
      auto-merge and changes are reviewed; past periods re-price from history
- [ ] Renovate or Dependabot active; owners named for security advisories and provider
      changes
- [ ] Unused upstream features deleted, as approved in the inventory
- [ ] `token_iq` is inside pyright, both lint gates and the Makefile, proven by planted
      violations
- [ ] Every page states what its figures mean and what to do next; sums reconcile on screen
- [ ] `tests/repo/test_no_litellm_name.py` passes in CI with the allowlist no larger than
      phase 10 permits
- [ ] An installation configured with `LITELLM_*` names upgrades, works and warns;
      `CHANGELOG.md` lists every rename
- [ ] `assert_ci_coverage.py` passes; Token IQ and gateway tests match the baseline
- [ ] The image builds and starts, Overview loads, and a request through the gateway is
      recorded
- [ ] The OpenAI line-item and Bedrock credential defects are fixed with regression tests
- [ ] `docs/status.md` records what was done, what was deferred and why
