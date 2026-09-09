from litellm.proxy.management_endpoints.provider_overview import (
    build_model_usage,
    build_provider_overview,
)


def _deployment(model: str, api_key: str | None = None) -> dict[str, object]:
    params: dict[str, object] = {"model": model}
    if api_key is not None:
        params["api_key"] = api_key
    return {"model_name": model, "litellm_params": params}


def test_a_provider_with_traffic_but_no_deployment_still_gets_a_row() -> None:
    result = build_provider_overview(
        model_list=[_deployment("anthropic/claude-haiku")],
        usage_rows=[{"custom_llm_provider": "openrouter", "api_requests": 24, "spend": 0.00642}],
    )

    providers = {row.provider: row for row in result.providers}
    assert set(providers) == {"anthropic", "openrouter"}
    assert providers["openrouter"].is_configured is False
    assert providers["openrouter"].models_configured == 0
    assert providers["openrouter"].has_credentials is False
    assert providers["anthropic"].is_configured is True


def test_traffic_from_an_unconfigured_provider_reaches_the_totals() -> None:
    result = build_provider_overview(
        model_list=[_deployment("anthropic/claude-haiku")],
        usage_rows=[
            {"custom_llm_provider": "openrouter", "api_requests": 24, "spend": 0.00642},
            {"custom_llm_provider": "anthropic", "api_requests": 10, "spend": 0.00038},
        ],
    )

    # The spend is real money that left the gateway; filing it under "no row" would
    # under-report the bill.
    assert result.total_requests == 34
    assert result.total_spend == 0.0068
    assert result.total_providers == 2


def test_a_configured_provider_with_no_traffic_is_still_listed() -> None:
    result = build_provider_overview(
        model_list=[_deployment("bedrock/claude-sonnet", api_key="sk-test")],
        usage_rows=[],
    )

    row = result.providers[0]
    assert row.provider == "bedrock"
    assert row.is_configured is True
    assert row.has_credentials is True
    assert row.requests == 0
    assert row.last_used is None


def test_last_used_comes_from_full_history_not_the_rollup_window() -> None:
    result = build_provider_overview(
        model_list=[_deployment("openai/gpt-4")],
        usage_rows=[],
        last_used_by_provider={"openai": "2026-08-02"},
    )

    # No usage inside the window, but the provider was plainly used. Reporting None here
    # would claim a provider had never served traffic when it had.
    assert result.providers[0].requests == 0
    assert result.providers[0].last_used == "2026-08-02"


def test_a_provider_never_used_reports_no_date() -> None:
    result = build_provider_overview(
        model_list=[_deployment("openai/gpt-4")],
        usage_rows=[],
        last_used_by_provider={"anthropic": "2026-08-02"},
    )

    assert result.providers[0].last_used is None


def test_rows_with_no_provider_are_left_out_of_the_totals() -> None:
    result = build_provider_overview(
        model_list=[_deployment("openai/gpt-4")],
        usage_rows=[
            {"custom_llm_provider": None, "api_requests": 8, "spend": 0.0},
            {"custom_llm_provider": "", "api_requests": 3, "spend": 0.0},
            {"custom_llm_provider": "openai", "api_requests": 1, "spend": 0.5},
        ],
    )

    # Failed calls that never reached a provider would otherwise inflate the request count.
    assert result.total_requests == 1
    assert result.total_providers == 1


def test_requests_and_spend_accumulate_across_days_for_one_provider() -> None:
    result = build_provider_overview(
        model_list=[_deployment("openai/gpt-4")],
        usage_rows=[
            {"custom_llm_provider": "openai", "api_requests": 2, "spend": 0.25},
            {"custom_llm_provider": "openai", "api_requests": 3, "spend": 0.5},
        ],
    )

    assert result.providers[0].requests == 5
    assert result.providers[0].spend == 0.75


def test_a_model_carries_the_provider_that_served_it() -> None:
    result = build_model_usage(
        range_key="week",
        start_date="2026-09-03",
        days=7,
        usage_rows=[
            {
                "model_group": "openrouter/openai/gpt-4o",
                "custom_llm_provider": "openrouter",
                "api_requests": 24,
                "prompt_tokens": 1000,
                "completion_tokens": 458,
                "spend": 0.00642,
            }
        ],
    )

    row = result.usage[0]
    assert row.model_group == "openrouter/openai/gpt-4o"
    # Without this the Models table has nothing to file an unconfigured model under.
    assert row.providers == ["openrouter"]
    assert row.requests == 24
    assert row.tokens == 1458


def test_a_model_served_by_two_providers_lists_both() -> None:
    result = build_model_usage(
        range_key="week",
        start_date="2026-09-03",
        days=7,
        usage_rows=[
            {"model_group": "gpt-4", "custom_llm_provider": "openai", "api_requests": 1, "spend": 0.1},
            {"model_group": "gpt-4", "custom_llm_provider": "azure_ai", "api_requests": 2, "spend": 0.2},
        ],
    )

    assert result.usage[0].providers == ["azure_ai", "openai"]
    assert result.usage[0].requests == 3


def test_a_model_row_with_no_provider_still_reports_its_usage() -> None:
    result = build_model_usage(
        range_key="week",
        start_date="2026-09-03",
        days=7,
        usage_rows=[{"model_group": "gpt-4", "custom_llm_provider": None, "api_requests": 4, "spend": 0.0}],
    )

    # The model group is known even when the provider column is blank, so the usage is
    # still attributable to a model even though it cannot be filed under a provider.
    assert result.usage[0].providers == []
    assert result.usage[0].requests == 4


def test_rows_with_no_model_group_are_dropped() -> None:
    result = build_model_usage(
        range_key="week",
        start_date="2026-09-03",
        days=7,
        usage_rows=[
            {"model_group": None, "model": None, "custom_llm_provider": "openai", "api_requests": 9, "spend": 0.0},
            {"model_group": "gpt-4", "custom_llm_provider": "openai", "api_requests": 1, "spend": 0.0},
        ],
    )

    assert [row.model_group for row in result.usage] == ["gpt-4"]
