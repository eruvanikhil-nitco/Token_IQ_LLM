# Phase 5 deletion: what is proposed, and what needs a decision

> **This phase does not start until the owner approves this sheet.** Spec 5.5 says so, because
> phase 5 is the only phase that removes capability rather than moving it, and a wrong deletion is
> found by a customer rather than by a test.

**Spec:** `docs/specs/2026-10-04-token-iq-independent-codebase.md`, section 5.5
**Measured from:** `docs/plans/2026-10-04-phase-0-inventory-data.json` and
`docs/plans/2026-10-04-phase-0-reachability.json`, 2431 modules analysed

## The one rule this sheet is built on

**Reachability proves "keep". It never proves "delete".**

It is `scripts/inventory/reachability.py`'s own docstring, and it is why no row below says
"delete" on the strength of a number. 716 of the 2431 modules are `unproven`, which means nothing
in the import graph was found to reach them. That is not the same as unused: it can also mean a
dynamic import the analysis could not resolve, of which 13 are recorded, a plugin loaded from a
config string, or an entry point nobody listed.

Conversely a module marked `used` is reachable, not needed. `litellm/router_strategy/` has 21 of
its 26 modules marked used, and routing was switched off by decision 0001. Something still imports
it. That is the work, not a reason to keep it.

## What the measurement says

| | Areas | Files | Lines | Modules used | Unproven |
|---|---|---|---|---|---|
| Delete candidates, per spec 5.5 | 36 | 314 | **103,420** | 107 | 207 |
| Keep, per spec 5.5 | 9 | 490 | 186,561 | 428 | 61 |
| Named by neither list | 98 | 2,142 | 763,466 | 1,505 | 637 |

The third row is the honest problem with this phase. The spec's two lists between them cover 45
of 143 areas. Everything else was never classified, and most of the codebase is in it.

## The delete candidates, largest first

| Lines | Files | Used | Unproven | Area | Note |
|---|---|---|---|---|---|
| 50,194 | 131 | 25 | 106 | `litellm/proxy/guardrails/` | Spec says "if unused". 25 modules are reachable, so it is not unused |
| 10,095 | 26 | 21 | 5 | `litellm/router_strategy/` | Routing off by decision 0001; importers have to go first |
| 4,785 | 29 | 1 | 28 | `litellm/a2a_protocol/` | |
| 4,555 | 11 | 8 | 3 | `litellm/proxy/policy_engine/` | Spec pairs policies with guardrails |
| 4,061 | 10 | 5 | 5 | `litellm/proxy/agent_endpoints/` | |
| 3,585 | 15 | 0 | 15 | `litellm/rag/` | Nothing reaches any of it |
| 1,974 | 2 | 1 | 1 | `litellm/evals/` | |
| 1,816 | 3 | 3 | 0 | `litellm/proxy/vector_store_endpoints/` | |
| 1,752 | 3 | 1 | 2 | `litellm/videos/` | |
| 1,645 | 4 | 4 | 0 | `litellm/vector_stores/` | |
| 1,403 | 11 | 9 | 2 | `litellm/rust_bridge/` | See the question below; this one is not like the others |
| 1,295 | 4 | 2 | 2 | `litellm/proxy/search_endpoints/` | |
| 1,202 | 3 | 1 | 2 | `litellm/images/` | |
| 1,166 | 3 | 2 | 1 | `litellm/experimental_mcp_client/` | |
| 1,113 | 2 | 0 | 2 | `litellm/proxy/vector_store_files_endpoints/` | |
| 1,098 | 3 | 2 | 1 | `litellm/proxy/rag_endpoints/` | |
| 1,039 | 2 | 0 | 2 | `litellm/proxy/openai_evals_endpoints/` | |
| 978 | 3 | 2 | 1 | `litellm/proxy/video_endpoints/` | |
| 960 | 5 | 0 | 5 | `litellm/proxy/a2a/` | |
| 899 | 8 | 7 | 1 | `litellm/compression/` | |
| 813 | 3 | 2 | 1 | `litellm/vector_store_files/` | |
| 791 | 2 | 0 | 2 | `litellm/skills/` | |

The remaining 14 areas are each under 800 lines.

## Four questions that need an answer before anything is deleted

**1. Guardrails, at 50,194 lines, is half the proposal.** The spec says delete "guardrails and
policies if unused", and they are not unused: 25 modules are reachable and 131 files are involved.
Is a Token IQ installation expected to offer guardrails to a customer, or not? If not, this is the
single largest reduction available and it needs the importers unpicked first. If so, the proposal
drops to about 53,000 lines.

**2. The Rust bridge changes the build, not just the code.** The spec notes that removing it lets
the build backend drop from maturin to a pure-Python one. That would also remove the need for a
Rust toolchain, which is currently why no wheel can be built on this machine and why the packaging
proof runs only in CI. It is a larger change than its 1,403 lines suggest, in both directions.

**3. Ninety-eight areas and 763,466 lines are in neither list.** Most of them are provider
folders under `litellm/llms/`. The spec says to delete "provider folders for unsupported
providers", which needs the supported list stated. Which providers must a Token IQ installation
price and serve? Everything else under `llms/` follows from that answer.

**4. Deleting a test is deleting coverage.** Every area removed takes its tests with it, and the
baseline will show those cases as `disappeared`, which is indistinguishable from the accident this
programme has already made twice. The plan for this phase should capture a baseline immediately
before each deletion and remap, as phase 4 does for the move, rather than deleting in one pass and
comparing at the end.

## What I recommend

Split phase 5 into two passes, called **5.1** and **5.2** here. Not 5A and 5B: **5A is already a
phase in the spec**, section 5.6, and it is a different thing entirely, rebuilding the screens so
they can be understood. Reusing the name would have collided with it.

**Pass 5.1** deletes the 13 areas where nothing is reachable at all or only a handful of modules
are, about 20,000 lines, which needs no judgement beyond confirming the feature is not wanted.

**Pass 5.2** handles guardrails, the router strategies and the provider folders, each of which
needs one of the answers above and each of which should be its own commit with its own baseline
comparison.

Approving 5.1 does not commit you to 5.2.

## What comes straight after, and why it matters to you

Phase 5A, the spec's own, runs next and is the one that answers the complaint that started this:
that the pages are data dumps and walking through Usage, Ledger and Recommendations explains
nothing. It collapses the three stacked rows of tabs on Usage, reconciles the two date controls
that currently disagree so switching tab silently changes the period, makes every analytics screen
open with a plain sentence saying what the figures mean and what to do, gives empty states the
action that fills them, and replaces raw team UUIDs with names.

It runs after phase 5 so no effort goes into a page about to be deleted, and before phase 6 so the
rename passes over the final shape of the UI. It also carries an open question for you: whether it
replaces the inherited LiteLLM usage dashboard embedded in Usage, which is a different product's
interface with its own controls, its own date range and a chat box.
