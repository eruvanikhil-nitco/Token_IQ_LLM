# Token IQ, current state

Updated 2026-09-29. This file is the one place to look for where the work stands. Keep it
current at the end of every session rather than rediscovering the answer from git log.

## What we are doing right now

**Phase 4's tool connectors are built.** Phase 2 readiness finished before them. Next is
Phase 0, the product-readiness work that decides whether any of this can be sold.

In progress 2026-09-29: `docs/superpowers/plans/2026-09-29-user-tool-connectors.md`, tasks 1
to 6 done, task 7 (docs) underway.

- Claude Code, Cursor and Copilot connectors, each held to its vendor's documented API by
  contract tests over a real HTTP client. 23 mutations applied across them, 23 caught
- Claude Code spend billed to an API organisation is tagged as already on the Anthropic bill
  and excluded from totals in SQL. Proved against real Postgres: a tagged and an untagged row
  for the same person, and only the untagged one reached the total
- Copilot returns seat holders rather than money through a protocol of its own, because GitHub
  publishes no cost and a guessed figure must not be possible to express
- A runner drives every tool, with one tool's failure never stopping the others. Proved live
  in the state we are actually in, with no credentials: cleanly skipped, nothing raised
- The User Tools page is built, one tab per tool, each stating what that tool cannot tell us
- Codex and ChatGPT deferred with a reason: no per-user admin endpoint exists, and that money
  is already collected by the OpenAI connector or carried by the Seats model

Finished 2026-09-29: `docs/superpowers/plans/2026-09-29-provider-readiness-without-accounts.md`,
all five tasks.

- A connector's vendor host is injectable, so a test can stand a server in front of it and an
  Azure Government or Azure China customer has somewhere to point
- All six connectors are held to the API their vendor documents by 76 contract tests, driven
  over a real HTTP client against payloads copied from each vendor's published reference.
  Thirteen mutations applied, thirteen caught, none survived
- Test connection button on each provider's Connection tab, reporting the provider's own words
  rather than a generic failure
- The product says which connectors have met a real account, derived from stored rows. Checked
  live: OpenRouter proved with 50 rows, the other five honestly marked never run
- The product doc records the three questions only a real account can settle

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

- **Phase 0, product readiness.** Not started, and it is the one that decides whether any of
  this can be sold. Token IQ still leans on LiteLLM's licence key, customer-visible LiteLLM
  branding remains, and the Audit Logs tab still points at the old trail. None of it is
  blocked on anything outside the repo. Queued next after the current plan
- **Phase 1, organisation and navigation.** Substantially done. Projects backend complete and
  the sidebar reorganisation landed
- **Phase 2, data sources and provider accounts.** Readiness complete. Only live verification
  against real accounts remains, and that needs accounts
- **Phase 3, combined view and ledger.** Complete and proven against the live database on
  2026-09-29, with the completion test actually run rather than assumed
- **Phase 4, users and user tools.** Seats and per-user cost are done. The Claude Code and
  Copilot connectors are blocked: no account of any kind exists to verify them against
- **Phase 5, recommendations.** Four rules built and running on real data. Its own success
  test is not met, and deliberately recorded as not met: only one rule can ever produce a
  savings figure, and the data it needs is not gathered
- **Phase 6, reports, alerts and forecasts.** Not started. Runs entirely on data we already
  have, so it is available whenever it is wanted

## Complete backlog: everything on the plan that is not built

Audited 2026-09-29 against the sidebar plan and phase list in the product design doc. The
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
| Claude Code connector | No. Buildable from the Admin API docs |
| GitHub Copilot connector | No. Buildable from the published metrics and billing APIs |
| Cursor connector | No. Buildable from the published admin API |
| ChatGPT and Codex connector | No, though the enterprise API details need confirming first |
| User Tools data source page, one tab per tool | No |
| User Directory page: SSO Sync, SCIM moved from Admin Settings, Import | No |
| Tools tab on a user | **Yes.** Nothing to show until a tool reports |
| Tool Logins tab on Attribution Rules | **Yes.** Same reason |
| Verifying any tool connector against a live account | **Yes** |

### Everything else on the plan, none of it account blocked

| Item | Phase |
|---|---|
| Overview home page: total spend across sources, change on last period, bill match per provider, share unallocated, top recommendations, data freshness | 1 |
| Token IQ plan system replacing the LiteLLM licence key | 0 |
| Remaining customer-visible LiteLLM branding | 0 |
| Audit Logs tab moved onto the working audit trail, endpoint limited to admins | 0 |
| Docker image from a clean checkout and a deployment pipeline | 0, waits on the cloud provider choice |
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

The user tool connectors are the biggest genuine gap, because nothing exists for them at all,
and they are not blocked. Building them now means that the day an account appears the work is
one credential and one click, exactly like the provider connectors are becoming.

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
