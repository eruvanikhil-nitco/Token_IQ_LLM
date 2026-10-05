# Token IQ, current state

Updated 2026-09-30. This file is the one place to look for where the work stands. Keep it
current at the end of every session rather than rediscovering the answer from git log.

## What we are doing right now

**The Overview landing page is built**, which was the last thing standing between six phases
of backend work and a customer being able to see it. Plan:
`docs/plans/2026-09-30-overview-home-page.md`, all five tasks.

It shows total spend and the change on the period before, how much the gateway can attribute,
how much nobody owns and what share that is, whether each provider's bill matched, the top
recommendations, and when each source last reported. It is in a new HOME group at the top of
the sidebar.

The rule it exists to protect: the headline total is what providers billed plus tool spend on
no provider bill plus seats. The gateway figure is excluded and labelled as attribution, in
words, on the screen. Adding the two would roughly double the number a customer repeats to
their finance team. Checked live: the total reads 0.00780515, the provider figure, and not
that plus the gateway's 0.00797225.

Phase 0 is otherwise complete apart from what needs an AWS account. The provider was chosen
on 2026-09-30: AWS, plain containers on ECS Fargate, shared VPC and Postgres server and load
balancer, with only the container, database, secrets and hostname separate per customer. The
image is built and proved, 1.69 GB from a clean checkout running against real Postgres.
Publishing it, applying Terraform and routing a hostname all wait on the account.

## Two real defects found by this work

Both were invisible to a fully green suite, because every connector test replaced the HTTP
client with a mock that cannot fail the way a real one does.

- Every connector crashed the entire sync run on a body that was not JSON. A vendor serving a
  maintenance page, a proxy returning an HTML error, a gateway truncating a response: any of
  the three stopped every other provider in the same pass. Fixed in `c74098aa6a`
- Anthropic, OpenAI and OpenRouter decoded money through a binary float, so a cost lost digits
  before anything could make a `Decimal` of it. They now share the exact decoder Azure and
  Vertex already used. Fixed in the same commit

## Where each phase stands

- **Phase 0, product readiness.** Done except the deployment pipeline, which waits on the
  cloud provider choice. The licence dependency, the metering, the clean-checkout build, the
  audit trail and the branding are all finished
- **Phase 1, organisation and navigation.** Substantially done. Projects backend complete and
  the sidebar reorganisation landed
- **Phase 2, data sources and provider accounts.** Readiness complete. Only live verification
  against real accounts remains, and that needs accounts
- **Phase 3, combined view and ledger.** Complete and proven against the live database on
  2026-09-29, with the completion test actually run rather than assumed
- **Phase 4, users and user tools.** Seats, per-user cost and all three tool connectors are
  built, along with the User Tools page. None has met a real account, so the phase's own
  test is not met. Codex and ChatGPT publish no per-user endpoint and are deferred
- **Phase 5, recommendations.** Four rules built and running on real data. Its own success
  test is not met, and deliberately recorded as not met: only one rule can ever produce a
  savings figure, and the data it needs is not gathered
- **Phase 6, reports, alerts and forecasts.** Not started. Runs entirely on data we already
  have, so it is available whenever it is wanted

## Complete backlog: everything on the plan that is not built

Audited 2026-09-29 and revised 2026-09-30 against the sidebar plan and phase list. The
question for each row is the one that matters: is a real account genuinely the blocker, or
have we just not built it yet.

**Only four things in the whole plan are truly blocked by not having an account, and all four
are the same blocker: a user tool that reports nothing cannot be displayed.** Everything else
is buildable today, including all four user tool connectors themselves.

### Phase 2, data sources and provider accounts

| Item | Blocked by an account |
|---|---|
| Test connection button per credential, backend probe already exists | No |
| Product reports which providers have really met a real account | No |
| Provider Keys tab on Attribution Rules. Needs connectors to record the provider's own API key id against a fact, which is a connector change, not an account | No |
| Actually running the five unproven connectors against a live account | **Yes, and only this** |

### Phase 4, users and user tools

| Item | Blocked by an account |
|---|---|
| ~~Claude Code connector~~ Built 2026-09-29 | No |
| ~~GitHub Copilot connector~~ Built 2026-09-29, reports seat holders because GitHub publishes no cost | No |
| ~~Cursor connector~~ Built 2026-09-29 | No |
| ChatGPT and Codex connector | Deferred: no per-user endpoint is published. That money already arrives through the OpenAI connector or the Seats model |
| ~~User Tools data source page, one tab per tool~~ Built 2026-09-29 | No |
| User Directory page: SSO Sync, SCIM moved from Admin Settings, Import | No |
| Tools tab on a user | **Yes.** Nothing to show until a tool reports |
| Tool Logins tab on Attribution Rules | **Yes.** Same reason |
| Verifying any tool connector against a live account | **Yes** |

### Everything else on the plan, none of it account blocked

| Item | Phase |
|---|---|
| Deployment pipeline for customer installations | 0, and the only Phase 0 item left. Waits on the cloud provider choice |
| Renaming identifiers that still carry the old product name, deliberately open | 0 |
| Projects out of Beta and open to team admins | 1 |
| Projects and Budget tabs on a team | 1 |
| Provider Accounts tab on a team | 1 |
| Savings tab on a virtual key | 1 |
| Seats tab on a user, which today lives only on the Ledger | 4 |
| Pricing Adjustments tab on the Ledger, a move of the existing Cost Tracking settings | 3 |
| Uploading an invoice file rather than typing a bill | 3 |
| Reports: scheduled reports, team statements, exports | 6 |
| Anomaly alerts | 6 |
| Forecasts | 6 |

### What this means for sequencing

The tool connectors and Phase 0 are done. What is left divides cleanly: Phase 6 (reports,
alerts, forecasts) and the Phase 1 screens need nothing external and can start whenever; the
deployment pipeline needs one decision from you; and everything else waits on an account.

## Blockers

- **No real provider or tool account except OpenRouter.** Five of six provider connectors and
  every user tool connector have never seen live data. The current plan closes everything that
  can be closed without one and records the three questions that stay open
- **`prisma generate` is blocked by Device Guard on this machine.** Every new table is read and
  written with raw parameterised SQL as a result
- **The budget gate scripts crash on Windows** (`scripts/gate_slot_lock.py` imports `fcntl`
  unconditionally). Run `type_discipline_gate.cmd_check(base_ref)` in-process instead

## Standing decisions worth not relitigating

- All new work goes on the single branch `litellm_token_iq`. Never `main`
- Python only through `.venv\Scripts\python.exe`, never the system 3.14
- Start the proxy only with `bash ~/.claude/scripts/litellm-dev-up.sh`, port 4001
- Never remove, merge or rename an existing UI tab without asking
- The hierarchy is teams, projects and users. Never "employees"
- A provider figure says how much was spent, a gateway figure says who spent it. They are
  never added together

## Phase 0 of the independent-codebase programme, 4 Oct 2026

Spec: `docs/specs/2026-10-04-token-iq-independent-codebase.md`
Plan: `docs/plans/2026-10-04-phase-0-baseline-and-inventory.md`

No product code changed. Three artifacts, all re-runnable:

| Artifact | Re-run with |
|---|---|
| `2026-10-04-phase-0-baseline.json` | `python -m scripts.inventory.capture --all` |
| `2026-10-04-phase-0-name-census.json` | `python -m scripts.inventory.census` |
| `2026-10-04-phase-0-reachability.json` | `python -m scripts.inventory.run_reachability` |
| `2026-10-04-feature-usage-inventory.md` | `python -m scripts.inventory.inventory && python -m scripts.inventory.write_inventory` |

### What the measurements say

The rename is 183,380 occurrences across 6,591 files, plus 3,458 more in history and legal
text that phase 10 permits to stay. The source document's 521,641 counted `node_modules`.
Counted per category so each rename phase can show its own line falling: 136,015 in Python,
18,592 config keys, 17,049 metrics, 6,060 in UI source, 3,072 environment variables, 1,315
headers, 271 Prisma model references, 8 console scripts.

The inventory is 143 rows, and 26 of them are wholly unproven, holding 13,118 lines. 18 are
proposed for deletion, 6 are unsure and 2 are keeps that look unproven only because they are
loaded by configuration or by path rather than imported.

### Two false negatives the tooling found on itself

Both would have proposed deleting live code, and both were caught by reading the analyser's
own output rather than trusting its summary.

`litellm/_lazy_imports_registry.py` holds 269 module paths as plain strings, which a
different file hands to `import_module`. Reading only the call site left 162 live modules
looking dead, most of them provider transformations, which is exactly what phase 5 decides
about. Registries are now named explicitly as literal sources.

`litellm.proxy.client.cli` is a declared console script. It was not in the hand-written seed
list, so 7,356 lines of CLI looked dead. Entry points now come from `pyproject.toml`.

### What phase 0 found and deliberately did not fix

- `assert_ci_coverage.py` still fails with 41 Token IQ test files in no CI job. Phase 4 fixes it
- 13 dynamic imports remain unresolvable, listed in the reachability artifact. They are the
  remaining hole in the evidence and the inventory says so rather than implying confidence
- `make lint` cannot run on this machine: `make` is absent and the gate slot lock imports
  `fcntl`. Recorded as unavailable, with `ruff check` captured separately as a named
  substitute. **CI has to supply the real lint baseline before phase 6**
- The two connector defects, OpenAI line items and Bedrock static keys, are untouched. They
  are phase 11

### The baseline is incomplete, and here is exactly how

788 tests are recorded across `token_iq`, `repositories` and `deploy`, all passing, plus the
`ci_coverage`, `lint` and `ruff` commands.

Five sections are missing because the machine ran out of memory and the runs were stopped:
the `token_iq_proxy` and `unit` suites, and the `ui_build`, `ui_tests` and `docker` commands.
Nothing failed; they were killed while still working. The capture is resumable by section, so
finishing it is one command per section and nothing already captured is lost:

```bash
python -m scripts.inventory.capture --section token_iq_proxy
python -m scripts.inventory.capture --section unit
python -m scripts.inventory.capture --section ui_build --section ui_tests
python -m scripts.inventory.capture --section docker
```

Run them one at a time rather than together; running several at once is what exhausted the
memory. **The baseline is not fit to compare phase 3 against until those five are in it**, so
this is the first thing to finish before any code moves.

### The gate

**Phase 5 does not start until the owner approves the inventory.** That approval is the whole
point of this phase.

## Phase 1 of the independent-codebase programme, 4 Oct 2026

Plan: `docs/plans/2026-10-04-phase-1-decisions-licence-documentation.md`

Documentation only. No behaviour changed.

### What was written

Decision records `0022-independent-codebase.md` and `0023-remove-litellm-names.md`, with
`0021` marked superseded. `LICENSE` corrected and `NOTICE` added. `docs/README.md` with the
glossary of the seven terms the product's screens use without explaining.
`docs/product/README.md` on how to read the blueprint. `README.md` and `CLAUDE.md` rewritten.

### The documentation now lives here

`docs/status.md`, `docs/decisions/` (24), `docs/plans/` (34), `docs/specs/` (5),
`docs/product/` (4). `project_usage/` and `docs/superpowers/` are gone.

### Three things worth remembering

**The case-only rename did exactly what the plan warned.** `git mv docs/Product docs/product`
reported success and left the directory named `Product`, because this filesystem does not
distinguish the two. Done through a temporary name instead. Any future case-only rename needs
the same treatment and needs checking with `git ls-files`, not `ls`.

**A literal search missed five files.** Eighteen files referenced the old paths as strings
and were rewritten. Five more built the same path from separate segments
(`REPO / "docs" / "superpowers" / "plans"`), so searching for `docs/superpowers` did not find
them. Those were the inventory scripts, which would have written their artifacts into a
folder that no longer exists.

**The blueprint and the restructure document were never in git.** Both arrived as browser
downloads, complete with `(1)` in their names. The two documents the whole programme is
written against existed only on one machine until this phase.

### A defect found while working, not fixed here

**Importing `litellm.proxy.proxy_server` rewrites the committed UI bundle in place.** At
module scope, around line 1998 of `proxy_server.py`, it reads every file under
`litellm/proxy/_experimental/out/` and writes back a copy with `/litellm-asset-prefix`
replaced by `$SERVER_ROOT_PATH`. It is not inside a function and nothing guards it.

So any test that sets `SERVER_ROOT_PATH` and imports the proxy permanently modifies 548
tracked files. It happened twice during this work, both times from the unit suite, and each
time left the working tree holding a bundle whose assets all point at `/my-custom-path/`.
Committing that would make the proxy serve a UI whose every stylesheet and script 404s.

Not fixed here because phase 1 changes no behaviour. It belongs with the other defects in
phase 11. Until then, check `git status` for changes under `_experimental/out/` after running
the Python suite, and restore with `git checkout -- litellm/proxy/_experimental/out/`.

## Two decisions taken 4 Oct 2026, before phase 2

**Helm is deleted rather than repointed.** The deployment path is `deploy/images`,
`deploy/installations` and `terraform/tokeniq/installation`, and none of them references
Helm. The chart's only dependents are `terraform/litellm/aws` and `terraform/litellm/gcp`,
upstream's own Terraform, already on phase 5's deletion list. Keeping it would mean carrying
70 files of a Kubernetes path nobody has used through phases 7 to 9, where every setting it
writes gets renamed underneath it. If Kubernetes is needed later, a fresh chart against the
final image and the final names will be less work than a renamed upstream one.

**Nikhil Eruva owns prices, security advisories and provider API changes.** One person is
named rather than a team, because there is one person, and a fictional owner makes a process
look covered while nobody does it.

The three are not equal and should not be treated as such:

| Owner | What it costs | Backstop |
|---|---|---|
| Prices | A daily pull request. Additions merge themselves; only changes need reading | The 2% reconciliation variance rule catches a wrong price that review waved through |
| Security advisories | Mostly Dependabot. Shrinks again once phase 5 deletes the features most advisories land on | The scanners already in CI |
| Provider API changes | The real work: six provider changelogs, monthly | The per-provider contract tests fail when a payload shape moves |

Provider API changes is the first of the three to hand off when there is somebody to hand it
to. Prices is the one that must never quietly lapse, because a stale price breaks every
figure in the product without failing anything.

## Token IQ has no documentation site, and the dashboard now shows that

Decided 4 Oct 2026, during phase 2 Task 6.

The dashboard carried 81 links to `docs.litellm.ai` across 52 files. They described a
different product, for features Token IQ is deleting in phase 5 and renaming in phases 7 to
9, so following one took a customer somewhere increasingly wrong. They are being removed
rather than repointed, because there is nowhere to repoint them to.

**This is a real gap, not a tidy-up.** Several of those links were the only explanation a
customer had for a setting. Where the component carried useful text as well as a link, the
text is kept and only the link is dropped: `DocsHint` and `labelWithDocsHint` now render
their tooltip without wrapping it in an anchor, so every word of explanation survives.
Where the link was the whole content, such as a "Docs" nav item or a "Read the docs" button,
it is gone.

Token IQ needs its own documentation before it is sold to anyone who did not build it. Until
then the product explains itself only through the in-page copy, the glossary in
`docs/README.md`, and the help text in the blueprint's page model.

### Task 6 is finished

All 334 Python references and all 81 dashboard links are gone, `schema.d.ts` is
regenerated, and the dashboard compiles and type-checks.

Where a component carried explanation as well as a link, the explanation stays:
`DocsHint`, `labelWithDocsHint` and `MetricLabel` now render their tooltip without an
anchor around it, so no help text was lost to remove a dead link. Four tests whose only
subject was a link were deleted with it; the rest kept everything except the href
assertion.

## Phase 2 Task 7: workflows, Helm, scripts and data files

17 workflows deleted, leaving 34. They served BerriAI's public project: issue triage and
labelling, duplicate-closing, stale-marking, daily branch creation, the Together AI model
sync, release and publishing. Deleting them orphaned seven scripts under `.github/scripts/`
and three test files, which went with them.

Helm is gone, 70 files plus its workflow and its two Makefile targets, per the decision
recorded above. Nothing in `deploy/` or `terraform/tokeniq/` referenced it.

The install scripts are gone, along with the curl hint in the autoroute CLI that pointed at
one of them. That hint was also the last thing keeping the second strict xfail alive in
`test_no_runtime_downloads.py`, so the marker came off.

Package metadata now names NITCO rather than BerriAI, in both `pyproject.toml` and the
migrations package. The `[project.urls]` sections are removed rather than repointed, because
Token IQ has no public site and a link to one that does not exist is worse than none. The
distribution is still named `litellm`; phase 6 renames it.

Data files: `cost.json` and the root `policy_templates.json` deleted after confirming
nothing reads either. Kept, with reasons: `provider_endpoints_support.json` until phase 5
decides on public endpoints, `mcp_servers.json` and `router_plugins.json` until phase 5
deletes MCP and routing, `whitelisted_bedrock_models.txt` owned by the Bedrock connector,
`license_cache.json` refreshed by the dependency job, and `policy_templates_backup.json`
which is now the only source the code reads.

The upstream-reference search is clean apart from `cookbook/`, which phase 5 deletes, and
the documents that describe this removal.

## Phase 2 Task 8: dependency updates, and what is still a manual setting

`.github/dependabot.yml` covers six node projects, the Python workspace through `uv`, the
Dockerfile and the GitHub Actions. Minor and patch updates are grouped into one pull
request a week per project, because a separate pull request per patch bump is how a
dependency queue stops being read.

Six node projects, not the two that were obvious. The dashboard and the e2e harness were
the ones anybody would list; the repository root, `tests/proxy_admin_ui_tests/ui_unit_tests`
and `tests/pass_through_tests` each have their own lockfile and were found by the test
rather than by looking.

`tests/code_coverage_tests/test_dependabot_config.py` exists because Dependabot fails
silently. A wrong ecosystem name, a renamed directory or a moved manifest produces no pull
requests and no error: the updates simply stop, and the first anyone knows is a dependency
years out of date. The test checks every watched directory exists, holds a manifest that
ecosystem can read, and that no lockfile in the repository is unwatched.

### Two things this file cannot do

**Security updates are a repository setting, not a key in this file.** They must be turned
on under Settings, Code security, Dependabot security updates. Nothing in the repository
can assert that, so it is an owner action and it is recorded here rather than assumed.

**Base images are pinned by digest through `ARG` defaults rather than on the `FROM` line**,
so Dependabot may not see all four. Whatever it catches is worth having, and `image-scan`
is what actually fails a stale base.

### Owners

Named on 4 Oct 2026, recorded above with what each costs: prices, security advisories and
provider API changes are all Nikhil Eruva, with provider API changes the first to delegate.

## Phase 2 Task 9: the proof, and what it found

### The network proof

With every outbound socket blocked, the package imports and 3,559 models price, the
Anthropic beta headers load, the auto-router presets and provider endpoint support load,
and the price history loads. **Zero outbound connections attempted.** Phase 2's central
claim holds: an installation behind a firewall behaves exactly as one with open egress.

The container run with restricted networking is still outstanding, because the Docker
daemon does not run on this machine. The socket-level proof is the stronger of the two for
the question being asked, but it is not the same as the container check the plan asked for.

### The search

Clean across product code, deployment files and documentation. What remains is `cookbook/`
(phase 5 deletes it), test fixtures that deliberately contain the patterns, the attribution
in `README.md` and `NOTICE` that the licence requires, and the documents describing this
removal.

### Three defects the proof found

**The price file would not have shipped.** `data/pricing/model_prices.json` sits outside the
Python package, and nothing added it to the wheel's include list. Every test passed from a
source checkout because the file is right there; an installed wheel would have had no price
list at all and every cost the product reports would have been missing. Fixed, with a test
that reads `pyproject.toml` and fails if `data/` stops being packaged.

**`provider_endpoints_support.json` had already diverged.** Two copies, and the proxy served
the smaller one: 149 providers against the maintained 176, so customers saw a list 27
providers stale. The same two-copy pattern the price consolidation was meant to end, caught
here only because the search counted its upstream URLs. Now one file, inside the package the
loader reads, with 209 upstream links stripped from it.

**Task 6's rewriter left dangling connector words.** Removing `: <url>` from a message left
the label behind, so thirteen places raised `"No DB Connected. See"` and others ended in
`Learn more` or `Docs` with nothing following. The file still parsed and the message still
rendered, which is why nothing failed. All repaired.

### A flaky test, not a regression

The baseline comparison reported one newly failing test on each of two runs, and a
*different* test each time. Both pass repeatedly in isolation. The proxy suite has tests
that fail intermittently under `-n 4`, so a single newly-failing result from a parallel run
needs re-running before it is believed. Nothing disappeared on either run, which is the
check that matters most.

## Phase 3, tasks 1 and 2: Token IQ's code has a package of its own

`token_iq/` now holds the nine product folders and the eleven repositories that were Token
IQ's, and every quality gate watches it. 227 dotted references and 12 docstring paths were
repointed by `scripts/move_token_iq_modules.py`, which carries the map of what moved. The
proxy registers 589 routes, nothing newly fails against the phase 0 baseline, and no test
disappeared or appeared.

### The gates went first, on purpose

`pyrightconfig.json` and both lint budget scripts named `litellm` as a literal. Had the
package been created before they were changed, every Token IQ module would have left type
checking and both budgets at once, and the budgets would have *improved*, because the
violations they were counting moved somewhere nothing was looking. Task 1 changed all four
and proved each by planting a violation in a throwaway file and watching it caught.

### There were no quoted module paths

The plan expected eleven strings that `mock.patch` resolves lazily, where a missed one
patches nothing and the test still goes green. The search found zero: the eleven belong to
task 3's router move. The search still had to happen, because an import error tells you
nothing about a string either way.

### Three failures the move surfaced that the move did not cause

**Phase 2 broke three tests and nobody re-ran that suite.** Repairing the dangling
`"No DB Connected. See"` message reworded it to `"No database connected"`, which three
assertions in `test_repositories.py` were matching on. They had been failing since
`fda886b696`. The phase 2 entry above says "All repaired", and the repair was right; what
was missing was running the tests that asserted the old text. The assertions now follow the
source.

**`make lint-ruff` was already red.** Three errors in `litellm/`: two empty comments left by
a comment-stripping pass, and `cache_type` in `router.py`, dead since decision 0005 removed
response caching. A red lint gate blocks every later phase, so they are fixed.

**The test lint gate was red on 21.** The nine in files written earlier in this programme
are fixed and each is stronger for it: `match=` naming the error rather than accepting any
`ValueError`, and `FrozenInstanceError` in place of a blind `Exception` that would have
passed on a typo in the attribute name. The remaining eleven are inherited engine tests and
are left alone.

### The codemod rewrote its own map

Run over `scripts/`, it turned its own `MOVES` table into an identity map, and the next run
then reported a clean "0 files rewritten". The rewrite itself was fine, because the rules
load before any file is touched, but a no-op that proves nothing is the same failure this
phase is about. The map is spelled in two pieces now and the script skips itself.

### What did not move

`tests/test_litellm/` stayed. The mirror rule says the test tree follows the source tree, so
this is a debt rather than a decision that the mirror does not matter. Moving it now would
make every nodeid in the phase 0 baseline read as `disappeared`, leaving nothing to compare
task 3 against. Phase 4 is where it moves: spec 5.4 puts the Token IQ tests in
`tests/token_iq/` mirroring the package, and phase 6 takes what is left of
`tests/test_litellm/` to `tests/gateway/`. Phase 4 re-cuts the baseline anyway, which makes it
the right moment.

The other sixteen files in `litellm/repositories/` are the engine's. The eleven that moved
import nothing from their former siblings.


### How the gate was actually proved

Counting basedpyright's errors across both trees was the obvious check and it does not run
here: the checker exhausts V8's default 4 GB heap partway through `litellm/`, so it needs
`NODE_OPTIONS=--max-old-space-size` to finish on this machine. The better check turned out not
to need the checker at all. `include` and `exclude` are path patterns, so whether anything
escaped the gate is a question about file sets: **2389 files were checked before the move and
2392 after**, nothing escaped, and the three additions are the new package `__init__.py` files.
That comparison is now a test, and it fails if an `exclude` pattern ever swallows part of
`token_iq/`.


## Phase 3, task 3: the API routers moved, and nothing 404s

Sixteen modules from `litellm/proxy/management_endpoints/` now live in `token_iq/api/`, with
their seven wire-type modules in `token_iq/api/types/`. 139 dotted references and 13 type
references repointed. Twelve of the sixteen define a router; the other four are helpers that
moved with them.

### The route list is the proof, not the test suite

**589 routes before, 589 after, byte-identical** as methods, path and endpoint name. A router
that stops being included answers 404 at runtime rather than failing to import, so no test in
the suite would have reported it. The comparison was captured to a file before the first `git
mv` and diffed literally afterwards.

### The eleven silent strings were really there

Six `patch()` calls naming `project_endpoints.get_daily_activity` and five naming
`provider_usage.ProviderUsageFactRepository`. Had any been missed it would have patched
nothing, exercised the real collaborator, and passed. They are now covered by a test that
resolves every `patch` string in the suite naming a `token_iq` path, proved by planting a stale
target and watching it named in the failure.

### Both lazy imports, found by walking the tree

`provider_overview.has_credentials` inside `model_info_v2()` and `courier_coverage`'s two names
inside `team_courier_coverage()`: nothing resolves either until that request arrives. Found by
parsing for imports nested inside a function rather than by reading, and resolved by name
afterwards. There are 57 function-local imports in `litellm/`; the other 55 name modules that
stayed.

### One name differs from the plan

`audit_log_endpoints.py` became `audit_logs.py`, where the plan wrote `audit_log.py`. The spec's
rule is "plural resource name, no `_endpoints` suffix" with `projects.py` as its example, and
dropping the suffix without the plural follows half of it.


## Phase 3, task 4: the types and the policy modules

Seven type modules moved from `litellm/types/proxy/` to `token_iq/types/`, and seven policy
modules the request path calls into moved to `token_iq/policy/`. 225 references repointed, none
of them inside a string.

### The cycle the spec predicted does not exist

Spec 5.3 says to leave `team_api_access` types where they are if importing `litellm.proxy._types`
creates a cycle. The dependency runs the other way: the types module imports nothing at all, and
it is `litellm/proxy/_types.py` that imports `TeamApiAccessMode` from it. The policy module beside
it imports both. Types, then `_types`, then policy, in a straight line.

Checked by importing each of the 16 moved modules **first, in a fresh interpreter**. A cycle that
only bites when a module is imported before anything else disappears the moment something has
already pulled the graph in, so importing them inside a session that has loaded the proxy would
have proved nothing. All 16 are clean, and the route list is still the same 589.

### They are called `policy/`, not `hooks/`

The plan calls them "the seven proxy hooks", but a hook in the gateway's vocabulary is a
`CustomLogger` subclass and none of these is one. They decide which way a team may reach the
models, what the plan allows, what is kept in the spend log, how long bodies are retained, who
may read a credential, which model names a courier request uses, and whether a pass-through retry
may go anywhere but the endpoint the client named. That last one is the observer-only constraint
expressed as code.

### A mistake worth recording

`ruff check --select I001 --fix` was run against `tests/` to tidy the import order the rewrite
disturbed. The tests config does not enable `I001`, so `--select` replaced the config's rules
rather than narrowing them, and 2218 import blocks were reordered across 1537 test files,
collapsing multi-line imports and removing 358 lines net. Reverted, and the path rewrites
reapplied to leave the intended 50 files.

The tell was the number. The move had touched 50 test files and the fix reported 2218. A count
that large from a tidy-up is the thing to stop at, not the thing to accept because the next
command printed "All checks passed".

### Where the two trees still touch

Thirteen modules under `litellm/` import from `token_iq/`, which is the coupling phase 6 resolves
when `litellm/` becomes `token_iq/gateway/`. Nothing under `token_iq/` imports a router or an
endpoint from the gateway; what it does import is `litellm.proxy._types` and one auth helper.

## Phase 3, task 5: packaging, and where phase 3 leaves things

`token_iq` would not have shipped. `tool.maturin.include` now names `token_iq/**/*.py`, because
maturin builds the one Python package `module-name` points at and that is `litellm`. A second
top-level package reaches an installed copy only by being listed. Nothing in a checkout notices,
since the directory sits on `sys.path` either way, which is exactly how phase 2's missing price
list went unseen while every test passed.

### The build proof runs in CI, because it cannot run here

There is no Rust toolchain on this machine, and maturin needs `cargo metadata` even to make an
sdist, so no wheel can be built locally at all.
`.github/scripts/verify_wheel_contents.py` runs in `test-rust.yml`, in the job that already
builds a release wheel. It opens the wheel, checks one file from every subpackage and both price
files, then installs it `--no-deps` into a throwaway environment and imports twelve modules with
the working directory outside the checkout, so anything that only resolves because the repository
is on `sys.path` fails there.

What could be proved locally was. The script ran against three wheels assembled by hand: one with
no `token_iq`, one with `token_iq` files but no `__init__.py`, and one laid out exactly as the
include globs would produce it from the real tree. The first two fail with different messages,
and the third installs and imports all twelve. The single step left for CI is the one needing a
compiler: whether maturin's glob actually places those files at the wheel root.

`tests/code_coverage_tests/test_packaging.py` is the half that runs anywhere. It also checks that
a workflow runs the verifier **in a job that builds a wheel**, because a verifier nothing invokes
is the same as no verifier. Both halves were proved by breaking what they guard.

### Phase 3, in numbers

| | |
|---|---|
| Modules now in `token_iq/` | 100, across 15 subpackages |
| References repointed | 227 modules, 139 routers, 13 router types, 225 types and policy |
| Quoted module paths found and fixed | 11, all in the router move |
| Routes before, and after every task | 589, byte-identical |
| Files type-checked before, and after | 2396 either way, nothing escaped |
| Left in `litellm/repositories/` | 16, the engine's |
| Left in `litellm/proxy/management_endpoints/` | 33 |
| Left in `litellm/types/proxy/` | 13, all engine types |

### Where the two trees still touch

Thirteen modules under `litellm/` import from `token_iq/`. In the other direction `token_iq`
imports 23 engine modules at 93 sites, and three of them account for most of it:
`litellm.proxy.proxy_server` at 31, which is where routers reach for `prisma_client`,
`litellm.proxy._types` at 15, and `litellm.proxy.auth.user_api_key_auth` at 12. Phase 6 turns
`litellm/` into `token_iq/gateway/`, at which point none of those crosses a package boundary.

### One check phase 3 did not finish

The three suites each task touched, `token_iq`, `repositories` and `token_iq_proxy`, were compared
against the phase 0 baseline after tasks 2, 3 and 4. All three were clean every time: nothing newly
failing, nothing disappeared, nothing appeared, with the same 20 pre-existing failures throughout.

The phase-level run that also covers `unit`, 30,369 cases, was killed partway through because the
machine ran low on memory. It did not fail and it says nothing about the code, but it did not
finish either, so **that comparison is outstanding**. Phase 4 re-cuts the baseline, so it should be
run before phase 4 starts rather than after.

### What phase 3 did not do, and who picks it up

`tests/test_litellm/` did not move. **Phase 4** moves the Token IQ tests to `tests/token_iq/`
mirroring the package, and has to re-cut the phase 0 baseline to do it, since that baseline is
keyed on the old nodeids. Phase 4's own acceptance is `assert_ci_coverage.py` exiting 0, which it
still does not: 42 test files are invoked by no job, down from 50 now that the quality guard tests
have one.

Nothing populates `model_price_variances`, so the price-drift rule is still armed and never
loaded. That is unchanged by this phase and belongs with the provider sync work.

### Two mistakes from this phase, both caught by looking at a number

The codemod, run over `scripts/`, rewrote its own map into an identity map and then reported a
clean "0 files rewritten". And `ruff --select I001 --fix` against `tests/`, whose config omits
that rule, replaced the config's rules instead of narrowing them and reordered 2218 import blocks
across 1537 files. Neither was caught by a test. Both were caught by a count that did not match
the size of the change: 0 where something was expected, 2218 where 50 was.

## Phase 4, task 1: the baseline was measuring itself wrong, twice

Phase 4 compares everything it does against the baseline, so the baseline came first. It
disagreed with itself about the Token IQ tests: the `token_iq` suite recorded 468 cases under
those directories and `unit` recorded 372 from the same ones. Both numbers came from the same
tooling, and the tooling was wrong in two separate ways.

### Collection stopped at the first file that would not import

`capture_suite` ran pytest without `--continue-on-collection-errors`. One unimportable file
interrupts collection, pytest writes the report with whatever it had gathered, and everything
after that is absent. `capture_suite` guarded the case where collection dies outright, because
then no report is written at all. It did not guard the case where collection stops partway, which
is the one that happened, and 96 Token IQ cases were recorded as not existing.

Collecting `tests/test_litellm` today errors on 31 files. With the flag, the same collection
yields 468 under those directories, matching a direct run. 468 was right.

A collection error also used to be recorded with the nodeid `.py::<module>`, which names no file
and matches nothing on either side of a comparison. The phase 0 artifact holds 31 of those.

### A run that stopped early was recorded as a complete one

The re-cut `unit` suite then recorded 44,743 cases where pytest collects 46,571, and the
comparison reported **241 cases as disappeared**, which is what a deleted test file looks like.
All 241 were accounted for rather than accepted:

- 29 were old `.py::` nodeids being renamed by the fix above
- 44 were the GitHub automation tests phase 2 deleted with the workflows that served upstream
- 52 belonged to files that no longer collect
- **116 were spread one and two at a time across 37 files that collect perfectly in isolation**

That last shape is not a change to any test. A worker died under `-n 4` and took its unreported
tests with it; pytest still exited and still wrote a report. `capture_suite` writes whatever junit
holds when pytest exits, which is right when the run finished and wrong when it did not.

A suite now records how many cases were collected alongside how many were reported, measured by a
separate serial collect-only pass that costs seconds and cannot itself lose a worker. `complete`
is false only when a count was measured and the report fell short, so the phase 0 artifact, which
predates the field, is not retroactively called incomplete.

### And a third defect, found while fixing the second

`capture_suite` takes `paths: Iterable[str]` and the fix used it twice. A generator would be empty
by the second use, which means pytest with no paths, which means collecting the whole repository
while still looking like a pass. There is now one end-to-end test of the capture path that
deliberately passes a generator: with the bug in place it fails and takes 83 seconds instead of
15, because it ran everything.

### Phase 3 broke nothing

The four suites phase 0 captured completely are identical in case count against the re-cut
baseline, with nothing newly failing and the same 20 pre-existing failures. The one
disappeared/appeared pair is `test_saml_sso` moving from the garbage nodeid to its real path.

The new baseline is `docs/plans/2026-10-05-phase-4-baseline.json`. The phase 0 file is kept as
written: it says what was true on 4 Oct, and a later phase that rewrites it loses the only thing
it was for. `capture.py` takes `--artifact` for that.

### Two pieces of debt this surfaced, neither phase 4's

**36 test files read a price file that no longer exists.** The list moved to
`data/pricing/model_prices.json` when it was consolidated into one copy, and those tests still
build a path to the deleted root `model_prices_and_context_window.json`. Five of them break at
collection, which is why they are among the 31. No production code is affected: all 41 other
references name the old filename only in prose, a log message or a docstring, though those
messages do now tell a user to edit a file that is not there. `test-model-map.yml` ran
`jq empty` on the old path and so failed on every pull request; that one line is fixed.

**A test for a feature that was deliberately removed.**
`tests/test_litellm/test_lowest_latency_zero_tokens.py` imports
`litellm.router_strategy.lowest_latency`, which `e422703a0d` deleted when scored routing went for
observer-only. It can never pass.

**`token_iq/repositories/overview_repository.py` has no test.** Found by validating the test move
map against the tree: ten of the eleven Token IQ repositories have one. Nothing exercises it
directly; the Overview router test injects a fake. Its methods are `provider_billed`,
`tool_new_money`, `seats` and `gateway_recorded`, the four figures the counting rule governs,
where a wrong one is the silent failure that rule exists to prevent.


## Phase 4 is done: the tests mirror the package and CI runs them

86 test files moved into `tests/token_iq/`, and **`assert_ci_coverage.py` exits 0 for the first
time**: 2,602 test files and 10 Dockerfiles each invoked by a job or carrying an allowlist entry,
down from 42 invoked by nothing.

**990 cases under the old paths, 990 at the new paths, nothing missing and nothing new.** 987 pass,
serially and at `-n 2`, four times over with random ordering. The three that fail are
`test_project_org_authz`, which failed in the baseline too because `litellm_enterprise` is not
installed on this machine.

### The comparison almost passed while measuring half the move

`planned()` in the move map expands its directory entries from the tree, so once the directories
had moved it could no longer enumerate what had been in them. The first comparison reported 480 of
990 and looked like a clean result. Driving it off `remap`, which works from the map's prefixes
rather than the tree, gave the exact match. A map that cannot describe the move afterwards is no
use for checking it.

### The re-exports resolve; none could be shown to be load-bearing

The plan said to remove one and require a sibling to fail. It did not fail. Removing
`isolate_litellm_state` leaves the suite identical. So does removing the `proxy_server` globals
hook pair. So does removing that pair and running the Token IQ router tests in the same workers as
`test_key_management_endpoints.py`, the engine test whose leak the hook's own docstring describes:
with and without, the same five failures.

What is proved is that all eight fixtures resolve for a moved test, which `pytest --fixtures`
reports directly. The likely reason removal changes nothing is that the leak came from engine
tests, and `tests/token_iq` is now its own shard, so it never shares a worker with them. They are
kept because they preserve the isolation these tests had before moving, not because a failure was
produced by removing them.

### Two assumptions in the plan were wrong

`tests/deploy` was to be exempted because those tests want Docker and a database. 30 of their 36
cases pass with no infrastructure and 6 skip cleanly, because three of the four files only parse
configuration. They got a job.

And four test files were in no capture suite at all, found by checking the move map against what
the suites cover. They are now the `token_iq_edges` section.

### Why `-n 4` is no longer used on this machine

Measured during this phase: 15.7 GB total with 10.5 GB already in use before pytest starts, VS Code
at 1.7 GB across 11 processes and `msedgewebview2` another 1.7 GB across 20. Each xdist worker
imports the whole engine, about 600 MB. At `-n 4` the machine pages: VS Code stops responding, the
MCP websocket drops, `git` fails to allocate 12 KB, basedpyright exhausts V8's 4 GB heap, and the
harness kills background jobs for memory pressure. Every one of those happened during this
programme and each was first read as an unrelated fault. `-n 2` runs the Token IQ suite in 29
seconds against 23 minutes serially.

The full `unit` suite is not captured on this machine for the same reason. It is not needed for
this phase: the move only touches tests covered by four suites that are captured and complete.


## Phase 0 is finished, and phase 5 is deliberately not started

Phase 0 item 3 wanted a table with a keep, delete or unsure proposal against every row, and said
"this table drives phase 5. Stop here for owner review." The file existed with two tables: 26 rows
carried a proposal and all 143 carried reachability without one. So 117 rows had no verdict and
phase 5's gate had nothing complete to approve. `docs/plans/2026-10-04-feature-usage-inventory.md`
is now one table with a proposal and a reason on all 143 rows: 49 delete, 94 keep, none unsure.

No row is proposed for deletion because nothing reached it. That is phase 0's own rule, that
reachability proves keep and never proves delete. Every delete either quotes the phrase in section 9
that names it or was read and decided.

Cross-checking the rule against the 26 rows a person had already read, 15 agreed and 11 differed,
and every difference was the rule saying unsure where the person had read the file. A first version
of the rule was also too broad: it matched "caching" and would have proposed deleting
`litellm/caching/`, which holds the DualCache the proxy uses for cooldowns and usage, when section 9
names only *response* caching.

### Why the deletions are not being made

The owner cannot evaluate which features the product serves at code level, so the decision came back
to me with the evidence. The evidence says not yet.

- **Guardrails, 50,194 lines and the largest single item, is entangled with auth.** 20 files outside
  it import it, and one is `litellm/proxy/auth/auth_checks.py`, which is kept, where the entanglement
  is `_guardrail_modification_check`, a security control that rejects user-supplied metadata flags.
  Unpicking a security check during a structural programme is how a hole gets made quietly
- **Most other candidates are live HTTP surfaces.** `_lazy_features.py` registers `agents`, `evals`,
  `realtime`, `vector_store_files`, `prompts`, `search_tools`, `policy_engine` and the MCP routers as
  lazy routers, so a customer can call them and deleting them removes an endpoint
- **Provider folders need a list the owner cannot confirm.** 631 of 916 modules under `litellm/llms/`
  are reachable, and section 9 says to confirm the supported providers with the owner

Section 9's own rule covers the first two: "if something still imports a deleted module, keep the
feature and record why." Ground rule 6 covers all three: "stop and ask when a phase would break a
running installation's configuration."

The asymmetry decides it. Keeping this code costs disk and build time. Deleting it wrongly costs a
customer's gateway failing on a call they make, or a security check removed as collateral. Nothing in
phases 6 to 11 or in the blueprint's build order depends on the deletion, so there is no reason to
take that risk now.

### Two findings for whenever phase 5 does run

**Guardrails is not in the product.** The word appears once in the 2,670-line blueprint, in quotes,
as a metaphor about suggested per-key budget limits. There is no guardrails page, tab, role
permission or setup dialog. On product grounds it is a strong delete, once the auth entanglement is
unpicked as its own deliberate piece of work.

**The provider list should be the blueprint's seven:** OpenAI, Anthropic, Azure OpenAI, Vertex AI,
AWS Bedrock, OpenRouter and Gemini. Section 9 of the restructure plan lists eight, adding Azure AI,
which the blueprint never mentions. One of the two documents is wrong and the blueprint is the
product specification.

### A deviation to record

Blueprint step 2 task 1, filtering billing credentials out of `GET /credentials`, was committed
before ground rule 5 was read: "behaviour stays the same except where a phase says otherwise. No new
features during this work." No phase sanctioned that change. It is kept rather than reverted, because
it is correct, tested, and the one test whose expectation changed was updated in the same commit, so
no later baseline comparison reads it as a regression. Recorded here as a known deviation rather than
left to be discovered.

---

## Phase 5A, tasks 4 to 6: empty states, names, and the walk

### Task 4: every empty state now offers the way out

Reconciliation answered "No bill entered" and stopped, while the form that fixes it sat in a
different tab the reader had to go and find. It now offers a control that takes them there, and
`LedgerTabs` became a controlled `Tabs` so the control can actually move the reader rather than
naming a place. Invoices and the attribution rules table say where their form is instead of only
reporting that they hold nothing.

Two empty states were left as they were, deliberately. `UnmatchedPanel`'s "This provider has
reported nothing in the last N days" and the cost ledger's "Nothing recorded for this provider in
this period" are not fixable by anything a reader can do, so naming an action would be a lie.

### Task 5: a team is called by its name, not by its uuid

The explorer grouped `LiteLLM_DailyTeamSpend` by `team_id` and printed that id, so a reader looking
for what their own team spent had nothing on the page to recognise. Team and user slices now carry
the name the database already holds, read in the same query by a left join. Project, provider and
model group by a column that already reads as a name and gained no join; project has no name
anywhere in the schema, so it keeps its id.

Three decisions worth keeping:

- **Left join, not join.** A team deleted from the team table still has spend on the rollup. An
  inner join would drop the row and quietly lower the page's own total
- **The identifier stays on the row.** It is what an attribution rule, a filter or a support
  question is written against. Outside-gateway spend is still matched to a slice by identifier, so
  renaming a team cannot move its money. The id is printed only when it differs from the name
- **The leak question was already answered.** The plan asked for a test proving a reader limited to
  one team cannot learn another team's name. The explorer route is admin-only through
  `_admin_or_403`, so no non-admin reaches any name at all, and the honest guard is a test holding
  that door shut now that names cross the wire. Mutation-tested by removing the guard

### Task 6: the walk, and three things it found

`tests/e2e/ui/tests/usage/screenClaims.spec.ts` opens each screen cold and asserts the sentence
saying what its figures mean, before any control is touched. It needs no traffic on purpose: the
claim belongs to the screen, not to its data, so a reader who arrives before anything is ingested is
still told what they are looking at. The arithmetic those claims describe is asserted where it can
be made deterministic, in the component tests beside each view, rather than as a browser test that
only fires when the database happens to hold a row.

The walk found three real defects, all fixed here:

- **Two existing specs were broken by task 3.** `usagePage.spec.ts` and `usageActivityTabs.spec.ts`
  both navigate to Usage and go straight for the Gateway view's contents. The page now opens on
  Combined, and `keepMounted` leaves Gateway in the DOM but hidden, so both would have failed on a
  visibility timeout rather than on anything to do with their subject. Both now click Gateway first
- **The APIs tab ignored the page's period.** Task 2 gave the page one date control and threaded it
  into Combined and Gateway. The APIs tab kept a hard-coded 30 days, so the header could say seven
  and that tab would answer about thirty with nothing saying so. `/provider/usage/summary` has the
  same `ge=1, le=90` "last N days" shape as the combined endpoints, so it now reads the same helper,
  renamed `lastNDaysCoverage` because it is no longer Combined's alone, and shows the same note when
  the chosen period cannot be served. The Raw Data view is deliberately left out: it is the newest
  rows the provider sent, keyset-paged, and claims no window
- **The APIs tab led with no claim at all, and the cost ledger led with its total.** The APIs tab now
  says these are the provider's own figures, which say how much was spent and never who spent it.
  The ledger's sentence moved above its total, because a reader who stops at the first figure was
  being handed one they could read as everything that was spent

### What has not been run here, and how to run it

The Playwright walk has not been executed on this machine. The suite needs a live proxy on port
4000, a seeded Postgres and the mock LLM upstream, and nothing is listening on any of those ports;
Docker is installed but its daemon is not running, and the box has 4.4 GB free against a stack that
wants postgres plus a Next build plus a proxy plus a browser. It is type-checked, Playwright collects
all eight cases, and the two specs it fixes are the evidence that the breakage it catches is real.

To run it: `tests/e2e/ui/run_e2e.sh tests/usage/screenClaims.spec.ts`, which brings up postgres, the
mock upstream and the proxy itself.

### The open question this phase cannot answer

**Does Token IQ keep the inherited usage dashboard that sits inside the Usage page?**

The Gateway tab is another product's interface: its own controls, its own grouping, its own filter
row, and a chat box. Section 7 of the spec carries this as a decision to make, and task 2 of this
phase only stopped it fighting the page over the date range. It is a product decision about what the
Usage page is, not a code decision, so it stays open rather than being settled by whoever happens to
touch the file next.

Three things are now true that were not when the question was first written, and they narrow it:

- The page has one period, and all three tabs read it, so the inherited view no longer contradicts
  the header
- Combined opens first, so the inherited view is no longer what a reader meets
- Combined, APIs and the ledger each say what their figures mean. The inherited view says nothing,
  and it is the only tab now that does not

---

## Phase 6, first deliverable: the rename map

`docs/plans/rename-map.csv` is built by `scripts/rename/build_rename_map.py`, which measures and
never edits. Phase 6 asks for this map before any rename and asks for it to be reviewed first, so
it is committed on its own.

**3,111 rows over 10,363 tracked files.** Counts come from the git index, not a directory walk, so
the virtualenv, `node_modules` and build output cannot inflate them.

| kind | rows | owned by |
|---|---|---|
| identifier | 2,217 | phase 6 |
| database model | 453 | phase 8 |
| env var | 287 | phase 7 |
| metric name | 141 | phase 9 |
| census fixture | 4 | nothing: a gate greps for these spellings |
| package | 3 | phase 6 |
| request header | 3 | phase 7 |
| config key | 2 | phase 7 |
| test tree | 1 | phase 6 |

Which phase owns a name is read from where it is written, not from how it is spelled, because a
name a running installation reads must not be renamed in phase 6. `LiteLLM_SpendLogs` appearing in
a raw SQL string inside Python is still a database model, which is the one case the schema rule
cannot see.

Three things the map settled that were open:

- **No genuine collisions.** Ten new names have two old names folding onto them, and every one is
  a case-variant pair of the same concept. `LiteLLMLogging` and `LitellmLogging` are both local
  aliases of one `Logging` class, imported with different spellings in different modules;
  `LiteLLMParams` is a local stub class in one test while `LitellmParams` is the guardrails model.
  All are module-scoped, so none share a namespace after the rename. The `note` column says which
  names fold with which, per row
- **Odd spellings exist and are still the name.** `liteLLM`, `LiTeLlM` and `LiteLlm` appear in 27
  files. They are renamed on the leading letter's case, because nothing else about them is
  consistent enough to read
- **Four spellings must not be renamed at all.** `tests/code_coverage_tests/test_inventory_census.py`
  holds them deliberately: they are what a gate greps for, so renaming them would leave the gate
  passing against names that no longer exist

The `files` column means two different things by design, and the `kind` says which. For an
identifier it is how many files contain that name. For a package or the test tree it is how many
files move, which is a question about paths: counting content occurrences reported 0 for the test
tree, whose own name appears inside no file, and 0 for `litellm_core_utils`, whose path is
`litellm/litellm_core_utils`.

An identifier row for a name that is also a package move is not a contradiction. The package
becomes `token_iq.gateway` while the name a module binds becomes `gateway`, which is both of the
plan's rules at once, and the note says so on the row so a reviewer reading only the identifier
rows cannot apply the wrong one.

`tests/test_litellm/test_build_rename_map.py` holds the rules. Five deliberate breakages were tried
against it: treating env vars as code, renaming `litellm_params` mechanically, dropping the
table-name rule, widening the census-fixture rule, and losing the screaming case. All five fail the
suite.

---

## Where to pick up

Phase 5A is finished. Phase 6 has its map and nothing renamed.

**The one thing blocking phase 6 is a review, not work.** `docs/plans/rename-map.csv` is the
artifact the plan asks to be reviewed before the codemod runs. Reading the `package`, `config key`
and `request header` rows is enough to catch the dangerous mistakes; the 2,217 identifier rows are
mechanical and the test holds their rules.

Next, in order:

1. Review the map, then run the codemod pass: move `litellm/` to `token_iq/gateway/`, rewrite
   imports and identifiers with libcst in one scripted pass, move `tests/test_litellm/` to
   `tests/gateway/`, and update packaging, the Dockerfile and the path-keyed budget files. Commit
   the codemod script
2. Phase 6's check is `rg -n "\blitellm\b" --type py` matching only names phases 7 to 9 own, plus
   `make check` green

**Two things need the owner and cannot be done from here.** Whether the inherited usage dashboard
embedded in the Usage page stays, written up above; and running the Playwright walk, which needs the
proxy, Postgres and the mock upstream up.
