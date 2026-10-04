# Phase 0: baseline and inventory

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Know exactly what this repository does today, in a form later phases can diff
against, and produce the evidence the owner needs to approve what gets deleted in phase 5.

**Architecture:** Three committed artifacts, all machine-generated and all re-runnable: a
test and build baseline, a name census, and a feature inventory backed by an import
reachability graph. Nothing is measured by hand, because a hand-written baseline cannot be
re-run in six weeks to prove a rename changed nothing.

**Tech Stack:** Python 3.12, pytest, ripgrep, Node for the UI build, Docker.

**Spec:** `docs/superpowers/specs/2026-10-04-token-iq-independent-codebase.md`, section 5.0

## Phase 0 changes no product code

The only files this phase adds are scripts under `scripts/inventory/` and artifacts under
`docs/superpowers/plans/`. If a task finds a bug, it records it and moves on. Fixing it here
would contaminate the baseline that every later phase measures against.

## The rule this phase must not break

**Reachability proves "keep". It never proves "delete".**

The inventory is built from an import graph, and Python resists static analysis: `importlib`
strings, `__import__`, `getattr` on modules, FastAPI route registration, plugin discovery and
config-driven loading all create edges a parser cannot see. A module the graph cannot reach
may still be loaded at runtime.

So the analyser emits exactly two verdicts, `used` and `unproven`. It never emits `delete`.
Turning `unproven` into a deletion proposal is a human reading the folder, and the owner
approving it. A plan that lets a script vote to delete code will eventually delete something
that was loaded by a string.

## Global Constraints

- No product code changes. No fixes, no cleanups, no renames
- Every number in every artifact comes from a committed script, re-runnable with one command
- Artifacts are written to `docs/superpowers/plans/`, the current plans folder. Phase 1 moves
  the whole folder to `docs/plans/`, so writing there now would create two plan folders
- Tests that already fail are recorded as already failing. They are not this phase's to fix,
  and later phases compare against them
- The census excludes `node_modules` and the committed UI bundle
  (`litellm/proxy/_experimental/out`, 1,016 tracked files of build output). Counting generated
  artifacts inflates the figure, which is how the source document reached 521,641
- Scripts are typed and pass the repo's gates. They are production scripts that phase 5 reuses
- Python line length 120. No `Any`, `: Final` on variables, immutable collections

---

## Task 1: A baseline later phases can diff against

**Files:**
- Create: `scripts/inventory/__init__.py`, `scripts/inventory/baseline.py`
- Create: `tests/token_iq_tooling/test_baseline.py`
- Create (generated): `docs/superpowers/plans/2026-10-04-phase-0-baseline.json`

- [ ] **Step 1: Write the failing tests**

The baseline's value is telling "this already failed" apart from "I broke this", so that is
what the tests check. Given a recorded baseline and a later run, the comparison reports a
test that newly fails, stays silent about one that failed in both, and reports a test that
disappeared entirely. A test that vanishes matters as much as one that fails: a move that
loses a file makes the suite greener, not redder.

- [ ] **Step 2: Write the capture**

Run each suite with `--json-report` or equivalent and record, per test id, its outcome. Record
the suites named in the spec: the Token IQ test folders, the full unit suite once, and the
deploy tests. Record the exit status and summary of `assert_ci_coverage.py`, `make lint`, the
UI build, the UI unit tests, and `docker build`.

Record the environment too: Python version, OS, commit SHA, and whether the run was parallel.
A baseline that does not say how it was produced cannot be reproduced.

- [ ] **Step 3: Capture it, and record what already fails**

Expect `assert_ci_coverage.py` to fail with 41 uncovered test files. That is the known state,
not a problem to solve here.

- [ ] **Step 4: Mutate the comparison and confirm a test dies**

Flip a recorded outcome from passed to failed and confirm the comparison reports it. Remove a
test id and confirm the disappearance is reported.

- [ ] **Step 5: Commit**

---

## Task 2: The name census, by category

**Files:**
- Create: `scripts/inventory/census.py`
- Create: `tests/token_iq_tooling/test_census.py`
- Create (generated): `docs/superpowers/plans/2026-10-04-phase-0-name-census.json`

- [ ] **Step 1: Write the failing tests**

The census is the progress measure for phases 6 to 9, so each category has to be counted
separately. One total going down tells nobody which phase is working.

Categories: total occurrences of the name in any case; `LITELLM_*` environment variables;
`x-litellm-*` headers; `litellm_*` Prometheus metrics; `LiteLLM_*` Prisma models; console
commands; config keys; and occurrences in UI source separately from Python.

Test against fixture files with known counts rather than against the repository, so the test
does not change meaning every time someone edits a file. Include a fixture that proves
exclusions work: a file under a `node_modules` path and one under the UI bundle path, both
containing the name, both uncounted.

- [ ] **Step 2: Write the census**

- [ ] **Step 3: Run it and reconcile against the spec's figures**

Section 3 of the spec says 143,494 occurrences across 6,153 files. If this script disagrees,
one of them is wrong, and the discrepancy is explained in the artifact before continuing.

- [ ] **Step 4: Mutate each category's pattern and confirm a test dies**

- [ ] **Step 5: Commit**

---

## Task 3: The reachability graph

**Files:**
- Create: `scripts/inventory/reachability.py`
- Create: `tests/token_iq_tooling/test_reachability.py`
- Create (generated): `docs/superpowers/plans/2026-10-04-phase-0-reachability.json`

This is the evidence engine. Task 4 reads its output; phase 5 re-runs it to check a deletion
is safe.

- [ ] **Step 1: Write the failing tests**

Build the tests on a small fixture package, not on the repository, so they state behaviour
rather than describe today's imports.

The cases that matter:

- a module imported from an entry point is `used`
- a module imported only by an unreachable module is **not** `used`, so unreachability
  propagates rather than stopping at the first hop
- a module reached only through `importlib.import_module("a.b.c")` is `used`, because the
  analyser reads dynamic-import string literals as edges
- a module reached only through a name built at runtime, for example
  `importlib.import_module(f"a.{name}")`, is reported as an **unresolved dynamic import**
  rather than silently ignored. This is the honest case: the analyser cannot follow it, and
  must say so loudly instead of letting the module look dead
- a module no edge reaches is `unproven`, never `delete`

- [ ] **Step 2: Write the analyser**

Entry points, each recorded in the output so a reader knows what the graph was seeded with:

1. The 434 files authored for Token IQ, listed by the command in spec section 3
2. `litellm/proxy/proxy_server.py`, the process entry point
3. Every module named in a `console_scripts` entry in `pyproject.toml`
4. Every module reached by a string literal passed to `importlib.import_module` or
   `__import__` anywhere in the tree
5. Every module backing a route the dashboard calls, derived from the UI's generated
   `schema.d.ts` paths mapped to their FastAPI routers

Parse with `ast`. Resolve relative imports properly. Follow `TYPE_CHECKING` imports, and mark
them as type-only edges, because a module used only for type annotations is a different kind
of "used" and phase 5 may treat it differently.

- [ ] **Step 3: Run it, and read the unresolved dynamic imports by hand**

Every unresolved dynamic import is a hole in the evidence. List them in the artifact with
their source location. If there are many, the inventory's `unproven` verdicts are weak and
Task 4 must say so rather than implying confidence it does not have.

- [ ] **Step 4: Mutate each rule and confirm a test dies**

In particular, break the propagation rule so unreachability stops after one hop, and confirm
a test catches it. That bug would mark most of the tree `used` and quietly make the whole
inventory worthless.

- [ ] **Step 5: Commit**

---

## Task 4: The feature inventory

**Files:**
- Create (generated, then annotated by hand):
  `docs/superpowers/plans/2026-10-04-feature-usage-inventory.md`
- Create: `scripts/inventory/inventory.py`

- [ ] **Step 1: Generate the skeleton**

149 rows: 48 folders in `litellm/`, 54 in `litellm/proxy/`, and the 47 loose Python files at
those two levels. The loose files are included because the source document asks only for
folders, and 47 files with no home is where things get missed.

Columns per row: path, file count, lines, verdict from Task 3 (`used`, `used (type-only)`,
`unproven`), which entry points reach it, and whether any unresolved dynamic import points
near it.

- [ ] **Step 2: Add what each one does, in one line**

Read the folder. One plain sentence. Not the docstring verbatim, and not a guess from the
name: `completion_extras`, `interactions`, `list_api` and `response_polling` cannot be
understood from their names, and those are exactly the rows an inventory gets wrong.

- [ ] **Step 3: Add the non-import evidence**

Reachability misses three kinds of use, and each is checked by hand against every `unproven`
row:

- a config key that enables it, found in `example_config_yaml/` and the config resolvers
- a UI page that calls it, found by matching routes in the dashboard's API client
- a database table or migration that only it writes

- [ ] **Step 4: Propose keep, delete or unsure, and say why**

A row is only proposed for deletion when it is `unproven` by the graph, has no config, UI or
database evidence, and a human has read it. Everything else is keep or unsure. The spec's
expected lists are a cross-check, not an input: if the graph says routing is reachable, that
is a finding worth reporting, not an error to correct.

Record the Rust bridge's verdict explicitly, because the build backend choice in phase 5
depends on it.

- [ ] **Step 5: Summarise for the owner**

At the top: how many rows in each verdict, how many files and lines deletion would remove,
the open questions, and the honest statement of how much the evidence can bear given the
unresolved dynamic imports from Task 3.

- [ ] **Step 6: Commit**

---

## Task 5: Hand over

**Files:**
- Modify: `PROJECT.md`

- [ ] **Step 1: Record the baseline, the census and the inventory, with how to re-run each**

- [ ] **Step 2: List what phase 0 found but did not fix**

Including the three known defects, and anything new. A finding recorded here is a finding;
one left in a terminal is lost.

- [ ] **Step 3: Commit, and stop for owner review**

**Phase 5 does not start until the owner approves the inventory.** That is the gate the whole
phase exists to produce.

---

## Self-Review

**1. Spec coverage**

| Spec requirement (5.0) | Task |
|---|---|
| Recorded baseline of tests, lint, CI gate, UI, Docker | Task 1 |
| Already-failing tests written down | Task 1, steps 1 and 3 |
| Name counts as the progress measure for phases 6 to 9 | Task 2 |
| Inventory row per folder, with evidence | Tasks 3 and 4 |
| Evidence means import chain, config, or UI call | Task 3 for imports, Task 4 step 3 for the rest |
| Absence of evidence recorded as unsure, never delete | The rule above, enforced in Task 3 step 1 |
| Owner approves before phase 5 | Task 5 step 3 |

**2. Placeholder scan**

No "TBD". Task 4 step 5 requires the limits of the evidence to be stated rather than left
implied.

**3. Type consistency**

Task 3 writes the reachability JSON and Task 4 reads it. One schema, defined once in
`scripts/inventory/`, so a verdict cannot mean one thing when written and another when read.

**4. The thing a reviewer should check hardest**

That the analyser never votes to delete, and that unreachability propagates.

Both failures are silent and both are expensive in opposite directions. If propagation breaks,
almost everything looks `used`, the inventory proposes nothing, and phase 5 deletes nothing
while appearing to have done its job. If the `unproven` verdict is ever allowed to mean
`delete`, phase 5 removes a module that was only ever loaded by a string, and the failure
appears at runtime in a customer's installation rather than in CI.

The second is the reason this plan refuses to let a script decide. A dynamic import is
invisible to `ast` by construction, so the analyser is wrong by design on exactly the cases
that matter most, and the only safe response is to make it say "I could not tell" loudly
enough that a person looks.
