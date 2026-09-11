from __future__ import annotations

from litellm.proxy.management_endpoints.courier_coverage import (
    pricing_branch_providers,
    provider_courier_coverage,
)


def test_a_provider_with_a_route_and_a_usage_reader_reads_as_covered():
    coverage = provider_courier_coverage("openrouter")
    assert coverage.has_route is True
    assert coverage.reads_usage is True


def test_a_provider_with_no_courier_route_says_so():
    coverage = provider_courier_coverage("voyage")
    assert coverage.has_route is False
    assert coverage.is_covered is False


def test_providers_priced_by_the_dispatch_are_reported_covered_too():
    """Two mechanisms price courier traffic. Anthropic and Vertex go through the
    dispatch rather than a pass-through config, and a report that only knew about
    configs would tell an admin they bill nothing, which is the opposite of true."""
    for provider in ("anthropic", "vertex_ai", "openai"):
        assert provider_courier_coverage(provider).reads_usage is True, provider


def test_route_coverage_is_read_from_the_list_the_request_path_gates_on():
    """A hand-maintained table drifts from the code and then lies to an admin."""
    from litellm.proxy._types import LiteLLMRoutes

    for provider in ("openrouter", "anthropic", "bedrock", "voyage"):
        expected = f"/{provider}" in LiteLLMRoutes.mapped_pass_through_routes.value
        assert provider_courier_coverage(provider).has_route is expected, provider


def test_every_pricing_branch_in_the_dispatch_is_accounted_for():
    """The guard that stops this rotting. Adding a provider branch to the success
    handler without teaching this module about it fails here, rather than silently
    reporting that provider as billing nothing."""
    from litellm.proxy._types import LiteLLMRoutes

    known_prefixes = {route.lstrip("/") for route in LiteLLMRoutes.mapped_pass_through_routes.value}
    unresolved = [p for p in pricing_branch_providers() if p not in known_prefixes]
    assert unresolved == [], (
        f"these pricing branches map to no known pass-through route prefix: {unresolved}. "
        "Add the alias in courier_coverage, or the coverage report will misreport them."
    )


def test_bedrock_is_reported_covered_now_that_its_reader_is_wired():
    coverage = provider_courier_coverage("bedrock")
    assert coverage.has_route is True
    assert coverage.reads_usage is True


def test_a_deployment_without_the_opt_in_is_reported_as_not_ready():
    """Courier mode uses a deployment's credential only when that deployment is opted
    in. Without it every call fails on credentials with nothing explaining why, so the
    report has to name the deployments that still need it."""
    from litellm.proxy.management_endpoints.courier_coverage import deployment_readiness

    deployments = [
        {"model_name": "a", "litellm_params": {"model": "openrouter/openai/gpt-4o-mini", "use_in_pass_through": True}},
        {"model_name": "b", "litellm_params": {"model": "openrouter/anthropic/claude-haiku-4.5"}},
    ]

    readiness = deployment_readiness(deployments, provider="openrouter")

    assert readiness.ready == ("a",)
    assert readiness.needs_opt_in == ("b",)


def test_deployments_for_other_providers_are_ignored():
    from litellm.proxy.management_endpoints.courier_coverage import deployment_readiness

    deployments = [{"model_name": "x", "litellm_params": {"model": "anthropic/claude-haiku-4-5"}}]

    readiness = deployment_readiness(deployments, provider="openrouter")

    assert readiness.ready == ()
    assert readiness.needs_opt_in == ()
