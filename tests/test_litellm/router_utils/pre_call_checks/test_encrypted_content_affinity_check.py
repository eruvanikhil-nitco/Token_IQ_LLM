"""
Tests for encrypted_content_affinity pre-call check.

The mechanism works without any cache and supports two encoding strategies:

1. **Items with IDs**: item IDs for output items with `encrypted_content` are rewritten to
   `encitem_{base64("litellm:model_id:{model_id};item_id:{original_id}")}`.

2. **Items without IDs** (Codex): encrypted_content itself is wrapped with model_id metadata:
   `litellm_enc:{base64("model_id:{model_id}")};{original_encrypted_content}`.

- On routing: `EncryptedContentAffinityCheck` decodes from either item IDs or wrapped
  encrypted_content to extract `model_id` and pins the request to that deployment.
- Before forwarding: `_restore_encrypted_content_item_ids_in_input` decodes IDs and unwraps
  encrypted_content back to their original forms before sending to the upstream provider.
"""

import time
from typing import List, Optional
from unittest.mock import AsyncMock, patch

import pytest


import litellm
from litellm.responses.utils import ResponsesAPIRequestUtils
from litellm.types.llms.openai import ResponsesAPIResponse

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_mock_response(output_items, response_id="resp_mock-123"):
    """Build a ResponsesAPIResponse that ``async_response_api_handler`` would return."""
    return ResponsesAPIResponse(
        id=response_id,
        created_at=1741476542,
        status="completed",
        model="openai/gpt-5.1-codex",
        output=output_items,
        usage={"input_tokens": 5, "output_tokens": 10, "total_tokens": 15},
    )


def _get_item_id(item) -> str:
    """Extract item ID from either a Pydantic model or a dict."""
    if isinstance(item, dict):
        return item.get("id", "")
    return getattr(item, "id", "") or ""


def _extract_encoded_item_id(response) -> str:
    """Return the first ``encitem_``-prefixed item ID from the response output."""
    for item in response.output or []:
        item_id = _get_item_id(item)
        if item_id.startswith("encitem_"):
            return item_id
    return ""


# ---------------------------------------------------------------------------
# Unit tests for encoding / decoding utilities
# ---------------------------------------------------------------------------


class TestEncryptedItemIdCodec:
    def test_roundtrip(self):
        model_id = "deployment-1"
        original_item_id = "rs_abc123def456"
        encoded = ResponsesAPIRequestUtils._build_encrypted_item_id(
            model_id, original_item_id
        )
        assert encoded.startswith("encitem_")
        decoded = ResponsesAPIRequestUtils._decode_encrypted_item_id(encoded)
        assert decoded is not None
        assert decoded["model_id"] == model_id
        assert decoded["item_id"] == original_item_id

    def test_decode_without_padding(self):
        """Decoding must succeed even if base64 padding (=) was stripped in transit."""
        model_id = "gpt-5.1-codex-openai-2"
        original_item_id = "rs_0efb96cb222403210069a01d5d52588196a9dc394ffdb89d00"
        encoded = ResponsesAPIRequestUtils._build_encrypted_item_id(
            model_id, original_item_id
        )
        # Strip any trailing '=' to simulate what happens in transit
        stripped = encoded.rstrip("=")
        decoded = ResponsesAPIRequestUtils._decode_encrypted_item_id(stripped)
        assert decoded is not None
        assert decoded["model_id"] == model_id
        assert decoded["item_id"] == original_item_id

    def test_non_encoded_id_returns_none(self):
        assert ResponsesAPIRequestUtils._decode_encrypted_item_id("rs_abc123") is None
        assert ResponsesAPIRequestUtils._decode_encrypted_item_id("msg_abc") is None
        assert ResponsesAPIRequestUtils._decode_encrypted_item_id("") is None

    def test_semicolon_in_item_id(self):
        """item_id values containing ';' must survive the roundtrip."""
        model_id = "deployment-1"
        original_item_id = "rs_part1;part2;part3"
        encoded = ResponsesAPIRequestUtils._build_encrypted_item_id(
            model_id, original_item_id
        )
        decoded = ResponsesAPIRequestUtils._decode_encrypted_item_id(encoded)
        assert decoded is not None
        assert decoded["item_id"] == original_item_id


class TestUpdateEncryptedContentItemIds:
    def test_rewrites_encrypted_items_in_dict_response(self):
        model_id = "deployment-1"
        response = {
            "id": "resp_123",
            "output": [
                {"id": "msg_abc", "type": "message", "content": []},
                {"id": "rs_xyz", "type": "reasoning", "encrypted_content": "secret"},
            ],
        }
        result = (
            ResponsesAPIRequestUtils._update_encrypted_content_item_ids_in_response(
                response, model_id
            )
        )
        # Plain message item untouched
        assert result["output"][0]["id"] == "msg_abc"
        # Reasoning item with encrypted_content gets encoded
        encoded_id = result["output"][1]["id"]
        assert encoded_id.startswith("encitem_")
        decoded = ResponsesAPIRequestUtils._decode_encrypted_item_id(encoded_id)
        assert decoded["model_id"] == model_id
        assert decoded["item_id"] == "rs_xyz"

    def test_no_op_when_model_id_is_none(self):
        response = {
            "output": [
                {"id": "rs_xyz", "type": "reasoning", "encrypted_content": "secret"}
            ]
        }
        result = (
            ResponsesAPIRequestUtils._update_encrypted_content_item_ids_in_response(
                response, None
            )
        )
        assert result["output"][0]["id"] == "rs_xyz"


class TestEncryptedContentWrapping:
    def test_wrap_and_unwrap_encrypted_content(self):
        """Test wrapping encrypted_content with model_id metadata."""
        model_id = "deployment-1"
        original_content = "gAAAAABpnW_yEYmSNEyOG_original_encrypted_data"
        wrapped = ResponsesAPIRequestUtils._wrap_encrypted_content_with_model_id(
            original_content, model_id
        )
        assert wrapped.startswith("litellm_enc:")
        assert wrapped != original_content

        (
            unwrapped_model_id,
            unwrapped_content,
        ) = ResponsesAPIRequestUtils._unwrap_encrypted_content_with_model_id(wrapped)
        assert unwrapped_model_id == model_id
        assert unwrapped_content == original_content

    def test_unwrap_plain_encrypted_content(self):
        """Unwrapping plain encrypted_content returns None for model_id."""
        plain_content = "gAAAAABpnW_yEYmSNEyOG_plain_content"
        (
            model_id,
            content,
        ) = ResponsesAPIRequestUtils._unwrap_encrypted_content_with_model_id(
            plain_content
        )
        assert model_id is None
        assert content == plain_content

    def test_update_response_wraps_encrypted_content_without_id(self):
        """Items with encrypted_content but no ID get the content wrapped."""
        model_id = "deployment-1"
        response = {
            "id": "resp_123",
            "output": [
                {"type": "message", "content": []},
                {
                    "type": "reasoning",
                    "encrypted_content": "gAAAAABpnW_yEYmSNEyOG_secret",
                },
            ],
        }
        result = (
            ResponsesAPIRequestUtils._update_encrypted_content_item_ids_in_response(
                response, model_id
            )
        )
        assert result["output"][0].get("encrypted_content") is None
        wrapped = result["output"][1]["encrypted_content"]
        assert wrapped.startswith("litellm_enc:")

        (
            model_id_extracted,
            unwrapped,
        ) = ResponsesAPIRequestUtils._unwrap_encrypted_content_with_model_id(wrapped)
        assert model_id_extracted == model_id
        assert unwrapped == "gAAAAABpnW_yEYmSNEyOG_secret"


class TestRestoreEncryptedContentItemIds:
    def test_restores_encoded_ids(self):
        model_id = "deployment-1"
        original_id = "rs_encrypted_item_456"
        encoded_id = ResponsesAPIRequestUtils._build_encrypted_item_id(
            model_id, original_id
        )

        request_input = [
            {"type": "message", "id": "msg_abc123", "role": "assistant"},
            {"type": "reasoning", "id": encoded_id, "encrypted_content": "secret"},
        ]
        restored = (
            ResponsesAPIRequestUtils._restore_encrypted_content_item_ids_in_input(
                request_input
            )
        )
        assert restored[0]["id"] == "msg_abc123"
        assert restored[1]["id"] == original_id

    def test_unwraps_encrypted_content(self):
        """Test that wrapped encrypted_content is unwrapped before forwarding."""
        model_id = "deployment-1"
        original_content = "gAAAAABpnW_yEYmSNEyOG_original"
        wrapped_content = (
            ResponsesAPIRequestUtils._wrap_encrypted_content_with_model_id(
                original_content, model_id
            )
        )

        request_input = [
            {"type": "reasoning", "encrypted_content": wrapped_content},
        ]
        restored = (
            ResponsesAPIRequestUtils._restore_encrypted_content_item_ids_in_input(
                request_input
            )
        )
        assert restored[0]["encrypted_content"] == original_content

    def test_no_op_for_plain_string_input(self):
        result = ResponsesAPIRequestUtils._restore_encrypted_content_item_ids_in_input(
            "Hello world"
        )
        assert result == "Hello world"

    def test_no_op_for_unencoded_ids(self):
        request_input = [{"type": "message", "id": "msg_plain"}]
        result = ResponsesAPIRequestUtils._restore_encrypted_content_item_ids_in_input(
            request_input
        )
        assert result[0]["id"] == "msg_plain"


# ---------------------------------------------------------------------------
# Integration tests (router-level)
# ---------------------------------------------------------------------------




@pytest.mark.asyncio
async def test_encrypted_content_affinity_no_effect_on_chat_completions():
    """
    Encrypted content affinity should not affect regular chat completions.
    """
    router = litellm.Router(
        model_list=[
            {
                "model_name": "gpt-3.5-turbo",
                "litellm_params": {
                    "model": "gpt-3.5-turbo",
                    "api_key": "test-key",
                    "mock_response": "Hello from chat completion!",
                },
                "model_info": {"id": "chat-deployment-1"},
            },
        ],
        optional_pre_call_checks=["encrypted_content_affinity"],
        num_retries=0,
    )

    response1 = await router.acompletion(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": "Hello"}],
    )
    response2 = await router.acompletion(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": "Hello again"}],
    )
    assert response1.id is not None
    assert response2.id is not None








def test_encrypted_content_wrapping_preserves_original_content():
    """
    Test that wrapping and unwrapping encrypted_content preserves the original content.
    This is critical for streaming responses where content must round-trip correctly.
    """
    model_id = "test-deployment-1"
    original_encrypted_content = (
        "gAAAAABpnW_yEYmSNEyOG_streaming_test_content_with_special_chars==+/"
    )

    wrapped = ResponsesAPIRequestUtils._wrap_encrypted_content_with_model_id(
        original_encrypted_content, model_id
    )

    assert wrapped.startswith("litellm_enc:")
    assert wrapped != original_encrypted_content

    (
        extracted_model_id,
        unwrapped_content,
    ) = ResponsesAPIRequestUtils._unwrap_encrypted_content_with_model_id(wrapped)

    assert extracted_model_id == model_id
    assert unwrapped_content == original_encrypted_content


def test_encrypted_content_wrapping_with_multiple_semicolons():
    """
    Test that encrypted_content containing semicolons is handled correctly.
    """
    model_id = "deployment-with-semicolons"
    original_content = "gAAAAAB;some;content;with;semicolons"

    wrapped = ResponsesAPIRequestUtils._wrap_encrypted_content_with_model_id(
        original_content, model_id
    )

    (
        extracted_model_id,
        unwrapped,
    ) = ResponsesAPIRequestUtils._unwrap_encrypted_content_with_model_id(wrapped)

    assert extracted_model_id == model_id
    assert unwrapped == original_content


# ---------------------------------------------------------------------------
# Regression tests: affinity check must not break tag-based routing
# ---------------------------------------------------------------------------

from litellm.router_utils.pre_call_checks.encrypted_content_affinity_check import (
    EncryptedContentAffinityCheck,
)


@pytest.mark.asyncio
async def test_encrypted_content_affinity_does_not_create_litellm_metadata_for_chat():
    """
    For chat completions / embeddings, request_kwargs uses 'metadata' (not
    'litellm_metadata').  The affinity check must NOT create a spurious
    'litellm_metadata' key, because that would cause
    _get_metadata_variable_name_from_kwargs to return 'litellm_metadata'
    and tag-based routing would look for tags in the wrong dict.
    """
    check = EncryptedContentAffinityCheck()
    deployments = [
        {"model_info": {"id": "dep-1"}, "litellm_params": {"model": "gpt-4"}},
    ]
    request_kwargs = {"metadata": {"tags": ["prod"]}}

    result = await check.async_filter_deployments(
        model="gpt-4",
        healthy_deployments=deployments,
        messages=[{"role": "user", "content": "hi"}],
        request_kwargs=request_kwargs,
    )

    # Must not inject litellm_metadata
    assert "litellm_metadata" not in request_kwargs
    # Tags must be untouched
    assert request_kwargs["metadata"]["tags"] == ["prod"]
    # All deployments returned (no pinning)
    assert len(result) == 1


@pytest.mark.asyncio
async def test_encrypted_content_affinity_preserves_litellm_metadata_for_responses():
    """
    For Responses API calls, litellm_metadata already exists.  The affinity
    check should set the flag there and preserve existing keys.
    """
    check = EncryptedContentAffinityCheck()
    deployments = [
        {"model_info": {"id": "dep-1"}, "litellm_params": {"model": "gpt-5.1-codex"}},
    ]
    request_kwargs = {
        "litellm_metadata": {"model_info": {"id": "dep-1"}},
    }

    await check.async_filter_deployments(
        model="gpt-5.1-codex",
        healthy_deployments=deployments,
        messages=None,
        request_kwargs=request_kwargs,
    )

    assert (
        request_kwargs["litellm_metadata"]["encrypted_content_affinity_enabled"] is True
    )
    assert request_kwargs["litellm_metadata"]["model_info"] == {"id": "dep-1"}


def test_encrypted_content_wrapping_empty_string():
    """
    Test that empty encrypted_content is handled gracefully.
    """
    model_id = "test-deployment"
    original_content = ""

    wrapped = ResponsesAPIRequestUtils._wrap_encrypted_content_with_model_id(
        original_content, model_id
    )

    assert wrapped.startswith("litellm_enc:")

    (
        extracted_model_id,
        unwrapped,
    ) = ResponsesAPIRequestUtils._unwrap_encrypted_content_with_model_id(wrapped)

    assert extracted_model_id == model_id
    assert unwrapped == original_content


# ---------------------------------------------------------------------------
# LIT-2531: cross-model-group fallback via encryption boundary (api_base + api_key)
# ---------------------------------------------------------------------------






def test_boundary_fallback_no_router_ref_returns_empty():
    """
    Standalone use (no router wired in) -> the boundary lookup short-circuits
    to ``[]`` instead of crashing on ``None.get_deployment``.
    """
    from litellm.router_utils.pre_call_checks.encrypted_content_affinity_check import (
        EncryptedContentAffinityCheck,
    )

    check = EncryptedContentAffinityCheck(router=None)
    healthy = [
        {
            "model_info": {"id": "dep-1"},
            "litellm_params": {"api_base": "https://x", "api_key": "k"},
        }
    ]
    matches, originating = check._find_deployments_on_same_encryption_boundary(
        healthy_deployments=healthy,
        model_id="dep-2",
    )
    assert matches == []
    assert originating is None


def test_boundary_fallback_originating_deployment_removed_returns_empty():
    """
    If the originating deployment has been removed from the router (e.g. via
    /model/delete), ``router.get_deployment`` returns None and we return [] so
    the caller falls back to the full healthy_deployments list.
    """
    from unittest.mock import MagicMock

    from litellm.router_utils.pre_call_checks.encrypted_content_affinity_check import (
        EncryptedContentAffinityCheck,
    )

    mock_router = MagicMock()
    mock_router.get_deployment.return_value = None

    check = EncryptedContentAffinityCheck(router=mock_router)
    healthy = [
        {
            "model_info": {"id": "dep-1"},
            "litellm_params": {"api_base": "https://x", "api_key": "k"},
        }
    ]
    matches, originating = check._find_deployments_on_same_encryption_boundary(
        healthy_deployments=healthy,
        model_id="dep-removed",
    )
    assert matches == []
    assert originating is None
    mock_router.get_deployment.assert_called_once_with(model_id="dep-removed")


def test_boundary_key_accepts_pydantic_litellm_params_instance():
    """
    Regression: ``_encryption_boundary_key`` must accept any object exposing
    dict-style ``.get()`` (incl. ``LiteLLM_Params`` Pydantic instances) — not
    just plain dicts.

    A stricter ``isinstance(dict)`` guard would silently return ``None`` for a
    ``LiteLLM_Params`` value, drop the deployment from boundary matching, and
    fall back to the full pool — which is the exact ``invalid_encrypted_content``
    failure this check exists to prevent.
    """
    from litellm.router_utils.pre_call_checks.encrypted_content_affinity_check import (
        EncryptedContentAffinityCheck,
    )
    from litellm.types.router import LiteLLM_Params

    pydantic_params = LiteLLM_Params(
        model="azure/gpt-5.3-codex",
        api_base="https://mateo-resource.openai.azure.com",
        api_key="fake-azure-resource-key-a",
    )
    plain_params = {
        "model": "azure/gpt-5.3-codex",
        "api_base": "https://mateo-resource.openai.azure.com",
        "api_key": "fake-azure-resource-key-a",
    }

    pydantic_key = EncryptedContentAffinityCheck._encryption_boundary_key(
        pydantic_params
    )
    plain_key = EncryptedContentAffinityCheck._encryption_boundary_key(plain_params)

    assert pydantic_key is not None
    assert (
        pydantic_key
        == plain_key
        == (
            "https://mateo-resource.openai.azure.com",
            "fake-azure-resource-key-a",
        )
    )


def test_boundary_key_rejects_non_dict_like_inputs():
    """
    Inputs that don't expose ``.get()`` (None, lists, strings, ints) -> None.
    Guards against accidentally treating a stray non-dict-like value as a
    valid boundary.
    """
    from litellm.router_utils.pre_call_checks.encrypted_content_affinity_check import (
        EncryptedContentAffinityCheck,
    )

    for bad in (None, [], "not a dict", 42, object()):
        assert EncryptedContentAffinityCheck._encryption_boundary_key(bad) is None

    assert (
        EncryptedContentAffinityCheck._encryption_boundary_key(
            {"api_base": "", "api_key": "k"}
        )
        is None
    )
    assert (
        EncryptedContentAffinityCheck._encryption_boundary_key(
            {"api_base": "https://x"}
        )
        is None
    )


# ---------------------------------------------------------------------------
# Fail-fast when originating deployment is unavailable and no boundary peer
# ---------------------------------------------------------------------------


def _make_originating_mock(api_base: str, api_key: str):
    from unittest.mock import MagicMock

    originating = MagicMock()
    originating.litellm_params.model_dump.return_value = {
        "api_base": api_base,
        "api_key": api_key,
    }
    return originating


def _make_router_mock_with_cooldown(
    originating, cooldown_entries: Optional[List[tuple]] = None
):
    """
    Build a MagicMock router whose ``cooldown_cache.async_get_active_cooldowns``
    returns ``cooldown_entries`` (defaulting to ``[]`` — no active cooldown).
    """
    from unittest.mock import AsyncMock, MagicMock

    mock_router = MagicMock()
    mock_router.get_deployment.return_value = originating
    mock_router.cooldown_cache.async_get_active_cooldowns = AsyncMock(
        return_value=list(cooldown_entries or [])
    )
    return mock_router


@pytest.mark.asyncio
async def test_affinity_raises_service_unavailable_when_origin_cooled_for_non_429():
    """
    Originating deployment is in the router config, in cooldown for a non-429
    cause (e.g. a 500), and no boundary peer is configured. The check must
    surface this as a 503 (transient, but not rate-limit-specific) rather than
    dispatching to a non-peer deployment.
    """
    from litellm.exceptions import ServiceUnavailableError
    from litellm.router_utils.pre_call_checks.encrypted_content_affinity_check import (
        EncryptedContentAffinityCheck,
    )

    originating = _make_originating_mock("https://account-a.openai.azure.com/", "key-a")
    mock_router = _make_router_mock_with_cooldown(
        originating,
        cooldown_entries=[
            (
                "deployment-a-cooled",
                {
                    "exception_received": "boom",
                    "status_code": "500",
                    "timestamp": time.time(),
                    "cooldown_time": 60.0,
                },
            )
        ],
    )

    check = EncryptedContentAffinityCheck(router=mock_router)
    encoded_id = ResponsesAPIRequestUtils._build_encrypted_item_id(
        "deployment-a-cooled", "rs_test"
    )
    healthy_only_b = [
        {
            "model_info": {"id": "deployment-b"},
            "litellm_params": {
                "api_base": "https://account-b.openai.azure.com/",
                "api_key": "key-b",
                "model": "azure/gpt-5.4",
            },
        }
    ]
    request_kwargs = {
        "input": [{"id": encoded_id, "type": "reasoning"}],
    }

    with pytest.raises(ServiceUnavailableError) as excinfo:
        await check.async_filter_deployments(
            model="gpt-5.4",
            healthy_deployments=healthy_only_b,
            messages=None,
            request_kwargs=request_kwargs,
        )

    # Public error message intentionally omits the originating model_id to
    # avoid an authenticated-caller probing oracle.
    assert "deployment-a-cooled" not in str(excinfo.value)
    assert excinfo.value.status_code == 503


@pytest.mark.asyncio
async def test_affinity_raises_rate_limit_with_retry_after_when_origin_cooled_for_429():
    """
    Originating deployment is in cooldown specifically because of a 429.
    The check must surface this as a 429 RateLimitError with a Retry-After
    header derived from the cooldown's remaining window, so OpenAI-compatible
    clients respect the backoff instead of giving up on a 503.
    """
    from litellm.exceptions import RateLimitError
    from litellm.router_utils.pre_call_checks.encrypted_content_affinity_check import (
        EncryptedContentAffinityCheck,
    )

    originating = _make_originating_mock("https://account-a.openai.azure.com/", "key-a")
    cooldown_started = time.time() - 5.0
    mock_router = _make_router_mock_with_cooldown(
        originating,
        cooldown_entries=[
            (
                "deployment-a-cooled-429",
                {
                    "exception_received": "rate limited",
                    "status_code": "429",
                    "timestamp": cooldown_started,
                    "cooldown_time": 60.0,
                },
            )
        ],
    )

    check = EncryptedContentAffinityCheck(router=mock_router)
    encoded_id = ResponsesAPIRequestUtils._build_encrypted_item_id(
        "deployment-a-cooled-429", "rs_test"
    )
    healthy_only_b = [
        {
            "model_info": {"id": "deployment-b"},
            "litellm_params": {
                "api_base": "https://account-b.openai.azure.com/",
                "api_key": "key-b",
                "model": "azure/gpt-5.4",
            },
        }
    ]
    request_kwargs = {
        "input": [{"id": encoded_id, "type": "reasoning"}],
    }

    with pytest.raises(RateLimitError) as excinfo:
        await check.async_filter_deployments(
            model="gpt-5.4",
            healthy_deployments=healthy_only_b,
            messages=None,
            request_kwargs=request_kwargs,
        )

    assert "deployment-a-cooled-429" not in str(excinfo.value)
    assert excinfo.value.status_code == 429
    retry_after = excinfo.value.response.headers.get("retry-after")
    assert retry_after is not None
    assert 1 <= int(retry_after) <= 60


@pytest.mark.asyncio
async def test_affinity_raises_service_unavailable_when_origin_filtered_without_cooldown_entry():
    """
    Originating deployment is configured but absent from healthy_deployments
    with no active cooldown entry. Surface as 503 (we cannot prove the cause
    was rate-limiting) rather than guessing 429.
    """
    from litellm.exceptions import ServiceUnavailableError
    from litellm.router_utils.pre_call_checks.encrypted_content_affinity_check import (
        EncryptedContentAffinityCheck,
    )

    originating = _make_originating_mock("https://account-a.openai.azure.com/", "key-a")
    mock_router = _make_router_mock_with_cooldown(originating, cooldown_entries=[])

    check = EncryptedContentAffinityCheck(router=mock_router)
    encoded_id = ResponsesAPIRequestUtils._build_encrypted_item_id(
        "deployment-a-filtered", "rs_test"
    )
    healthy_only_b = [
        {
            "model_info": {"id": "deployment-b"},
            "litellm_params": {
                "api_base": "https://account-b.openai.azure.com/",
                "api_key": "key-b",
                "model": "azure/gpt-5.4",
            },
        }
    ]
    request_kwargs = {
        "input": [{"id": encoded_id, "type": "reasoning"}],
    }

    with pytest.raises(ServiceUnavailableError) as excinfo:
        await check.async_filter_deployments(
            model="gpt-5.4",
            healthy_deployments=healthy_only_b,
            messages=None,
            request_kwargs=request_kwargs,
        )

    assert excinfo.value.status_code == 503


@pytest.mark.asyncio
async def test_affinity_raises_bad_request_when_origin_removed():
    """
    Originating deployment was removed from the router config and no boundary
    peer is available. This is permanent (the stale encrypted_content cannot
    be honored), so surface a 400 with actionable text.
    """
    from unittest.mock import MagicMock

    from litellm.exceptions import BadRequestError
    from litellm.router_utils.pre_call_checks.encrypted_content_affinity_check import (
        EncryptedContentAffinityCheck,
    )

    mock_router = MagicMock()
    mock_router.get_deployment.return_value = None

    check = EncryptedContentAffinityCheck(router=mock_router)
    encoded_id = ResponsesAPIRequestUtils._build_encrypted_item_id(
        "deployment-removed", "rs_test"
    )
    healthy_only_b = [
        {
            "model_info": {"id": "deployment-b"},
            "litellm_params": {
                "api_base": "https://account-b.openai.azure.com/",
                "api_key": "key-b",
                "model": "azure/gpt-5.4",
            },
        }
    ]
    request_kwargs = {
        "input": [{"id": encoded_id, "type": "reasoning"}],
    }

    with pytest.raises(BadRequestError) as excinfo:
        await check.async_filter_deployments(
            model="gpt-5.4",
            healthy_deployments=healthy_only_b,
            messages=None,
            request_kwargs=request_kwargs,
        )

    assert "deployment-removed" not in str(excinfo.value)


@pytest.mark.asyncio
async def test_affinity_does_not_raise_when_boundary_peer_available():
    """
    Even when the originating deployment is filtered out, if a peer on the
    same (api_base, api_key) is in healthy_deployments, the boundary-match
    path must succeed silently — no exception.
    """
    from unittest.mock import MagicMock

    from litellm.router_utils.pre_call_checks.encrypted_content_affinity_check import (
        EncryptedContentAffinityCheck,
    )

    originating = MagicMock()
    originating.litellm_params.model_dump.return_value = {
        "api_base": "https://account-a.openai.azure.com/",
        "api_key": "key-a",
    }
    mock_router = MagicMock()
    mock_router.get_deployment.return_value = originating

    check = EncryptedContentAffinityCheck(router=mock_router)
    encoded_id = ResponsesAPIRequestUtils._build_encrypted_item_id(
        "deployment-a", "rs_test"
    )
    peer = {
        "model_info": {"id": "deployment-a-peer"},
        "litellm_params": {
            "api_base": "https://account-a.openai.azure.com/",
            "api_key": "key-a",
            "model": "azure/gpt-5.4",
        },
    }
    request_kwargs = {
        "input": [{"id": encoded_id, "type": "reasoning"}],
    }

    result = await check.async_filter_deployments(
        model="gpt-5.4",
        healthy_deployments=[peer],
        messages=None,
        request_kwargs=request_kwargs,
    )

    assert result == [peer]
    assert request_kwargs.get("_encrypted_content_affinity_pinned") is True


@pytest.mark.asyncio
async def test_model_group_affinity_config_enables_encrypted_content_affinity():
    from litellm.router_utils.pre_call_checks.encrypted_content_affinity_check import (
        EncryptedContentAffinityCheck,
    )

    model_group = "openai.gpt-5.1-codex"
    target_deployment = {
        "model_name": model_group,
        "litellm_params": {"model": "openai/gpt-5.1-codex"},
        "model_info": {"id": "deployment-b"},
    }
    healthy_deployments = [
        {
            "model_name": model_group,
            "litellm_params": {"model": "openai/gpt-5.1-codex"},
            "model_info": {"id": "deployment-a"},
        },
        target_deployment,
    ]
    encoded_id = ResponsesAPIRequestUtils._build_encrypted_item_id(
        "deployment-b", "rs_test"
    )
    request_kwargs = {
        "input": [{"type": "reasoning", "id": encoded_id}],
        "litellm_metadata": {},
    }
    check = EncryptedContentAffinityCheck(
        enable_global_affinity=False,
        model_group_affinity_config={
            model_group: ["encrypted_content_affinity"],
        },
    )

    filtered = await check.async_filter_deployments(
        model=model_group,
        healthy_deployments=healthy_deployments,
        messages=None,
        request_kwargs=request_kwargs,
    )

    assert filtered == [target_deployment]
    assert request_kwargs["litellm_metadata"]["encrypted_content_affinity_enabled"]
    assert request_kwargs.get("_encrypted_content_affinity_pinned") is True


@pytest.mark.asyncio
async def test_model_group_affinity_config_does_not_disable_global_encrypted_content_affinity():
    from litellm.router_utils.pre_call_checks.encrypted_content_affinity_check import (
        EncryptedContentAffinityCheck,
    )

    model_group = "openai.gpt-5.1-codex"
    target_deployment = {
        "model_name": model_group,
        "litellm_params": {"model": "openai/gpt-5.1-codex"},
        "model_info": {"id": "deployment-b"},
    }
    healthy_deployments = [
        {
            "model_name": model_group,
            "litellm_params": {"model": "openai/gpt-5.1-codex"},
            "model_info": {"id": "deployment-a"},
        },
        target_deployment,
    ]
    encoded_id = ResponsesAPIRequestUtils._build_encrypted_item_id(
        "deployment-b", "rs_test"
    )
    request_kwargs = {
        "input": [{"type": "reasoning", "id": encoded_id}],
        "litellm_metadata": {},
    }
    check = EncryptedContentAffinityCheck(
        enable_global_affinity=True,
        model_group_affinity_config={
            model_group: ["deployment_affinity"],
        },
    )

    filtered = await check.async_filter_deployments(
        model=model_group,
        healthy_deployments=healthy_deployments,
        messages=None,
        request_kwargs=request_kwargs,
    )

    assert filtered == [target_deployment]
    assert request_kwargs["litellm_metadata"]["encrypted_content_affinity_enabled"]
    assert request_kwargs.get("_encrypted_content_affinity_pinned") is True


