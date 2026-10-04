# Removing the LiteLLM name

> **Status: DECIDED, 4 Oct 2026.** Carried out by phases 6 to 10 of
> `docs/plans/2026-10-04-independent-codebase.md`.

## The decision

The name `litellm`, in any case, is removed from the codebase. Package, modules, classes and
functions. Commands. Environment variables and config keys. HTTP headers and metric names.
Database models and tables. Docker images, folders, UI text and log output.

[0022](0022-independent-codebase.md) makes this possible by ending the merges that
[0021](0021-client-facing-rebrand.md) was protecting.

## The exception, which is permanent

Four places keep the name forever:

- `LICENSE`, which carries BerriAI's copyright notice and the MIT permission text
- `NOTICE`, which states that Token IQ includes code derived from LiteLLM
- `CHANGELOG.md`, where upgrade notes name the settings that changed
- the decision records and historical plans, which are the record of how this happened

The first two are a legal obligation, not an oversight. The MIT licence requires the original
copyright notice and permission text to be included in all copies of the software. Deleting
them does not complete this decision, it makes every distribution of Token IQ a licence
violation.

This matters because the mistake is so natural. Somebody finishing the rename, working from
a decision that says "no `litellm` name anywhere", greps the repository, finds the name in
`LICENSE`, and removes it believing they are doing the job. They are not. No customer ever
sees those files in the product, so they cost the rename nothing, and phase 10's gate
allowlists exactly those paths so the test cannot be satisfied by deleting them.

Two more entries are allowlisted temporarily: the compatibility module from phase 7, until
the release after the transition, and the price update script, which names the upstream
source it fetches from.

## Target names

| Today | New name |
|---|---|
| Python package `litellm` | `token_iq.gateway` |
| Token IQ's own modules | `token_iq.<module>` |
| Distribution `litellm` | `token-iq` |
| `litellm-proxy-extras` | `token-iq-migrations` |
| Commands `litellm`, `litellm-proxy`, `lite` | `token-iq`, `token-iq-cli` |
| `LITELLM_*` | `TOKEN_IQ_*` |
| `litellm_settings`, `litellm_params` | `gateway_settings`, `model_params` |
| `x-litellm-*` | `x-token-iq-*` |
| `litellm_*` metrics | `token_iq_*` |
| `LiteLLM_*` Prisma models | prefix dropped, snake_case tables later |
| `LiteLLMRoutes`, `litellm_logging`, `litellm_core_utils` | `GatewayRoutes`, `gateway_logging`, `core_utils` |
| `ui/litellm-dashboard/` | `ui/dashboard/` |
| `tests/test_litellm/` | `tests/gateway/` |

## In layers, with one transition release

A rename that breaks a customer's running configuration on upgrade is not acceptable, so the
parts a customer configures move separately from the parts they do not.

Phase 6 renames the package and the identifiers, which no customer ever types. Phases 7 to 9
move the environment variables, config keys, headers, database names, metrics and cache keys,
each with a compatibility window: the new name is read first, the old one still works and
warns once, and `CHANGELOG.md` lists every rename. One module, `compat.py`, holds all of it
and is deleted a release later.

The database is the slowest on purpose. Phase 8 renames the models in code while `@@map`
keeps the real tables untouched, and only a later release, after a rehearsal against a copy
of a real installation and the owner's approval, renames the tables themselves.

## The size of it

Measured on 4 Oct 2026: 183,380 occurrences across 6,591 files, plus 3,458 in the history and
legal text that stay. Split by the phase that removes them: 136,015 in Python, 18,592 config
keys, 17,049 metrics, 6,060 in UI source, 3,072 environment variables, 1,315 headers, 271
Prisma model references, 8 console scripts.

0021 recorded 521,641 occurrences. That figure counted `node_modules` and is roughly three
and a half times the real number. It is corrected here because a plan sized against it would
schedule the wrong amount of work.
