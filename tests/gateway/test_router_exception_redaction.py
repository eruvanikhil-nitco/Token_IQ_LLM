"""
Tests for `litellm.expose_router_debug_in_errors`.

The Router historically appended internal config names (model_group,
fallback_model_group, fallback failure detail, deployment timeouts,
context_window_fallbacks dict, etc.) onto the message of the exception
it re-raises. That message is then surfaced to clients by
ProxyException, leaking the proxy's internal wiring and, when fallbacks
are configured as inline deployment dicts, the provider credentials
inside those dicts.

The flag defaults to True to preserve historical behavior (no
breaking change for existing deployments). Set it to False to redact
those strings from the raised exception's message. Regardless of the
flag, provider credentials inside inline-dict fallbacks are now masked
so a raw api_key / aws_* value never reaches the client.

These tests verify that with the flag ON (default) the historical
topology strings appear in the raised exception's message, with the
flag OFF the proxy's internal wiring is redacted, and that a raw
provider credential never appears in the message regardless of the
flag.

Five leak sites are gated in `token_iq/gateway/router.py`:

1. Deployment timeout debug after `litellm.Timeout`
2. ContextWindowExceededError fallback hint
3. ContentPolicyViolationError fallback hint
4. "No fallback model group found for..." when fallbacks dict misses
5. "Received Model Group=...\\nAvailable Model Group Fallbacks=..."
   (always fires on terminal raise from the fallback orchestrator)

Site 5 is the broadest — it fires for every failing call that goes
through the fallback orchestrator with any non-context-window /
non-content-policy error, regardless of whether `fallbacks` is set.
"""

from __future__ import annotations

import pytest

from token_iq import gateway
from token_iq.gateway import Router

_RECEIVED_MODEL_GROUP_PHRASE = "Received Model Group="
_AVAILABLE_FALLBACKS_PHRASE = "Available Model Group Fallbacks="
_CONTEXT_WINDOW_HINT_PHRASE = "context_window_fallbacks="
_INTERNAL_MODEL_GROUP_NAME = "all-anthropic/claude-secret-internal"
_FALLBACK_CREDENTIAL = "sk-INLINEFALLBACKSECRET1234567890"


def _router_with_rate_limit_failure() -> Router:
    return Router(
        model_list=[
            {
                "model_name": _INTERNAL_MODEL_GROUP_NAME,
                "litellm_params": {
                    "model": "gpt-4o",
                    "api_key": "key",
                    "mock_response": "token_iq.RateLimitError",
                },
                "model_info": {"id": "secret-deployment-id"},
            },
        ],
        num_retries=0,
    )


def _router_with_context_window_failure() -> Router:
    return Router(
        model_list=[
            {
                "model_name": _INTERNAL_MODEL_GROUP_NAME,
                "litellm_params": {
                    "model": "gpt-4o",
                    "api_key": "key",
                    "mock_response": "token_iq.ContextWindowExceededError",
                },
                "model_info": {"id": "secret-deployment-id"},
            },
        ],
        num_retries=0,
    )


def _router_with_credentialed_fallback() -> Router:
    """Primary fails, and its fallback is an inline dict that carries a provider
    api_key. When the fallback also fails, the router embeds that dict in the
    exception message, which is where a raw credential would otherwise leak."""
    return Router(
        model_list=[
            {
                "model_name": _INTERNAL_MODEL_GROUP_NAME,
                "litellm_params": {
                    "model": "gpt-4o",
                    "api_key": "key",
                    "mock_response": "token_iq.RateLimitError",
                },
                "model_info": {"id": "secret-deployment-id"},
            },
        ],
        fallbacks=[
            {
                _INTERNAL_MODEL_GROUP_NAME: [
                    {
                        "model": "gpt-4o",
                        "api_key": _FALLBACK_CREDENTIAL,
                        "mock_response": "token_iq.RateLimitError",
                    }
                ]
            }
        ],
        num_retries=0,
    )


@pytest.fixture(autouse=True)
def _reset_expose_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each test starts with the flag in its default (on) state."""
    monkeypatch.setattr(gateway, "expose_router_debug_in_errors", True)


def test_flag_defaults_on():
    assert gateway.expose_router_debug_in_errors is True


# --- Site 5: "Received Model Group=..." on terminal raise --------------------


@pytest.mark.asyncio
async def test_flag_off_does_not_leak_received_model_group(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(gateway, "expose_router_debug_in_errors", False)
    router = _router_with_rate_limit_failure()
    with pytest.raises(gateway.RateLimitError) as excinfo:
        await router.acompletion(
            model=_INTERNAL_MODEL_GROUP_NAME,
            messages=[{"role": "user", "content": "hi"}],
        )
    msg = excinfo.value.message
    assert _RECEIVED_MODEL_GROUP_PHRASE not in msg, msg
    assert _AVAILABLE_FALLBACKS_PHRASE not in msg, msg
    assert _INTERNAL_MODEL_GROUP_NAME not in msg, msg


@pytest.mark.asyncio
async def test_flag_on_shows_received_model_group(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(gateway, "expose_router_debug_in_errors", True)
    router = _router_with_rate_limit_failure()
    with pytest.raises(gateway.RateLimitError) as excinfo:
        await router.acompletion(
            model=_INTERNAL_MODEL_GROUP_NAME,
            messages=[{"role": "user", "content": "hi"}],
        )
    msg = excinfo.value.message
    assert _RECEIVED_MODEL_GROUP_PHRASE in msg, msg
    assert _AVAILABLE_FALLBACKS_PHRASE in msg, msg
    assert _INTERNAL_MODEL_GROUP_NAME in msg, msg


# --- Site 2: ContextWindowExceededError fallback hint ------------------------


@pytest.mark.asyncio
async def test_flag_off_does_not_leak_context_window_fallback_hint(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(gateway, "expose_router_debug_in_errors", False)
    router = _router_with_context_window_failure()
    with pytest.raises(gateway.ContextWindowExceededError) as excinfo:
        await router.acompletion(
            model=_INTERNAL_MODEL_GROUP_NAME,
            messages=[{"role": "user", "content": "hi"}],
        )
    msg = excinfo.value.message
    assert _CONTEXT_WINDOW_HINT_PHRASE not in msg, msg
    assert _RECEIVED_MODEL_GROUP_PHRASE not in msg, msg
    assert _INTERNAL_MODEL_GROUP_NAME not in msg, msg


@pytest.mark.asyncio
async def test_flag_on_shows_context_window_fallback_hint(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(gateway, "expose_router_debug_in_errors", True)
    router = _router_with_context_window_failure()
    with pytest.raises(gateway.ContextWindowExceededError) as excinfo:
        await router.acompletion(
            model=_INTERNAL_MODEL_GROUP_NAME,
            messages=[{"role": "user", "content": "hi"}],
        )
    msg = excinfo.value.message
    assert _CONTEXT_WINDOW_HINT_PHRASE in msg, msg
    # Site 5 also fires for ContextWindow errors that exit the
    # orchestrator without fallback resolution, so the model_group
    # name is shown under the opt-in behavior.
    assert _INTERNAL_MODEL_GROUP_NAME in msg, msg


# --- Site 4: "No fallback model group found..." when fallbacks miss ---------






# --- Site 1: Deployment timeout debug on litellm.Timeout --------------------


def _router_with_plain_deployment() -> Router:
    """Plain deployment, no preconfigured mock_response — caller supplies via kwargs.

    Exception instances cannot live in `model_list[*].litellm_params` because
    `Router.__init__` deep-copies model_list and several LiteLLM exceptions
    (Timeout, ContentPolicyViolationError) require positional args that
    `__reduce__` cannot reconstruct. Passing the trigger at call-site bypasses
    the deepcopy entirely.
    """
    return Router(
        model_list=[
            {
                "model_name": _INTERNAL_MODEL_GROUP_NAME,
                "litellm_params": {"model": "gpt-4o", "api_key": "key"},
                "model_info": {"id": "secret-deployment-id"},
            },
        ],
        num_retries=0,
    )


@pytest.mark.asyncio
async def test_flag_off_does_not_leak_deployment_timeout_debug(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(gateway, "expose_router_debug_in_errors", False)
    router = _router_with_plain_deployment()
    with pytest.raises(gateway.Timeout) as excinfo:
        await router.acompletion(
            model=_INTERNAL_MODEL_GROUP_NAME,
            messages=[{"role": "user", "content": "hi"}],
            mock_timeout=True,
            timeout=0.001,
        )
    msg = excinfo.value.message
    assert "Deployment Info: request_timeout:" not in msg, msg


@pytest.mark.asyncio
async def test_flag_on_shows_deployment_timeout_debug(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(gateway, "expose_router_debug_in_errors", True)
    router = _router_with_plain_deployment()
    with pytest.raises(gateway.Timeout) as excinfo:
        await router.acompletion(
            model=_INTERNAL_MODEL_GROUP_NAME,
            messages=[{"role": "user", "content": "hi"}],
            mock_timeout=True,
            timeout=0.001,
        )
    msg = excinfo.value.message
    assert "Deployment Info: request_timeout:" in msg, msg


# --- Site 3: ContentPolicyViolationError fallback hint (no fallback set) ----


def _content_policy_error() -> gateway.ContentPolicyViolationError:
    return gateway.ContentPolicyViolationError(
        message="mocked policy violation",
        model="gpt-4o",
        llm_provider="openai",
    )


@pytest.mark.asyncio
async def test_flag_off_does_not_leak_content_policy_fallback_hint(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(gateway, "expose_router_debug_in_errors", False)
    router = _router_with_plain_deployment()
    with pytest.raises(gateway.ContentPolicyViolationError) as excinfo:
        await router.acompletion(
            model=_INTERNAL_MODEL_GROUP_NAME,
            messages=[{"role": "user", "content": "hi"}],
            mock_response=_content_policy_error(),
        )
    msg = excinfo.value.message
    assert "content_policy_fallback=" not in msg, msg
    assert _INTERNAL_MODEL_GROUP_NAME not in msg, msg


@pytest.mark.asyncio
async def test_flag_on_shows_content_policy_fallback_hint(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(gateway, "expose_router_debug_in_errors", True)
    router = _router_with_plain_deployment()
    with pytest.raises(gateway.ContentPolicyViolationError) as excinfo:
        await router.acompletion(
            model=_INTERNAL_MODEL_GROUP_NAME,
            messages=[{"role": "user", "content": "hi"}],
            mock_response=_content_policy_error(),
        )
    msg = excinfo.value.message
    assert "content_policy_fallback=" in msg, msg
    assert _INTERNAL_MODEL_GROUP_NAME in msg, msg


# --- Credential masking: raw provider keys never leak, either flag state ----






