# Phase 4: the tests mirror the package, and CI runs them

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** every Token IQ test lives at the path that mirrors the module it tests, every one of
them runs in CI, and `assert_ci_coverage.py` exits 0 for the first time.

**Architecture:** `git mv` plus conftest re-exports. No test is rewritten and no assertion
changes. The phase is finished when the same cases pass from the same assertions at a different
path, with the same isolation they had before.

**Tech Stack:** Python 3.12, pytest, pytest-xdist, GitHub Actions.

**Spec:** `docs/specs/2026-10-04-token-iq-independent-codebase.md`, section 5.4

## The rule this phase must not break

**A missing conftest re-export does not fail. It removes isolation between tests.**

Phase 3's danger was a `mock.patch` string that silently patched nothing. This one is worse,
because the damage lands somewhere else. pytest finds fixtures and hook implementations by name
in the conftest files along a test's own directory path. Move a test out from under a conftest
and every autouse fixture and every hook in it stops applying to that test, with no error and
nothing missing from the run. The test still passes.

What breaks is the next test in the same xdist worker. `tests/test_litellm/proxy/conftest.py`
says it plainly: a leaked `master_key` flips the auth short-circuit in `user_api_key_auth` and
unrelated tests return 401 instead of 200; a leaked `llm_router` makes the PTU rollup count a
sibling test's deployments as the proxy's own. That surfaces as a flake nobody can reproduce,
days later, in a test nobody touched.

So isolation is not something to check at the end. It is checked before the bulk of the tests
move, on one directory, by deliberately breaking it and watching a sibling fail.

## Facts measured on 5 Oct 2026

| What | Count |
|---|---|
| Test files moving | **75**: 40 in the dedicated directories, 18 router tests, 10 repository tests, 6 policy tests, 1 types test |
| Plus package and fixture files | 9 `__init__.py`, 2 `conftest.py` |
| Conftests whose contents the moved tests depend on | **4** |
| Autouse fixtures in them | **6** |
| Hook implementations in them | **5** |
| Token IQ test directories in no CI shard today | 7 of 9 |
| Test files `assert_ci_coverage.py` reports as invoked by no job | **42** |
| Shard names that are branch-ruleset required contexts | all 14 |

### The four conftests, and what each one holds

| File | What the moved tests need from it |
|---|---|
| `tests/test_litellm/conftest.py` (597 lines) | 4 autouse fixtures (`isolate_host_aws_config`, `isolate_host_proxy_base_url`, `isolate_host_os_keychain`, `isolate_litellm_state`), the module-scoped autouse `setup_and_teardown`, the named fixtures `isolated_aws_credentials_dir`, `secret_vault_factory`, `local_model_cost_map`, `strict_isolation`, and the hooks `pytest_collection_modifyitems`, `pytest_configure`, `pytest_sessionfinish` |
| `tests/test_litellm/proxy/conftest.py` (274 lines) | the `pytest_runtest_setup` / `pytest_runtest_teardown` hook pair that snapshots and restores `proxy_server`'s module globals, the autouse `_reset_graceful_shutdown_state`, the `disconnected_prisma` fixture, and four builder helpers |
| `tests/test_litellm/provider_billing/contract/conftest.py` | the `vendor` fixture and the `Recorded`, `Reply`, `Vendor` helpers: the stand-in provider server |
| `tests/test_litellm/tool_usage/contract/conftest.py` | nothing of its own. It already re-exports the four names above, with the `# noqa: F401` the pattern needs, and is the worked example to copy |

The hook pair is the one that cannot become an autouse fixture. Its docstring explains why: an
autouse fixture in the root conftest requests `monkeypatch`, so `monkeypatch`'s undo stack
unwinds after every other finalizer, and a test that patches a global while a fixture holds it
patched records the fixture's mock as the original. `monkeypatch.undo` then re-plants that mock
after all the restores have run. Do not "simplify" it into a fixture.

## The traps

**1. The phase 0 baseline is keyed on the paths this phase changes.** Every nodeid in it begins
`tests/test_litellm/...`. After the move, a straight comparison reports every moved case as
`disappeared` and every new one as `appeared`, which is the same output a deleted test file
produces. The comparison has to go through a nodeid remap built from the same move map the `git
mv`s use, exactly as phase 3 repointed imports from a committed map.

**2. The baseline's two suites disagree about the Token IQ tests.** The `token_iq` suite recorded
**468** cases under those directories; `unit`, which collects `tests/test_litellm` wholesale,
recorded **372** from the same ones. One of those numbers is wrong, and until it is known which,
"nothing disappeared" cannot be read off either. Task 1 settles it.

**3. Shard names are required checks.** `test-unit.yml` says so: the `name` of each matrix entry
is the branch ruleset's required context, so renaming an entry renames a check and the ruleset
stops matching it. A new shard is safe. Renaming or removing one is not, and needs the ruleset
changed in the same breath.

**4. `tests/proxy_unit_tests` has its own caller** (`test-unit-proxy-db.yml`) with a
shard-coverage guard that reads that file by name. Nothing in this phase should move a test into
or out of it without looking at that guard.

## Global Constraints

- `git mv` only. No test is retyped, no assertion changes, no test is deleted or skipped
- `__init__.py` in every new test directory, matching the existing tree
- Every conftest re-export carries `# noqa: F401` and says in a comment what it is for
- A fixture or hook that cannot be re-exported is reported, not reimplemented
- After each task: the moved tests pass serially **and** under `-n 4`, and the comparison against
  the re-cut baseline is clean
- Python line length 120, `: Final` on variables, immutable collections

---

## Task 1: Re-cut the baseline, and settle the 468 against 372

**Files:** `docs/plans/2026-10-04-phase-0-baseline.json`, `scripts/inventory/`

- [ ] **Step 1: Finish the comparison phase 3 left outstanding**

Phase 3's phase-level run over `unit` was killed partway through when the machine ran low on
memory, so it never finished. Run it against the current tree before anything moves. If it is
clean, phase 3 closes. If it is not, that is a phase 3 finding and belongs there, not here.

- [ ] **Step 2: Find out why the two suites counted differently**

468 cases against 372 for the same directories. Either `unit` under-collected, which makes it an
unreliable reference for everything after this, or `token_iq` double-counted. Collect both
without running them (`--collect-only -q`) and compare the sets, not the totals.

Not a detail to note and move past. A baseline that disagrees with itself cannot answer the one
question this phase needs answered.

- [ ] **Step 3: Re-cut the baseline on the current tree**

Phase 3 moved 100 modules, so the figures recorded on 4 Oct describe a tree that no longer
exists. Capture fresh, keep the old file as the historical record rather than overwriting it, and
say in the new one what it supersedes and why.

- [ ] **Step 4: Commit**

---

## Task 2: Build `tests/token_iq/` and prove isolation before trusting it

**Files:** `tests/token_iq/conftest.py`, `tests/token_iq/api/conftest.py`, the `__init__.py` files

- [ ] **Step 1: Write the conftests that re-export, before moving any test**

`tests/token_iq/conftest.py` re-exports from `tests/test_litellm/conftest.py`, and
`tests/token_iq/api/conftest.py` from `tests/test_litellm/proxy/conftest.py`, because the router
and policy tests need the `proxy_server` globals hook pair. Copy the pattern from
`tests/test_litellm/tool_usage/contract/conftest.py`, which already does this correctly.

Underscore-prefixed names are not picked up by a star import and have to be named. So do hook
functions: pytest looks them up by name in the conftest module's own namespace, so an imported
`pytest_runtest_setup` works, and a missing one fails silently.

- [ ] **Step 2: Move one directory, the smallest, and run it**

`tests/test_litellm/ledger` is one test file. Move it, run it, and confirm it passes.

- [ ] **Step 3: Prove the re-export is load-bearing, by removing it**

Delete one autouse re-export from `tests/token_iq/conftest.py` and run the moved test together
with a test that depends on that isolation. **It must fail.** If everything still passes, the
re-export was not doing anything and the real dependency has not been found yet.

This step is the whole task. Isolation that looks wired up and is not is indistinguishable from
isolation that works, until a flake appears weeks later in something unrelated.

- [ ] **Step 4: Write the test that keeps this honest**

A repository test asserting that every autouse fixture and every hook implementation reachable
from `tests/test_litellm/conftest.py` and `tests/test_litellm/proxy/conftest.py` is reachable
from the matching `tests/token_iq/` conftest. It reads the modules, because the failure being
guarded is a name going missing, not a fixture misbehaving.

- [ ] **Step 5: Commit**

---

## Task 3: Move the tests

**Files:** 75 test files, 9 `__init__.py`, 2 `conftest.py`

- [ ] **Step 1: Move, mirroring the package exactly**

| From | To |
|---|---|
| `tests/test_litellm/provider_billing/` (15 + contract 6) | `tests/token_iq/connectors/billing/` (+ `contract/`) |
| `tests/test_litellm/tool_usage/` (4 + contract 3) | `tests/token_iq/connectors/tools/` (+ `contract/`) |
| the 10 Token IQ repository tests | `tests/token_iq/repositories/` |
| `ledger`, `attribution`, `overview`, `seats`, `recommendations`, `pricing` | `tests/token_iq/<same>/` |
| 18 router tests from `proxy/management_endpoints/` | `tests/token_iq/api/` |
| 6 policy tests from four `proxy/` subdirectories | `tests/token_iq/policy/` |
| `types/proxy/test_provider_billing.py` | `tests/token_iq/types/` |

Four are renamed to follow the modules phase 3 renamed: `test_audit_log_endpoints.py` to
`test_audit_logs.py`, `test_project_endpoints.py` to `test_projects.py`, `test_token_iq_plan.py`
to `test_plan.py`, and `test_capture_policy.py` to `test_capture.py`.

- [ ] **Step 2: Move `test_daily_reconciliation.py` too, and say why it was nearly missed**

Its subject is `token_iq.api.provider_reconciliation.daily_reconciliation`, but its filename is
the endpoint's name rather than the module's, so a rule based on filenames does not catch it.
**The filename is not a reliable guide to the subject.** Eight other tests that import
`token_iq` do not move, because they exercise engine endpoints under plan gating and only treat
Token IQ policy as a collaborator. Every one of the nine was read before being placed.

- [ ] **Step 3: Update what refers to these paths by name**

Cross-directory conftest imports, `tests/code_coverage_tests/` scripts that walk the test tree,
`scripts/inventory/capture.py`, which names the Token IQ directories as literal strings, and the
guard tests added in phase 3. Found by searching for the text.

- [ ] **Step 4: Run them, serially and under `-n 4`, and compare against the re-cut baseline**

Through the nodeid remap. Nothing newly failing, and the count of cases that moved must equal
the count that arrived. A case that quietly stops being collected looks identical to one that
moved, unless both sides are counted.

- [ ] **Step 5: Commit**

---

## Task 4: Make CI run them

**Files:** `.github/workflows/test-unit.yml`, `.github/scripts/assert_ci_coverage.py`

- [ ] **Step 1: Add a `token-iq` shard**

A new matrix entry, which is safe because a new name is a new check rather than a renamed one.
`tests/test_litellm/repositories` currently sits in the `misc` shard; the ten that moved leave it
and the sixteen engine ones stay, so `misc` keeps its name and loses some paths.

- [ ] **Step 2: Decide the workers and reruns deliberately**

Every other entry states all four numbers even when they match the defaults, because an absent
matrix key renders as an empty string and fails the call. Reruns hide flakes, so start at 0 and
raise only with a reason recorded.

- [ ] **Step 3: Get `assert_ci_coverage.py` to 0**

42 files today. The 7 Token IQ directories and `tests/deploy` are the bulk. `tests/deploy` needs
a decision rather than a shard: those tests want Docker and a database, and a job that cannot run
them is worse than an allowlist entry saying so.

- [ ] **Step 4: Prove the shard runs what it claims**

Compare the case count the new shard collects against the count that moved. A shard with a typo
in its path collects nothing and reports success.

- [ ] **Step 5: Commit**

---

## Task 5: Isolation under parallelism, and the handover

**Files:** `docs/status.md`

- [ ] **Step 1: Run the whole Token IQ suite under `-n 4` repeatedly**

The spec's acceptance is that it passes with and without `-n 4`. Once each is not enough for the
failure mode this phase risks, which is order-dependent and worker-dependent. Run it several
times, and with `-p no:randomly` off so the order varies.

- [ ] **Step 2: Run the suites that lost tests, too**

`tests/test_litellm/proxy/management_endpoints` keeps 42 of its 60 test files after 18 leave, and
four proxy subdirectories lose one each. If any of those 18 was providing isolation the remaining
tests depended on, this is where it shows. The three `test_project_org_authz` cases already fail
in the baseline and move with the rest, so they must still fail afterwards and in the same way:
a pre-existing failure that quietly turns into a pass is as much a signal as a new failure.

- [ ] **Step 3: Record what moved, what stayed and why**

- [ ] **Step 4: Commit**

---

## Self-Review

**1. Spec coverage**

| Spec requirement (5.4) | Task |
|---|---|
| Token IQ tests move to `tests/token_iq/` mirroring the package | Task 3 |
| A CI shard runs them | Task 4 |
| Conftests re-export fixtures, hooks and underscore-prefixed names | Task 2 |
| `assert_ci_coverage.py` exits 0 | Task 4 step 3 |
| Passes with and without `-n 4`, matching the baseline | Task 3 step 4, Task 5 step 1 |

**2. Placeholder scan**

No "TBD". The conftest contents are enumerated rather than described as "the fixtures", and the
75 files are broken down by where they come from.

**3. Type consistency**

Not applicable: no test is retyped. The nearest equivalent is that no test changes shape, which
`git mv` guarantees and task 3 step 1 relies on.

**4. The thing a reviewer should check hardest**

The conftest re-exports, and specifically whether anyone proved they do anything.

A missing import of a fixture is invisible. The moved test passes, the run is green, and the
isolation it used to get is simply gone. What breaks is a different test, in a different file, on
a later day, and the first instinct will be to call it flaky and add a rerun. Task 2 step 3
exists so that cannot be claimed without evidence: the re-export is removed on purpose and a
sibling has to fail.

Second hardest: the two baseline numbers. 468 against 372 for the same directories means the
reference this phase measures itself against currently disagrees with itself, and no amount of
careful moving fixes a yardstick that is wrong.
