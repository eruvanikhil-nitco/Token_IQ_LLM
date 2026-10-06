from __future__ import annotations

from token_iq.api.courier_coverage import (
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
    from token_iq.gateway.proxy._types import LiteLLMRoutes

    for provider in ("openrouter", "anthropic", "bedrock", "voyage"):
        expected = f"/{provider}" in LiteLLMRoutes.mapped_pass_through_routes.value
        assert provider_courier_coverage(provider).has_route is expected, provider


def test_every_pricing_branch_in_the_dispatch_is_accounted_for():
    """The guard that stops this rotting. Adding a provider branch to the success
    handler without teaching this module about it fails here, rather than silently
    reporting that provider as billing nothing."""
    from token_iq.gateway.proxy._types import LiteLLMRoutes

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


def test_the_providers_a_team_reaches_come_from_its_deployments():
    """The panel warns per provider, so it has to know which providers are in play. A
    warning about a provider the team was never granted is noise, and noise teaches
    admins to skim the one warning that mattered."""
    from token_iq.api.courier_coverage import providers_of

    deployments = [
        {"model_name": "a", "litellm_params": {"model": "openrouter/openai/gpt-4o-mini"}},
        {"model_name": "b", "litellm_params": {"model": "anthropic/claude-haiku-4-5"}},
        {"model_name": "c", "litellm_params": {"model": "openrouter/meta/llama-3"}},
    ]

    assert providers_of(deployments) == ("anthropic", "openrouter")


def test_a_deployment_naming_no_provider_is_not_guessed_at():
    from token_iq.api.courier_coverage import providers_of

    assert providers_of([{"model_name": "a", "litellm_params": {"model": "gpt-4o-mini"}}]) == ()
