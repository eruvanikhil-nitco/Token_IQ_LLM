# Auditing the three model tables

> **Status: FIXED (all three tables), plus a credential-rule fix that affects every
> surface.** No code removed.

## The three tables and what each asks

| Table | Endpoint | Question it answers | Filtered |
|---|---|---|---|
| AI Hub > Model Hub | `/model_group/info` | what can I call | yes |
| Providers > Models | `/model_group/info` | what does this provider serve | yes |
| Models + Endpoints > All Models | `/v2/model/info` | what is deployed on this proxy | yes, opt-in |

All three showed 42 models, the two configured through the Admin UI plus the 40 samples that
ship in `dev_config.yaml` pointing at `os.environ` placeholders for variables nobody set.

## The credential rule was too narrow, and this is the important bit

`has_credentials` tested `litellm_params["api_key"]` alone. That is only how OpenAI-style
providers authenticate. Bedrock uses `aws_access_key_id` or a role, Vertex uses
`vertex_credentials`, Azure uses `azure_ad_token`. A perfectly working Bedrock deployment
carries no `api_key` at all and would have been hidden as "not set up".

It happened to give the right answer here only because the sample Bedrock entries carry
`aws_region_name` and nothing else, and a region says where to call, not that anyone may.

`_CREDENTIAL_FIELDS` now covers the AWS, Vertex and Azure families. Three tests pin it: AWS
keys count, Vertex credentials count, a region alone does not.

**The limit that remains, and it cannot be fixed from the model list.** Ambient credentials
never appear in `litellm_params`: an EC2 instance role, or Google application default
credentials, leave nothing but a model name behind. Such a deployment is invisible to any
check of this kind. It surfaces once it has served traffic, which `_is_set_up` already treats
as its own proof, but until then it will be missing from the page. Anyone deploying on IAM
roles should know that before trusting this filter.

## AI Hub

`ModelHubTable` fetches `/provider/overview` and filters its rows through the same helper the
Providers page uses. This is the surface where an unusable model does the most damage: the
page exists to answer "what can I call", and offering a model that cannot answer sends
someone down a dead end.

The public hub is deliberately left unfiltered. It has no token to ask `/provider/overview`
with, so the provider list stays undefined and everything is shown. Failing open beats
blanking a page because a request could not be made.

## Models + Endpoints, filtered through an opt-in flag

Two things made this one different from the other tables.

**The rows are paginated server-side.** A client-side filter would leave `total_count` and
the page numbers describing rows the table never renders, the same defect the
`exclude_auto_routers` tests already pin. The filter had to be server-side.

**The credentials are gone by the time the handler assembles its output.**
`_enrich_model_info_with_litellm_data` calls `remove_sensitive_info_from_deployment`, which
strips `api_key` and the Vertex credentials, so a filter placed next to
`exclude_auto_routers` near the end of the handler would have seen nothing to test and
dropped every row. It runs immediately after `copy.deepcopy(llm_router.model_list)` instead,
on the raw list.

`configured_only` is a query parameter defaulting to false, matching how `user_models_only`
and `exclude_auto_routers` already work on that endpoint. Only the All Models table passes
it. Every other caller, the health panel, the edit form, the auto-router lookup and the CLI,
keeps the complete list, which is what made this safe to do at all: the original objection
was that filtering the config surface would leave deployments loaded with nothing in the UI
admitting they exist, and an opt-in flag means the endpoint still tells the truth to anyone
who asks plainly.

Live:

```
/v2/model/info?size=100                        total_count 42
/v2/model/info?size=100&configured_only=true   total_count 2
```

`has_credentials` moved from private to public in `provider_overview.py` so both surfaces
share one definition of "configured". Two definitions drifting apart would be worse than the
coupling.

Worth knowing regardless: those config rows are read-only in that table. `/model/delete`
refuses anything not in `LiteLLM_ProxyModelTable`, so a config-file model could be seen but
never edited or removed from the UI. Hiding them costs no management capability.

## Where the filter did not go

`/model_group/info` was left unchanged even though filtering it server-side would have fixed
AI Hub, the Providers table and three model pickers at once. It is a documented upstream
endpoint, consumed by the CLI (`client/cli/commands/model_groups.py`) and by the public hub,
and its docstring names it as the endpoint end users should read. Changing what it returns
would alter behaviour well outside this dashboard.

The consequence is a known gap: the model pickers in `ai_suggestion_modal`,
`template_parameter_modal` and `PromptTable` still offer all 42. They are pickers, so they
have the same problem, and the shared helper is now sitting in `utils/providerVisibility.ts`
ready for them.

## A layering fix that came with it

`filterModelsByVisibleProviders` and `isObservedOnly` started in
`app/(dashboard)/providers/_components/selectors.ts`. A shared component importing from
another route's `_components` is backwards, so both moved to `utils/providerVisibility.ts`
with their own test file. `observedOnlyModels` stayed behind, since it is only meaningful on
the Providers page.

## Tests

Backend goes to 17 in `test_provider_overview.py`, plus 4 in `test_routes_model_info.py`
covering the new parameter: off by default, AWS and Vertex auth counted, a region alone not,
and `total_count` shrinking with the filter. Frontend: 6 new for the moved helper, 2 for AI
Hub, 1 for the All Models opt-in. 241 pass in the models-and-endpoints suites.

Mutation-checked throughout: bypassing the AI Hub memo kills its hiding test, short-circuiting
the helper kills the Providers one, disabling `configured_only` in the handler kills three
backend tests, and flipping the table's opt-in to false kills the UI one.

Two AI Hub tests were passing for the wrong reason before this. Nothing in that file asserted
a model row renders, so the table could have been empty and the suite would not have noticed.
There is now a test that a set-up model is listed, alongside the one that an unusable model
is not.

## How to restore

Revert this commit, then rebuild and redeploy the bundle:

```bash
cd ui/litellm-dashboard && npm run build
rm -rf ../../litellm/proxy/_experimental/out/* && cp -r ./out/* ../../litellm/proxy/_experimental/out/ && rm -rf ./out
```
