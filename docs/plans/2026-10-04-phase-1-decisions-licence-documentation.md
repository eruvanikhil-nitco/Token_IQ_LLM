# Phase 1: decisions, licence and documentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Write down the decisions that make Token IQ an independent codebase, satisfy the
MIT attribution the fork legally owes, and put the documentation into the shape every later
phase refers to.

**Architecture:** Documentation only. No Python, no TypeScript, no configuration that the
running proxy reads. The one thing here that is not prose is the licence, and that is a legal
obligation rather than a preference.

**Tech Stack:** Markdown, `git mv`.

**Spec:** `docs/superpowers/specs/2026-10-04-token-iq-independent-codebase.md`, section 5.1

## Phase 1 changes no behaviour

If a task here would alter what the proxy does, it belongs in another phase. The test for
every change in this plan: a running installation upgraded to this commit behaves identically.

## The rule this phase must not break

**The MIT attribution is permanent, and it is not branding.**

LiteLLM is MIT-licensed. The licence requires its copyright notice and permission text to
travel with every copy of the software, including this one, forever. Removing BerriAI's
copyright line would make every distribution of Token IQ a licence violation.

This sits uncomfortably beside the decision that no `litellm` name appears in the product, so
the two are reconciled explicitly rather than left to judgement: `LICENSE`, `NOTICE` and
`CHANGELOG.md` keep the name permanently, no customer ever sees those files in the product,
and phase 10's gate allowlists exactly those paths. Anyone who later "finishes the rename" by
deleting the notice has broken the law, not completed the work, which is why this plan says
so in the file itself.

## What was checked before writing this

- `enterprise/` holds **0 git-tracked files**. It was removed by decision 06, and the 42
  files on disk are stale `__pycache__` bytecode. So the `LICENSE` clause pointing at
  `enterprise/LICENSE` is genuinely dead text and removing it is correct. The restructure
  document asserted this; it is true, but it was worth confirming before editing a licence
- `NOTICE` does not exist yet
- `README.md` line 21 reads "Built on LiteLLM, which does the provider translation"
- The documentation to move: 22 files in `project_usage/`, 7 specs and 29 plans under
  `docs/superpowers/`, and the blueprint in `docs/Product/`
- Both source documents still carry download suffixes: `TOKEN_IQ_RESTRUCTURE (1).md` and
  `docs/Product/tokeniq-blueprint (1).html`

## Global Constraints

- Documentation only. No behaviour changes
- Move with `git mv` so history follows the file
- No path in the repository may contain a space or a parenthesis when this phase ends
- Folder case is explicit: `docs/product`, lower case. This checkout is on a case-insensitive
  filesystem and CI is not, so a rename that only changes case needs two `git mv` steps
- The name `litellm` stays in `LICENSE`, `NOTICE`, `CHANGELOG.md` and the historical records.
  Everywhere else in documentation it goes
- Human-facing text follows the repository's writing rules: no emoji, no em dash, prose over
  bullets, no trailing full stop at the end of a paragraph

---

## Task 1: The decision records

**Files:**
- Create: `docs/decisions/0022-independent-codebase.md`
- Create: `docs/decisions/0023-remove-litellm-names.md`
- Modify: `project_usage/21-client-facing-rebrand.md` (moved in Task 3)

- [ ] **Step 1: Write 0022, the hard fork**

What was decided, and what it costs. The honest part is the cost: upstream supplied provider
fixes, price updates and security patches, and all three now have to come from somewhere
else. Name where each one goes, pointing at phase 2 rather than restating it.

- [ ] **Step 2: Write 0023, removing the name**

The target names from spec section 2, the compatibility window in phase 7, and the licence
exception. State plainly that the exception is permanent and why.

- [ ] **Step 3: Supersede 0021**

`21-client-facing-rebrand.md` deliberately kept `litellm` identifiers so upstream merges
stayed possible. 0022 reverses exactly that. A note at the top saying "Superseded by 0022 and
0023", not a rewrite: the reasoning was correct when it was written and the record of why it
changed is worth more than a tidy file.

- [ ] **Step 4: Commit**

---

## Task 2: The licence and the notice

**Files:**
- Modify: `LICENSE`
- Create: `NOTICE`

- [ ] **Step 1: Correct the licence**

Remove the clause pointing at `enterprise/LICENSE`, which names a directory the repository no
longer contains. **Keep the MIT text and BerriAI's 2023 copyright line untouched**, and add
`Copyright (c) 2026 NITCO Inc.` beside it. Two copyright holders, both listed, which is what
a derivative work under MIT looks like.

- [ ] **Step 2: Write NOTICE**

That Token IQ includes code derived from LiteLLM, MIT licensed, Copyright (c) 2023 Berri AI.

- [ ] **Step 3: Check the result against the licence text itself**

Read the permission paragraph and confirm the repository now satisfies it. This is the one
step in the phase where being approximately right is not good enough.

- [ ] **Step 4: Commit**

---

## Task 3: Move the documentation

**Files:** as the table below

- [ ] **Step 1: Make the moves**

| From | To |
|---|---|
| `PROJECT.md` | `docs/status.md` |
| `project_usage/NN-slug.md` (21 records) | `docs/decisions/00NN-slug.md` |
| `project_usage/README.md` | `docs/decisions/README.md` |
| `docs/superpowers/specs/2026-09-14-token-iq-product-design.md` | `docs/product/` |
| `docs/superpowers/specs/2026-09-15-cost-platform-reference.md` | `docs/product/` |
| the other 5 specs | `docs/specs/` |
| `docs/superpowers/plans/*` (29 files) | `docs/plans/` |
| `TOKEN_IQ_RESTRUCTURE (1).md` | `docs/plans/2026-10-04-independent-codebase.md` |
| `docs/Product/tokeniq-blueprint (1).html` | `docs/product/token-iq-product-blueprint.html` |

Two traps. `docs/Product` to `docs/product` is a case-only rename, which a
case-insensitive filesystem will silently ignore, so do it through a temporary name and
confirm with `git ls-files` rather than `ls`. And the phase 0 artifacts move with the plans,
so the commands recorded in `docs/status.md` need their paths updated in the same commit.

- [ ] **Step 2: Fix every reference to a moved file**

`rg -n "project_usage/|docs/superpowers|PROJECT\.md"` and work through what it finds,
including references inside `CLAUDE.md`, `README.md` and the plans themselves.

- [ ] **Step 3: Confirm no path has a space or a parenthesis**

- [ ] **Step 4: Commit**

---

## Task 4: The documents that explain the rest

**Files:**
- Create: `docs/README.md`, `docs/product/README.md`
- Modify: `README.md`, `CLAUDE.md`

- [ ] **Step 1: `docs/README.md`, the index and the glossary**

One paragraph per folder. Then the glossary, which matters more than the index: observer-only,
pass-through mode, virtual key, provider usage fact, evidence level with its three values,
attribution, and seat. Every one of those appears in the product's own interface and none of
them explains itself, which is the complaint the owner has already made about the screens.

- [ ] **Step 2: `docs/product/README.md`, how to read the blueprint**

What it is, that it is a specification and not code, where the page model lives inside it,
and the rule that its figures are example data and are never hard-coded.

- [ ] **Step 3: `README.md`**

Keep the content. Replace "Built on LiteLLM, which does the provider translation" at line 21
with an Acknowledgements line pointing at `NOTICE`. Add the repository layout from spec
section 11, described as where things are going rather than where they are, since phases 3
to 9 have not run yet.

- [ ] **Step 4: `CLAUDE.md`**

Keep the existing coding rules, which are good and hard-won: the comment policy, the testing
and mutation-testing standards, the immutability and typing rules. Replace the
upstream-specific parts with the observer-only rule, the counting rule, where code lives, the
naming conventions, and the instruction to update `docs/status.md` at the end of a session.

The counting rule is written out in full rather than referenced, because it is the one rule
whose breach is silent and expensive: the headline total is provider-billed cost plus tool
spend on no provider bill plus seats, and the gateway's figure is attribution that is never
added to it.

- [ ] **Step 5: Commit**

---

## Task 5: Verify and hand over

**Files:**
- Modify: `docs/status.md`

- [ ] **Step 1: Run the checks**

- `rg -n "project_usage/|docs/superpowers|PROJECT\.md"` outside `docs/plans/` and
  `docs/decisions/` returns nothing
- no tracked path contains a space or a parenthesis
- `git ls-files docs/` shows `docs/product`, lower case
- every relative link in the moved documents resolves to a file that exists

The last one needs a script rather than an eye: 29 plans and 22 decision records all moved at
once, and a broken link in a document nobody opens for a month is found by nobody.

- [ ] **Step 2: Record what moved and what the next phase needs**

- [ ] **Step 3: Commit**

---

## Self-Review

**1. Spec coverage**

| Spec requirement (5.1) | Task |
|---|---|
| Decision records 0022 and 0023 | Task 1 |
| 0021 marked superseded | Task 1, step 3 |
| `LICENSE` corrected, `NOTICE` added | Task 2 |
| Documentation moved into `docs/` | Task 3 |
| Index and glossary | Task 4, step 1 |
| `README.md` and `CLAUDE.md` rewritten | Task 4, steps 3 and 4 |
| Both `(1)` files renamed | Task 3, step 1 |
| Reference check returns nothing | Task 5, step 1 |

**2. Placeholder scan**

No "TBD". The glossary terms are listed rather than left to the writer's memory.

**3. Type consistency**

Not applicable: no code changes. The nearest equivalent is path consistency, and Task 5 step 1
checks it mechanically rather than by reading.

**4. The thing a reviewer should check hardest**

The licence.

Everything else in this phase is reversible by a revert, and a wrong word in a glossary costs
somebody five minutes. Deleting or weakening BerriAI's copyright line makes every subsequent
distribution of Token IQ a licence violation, and it would be easy to do by accident while
carrying out a decision whose stated goal is removing that exact name from the codebase.

The second thing to check is the case-only folder rename, because it is the one change in the
phase that can appear to have worked on this machine and fail in CI.
