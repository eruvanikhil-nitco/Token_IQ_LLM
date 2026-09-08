# The Providers tab

> **Status: ADDED.** New page, two new endpoints, and a shared dialog extracted from
> AI Hub. Also folds three small UI removals that landed alongside it.

## What it is

`Model Management` in the AI Gateway nav, holding two children: `Providers` and the
existing `Models + Endpoints`. They answer the same question from two sides, reference and
configuration, so they sit together rather than competing as siblings.

The Providers page itself has two sub-tabs and one provider filter that drives both.

**Overview**: four stat blocks (Total Providers, Total Models, Requests, Cost) over a table
with one row per provider: models configured, models in catalogue, credentials present,
requests, cost, last used.

**Models**: the AI Hub model table, plus a Usage column and a Today / This week / This month
range selector.

## Endpoints

- `GET /provider/overview` — provider rollup and the four totals
- `GET /provider/models` — every catalogue model for a provider, flagged `configured`
- `GET /provider/model-usage?usage_range=day|week|month` — per-model requests, tokens, spend

`build_provider_overview`, `build_provider_models` and `build_model_usage` take their rows
as arguments rather than querying, so the merge logic is testable without a database.

`/provider/models` is currently unused by the UI: the Models sub-tab renders AI Hub's table
instead, which lists configured models rather than the catalogue. It is kept because it is
the only thing that answers "what could we serve but do not", and it is what to reach for
when adding a provider whose catalogue coverage is worse than OpenRouter's.

## Honest labelling

`LiteLLM_DailyUserSpend` buckets by whole UTC day and cannot answer a rolling window, so
nothing here says "24h". The overview returns `rollup_days` and the UI renders whatever it
says; the usage ranges are labelled Today / This week / This month for 1, 7 and 30 whole
days including today.

Rows carrying no provider or no model group are dropped from both rollups. Those are failed
calls that never reached a provider, and counting them would show traffic against a phantom
model that costs nothing. Verified: 8 such rows exist, all `status=failure` with zero
tokens.

A model with no traffic in the range renders `—`, not `0`, because unused and "used but
free" are different facts. This matters: `gpt-4o-mini` genuinely has requests and zero spend.

## The dialog extraction

`ModelHubDetailsDialog` was pulled out of `ModelHubTable` so both AI Hub and Providers show
the same detail view. Duplicating 147 lines would have guaranteed drift.

That also removed real duplication found on the way: `formatCost`, `getModelCapabilities`
and `formatCapabilityName` existed twice, once in `ModelHubTable` and once in
`ModelHubTableColumns`. The canonical copies are now exported from the columns file and the
dead ones deleted. `ModelHubTable` drops from 1,186 to 1,040 lines.

## A routing trap worth recording

Adding a page under `app/(dashboard)/` and a nav entry is not enough. `leftnav.tsx` picks
its href with `MIGRATED_PAGES[item.page] ? migratedHref(...) : legacyPageHref(...)`, so an
unregistered page falls through to `/ui/?page=<key>`, which the legacy switch does not know,
and it silently renders its default panel: Virtual Keys.

The page served fine at its own URL the whole time. Curling the route proves nothing about
what the nav does. Any new page needs an entry in `MIGRATED_PAGES`.

## Three removals folded in

**Slack and GitHub icons** in the header are now inert `<span>` elements with
`pointer-events-none`, wrapped in `aria-hidden`. They linked to `litellm.ai/support` and the
BerriAI repo, which are not this deployment's community. Tooltips dropped too, since they
named LiteLLM. Give an entry an `href` to make it a real link again.

**The Tools group** (Search Tools, Vector Stores, Tool Policies) is gone from the nav, along
with its dead `vector-stores` filter branch and the icons, `isTeamAdmin` memo, `useTeams`
hook and `isUserTeamAdminForAnyTeam` import that went unused with it. The pages remain
routable by URL. Worth knowing: `VectorStorePreCallHook` still rewrites a user's prompt with
retrieved context if a vector store is ever configured, which is the sharpest violation of
the observer-only requirement in this codebase, and nothing guards it.

**The Default Organization row** in Default Team Settings is gone, with the
`useOrganizations` hook, `OrganizationDropdown` import, `getOrganizationLabel` helper and
`Organization` type that only it used. Organizations is enterprise-gated, its nav entry was
already removed, and the database holds none, so the dropdown could only ever offer an empty
list. `organization_id` stays in `SettingsValues` because the API still returns it.

## Known duplication this creates

There are now three tables listing configured models: `All Models` under Models + Endpoints,
`AI Hub`, and `Providers > Models`. Nesting the nav did not reduce that count. Deciding
which is canonical is outstanding work.

## Tests

7 for the discovery merge, in `test_model_discovery.py`. The Providers page components have
none yet, which is the main gap in this change.

## How to restore

Revert this commit, then rebuild and redeploy the bundle:

```bash
cd ui/litellm-dashboard && npm run build
rm -rf ../../litellm/proxy/_experimental/out/* && cp -r ./out/* ../../litellm/proxy/_experimental/out/ && rm -rf ./out
```
