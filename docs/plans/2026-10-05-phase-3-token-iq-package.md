# Phase 3: one package for Token IQ's own modules

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Token IQ's own code lives in `token_iq/`, separate from the engine it was grafted
onto, and every quality gate watches it.

**Architecture:** Pure `git mv` plus reference updates. No behaviour changes, no logic
rewritten, no abstractions introduced. The phase is finished when the same tests pass from
the same assertions against the same code at a different path.

**Tech Stack:** Python 3.12, pytest, pyright, ruff.

**Spec:** `docs/specs/2026-10-04-token-iq-independent-codebase.md`, section 5.3

## The rule this phase must not break

**A missed `mock.patch` string does not fail. It patches nothing and the test still passes.**

An import that moves and is not updated raises `ModuleNotFoundError` on the first run, which
is the safe failure. A patch target written as a string behaves differently: `mock.patch`
resolves it lazily, and a test whose patch silently stops applying goes green while
exercising the real collaborator, or nothing at all. Every one has to be found by searching
for the text rather than by running the suite.

The count is **11, all of them in task 3's router move**. Task 2 turned out to have none, which
was only learnable by looking: the import errors say nothing about it either way.

The same is true of `importlib` strings, and of anything that names a module path in a
config, a workflow or a gate script.

## Facts measured on 5 Oct 2026

| What | Count |
|---|---|
| Modules moving out of `litellm/` | 9 folders: `provider_billing` (16 files), `tool_usage` (10), `repositories` (27, of which 11 are Token IQ's), `recommendations` (3), `ledger`, `attribution`, `overview`, `seats`, `pricing` (2 each) |
| Routers moving out of `management_endpoints/` | 16, all present |
| Dotted references to the moving modules | **227 across 87 files**: 76 in `litellm/`, 149 in `tests/`, 2 in `scripts/` |
| Dotted references to the moving routers | **139 across 23 files** |
| Of the router references, inside quotes, so silent if missed | **11** (the module move has none) |

The spec estimated about 38 import lines and 73 patch strings. The import count is twice
that and the patch-string count is far lower, because most test coupling here is ordinary
imports rather than patch targets. Both figures are worth having right: the imports are
noisy but safe, and the eleven strings are quiet and dangerous.

## The trap the spec singles out

**`token_iq/` would escape every quality gate, silently.**

- `pyrightconfig.json` has `include: ["litellm"]`
- `scripts/ruff_strict_gate.py` has `TARGET = "litellm"`
- `scripts/type_discipline_gate.py` has `TARGET = "litellm"`

The moment the package exists, every Token IQ module leaves type checking and both lint
budgets. Nothing fails. The budgets even appear to improve, because the violations they
counted have moved somewhere unwatched. Task 1 does this before anything moves, and proves
each gate by planting a violation and watching it caught.

## Global Constraints

- `git mv` only, so history follows the file. No file is retyped
- No behaviour changes. If a move requires a logic change to work, stop and record why
- `__init__.py` in every new folder, including test folders
- After each task: the proxy imports, and the touched suites match the phase 0 baseline
- A circular import that the move itself creates is reported, not worked around with a
  local import or a new abstraction
- Python line length 120, no `Any`, `: Final` on variables, immutable collections

---

## Task 1: Make the gates watch `token_iq/` before it exists

**Files:** `pyrightconfig.json`, `scripts/ruff_strict_gate.py`, `scripts/type_discipline_gate.py`, `Makefile`

- [x] **Step 1: Write the failing test**

A repository test asserting that each gate's configured target includes `token_iq`. It reads
the config and the scripts rather than running them, because the failure being guarded is a
path going unwatched, not a rule misbehaving.

- [x] **Step 2: Add `token_iq` to all four**

- [x] **Step 3: Prove each one, by planting a violation**

Create a throwaway `token_iq/_gate_probe.py` holding an untyped function, an `Any`, a mutable
module-level list and a missing `: Final`. Run pyright and both gates. Each must report it.
Delete the probe.

This step is the whole point of the task. A configuration change that looks right and
watches nothing is indistinguishable from one that works, until a phase later when the
budgets are meaningless.

- [x] **Step 4: Commit**

---

## Task 2: Move the product modules

**Files:** the 9 folders listed above, into `token_iq/`

- [x] **Step 1: Move with `git mv`**

| From | To |
|---|---|
| `litellm/provider_billing/` | `token_iq/connectors/billing/` |
| `litellm/tool_usage/` | `token_iq/connectors/tools/` |
| `litellm/ledger/`, `attribution/`, `overview/`, `seats/`, `recommendations/`, `pricing/` | `token_iq/<same>/` |
| the 11 Token IQ repositories | `token_iq/repositories/` |

The other 16 files in `litellm/repositories/` are the engine's and stay. Moving the folder
wholesale would take them with it.

- [x] **Step 2: Update the 227 dotted references**

By script, with the map committed. Imports fail loudly, so this part is self-checking.

- [x] **Step 3: Find the string references by searching for the text**

Not by running the suite. A patch string that no longer resolves patches nothing and the
test still passes.

- [x] **Step 4: Confirm the proxy imports, and run the touched suites against the baseline**

- [x] **Step 5: Commit**

### What task 2 found

The 227 dotted references were exactly as measured, and the 12 slashed ones were all docstrings
pointing at a source path, which would have rotted silently.

**There were no quoted module paths in this move.** The "11 quoted" figure in the table above
belongs to the routers row, not this one, and the rule section overstated it by saying the eleven
were "across this move". They are task 3's. The search still had to happen to learn that, which
is the point: the count was not knowable from the import errors.

Three things the move surfaced that were not the move's doing:

- `tests/test_litellm/repositories/test_repositories.py` had three tests failing since
  `fda886b696`, where phase 2 reworded `base_repository`'s error from `"No DB Connected. See"`
  (a message left dangling by a stripped docs link) to `"No database connected"`. Phase 2 did not
  re-run that suite. The three assertions now match the source
- `make lint-ruff` was red at HEAD on three errors in `litellm/`: two empty comments left by a
  comment-stripping pass, and `cache_type` in `router.py`, dead since decision 0005 removed
  response caching. Fixed, because a red lint gate blocks every later phase
- `ruff check --config ruff-tests.toml tests` was red on 21 errors. The 9 in test files written
  earlier in this programme are fixed, and each got stronger for it: a `match=` naming the error,
  and `FrozenInstanceError` where a blind `Exception` would have passed on a typo in the attribute
  name. The remaining 11 are inherited engine tests and are left alone

A fourth thing was the codemod rewriting its own map, turning it into an identity map and then
reporting a clean no-op on the second run. The rewrite itself was unaffected, because the rules
load before any file is touched, but a "0 files rewritten" that proves nothing is the same failure
shape this phase is about. The map is now spelled in two pieces and the script skips itself.

### What stayed, and why

`tests/test_litellm/` did not move. The mirror rule in `CLAUDE.md` says the test tree follows the
source tree, so this is a real debt rather than a decision that the mirror does not matter. It is
deferred to phase 6 for two reasons: the phase 0 baseline is keyed on `tests/test_litellm/...`
nodeids, so moving the tree now would make every suite in it read as `disappeared` and leave
nothing to compare task 3 against; and phase 6 turns `litellm/` into `token_iq/gateway/`, which
moves the same tree again. One move, at the point where the baseline is being re-cut anyway.

The other 16 files in `litellm/repositories/` are the engine's and stayed. The 11 that moved
import nothing from their former siblings, only stdlib and
`litellm.types.proxy.provider_billing`, which task 4 moves.

### The figure task 3 has to preserve

The proxy registers **589 routes** after this move. Task 3 moves the routers themselves, where an
unregistered router is a 404 rather than an import error, so that is the number to compare
against.

---

## Task 3: Move the API routers

**Files:** 16 routers from `litellm/proxy/management_endpoints/` to `token_iq/api/`

- [ ] **Step 1: Move, renaming the three the spec renames**

`audit_log_endpoints.py` to `audit_log.py`, `project_endpoints.py` to `projects.py`, and the
`*_endpoints.py` types alongside them.

- [ ] **Step 2: Update `proxy_server.py`**

It imports the routers in a block around line 506 and lazily in two places. A lazy import
inside a function is easy to miss because nothing resolves it until that path runs.

- [ ] **Step 3: Update the 139 references and the 11 quoted ones**

- [ ] **Step 4: Confirm every route is still registered**

Start the proxy and compare its route list against the one before the move. An unregistered
router is a 404 at runtime, not an import error, so the suite will not tell you.

- [ ] **Step 5: Commit**

---

## Task 4: Move the hooks and the types

**Files:** the seven proxy hooks and the Token IQ type modules named in the spec

- [ ] **Step 1: Move them**

- [ ] **Step 2: If `team_api_access` creates a cycle, leave it and record it**

The spec predicts this one. A cycle is resolved by phase 6, not by a local import here.

- [ ] **Step 3: Commit**

---

## Task 5: Packaging, and the handover

**Files:** `pyproject.toml`, `docs/status.md`

- [ ] **Step 1: Package `token_iq`**

Add it under `[tool.maturin]`, and confirm `import token_iq` works in a non-editable install,
not only from the checkout. Phase 2 shipped a wheel with no price file for exactly this
reason: everything passes from a source tree because the files are right there.

- [ ] **Step 2: Compare against the phase 0 baseline**

Nothing newly failing, nothing disappeared. Re-run a parallel failure before believing it;
the proxy suite is flaky under `-n 4`.

- [ ] **Step 3: Record what moved, what stayed and why**

- [ ] **Step 4: Commit**

---

## Self-Review

**1. Spec coverage**

| Spec requirement (5.3) | Task |
|---|---|
| `token_iq/` created, modules moved | Task 2 |
| Routers into `token_iq/api/` | Task 3 |
| Proxy hooks and types moved | Task 4 |
| Importers and patch strings updated | Tasks 2 and 3 |
| `token_iq` added to pyright, gates, Makefile | Task 1 |
| Cycle left in place and recorded if it appears | Task 4 step 2 |
| Packaged, and importable when installed | Task 5 step 1 |

**2. Placeholder scan**

No "TBD". The repositories that stay are counted rather than described as "the others".

**3. Type consistency**

Not applicable: nothing is retyped. The nearest equivalent is that no module changes shape,
which `git mv` guarantees and Task 2 step 1 relies on.

**4. The thing a reviewer should check hardest**

The eleven quoted module paths, and the gates.

A missed import fails on the first run. A missed patch string does not: the test goes green
having patched nothing, and the thing it was supposed to be proving is no longer proved by
anything. That failure survives review precisely because the suite is green.

The gates are the same shape of problem one level up. If `token_iq` is not added to all
four, the budgets will report an improvement, because the violations they were counting
moved somewhere nothing is looking.
