# Token IQ, current state

Updated 2026-09-29. This file is the one place to look for where the work stands. Keep it
current at the end of every session rather than rediscovering the answer from git log.

## What we are doing right now

**Phase 2, data sources and provider accounts.** Specifically the part of it that does not need
a real provider account, because only OpenRouter is available and that will not change soon.

Plan: `docs/superpowers/plans/2026-09-29-provider-readiness-without-accounts.md`

- Task 1, done. A connector's vendor host is injectable instead of hardcoded, so a test can
  stand a server in front of it, and an Azure Government or Azure China customer has somewhere
  to point. Ten tests hold both the default and the override
- Task 2, in progress. Contract tests that drive the real connector over a real HTTP client
  against payloads copied from each vendor's published documentation. Anthropic, OpenAI,
  OpenRouter and Azure are done, 54 tests. Vertex and Bedrock remain, then a mutation round
- Task 3, not started. The connection probe already exists in the backend but has never been
  reachable from the product. It needs a Test connection button per credential
- Task 4, not started. The product should report which providers have actually met a real
  account, derived from stored runs rather than from a sentence in a doc that goes stale
- Task 5, not started. Record what is ready and what only a real account can settle

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
- **Phase 2, data sources and provider accounts.** In progress, as above
- **Phase 3, combined view and ledger.** Complete and proven against the live database on
  2026-09-29, with the completion test actually run rather than assumed
- **Phase 4, users and user tools.** Seats and per-user cost are done. The Claude Code and
  Copilot connectors are blocked: no account of any kind exists to verify them against
- **Phase 5, recommendations.** Four rules built and running on real data. Its own success
  test is not met, and deliberately recorded as not met: only one rule can ever produce a
  savings figure, and the data it needs is not gathered
- **Phase 6, reports, alerts and forecasts.** Not started. Runs entirely on data we already
  have, so it is available whenever it is wanted

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
