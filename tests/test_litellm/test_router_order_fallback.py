"""
Tests for order-based fallback routing.

When deployments have `order` set in litellm_params, lower order deployments
should be tried first, and higher order deployments should be used as fallbacks
when lower order deployments fail.
"""

import json
from typing import Final, Optional

import httpx
import pytest
from openai import AsyncOpenAI

import litellm
from litellm import Router
from litellm.integrations.custom_logger import CustomLogger
from litellm.router_utils.prompt_caching_cache import PromptCachingCache
from litellm.types.router import RouterRateLimitError
from litellm.utils import _get_deployment_order, _get_order_filtered_deployments

# ---------------------------------------------------------------------------
# Unit tests for _get_order_filtered_deployments
# ---------------------------------------------------------------------------


class TestGetOrderFilteredDeployments:
    def _make_deployment(self, order: Optional[int], dep_id: str) -> dict:
        params: dict = {"model": "gpt-4o", "api_key": "key"}
        if order is not None:
            params["order"] = order
        return {
            "model_name": "test-model",
            "litellm_params": params,
            "model_info": {"id": dep_id},
        }

    def test_returns_min_order_group(self):
        deps = [
            self._make_deployment(1, "a"),
            self._make_deployment(2, "b"),
            self._make_deployment(1, "c"),
        ]
        result = _get_order_filtered_deployments(deps)
        assert len(result) == 2
        assert all(d["model_info"]["id"] in ("a", "c") for d in result)

    def test_target_order_filters_to_exact_level(self):
        deps = [
            self._make_deployment(1, "a"),
            self._make_deployment(2, "b"),
            self._make_deployment(3, "c"),
        ]
        result = _get_order_filtered_deployments(deps, target_order=2)
        assert len(result) == 1
        assert result[0]["model_info"]["id"] == "b"

    def test_target_order_no_match_returns_empty(self):
        deps = [
            self._make_deployment(1, "a"),
            self._make_deployment(2, "b"),
        ]
        result = _get_order_filtered_deployments(deps, target_order=99)
        assert result == []

    def test_target_order_no_match_does_not_reselect_lower_order(self):
        deps = [
            self._make_deployment(1, "a"),
            self._make_deployment(2, "b"),
        ]
        remaining_after_pre_call = [deps[0]]
        result = _get_order_filtered_deployments(remaining_after_pre_call, target_order=2)
        assert result == []

    def test_no_order_set_returns_all(self):
        deps = [
            self._make_deployment(None, "a"),
            self._make_deployment(None, "b"),
        ]
        result = _get_order_filtered_deployments(deps)
        assert len(result) == 2

    def test_empty_list(self):
        result = _get_order_filtered_deployments([])
        assert result == []

    def test_single_order_returns_all_with_that_order(self):
        deps = [
            self._make_deployment(1, "a"),
            self._make_deployment(1, "b"),
        ]
        result = _get_order_filtered_deployments(deps)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# Integration tests for order-based fallback in Router
# ---------------------------------------------------------------------------
























@pytest.mark.asyncio
async def test_generic_api_call_strips_target_order_from_provider_kwargs():
    captured: Final = {}

    async def _fake_provider(**provider_kwargs):
        captured.update(provider_kwargs)
        return "ok"

    router = Router(
        model_list=[
            {
                "model_name": "test-model",
                "litellm_params": {"model": "gpt-4o", "api_key": "key", "order": 2},
                "model_info": {"id": "2"},
            },
        ],
    )
    response = await router._ageneric_api_call_with_fallbacks_helper(
        model="test-model",
        original_generic_function=_fake_provider,
        _target_order=2,
        messages=[{"role": "user", "content": "hi"}],
    )
    assert response == "ok"
    assert captured["model"] == "gpt-4o"
    assert "_target_order" not in captured




def test_check_non_standard_fallback_format():
    from litellm.router_utils.fallback_event_handlers import (
        _check_non_standard_fallback_format,
    )

    # Standard formats
    assert _check_non_standard_fallback_format([{"gpt-3.5-turbo": ["claude-3-haiku"]}]) == False
    assert _check_non_standard_fallback_format([{"model": ["qwen-backup"]}]) == False
    assert _check_non_standard_fallback_format([{"model": ["qwen-backup"], "region": ["us-east-1"]}]) == False

    # Non-standard formats
    assert _check_non_standard_fallback_format([{"model": "qwen-backup"}]) == True
    assert (
        _check_non_standard_fallback_format([{"model": "qwen-backup", "messages": [{"role": "user", "content": "hi"}]}])
        == True
    )
    assert _check_non_standard_fallback_format([{"model": ["qwen-backup"], "api_key": "some-key"}]) == True
