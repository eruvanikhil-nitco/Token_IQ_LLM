import asyncio
from unittest.mock import AsyncMock, patch

import pytest


import json

import litellm
from litellm.caching.dual_cache import DualCache
from litellm.router_utils.pre_call_checks.deployment_affinity_check import (
    DeploymentAffinityCheck,
)


class MockResponse:
    def __init__(self, json_data, status_code):
        self._json_data = json_data
        self.status_code = status_code
        self.text = json.dumps(json_data)
        self.headers = {}

    def json(self):
        return self._json_data










@pytest.mark.asyncio
async def test_async_pre_call_hook_uses_model_map_key_scope():
    """
    Deployment affinity caching uses (user_api_key_hash, model_map_key) -> model_id.
    """

    cache = DualCache()

    callback = DeploymentAffinityCheck(
        cache=cache,
        ttl_seconds=123,
        enable_user_key_affinity=True,
        enable_responses_api_affinity=False,
    )

    kwargs = {
        "model_info": {"id": "model-id-123"},
        "litellm_metadata": {
            "user_api_key_hash": "user-key-abc",
            "deployment_model_name": "claude-sonnet-4-5@20250929",
        },
    }

    await callback.async_pre_call_deployment_hook(kwargs=kwargs, call_type=None)

    expected_cache_key = DeploymentAffinityCheck.get_affinity_cache_key(
        model_group="claude-sonnet-4-5@20250929",
        user_key="user-key-abc",
    )
    assert await cache.async_get_cache(key=expected_cache_key) == {"model_id": "model-id-123"}


@pytest.mark.asyncio
async def test_async_filter_deployments_uses_stable_model_map_key_for_affinity_scope():
    """
    When a stable model-map key can be derived from the deployment set, affinity should
    be scoped to that key (this helps stickiness across aliases).

    This is intentionally tested at the callback level (not via Router), to validate the
    cache key selection logic deterministically.
    """

    user_key = "user-key-abc"
    stable_model_map_key = "claude-sonnet-4-5@20250929"

    cache = AsyncMock()
    cache.async_get_cache = AsyncMock()

    callback = DeploymentAffinityCheck(
        cache=cache,
        ttl_seconds=123,
        enable_user_key_affinity=True,
        enable_responses_api_affinity=False,
    )

    healthy_deployments = [
        {
            "model_name": stable_model_map_key,
            "litellm_params": {"model": f"vertex_ai/{stable_model_map_key}"},
            "model_info": {"id": "deployment-1"},
        },
        {
            "model_name": stable_model_map_key,
            "litellm_params": {
                "model": f"bedrock/global.anthropic.{stable_model_map_key}-v1:0"
            },
            "model_info": {"id": "deployment-2"},
        },
    ]

    expected_cache_key = DeploymentAffinityCheck.get_affinity_cache_key(
        model_group=stable_model_map_key,
        user_key=user_key,
    )

    async def get_cache_side_effect(*, key: str):
        if key == expected_cache_key:
            return {"model_id": "deployment-2"}
        return None

    cache.async_get_cache.side_effect = get_cache_side_effect

    filtered = await callback.async_filter_deployments(
        model="some-router-model-group",
        healthy_deployments=healthy_deployments,
        messages=None,
        request_kwargs={
            "metadata": {"user_api_key_hash": user_key, "model_group": "alias-group"}
        },
        parent_otel_span=None,
    )

    assert len(filtered) == 1
    assert filtered[0]["model_info"]["id"] == "deployment-2"


@pytest.mark.asyncio
async def test_async_filter_deployments_falls_back_when_cached_deployment_is_unhealthy():
    """
    If affinity cache points to a deployment that's no longer healthy, callback should
    return all healthy deployments so router can pick an available one.
    """

    user_key = "user-key-unhealthy"
    stable_model_map_key = "claude-sonnet-4-5@20250929"

    cache = AsyncMock()
    cache.async_get_cache = AsyncMock(return_value={"model_id": "stale-deployment"})

    callback = DeploymentAffinityCheck(
        cache=cache,
        ttl_seconds=123,
        enable_user_key_affinity=True,
        enable_responses_api_affinity=False,
    )

    healthy_deployments = [
        {
            "model_name": stable_model_map_key,
            "litellm_params": {"model": f"vertex_ai/{stable_model_map_key}"},
            "model_info": {"id": "deployment-1"},
        },
        {
            "model_name": stable_model_map_key,
            "litellm_params": {
                "model": f"bedrock/global.anthropic.{stable_model_map_key}-v1:0"
            },
            "model_info": {"id": "deployment-2"},
        },
    ]

    filtered = await callback.async_filter_deployments(
        model="some-router-model-group",
        healthy_deployments=healthy_deployments,
        messages=None,
        request_kwargs={"metadata": {"user_api_key_hash": user_key}},
        parent_otel_span=None,
    )

    assert filtered == healthy_deployments


@pytest.mark.asyncio
async def test_async_filter_deployments_does_not_pin_when_target_order_is_set():
    user_key = "user-key-order-fallback"
    stable_model_map_key = "claude-sonnet-4-5@20250929"
    cache = AsyncMock()
    cache.async_get_cache = AsyncMock(return_value={"model_id": "deployment-1"})
    callback = DeploymentAffinityCheck(
        cache=cache,
        ttl_seconds=123,
        enable_user_key_affinity=True,
        enable_responses_api_affinity=False,
    )
    healthy_deployments = [
        {
            "model_name": stable_model_map_key,
            "litellm_params": {"model": f"vertex_ai/{stable_model_map_key}"},
            "model_info": {"id": "deployment-1"},
        },
        {
            "model_name": stable_model_map_key,
            "litellm_params": {
                "model": f"bedrock/global.anthropic.{stable_model_map_key}-v1:0"
            },
            "model_info": {"id": "deployment-2"},
        },
    ]

    filtered = await callback.async_filter_deployments(
        model="some-router-model-group",
        healthy_deployments=healthy_deployments,
        messages=None,
        request_kwargs={"_target_order": 2, "metadata": {"user_api_key_hash": user_key}},
        parent_otel_span=None,
    )

    assert filtered == healthy_deployments
    cache.async_get_cache.assert_not_called()


@pytest.mark.asyncio
async def test_async_user_key_affinity_ttl_expiry_allows_reroute():
    """
    After affinity TTL expires, cached pinning should no longer filter deployments.
    """

    callback = DeploymentAffinityCheck(
        cache=DualCache(),
        ttl_seconds=1,
        enable_user_key_affinity=True,
        enable_responses_api_affinity=False,
    )

    user_key = "ttl-user-key"
    stable_model_map_key = "claude-sonnet-4-5@20250929"
    healthy_deployments = [
        {
            "model_name": stable_model_map_key,
            "litellm_params": {"model": f"vertex_ai/{stable_model_map_key}"},
            "model_info": {"id": "deployment-1"},
        },
        {
            "model_name": stable_model_map_key,
            "litellm_params": {
                "model": f"bedrock/global.anthropic.{stable_model_map_key}-v1:0"
            },
            "model_info": {"id": "deployment-2"},
        },
    ]

    await callback.async_pre_call_deployment_hook(
        kwargs={
            "model_info": {"id": "deployment-1"},
            "metadata": {
                "user_api_key_hash": user_key,
                "deployment_model_name": stable_model_map_key,
            },
        },
        call_type=None,
    )

    pinned = await callback.async_filter_deployments(
        model="some-router-model-group",
        healthy_deployments=healthy_deployments,
        messages=None,
        request_kwargs={"metadata": {"user_api_key_hash": user_key}},
        parent_otel_span=None,
    )
    assert len(pinned) == 1
    assert pinned[0]["model_info"]["id"] == "deployment-1"

    await asyncio.sleep(1.2)

    after_ttl_expiry = await callback.async_filter_deployments(
        model="some-router-model-group",
        healthy_deployments=healthy_deployments,
        messages=None,
        request_kwargs={"metadata": {"user_api_key_hash": user_key}},
        parent_otel_span=None,
    )
    assert after_ttl_expiry == healthy_deployments


def test_cache_key_does_not_double_hash_user_api_key_hash():
    """
    Proxy typically provides `metadata.user_api_key_hash` as a SHA-256 hex string.
    The affinity cache key should not hash it again.
    """

    user_api_key_hash = (
        "b95b015b66dd02a1c14e1e0a8729211f8ee53ec962658764f4cf58546c2c68e1"
    )
    key = DeploymentAffinityCheck.get_affinity_cache_key(
        model_group="any-model-group",
        user_key=user_api_key_hash,
    )
    assert key.endswith(user_api_key_hash)


def test_get_effective_flags_returns_per_group_config():
    """
    _get_effective_flags should return per-group flags when the model group has an entry
    in model_group_affinity_config, and global flags otherwise.
    """
    callback = DeploymentAffinityCheck(
        cache=AsyncMock(),
        ttl_seconds=60,
        enable_user_key_affinity=True,
        enable_responses_api_affinity=True,
        enable_session_id_affinity=False,
        model_group_affinity_config={
            "gpt-4": ["deployment_affinity"],
            "claude-3": ["session_affinity", "responses_api_deployment_check"],
        },
    )

    # gpt-4: only deployment_affinity
    user_key, responses_api, session_id = callback._get_effective_flags("gpt-4")
    assert user_key is True
    assert responses_api is False
    assert session_id is False

    # claude-3: session_affinity + responses_api_deployment_check
    user_key, responses_api, session_id = callback._get_effective_flags("claude-3")
    assert user_key is False
    assert responses_api is True
    assert session_id is True

    # unconfigured-model: falls back to global flags
    user_key, responses_api, session_id = callback._get_effective_flags(
        "unconfigured-model"
    )
    assert user_key is True
    assert responses_api is True
    assert session_id is False




@pytest.mark.asyncio
async def test_model_group_affinity_config_falls_back_to_global():
    """
    When both global optional_pre_call_checks and model_group_affinity_config are set,
    unconfigured model groups should use the global settings.
    """
    callback = DeploymentAffinityCheck(
        cache=DualCache(),
        ttl_seconds=60,
        enable_user_key_affinity=True,
        enable_responses_api_affinity=False,
        enable_session_id_affinity=False,
        model_group_affinity_config={
            "claude-3": ["session_affinity"],
        },
    )

    stable_model_map_key = "gpt-4"
    user_key = "test-fallback-key"

    healthy_deployments = [
        {
            "model_name": stable_model_map_key,
            "litellm_params": {"model": "openai/gpt-4"},
            "model_info": {"id": "deployment-1"},
        },
        {
            "model_name": stable_model_map_key,
            "litellm_params": {"model": "openai/gpt-4"},
            "model_info": {"id": "deployment-2"},
        },
    ]

    # Set up affinity cache for gpt-4 (should work since global has deployment_affinity)
    await callback.async_pre_call_deployment_hook(
        kwargs={
            "model_info": {"id": "deployment-1"},
            "metadata": {
                "user_api_key_hash": user_key,
                "deployment_model_name": stable_model_map_key,
            },
        },
        call_type=None,
    )

    # gpt-4 not in model_group_affinity_config, so global flags apply (user_key affinity ON)
    filtered = await callback.async_filter_deployments(
        model="gpt-4",
        healthy_deployments=healthy_deployments,
        messages=None,
        request_kwargs={"metadata": {"user_api_key_hash": user_key}},
        parent_otel_span=None,
    )
    assert len(filtered) == 1
    assert filtered[0]["model_info"]["id"] == "deployment-1"


@pytest.mark.asyncio
async def test_model_group_affinity_config_overrides_global():
    """
    When model_group_affinity_config specifies session_affinity for a model group,
    user-key affinity (from global config) should NOT apply to that group.
    """
    callback = DeploymentAffinityCheck(
        cache=DualCache(),
        ttl_seconds=60,
        enable_user_key_affinity=True,
        enable_responses_api_affinity=False,
        enable_session_id_affinity=False,
        model_group_affinity_config={
            "claude-3": ["session_affinity"],
        },
    )

    stable_model_map_key = "claude-3"
    user_key = "test-override-key"

    healthy_deployments = [
        {
            "model_name": stable_model_map_key,
            "litellm_params": {"model": "anthropic/claude-3-opus"},
            "model_info": {"id": "deployment-1"},
        },
        {
            "model_name": stable_model_map_key,
            "litellm_params": {"model": "anthropic/claude-3-opus"},
            "model_info": {"id": "deployment-2"},
        },
    ]

    # Set up user-key affinity cache for claude-3
    cache_key = DeploymentAffinityCheck.get_affinity_cache_key(
        model_group=stable_model_map_key, user_key=user_key
    )
    await callback.cache.async_set_cache(
        cache_key, {"model_id": "deployment-1"}, ttl=60
    )

    # claude-3 has per-group config (session_affinity only), so user-key affinity
    # should NOT apply even though it's globally enabled
    filtered = await callback.async_filter_deployments(
        model="claude-3",
        healthy_deployments=healthy_deployments,
        messages=None,
        request_kwargs={"metadata": {"user_api_key_hash": user_key}},
        parent_otel_span=None,
    )
    # All deployments returned (user-key affinity disabled for this group)
    assert len(filtered) == 2
