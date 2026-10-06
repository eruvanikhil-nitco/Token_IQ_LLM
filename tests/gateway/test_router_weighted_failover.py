"""
Tests for weighted-routing failover (router_settings.enable_weighted_failover).

When enabled and the routing strategy is "simple-shuffle", a retryable failure
on one deployment causes the request to re-pick a different deployment in the
SAME model group (weighted across the remaining deployments) before any
cross-group fallback runs.
"""

from collections import Counter
from typing import Optional
from unittest.mock import AsyncMock, patch

import pytest

from token_iq import gateway
from token_iq.gateway import Router
from token_iq.gateway.utils import _get_excluded_filtered_deployments


# ---------------------------------------------------------------------------
# Unit tests for _get_excluded_filtered_deployments
# ---------------------------------------------------------------------------


def _make_dep(dep_id: str, weight: Optional[int] = None) -> dict:
    params: dict = {"model": "gpt-4o", "api_key": "key"}
    if weight is not None:
        params["weight"] = weight
    return {
        "model_name": "test-model",
        "litellm_params": params,
        "model_info": {"id": dep_id},
    }


class TestGetExcludedFilteredDeployments:
    def test_no_excluded_returns_all(self):
        deps = [_make_dep("a"), _make_dep("b")]
        result = _get_excluded_filtered_deployments(deps, excluded_deployment_ids=None)
        assert len(result) == 2

    def test_empty_excluded_returns_all(self):
        deps = [_make_dep("a"), _make_dep("b")]
        result = _get_excluded_filtered_deployments(deps, excluded_deployment_ids=[])
        assert len(result) == 2

    def test_drops_excluded(self):
        deps = [_make_dep("a"), _make_dep("b"), _make_dep("c")]
        result = _get_excluded_filtered_deployments(deps, excluded_deployment_ids=["b"])
        ids = sorted(d["model_info"]["id"] for d in result)
        assert ids == ["a", "c"]

    def test_all_excluded_returns_empty(self):
        # When every healthy deployment has been excluded, the helper must
        # return an empty list so the caller raises its usual no-deployments
        # error. Returning the original list here would re-include the
        # just-failed deployment and let weighted failover re-pick it.
        deps = [_make_dep("a"), _make_dep("b")]
        result = _get_excluded_filtered_deployments(deps, excluded_deployment_ids=["a", "b"])
        assert result == []

    def test_excluded_set_with_unknown_ids(self):
        deps = [_make_dep("a"), _make_dep("b")]
        result = _get_excluded_filtered_deployments(deps, excluded_deployment_ids=["zzz"])
        assert len(result) == 2

    def test_handles_missing_model_info(self):
        deps = [
            {"model_name": "x", "litellm_params": {"model": "gpt-4o"}},  # no model_info
            _make_dep("b"),
        ]
        result = _get_excluded_filtered_deployments(deps, excluded_deployment_ids=["b"])
        assert len(result) == 1


# ---------------------------------------------------------------------------
# Router helpers (router_code_coverage.py requires these names in a *router* test file)
# ---------------------------------------------------------------------------


def test_set_failed_deployment_id_on_exception():
    router = Router(
        model_list=[
            {
                "model_name": "test-model",
                "litellm_params": {"model": "gpt-4o", "api_key": "key"},
                "model_info": {"id": "dep-a"},
            }
        ],
    )
    exc = Exception("fail")
    dep = _make_dep("dep-a")
    router._set_failed_deployment_id_on_exception(exc, dep)
    assert getattr(exc, "failed_deployment_id", None) == "dep-a"
    router._set_failed_deployment_id_on_exception(exc, _make_dep("dep-b"))
    assert exc.failed_deployment_id == "dep-a"


def test_stamp_failed_deployment_id_with_effective_model_info_prefers_kwargs():
    """kwargs["model_info"] (the dynamic client-side-credential id, when present) must win
    over the static deployment's model_info, so a bad-credential tenant's failures are
    attributed to their own dynamic deployment id, not the shared static one."""
    router = Router(
        model_list=[
            {
                "model_name": "test-model",
                "litellm_params": {"model": "gpt-4o", "api_key": "key"},
                "model_info": {"id": "dep-a"},
            }
        ],
    )
    exc = Exception("fail")
    router._stamp_failed_deployment_id_with_effective_model_info(
        exc, _make_dep("dep-a"), {"model_info": {"id": "dynamic-dep"}}
    )
    assert exc.failed_deployment_id == "dynamic-dep"


def test_stamp_failed_deployment_id_with_effective_model_info_falls_back_to_deployment():
    """With no dynamic id in kwargs (the common, non-client-side-credential case), the
    static deployment's own model_info.id must still be stamped."""
    router = Router(
        model_list=[
            {
                "model_name": "test-model",
                "litellm_params": {"model": "gpt-4o", "api_key": "key"},
                "model_info": {"id": "dep-a"},
            }
        ],
    )
    exc = Exception("fail")
    router._stamp_failed_deployment_id_with_effective_model_info(exc, _make_dep("dep-a"), {})
    assert exc.failed_deployment_id == "dep-a"


@pytest.mark.asyncio
async def test_ageneric_api_call_with_fallbacks_helper_stamps_failed_deployment_id():
    """_ageneric_api_call_with_fallbacks_helper must stamp failed_deployment_id on a
    failure, same as _completion/_acompletion, so callers identifying the failed
    deployment (cooldown, weighted failover) work for this call type too instead of
    depending on which metadata bucket ("metadata" vs "litellm_metadata") it uses."""
    router = Router(
        model_list=[
            {
                "model_name": "test-model",
                "litellm_params": {"model": "openai/gpt-4o", "api_key": "test-key"},
                "model_info": {"id": "dep-a"},
            }
        ],
    )

    async def _failing_original_function(**kwargs):
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError) as exc_info:
        await router._ageneric_api_call_with_fallbacks_helper(
            model="test-model",
            original_generic_function=_failing_original_function,
        )

    assert getattr(exc_info.value, "failed_deployment_id", None) == "dep-a"


@pytest.mark.asyncio
async def test_ageneric_api_call_with_fallbacks_helper_stamps_dynamic_id_for_clientside_credentials():
    """A client-side-credential call (tenant-supplied api_key) generates a dynamic
    deployment id distinct from the shared static deployment. Stamping the static id
    instead would let one tenant's bad credentials cool down the deployment every
    other tenant sharing this config relies on."""
    router = Router(
        model_list=[
            {
                "model_name": "test-model",
                "litellm_params": {"model": "openai/gpt-4o", "api_key": "test-key"},
                "model_info": {"id": "dep-a"},
            }
        ],
    )

    async def _failing_original_function(**kwargs):
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError) as exc_info:
        await router._ageneric_api_call_with_fallbacks_helper(
            model="test-model",
            original_generic_function=_failing_original_function,
            api_key="tenant-supplied-key",
            litellm_metadata={"model_group": "test-model"},
        )

    failed_deployment_id = getattr(exc_info.value, "failed_deployment_id", None)
    assert failed_deployment_id is not None
    assert failed_deployment_id != "dep-a"


@pytest.mark.asyncio
async def test_acompletion_stamps_dynamic_id_for_clientside_credentials():
    """Same bug as the generic-API-call helper above, but in the regular completion
    path: _acompletion's exception handlers must stamp the dynamic client-side-credential
    deployment id, not the shared static deployment's id."""
    router = Router(
        model_list=[
            {
                "model_name": "test-model",
                "litellm_params": {"model": "openai/gpt-4o", "api_key": "test-key"},
                "model_info": {"id": "dep-a"},
            }
        ],
    )

    with patch("token_iq.gateway.acompletion", new_callable=AsyncMock, side_effect=RuntimeError("boom")):
        with pytest.raises(RuntimeError) as exc_info:
            await router._acompletion(
                model="test-model",
                messages=[{"role": "user", "content": "Hello"}],
                api_key="tenant-supplied-key",
                metadata={"model_group": "test-model"},
            )

    failed_deployment_id = getattr(exc_info.value, "failed_deployment_id", None)
    assert failed_deployment_id is not None
    assert failed_deployment_id != "dep-a"


@pytest.mark.asyncio
async def test_acompletion_stamps_dynamic_id_for_clientside_credentials_on_timeout():
    """Same bug as the RuntimeError case above, but for the separate `except litellm.Timeout`
    branch in `_acompletion`: it has its own call to the stamping helper, so a fix that only
    covers the generic `except Exception` branch would leave a caller-supplied timeout
    (`litellm.Timeout` is what `x-litellm-timeout` maps to) stamping the shared static id."""
    router = Router(
        model_list=[
            {
                "model_name": "test-model",
                "litellm_params": {"model": "openai/gpt-4o", "api_key": "test-key"},
                "model_info": {"id": "dep-a"},
            }
        ],
    )

    timeout_exc = gateway.Timeout(message="boom", model="test-model", llm_provider="openai")
    with patch("token_iq.gateway.acompletion", new_callable=AsyncMock, side_effect=timeout_exc):
        with pytest.raises(gateway.Timeout) as exc_info:
            await router._acompletion(
                model="test-model",
                messages=[{"role": "user", "content": "Hello"}],
                api_key="tenant-supplied-key",
                metadata={"model_group": "test-model"},
            )

    failed_deployment_id = getattr(exc_info.value, "failed_deployment_id", None)
    assert failed_deployment_id is not None
    assert failed_deployment_id != "dep-a"


def test_completion_stamps_dynamic_id_for_clientside_credentials():
    """Sync counterpart: _completion's exception handler must stamp the dynamic
    client-side-credential deployment id, not the shared static deployment's id."""
    router = Router(
        model_list=[
            {
                "model_name": "test-model",
                "litellm_params": {"model": "openai/gpt-4o", "api_key": "test-key"},
                "model_info": {"id": "dep-a"},
            }
        ],
    )

    with patch("token_iq.gateway.completion", side_effect=RuntimeError("boom")):
        with pytest.raises(RuntimeError) as exc_info:
            router._completion(
                model="test-model",
                messages=[{"role": "user", "content": "Hello"}],
                api_key="tenant-supplied-key",
                metadata={"model_group": "test-model"},
            )

    failed_deployment_id = getattr(exc_info.value, "failed_deployment_id", None)
    assert failed_deployment_id is not None
    assert failed_deployment_id != "dep-a"






# ---------------------------------------------------------------------------
# Integration tests for weighted-failover end-to-end via Router
# ---------------------------------------------------------------------------




















# ---------------------------------------------------------------------------
# Tests for healthy-deployment-only check in _maybe_run_weighted_failover
# (Issue: weighted failover checked all deployments, not just healthy ones)
# ---------------------------------------------------------------------------






