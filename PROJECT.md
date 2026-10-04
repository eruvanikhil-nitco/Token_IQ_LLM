# Token IQ, current state

Updated 2026-09-30. This file is the one place to look for where the work stands. Keep it
current at the end of every session rather than rediscovering the answer from git log.

## What we are doing right now

**The Overview landing page is built**, which was the last thing standing between six phases
of backend work and a customer being able to see it. Plan:
`docs/superpowers/plans/2026-09-30-overview-home-page.md`, all five tasks.

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

Spec: `docs/superpowers/specs/2026-10-04-token-iq-independent-codebase.md`
Plan: `docs/superpowers/plans/2026-10-04-phase-0-baseline-and-inventory.md`

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
