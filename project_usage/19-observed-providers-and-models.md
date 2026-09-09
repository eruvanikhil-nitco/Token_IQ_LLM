# Providers tab reports observed traffic, not just configuration

> **Status: FIXED.** Two correctness bugs in change 16, plus `store_model_in_db` added to
> the dev config. No code removed.

## What went wrong first, and it was not the code

OpenRouter vanished from the Providers tab. The cause was an incomplete restart, not a lost
change: the two OpenRouter models live in `LiteLLM_ProxyModelTable`, added through the Admin
UI, and loading DB-backed models requires `store_model_in_db`. That was never in
`dev_config.yaml`, so it had been passed as an environment variable. A restart without it
brought the proxy up with only the 40 models the config file lists.

The rows were untouched the whole time:

```
select model_name from "LiteLLM_ProxyModelTable";
 openrouter/openai/gpt-4o
 openrouter/openai/gpt-4o-mini
```

`general_settings.store_model_in_db: true` is now in `dev_config.yaml`, verified by restarting
with no environment variable at all and getting 42 models and seven providers back.

## The two real bugs it exposed

**A provider with traffic but no deployment got no row at all.** `build_provider_overview`
iterated only `configured.items()`, so a provider absent from `model_list` was skipped, and
because the four totals sum over the rows, its requests and spend were dropped from the
totals too. On an observer gateway that is backwards: real money left the building and the
page reported zero. Rows are now the union of configured providers and providers seen in
usage, with the ones no longer configured flagged `is_configured=False`.

Replaying the real rows against an empty model list, which is exactly the state the proxy
was in before the config fix:

```
  openrouter   is_configured=False models=0 reqs=12 last_used=2026-09-08
  totals -> requests 12 spend 0.0010225
```

Before, that produced no rows and zero totals.

**`last_used` was computed from the 2-day rollup window**, so a provider last called a month
ago reported `None`, which the table renders as never used. It now comes from a separate
full-history query. That query is a `group_by(by=["custom_llm_provider"], max={"date": True})`
rather than `find_many(distinct=[...])`, following the precedent in
`tag_management_endpoints.py`: Prisma's `distinct` fetches every column of every row and
dedupes in application code, which does not scale on this table.

The same gap existed in the Models sub-tab, which built its rows from the configured model
list and joined usage onto them, so a model that recorded traffic and was later removed was
fetched and then discarded. `build_model_usage` now returns the providers that served each
model group, and `observedOnlyModels` in `selectors.ts` turns the leftovers into rows flagged
"Not configured". The provider attribution is what lets those rows survive the page's
provider filter, which has nothing else to file them under.

## A `# type: ignore` that did nothing

`provider_overview.py:168` carried `# type: ignore[arg-type]` on the `last_used` assignment.
The project bans it (LIT009) and `pyrightconfig.json` sets `enableTypeIgnoreComments` to
false, so it was silently inert. It is gone: the untyped `dict[str, object]` accumulator it
was papering over is now a frozen `_ProviderUsage` dataclass, and both rollups are built in
one shot with `itertools.groupby` instead of seeding an empty dict and mutating it.

## Honest limits

A provider whose only traffic predates the rollup window still shows `requests=0`, correctly,
but now carries a real `last_used` date instead of claiming it was never used. Widening the
Overview's window to match the Models tab's selector is a separate decision and was not made
here.

Rows whose `custom_llm_provider` is blank stay excluded from provider rollups. On this
database that is 7 rows and 12 requests, calls that recorded a model group but no provider.
They still appear in the Models tab, attributed to a model with an empty provider list.

## Tests

11 new backend tests in `tests/test_litellm/proxy/management_endpoints/test_provider_overview.py`,
which had no mapped test file before. Mutation-checked: reverting the row union kills three,
zeroing `last_used` kills one, and dropping the provider attribution kills two.

Frontend goes from 30 to 39. Mutation-checked: making `observedOnlyModels` return nothing
kills three across all three files, and never rendering the "Not configured" badge kills one.

## How to restore

Revert this commit, then rebuild and redeploy the bundle:

```bash
cd ui/litellm-dashboard && npm run build
rm -rf ../../litellm/proxy/_experimental/out/* && cp -r ./out/* ../../litellm/proxy/_experimental/out/ && rm -rf ./out
```
