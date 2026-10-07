"""Tests for litellm.core_utils.fallback_utils."""

import pytest
import httpx

from token_iq import gateway
from token_iq.gateway.core_utils.core_helpers import process_response_headers
from token_iq.gateway.core_utils.fallback_utils import (
    async_completion_with_fallbacks,
)


@pytest.mark.asyncio
async def test_fallback_dict_not_mutated(monkeypatch):
    fallback_dict = {"model": "fallback-model", "temperature": 0.2}
    original_fallback_dict = dict(fallback_dict)

    attempted_models: list[str] = []

    async def _fake_acompletion(*, model: str, **kwargs):
        attempted_models.append(model)
        if model == "primary-model":
            raise Exception("primary failed")
        return {"model": model, "temperature": kwargs.get("temperature")}

    monkeypatch.setattr(gateway, "acompletion", _fake_acompletion)

    # Call 1: primary fails, fallback dict succeeds
    response_1 = await async_completion_with_fallbacks(
        model="primary-model",
        kwargs={"fallbacks": [fallback_dict]},
    )
    assert response_1["model"] == "fallback-model"
    assert fallback_dict == original_fallback_dict

    # Call 2: re-use the same dict object; it should still work and remain unchanged
    response_2 = await async_completion_with_fallbacks(
        model="primary-model",
        kwargs={"fallbacks": [fallback_dict]},
    )
    assert response_2["model"] == "fallback-model"
    assert fallback_dict == original_fallback_dict

    assert attempted_models == [
        "primary-model",
        "fallback-model",
        "primary-model",
        "fallback-model",
    ]


@pytest.mark.asyncio
async def test_async_completion_with_fallbacks_sets_attempted_fallbacks_header():
    """
    When a fallback succeeds, the response must carry the
    `x-litellm-attempted-fallbacks` header so the proxy and other callers can
    detect that a fallback occurred. Without it,
    `_override_openai_response_model` stamps the requested model back over the
    fallback model used. See issue #28241.
    """
    response = await async_completion_with_fallbacks(
        model="openai/primary-llm",
        messages=[{"role": "user", "content": "hi"}],
        api_key="fake-key",
        mock_response=Exception("forced failure"),
        kwargs={
            "fallbacks": [
                {
                    "model": "openai/backup-llm",
                    "api_key": "fake-key",
                    "mock_response": "backup-resp",
                }
            ]
        },
    )

    hidden_params = getattr(response, "_hidden_params", None)
    assert isinstance(hidden_params, dict)
    headers = hidden_params.get("additional_headers") or {}
    assert headers.get("x-token-iq-attempted-fallbacks") == 1


@pytest.mark.asyncio
async def test_async_completion_with_fallbacks_header_is_zero_when_primary_succeeds():
    """
    When the primary model succeeds on the first attempt, the header should be
    `0` (no fallback was used). This mirrors the existing router-level
    semantics in `async_function_with_fallbacks`.
    """
    response = await async_completion_with_fallbacks(
        model="openai/primary-llm",
        messages=[{"role": "user", "content": "hi"}],
        api_key="fake-key",
        mock_response="primary-resp",
        kwargs={
            "fallbacks": [
                {
                    "model": "openai/backup-llm",
                    "api_key": "fake-key",
                    "mock_response": "backup-resp",
                }
            ]
        },
    )

    hidden_params = getattr(response, "_hidden_params", None)
    assert isinstance(hidden_params, dict)
    headers = hidden_params.get("additional_headers") or {}
    assert headers.get("x-token-iq-attempted-fallbacks") == 0
    assert response.choices[0].message.content == "primary-resp"


BOTH_SPELLINGS = pytest.mark.parametrize("prefix", ["x-token-iq-", "x-litellm-"])
"""The seam accepts both for one more release, so every property below has to hold for both. Said this way
because the rename moved the header these tests send without moving the key they expected back, and they had
been failing ever since."""


@BOTH_SPELLINGS
def test_process_response_headers_preserves_gateway_headers_when_internal(prefix: str):
    """
    `process_response_headers` must not add the `llm_provider-` prefix to the gateway's own internal
    headers when the caller has marked the input as gateway-owned. These are markers the gateway sets
    itself, for fallbacks and retries, and the proxy and other callers look up the bare key.
    """
    result = process_response_headers(
        {
            f"{prefix}attempted-fallbacks": 1,
            f"{prefix}model-group": "gpt-4",
            "x-stainless-arch": "arm64",
        },
        preserve_gateway_internal_headers=True,
    )
    assert result[f"{prefix}attempted-fallbacks"] == 1
    assert result[f"{prefix}model-group"] == "gpt-4"
    assert result["llm_provider-x-stainless-arch"] == "arm64"


@BOTH_SPELLINGS
def test_process_response_headers_prefixes_gateway_headers_from_raw_provider(prefix: str):
    """
    On raw upstream-provider headers, which is the default, a header named like one of the gateway's own
    must still get the `llm_provider-` prefix. Otherwise a provider could return
    `x-token-iq-attempted-fallbacks` and spoof a gateway-internal marker, getting past the proxy's
    model-override guard.
    """
    result = process_response_headers(
        {
            f"{prefix}attempted-fallbacks": 99,
            "x-stainless-arch": "arm64",
        }
    )
    assert f"{prefix}attempted-fallbacks" not in result
    assert result[f"llm_provider-{prefix}attempted-fallbacks"] == 99
    assert result["llm_provider-x-stainless-arch"] == "arm64"


@BOTH_SPELLINGS
def test_process_response_headers_ignores_preserve_flag_for_httpx_headers(prefix: str):
    """
    Some providers store raw httpx.Headers straight into `_hidden_params["additional_headers"]` with no
    normalisation pass first. If the preserve flag were honoured for an httpx.Headers input, a provider
    returning the attempted-fallbacks marker could pass it off as a bare gateway-internal one and make the
    proxy skip stamping the right response model. The flag must be ignored for httpx.Headers.
    """
    raw = httpx.Headers(
        {
            f"{prefix}attempted-fallbacks": "1",
            "content-type": "application/json",
        }
    )
    result = process_response_headers(raw, preserve_gateway_internal_headers=True)
    assert f"{prefix}attempted-fallbacks" not in result
    assert result[f"llm_provider-{prefix}attempted-fallbacks"] == "1"
