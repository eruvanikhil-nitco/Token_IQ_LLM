"""
Tests for health check failures integrating with allowed_fails_policy cooldown pipeline.

When enable_health_check_routing is True and a health check fails, the failure
should increment the same counters used by allowed_fails_policy, using the
actual exception type from the health check error.
"""

from unittest.mock import patch

import pytest

from token_iq import gateway
from token_iq.gateway.proxy.health_check import run_with_timeout
from token_iq.gateway.router import Router
from token_iq.gateway.types.router import AllowedFailsPolicy


def _make_model(model_id: str, model_name: str = "gpt-4") -> dict:
    return {
        "model_name": model_name,
        "litellm_params": {"model": model_name, "api_key": "fake-key"},
        "model_info": {"id": model_id},
    }


class TestAhealthCheckExceptionPreservation:
    """Test that ahealth_check() preserves the exception object in its return dict."""

    @pytest.mark.asyncio
    async def test_run_with_timeout_returns_timeout_exception(self):
        """run_with_timeout should return a litellm.Timeout in the 'exception' key on timeout."""
        import asyncio

        async def slow_task():
            await asyncio.sleep(10)

        result = await run_with_timeout(slow_task(), timeout=0.01)

        assert "error" in result
        assert "exception" in result
        assert isinstance(result["exception"], gateway.Timeout)


class TestHealthCheckEndpointExceptionPropagation:
    """Test that _perform_health_check returns exceptions via exceptions_by_model_id."""

    @pytest.mark.asyncio
    async def test_unhealthy_endpoint_dict_exception_in_map(self):
        """When ahealth_check returns {"error": ..., "exception": e}, the exception
        must appear in exceptions_by_model_id keyed by model_id — not in the endpoint dict.
        """
        from unittest.mock import AsyncMock, patch

        from token_iq.gateway.proxy.health_check import _perform_health_check

        auth_error = gateway.AuthenticationError(
            message="Invalid key", llm_provider="openai", model="gpt-4"
        )
        model_list = [
            {
                "model_name": "gpt-4",
                "litellm_params": {"model": "gpt-4", "api_key": "fake"},
                "model_info": {"id": "deploy-abc"},
            }
        ]

        with patch(
            "token_iq.gateway.proxy.health_check.gateway.ahealth_check",
            new=AsyncMock(
                return_value={"error": "auth failed", "exception": auth_error}
            ),
        ):
            healthy, unhealthy, exc_map = await _perform_health_check(model_list)

        assert len(unhealthy) == 1
        assert "exception" not in unhealthy[0], "exception must not be in endpoint dict"
        assert exc_map.get("deploy-abc") is auth_error

    @pytest.mark.asyncio
    async def test_raw_exception_from_gather_in_map(self):
        """When asyncio.gather returns a raw Exception, it must appear in
        exceptions_by_model_id — not in the endpoint dict."""
        from unittest.mock import patch

        from token_iq.gateway.proxy.health_check import _perform_health_check

        raw_exc = gateway.RateLimitError(
            message="Rate limited", llm_provider="openai", model="gpt-4"
        )
        model_list = [
            {
                "model_name": "gpt-4",
                "litellm_params": {"model": "gpt-4", "api_key": "fake"},
                "model_info": {"id": "deploy-xyz"},
            }
        ]

        # Simulate asyncio.gather returning a raw exception for this task
        with patch(
            "token_iq.gateway.proxy.health_check._run_model_health_check",
            side_effect=raw_exc,
        ):
            healthy, unhealthy, exc_map = await _perform_health_check(model_list)

        assert len(unhealthy) == 1
        assert "exception" not in unhealthy[0], "exception must not be in endpoint dict"
        assert exc_map.get("deploy-xyz") is raw_exc


class TestGetAllowedFailsFromPolicyWithHealthCheckExceptions:
    """Test that get_allowed_fails_from_policy correctly resolves thresholds for health-check exceptions."""




class TestHealthCheckCooldownIntegration:
    """Test that health check failures trigger cooldown via _set_cooldown_deployments."""







class TestWriteHealthStateIntegration:
    """Test _write_health_state_to_router_cache integrates with cooldown pipeline."""





class TestHealthCheckFilterBypassWithPolicy:
    """
    When allowed_fails_policy is set, the binary health check filter should be
    bypassed so cooldown is the sole routing exclusion mechanism.
    """


    def test_filter_active_when_no_policy(self):
        """Binary health check filter still works when no allowed_fails_policy is configured."""
        import time

        from token_iq.gateway.caching.caching import DualCache
        from token_iq.gateway.router_utils.health_state_cache import DeploymentHealthCache

        router = Router(
            model_list=[_make_model("deploy-1"), _make_model("deploy-2", "gpt-5")],
            enable_health_check_routing=True,
        )

        cache = DualCache()
        health_cache = DeploymentHealthCache(cache=cache, staleness_threshold=60.0)
        health_cache.set_deployment_health_states(
            {
                "deploy-1": {
                    "is_healthy": False,
                    "timestamp": time.time(),
                    "reason": "test",
                },
            }
        )
        router.health_state_cache = health_cache

        deployments = [_make_model("deploy-1"), _make_model("deploy-2", "gpt-5")]

        result = router._filter_health_check_unhealthy_deployments(deployments)
        assert len(result) == 1
        assert result[0]["model_info"]["id"] == "deploy-2"


    def _make_scoped_router_with_unhealthy(self, policy) -> Router:
        import time

        from token_iq.gateway.caching.caching import DualCache
        from token_iq.gateway.router_utils.health_state_cache import DeploymentHealthCache

        router = Router(
            model_list=[
                _make_model("bad-listed"),
                _make_model("ok-listed"),
                _make_model("bad-unlisted", "gpt-5"),
            ],
            allowed_fails_policy=policy,
            enable_health_check_routing=True,
            background_health_check_model_groups=["gpt-4"],
        )
        cache = DualCache()
        health_cache = DeploymentHealthCache(cache=cache, staleness_threshold=60.0)
        health_cache.set_deployment_health_states(
            {
                model_id: {
                    "is_healthy": False,
                    "timestamp": time.time(),
                    "reason": "test",
                }
                for model_id in ("bad-listed", "bad-unlisted")
            }
        )
        router.health_state_cache = health_cache
        return router




class TestAllDeploymentsInCooldownSafetyNet:
    """
    When enable_health_check_routing=True and ALL deployments enter cooldown,
    the async routing path should bypass the cooldown filter and return all
    deployments rather than blocking all traffic.
    """

    def test_raw_cooldown_filter_returns_empty_when_all_cooled(self):
        """The raw _filter_cooldown_deployments has no safety net -- it returns empty."""
        router = Router(
            model_list=[_make_model("deploy-1"), _make_model("deploy-2", "gpt-5")],
            enable_health_check_routing=True,
        )
        deployments = [_make_model("deploy-1"), _make_model("deploy-2", "gpt-5")]
        result = router._filter_cooldown_deployments(
            healthy_deployments=deployments,
            cooldown_deployments=["deploy-1", "deploy-2"],
        )
        assert result == []  # raw filter has no safety net



class TestHealthCheckIgnoreTransientErrors:
    """
    When health_check_ignore_transient_errors=True, health check failures with
    429 or 408 status codes should NOT increment failure counters or trigger cooldown.
    401, 404, and 5xx errors should still be processed normally.
    """




    def test_429_not_written_to_health_state_cache_when_flag_enabled(self):
        """429 endpoint is excluded from health state cache when flag is set,
        so the binary health check filter does not mark it as unhealthy."""
        import token_iq.gateway.proxy.proxy_server as proxy_module
        from token_iq.gateway.proxy.proxy_server import _write_health_state_to_router_cache

        router = Router(
            model_list=[_make_model("deploy-1")],
            enable_health_check_routing=True,
            health_check_ignore_transient_errors=True,
        )

        rate_exc = gateway.RateLimitError(
            message="Rate limited", model="gpt-4", llm_provider="openai"
        )

        unhealthy_endpoints = [
            {"model_id": "deploy-1", "error": "rate limited"},
        ]

        with patch.object(proxy_module, "llm_router", router):
            _write_health_state_to_router_cache(
                healthy_endpoints=[],
                unhealthy_endpoints=unhealthy_endpoints,
                exceptions_by_model_id={"deploy-1": rate_exc},
            )

        # Health state cache should have NO entry for deploy-1
        # (429 was ignored, not written as unhealthy)
        unhealthy_ids = router.health_state_cache.get_unhealthy_deployment_ids()
        assert "deploy-1" not in unhealthy_ids



class TestSharedCacheTransientErrorFilter:
    """
    When SharedHealthCheckManager returns cached results, exceptions_by_model_id
    is always {}. The filter must fall back to the 'exception_status' field stored
    on each endpoint dict so 429/408 endpoints are still excluded correctly.
    """

    def test_cached_429_excluded_via_exception_status_field(self):
        """Cache-hit path: endpoint with exception_status=429 is excluded from health state."""
        import token_iq.gateway.proxy.proxy_server as proxy_module
        from token_iq.gateway.proxy.proxy_server import _write_health_state_to_router_cache

        router = Router(
            model_list=[_make_model("deploy-1"), _make_model("deploy-2", "gpt-5")],
            enable_health_check_routing=True,
            health_check_ignore_transient_errors=True,
        )

        # Simulate a cache-hit endpoint: exception_status stored as int, no exceptions dict
        unhealthy_endpoints = [
            {"model_id": "deploy-1", "error": "rate limited", "exception_status": 429},
        ]

        with patch.object(proxy_module, "llm_router", router):
            _write_health_state_to_router_cache(
                healthy_endpoints=[],
                unhealthy_endpoints=unhealthy_endpoints,
                exceptions_by_model_id={},
            )

        # deploy-1 should NOT be marked unhealthy (429 was filtered)
        unhealthy_ids = router.health_state_cache.get_unhealthy_deployment_ids()
        assert "deploy-1" not in unhealthy_ids

    def test_cached_401_still_marked_unhealthy(self):
        """Cache-hit path: endpoint with exception_status=401 is still written as unhealthy."""
        import token_iq.gateway.proxy.proxy_server as proxy_module
        from token_iq.gateway.proxy.proxy_server import _write_health_state_to_router_cache

        router = Router(
            model_list=[_make_model("deploy-1"), _make_model("deploy-2", "gpt-5")],
            enable_health_check_routing=True,
            health_check_ignore_transient_errors=True,
        )

        unhealthy_endpoints = [
            {"model_id": "deploy-1", "error": "auth failed", "exception_status": 401},
        ]

        with patch.object(proxy_module, "llm_router", router):
            _write_health_state_to_router_cache(
                healthy_endpoints=[],
                unhealthy_endpoints=unhealthy_endpoints,
                exceptions_by_model_id={},
            )

        unhealthy_ids = router.health_state_cache.get_unhealthy_deployment_ids()
        assert "deploy-1" in unhealthy_ids
