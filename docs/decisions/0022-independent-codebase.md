# Token IQ becomes an independent codebase

> **Status: DECIDED, 4 Oct 2026.** Carried out by phases 2 to 10 of
> `docs/plans/2026-10-04-independent-codebase.md`.

## The decision

The fork from LiteLLM is disconnected. Upstream is never merged again. No `upstream` remote,
no `git fetch upstream`, no rebasing onto their main.

This **reverses** [0021](0021-client-facing-rebrand.md), which kept every `litellm`
identifier specifically so upstream merges stayed possible. That reasoning was sound while
merging was the plan. It is not the plan any more, so the constraint it imposed goes with it.

## Why

Keeping the merge path open has a price, and the price is paid every day in a codebase that
cannot be named after the product it is. 0021 could only rebrand what a customer sees, which
left the package, the commands, the environment variables, the config keys, the headers, the
metrics and 85 database tables all named after somebody else's project. A product sold as one
installation per customer, running in that customer's own cloud, cannot have an engineer open
it and find a different company's name on everything.

The merge path was also worth less than it looked. Token IQ deletes most of what upstream
ships: routing, load balancing, fallbacks and caching are already switched off by decisions
0001 to 0005 and 0012, because an observer-only gateway must not choose where a request goes.
Agents, MCP, RAG, vector stores, evals, fine-tuning and the realtime, image, OCR and rerank
APIs are all unused. Merging upstream mostly means merging changes to code that is on its way
out.

## What is lost, and where each replacement goes

Upstream did four things for this codebase beyond supplying code. None of them disappears
quietly, so each is named here with its new owner.

**Prices.** `model_prices_and_context_window.json` holds every price Token IQ uses to turn a
response into a cost, and it was downloaded from upstream at startup. This is the one with
teeth: a stale price does not crash anything, it quietly makes every figure in the product
wrong. Replaced by the price pipeline in phase 2, where the file is bundled and read locally,
a daily job opens a pull request for upstream's changes, additions merge automatically,
changes need a named reviewer, and nothing is ever deleted that price history still needs.

**Security fixes.** Replaced by watching upstream's advisories. For each one: check whether
the affected code still exists here after phase 5, fix it, record it in `CHANGELOG.md`. The
scanners in CI stay.

**Provider API changes.** Replaced by contract tests per supported provider, built from the
vendors' published payloads, plus a monthly read of each provider's changelog by a named
person.

**Dependency and base-image updates.** Replaced by Renovate or Dependabot.

The owners of the last three are named in `docs/status.md`. A process with nobody's name on
it is not a process.

## What this does not change

The licence. LiteLLM is MIT-licensed, and the MIT licence requires its copyright notice to
travel with every copy of the software. Disconnecting from upstream does not end that
obligation, and no amount of renaming ever will. See
[0023](0023-remove-litellm-names.md) for how that is reconciled with removing the name
everywhere else.
