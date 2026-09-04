# Pre-routing model substitution

> **Status: REFUSED at registration.** No strategy module was deleted; a deployment that
> would install one is rejected when the Router registers it.

## What these are

Four strategies pick the model from the request rather than taking the one the caller
named: the semantic auto-router, the complexity router, the adaptive router and the quality
router. Each resolves a `PreRoutingHookResponse` whose `model` replaces the caller's before
routing. LAR-1 is a fifth of the same kind, installing a custom routing strategy that picks
from an agent confidence score in request metadata.

## Why they are refused

The caller commits to a model and a different one serves the request, with nothing in the
response to say so. Unlike a fallback this is not an error path, it is the feature working
as designed.

## How

`Router._reject_pre_routing_deployment` runs in `_add_deployment`, which every deployment
passes through whether it came from config.yaml or the database. It keys off
`classify_strategy_router_model`, the same classifier the Router registers by, so a strategy
kind added upstream is refused by default rather than silently admitted.

LAR-1 is handled separately, through `_REMOVED_ROUTING_STRATEGIES` in
`_validate_routing_strategy`.

## The ordering bug this uncovered

Adding `lar1` to the rejected set was not enough. `router.py` applied it in `__init__` before
`routing_strategy_init` ever validated, so the custom picker was installed and validation
never ran. `_validate_routing_strategy` is now called ahead of that branch.

This was only found because the test cleanup forced a read of `test_lar1_routing.py`. The
guard had been reported as verified before it.

## Test fallout

The guards made a large amount of the upstream suite unreachable, and it was pruned rather
than skipped. Deleted outright: `test_complexity_router`, `test_quality_router`,
`test_lar1_routing`, `test_lowest_latency`, `test_auto_router`, `test_litellm_encoder`,
`test_router_tag_routing`, `test_router_tag_regex_routing`, `adaptive_router/`,
`test_router_routing_groups` (per-group strategies), `test_router_routing_plugins`
(pre-routing pool narrowing) and `test_savings_baseline` (only reachable via the removed
strategies). Roughly 3,900 lines came out of `test_router.py` and 4,042 more across 15 files.

Most of what went was affinity: session-id, encrypted-content, deployment and prompt-caching
affinity all exist to pin a request to one deployment *within a group*. With one deployment
per `model_name` that holds by construction, so the machinery is inert. Same for
`model_group_info` capability intersection and the fully-blocked / fully-unhealthy
aggregations. The guard did not only disable load balancing; it made a whole layer of the
Router unreachable.

`_router_with_two_deployments` was rewritten to give each deployment its own `model_name`
rather than deleted, which fixed 7 tests whose second deployment was scaffolding.

`TestModelsRouteExemptFromDisableLLMEndpoints` was also removed, but for a different reason:
it loads `EnterpriseRouteChecks` from `enterprise/litellm_enterprise/proxy/auth/route_checks.py`,
deleted in `728daee2d8`. Fallout from the enterprise removal, missed at the time because only
the pass-through and UI suites were run then.

## Two failures deliberately left red

Neither is caused by this work and neither is hidden behind a skip.

`test_post_custom_auth_expired_key_returns_unauthorized` builds a naive
`datetime.now() - timedelta(minutes=1)` while `_run_post_custom_auth_checks` stamps naive
values as UTC. On a machine ahead of UTC the "expired" key lands in the future and nothing
raises. Measured on this box at +05:30: expiry resolved to 18:39 UTC against a current time
of 13:10 UTC. Fails on IST, passes in CI.

`test_ttft_keepalive_unconfigured_leaves_the_call_completely_untouched` passes alone (7
passed) and fails only in a combined run. Order-dependent pollution.

## Verification

Router suites 318 passed, pass-through 706 passed, and the combined run across 14 affected
paths reached 2,904 passed with only the two failures above remaining.

## How to restore

Delete the `_reject_pre_routing_deployment` call in `_add_deployment` and its method, drop
`"lar1"` from `_REMOVED_ROUTING_STRATEGIES`, and move `_validate_routing_strategy` back
below the lar1 branch in `__init__`. The deleted tests are in this commit's diff.
