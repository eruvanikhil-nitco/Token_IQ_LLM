import litellm
import pytest

from litellm.proxy.management_endpoints.model_discovery import (
    merge_with_local_pricing,
)


def test_a_model_the_catalogue_prices_is_reported_as_priced() -> None:
    result = merge_with_local_pricing(
        custom_llm_provider="openrouter",
        discovered_models=["openrouter/openai/gpt-4o"],
    )

    assert result.total == 1
    assert result.priced == 1
    assert result.unpriced == 0
    model = result.models[0]
    assert model.has_local_pricing is True
    assert model.input_cost_per_token is not None
    assert model.output_cost_per_token is not None


def test_a_model_the_catalogue_cannot_price_is_flagged_not_hidden() -> None:
    """The gap this exists to close: a model the provider serves but we cannot price.
    It must be returned, and marked, rather than dropped or silently costed at zero."""
    result = merge_with_local_pricing(
        custom_llm_provider="openrouter",
        discovered_models=["openrouter/some-vendor/model-that-does-not-exist"],
    )

    assert result.total == 1
    assert result.priced == 0
    assert result.unpriced == 1
    model = result.models[0]
    assert model.has_local_pricing is False
    assert model.input_cost_per_token is None
    assert model.output_cost_per_token is None


def test_a_mixed_list_counts_both_sides() -> None:
    result = merge_with_local_pricing(
        custom_llm_provider="openrouter",
        discovered_models=[
            "openrouter/openai/gpt-4o",
            "openrouter/some-vendor/unknown-a",
            "openrouter/some-vendor/unknown-b",
        ],
    )

    assert (result.total, result.priced, result.unpriced) == (3, 1, 2)
    assert result.priced + result.unpriced == result.total


def test_duplicates_collapse_and_order_is_stable() -> None:
    """The provider may repeat a name across pages; the dropdown must not."""
    result = merge_with_local_pricing(
        custom_llm_provider="openrouter",
        discovered_models=["openrouter/b", "openrouter/a", "openrouter/b"],
    )

    assert result.total == 2
    assert [m.model_name for m in result.models] == ["openrouter/a", "openrouter/b"]


def test_an_empty_provider_answer_is_not_an_error_here() -> None:
    """The endpoint decides what an empty answer means; the merge just reports it."""
    result = merge_with_local_pricing(custom_llm_provider="openrouter", discovered_models=[])

    assert (result.total, result.priced, result.unpriced) == (0, 0, 0)
    assert result.models == []


def test_a_catalogue_row_without_costs_does_not_count_as_priced(monkeypatch: pytest.MonkeyPatch) -> None:
    """Some rows exist for metadata only. Counting those as priced would report a
    metering hole as covered, which is the exact failure this flag guards against."""
    monkeypatch.setitem(litellm.model_cost, "openrouter/metadata-only", {"max_tokens": 4096})

    result = merge_with_local_pricing(
        custom_llm_provider="openrouter",
        discovered_models=["openrouter/metadata-only"],
    )

    assert result.unpriced == 1
    assert result.models[0].has_local_pricing is False


def test_one_sided_pricing_still_counts_as_priced(monkeypatch: pytest.MonkeyPatch) -> None:
    """An embedding model prices input only. Treating that as unpriced would be a false alarm."""
    monkeypatch.setitem(litellm.model_cost, "openrouter/input-only", {"input_cost_per_token": 1e-06})

    result = merge_with_local_pricing(
        custom_llm_provider="openrouter",
        discovered_models=["openrouter/input-only"],
    )

    assert result.priced == 1
    model = result.models[0]
    assert model.has_local_pricing is True
    assert model.input_cost_per_token == 1e-06
    assert model.output_cost_per_token is None
