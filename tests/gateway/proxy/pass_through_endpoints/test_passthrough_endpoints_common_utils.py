import json
import traceback
from unittest import mock
from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastapi import Request, Response
from fastapi.testclient import TestClient

from token_iq.gateway.caching.dual_cache import DualCache
from token_iq.gateway.passthrough.utils import CommonUtils


from unittest.mock import Mock

from token_iq.gateway.proxy.pass_through_endpoints.common_utils import get_gateway_virtual_key


@pytest.mark.asyncio
async def test_get_gateway_virtual_key():
    """
    Test that the get_litellm_virtual_key function correctly handles the API key authentication
    """
    # Test with x-litellm-api-key
    mock_request = Mock()
    mock_request.headers = {"x-token-iq-api-key": "test-key-123"}
    result = get_gateway_virtual_key(mock_request)
    assert result == "Bearer test-key-123"

    # Test with Authorization header
    mock_request.headers = {"Authorization": "Bearer auth-key-456"}
    result = get_gateway_virtual_key(mock_request)
    assert result == "Bearer auth-key-456"

    # Test with both headers (x-litellm-api-key should take precedence)
    mock_request.headers = {
        "x-token-iq-api-key": "test-key-123",
        "Authorization": "Bearer auth-key-456",
    }
    result = get_gateway_virtual_key(mock_request)
    assert result == "Bearer test-key-123"


def test_encode_bedrock_runtime_modelid_arn():
    # Test application-inference-profile ARN
    endpoint = "model/arn:aws:bedrock:us-east-1:123456789123:application-inference-profile/r742sbn2zckd/converse"
    expected = "model/arn:aws:bedrock:us-east-1:123456789123:application-inference-profile%2Fr742sbn2zckd/converse"
    result = CommonUtils.encode_bedrock_runtime_modelid_arn(endpoint)
    assert result == expected

    # Test inference-profile ARN
    endpoint = "model/arn:aws:bedrock:us-east-1:123456789012:inference-profile/test-profile/invoke"
    expected = "model/arn:aws:bedrock:us-east-1:123456789012:inference-profile%2Ftest-profile/invoke"
    result = CommonUtils.encode_bedrock_runtime_modelid_arn(endpoint)
    assert result == expected

    # Test foundation-model ARN
    endpoint = "model/arn:aws:bedrock:us-east-1:123456789012:foundation-model/anthropic.claude-3/converse"
    expected = "model/arn:aws:bedrock:us-east-1:123456789012:foundation-model%2Fanthropic.claude-3/converse"
    result = CommonUtils.encode_bedrock_runtime_modelid_arn(endpoint)
    assert result == expected

    # Test custom-model ARN (2 slashes)
    endpoint = "model/arn:aws:bedrock:us-east-1:123456789012:custom-model/my-model.fine-tuned/abc123/invoke"
    expected = "model/arn:aws:bedrock:us-east-1:123456789012:custom-model%2Fmy-model.fine-tuned%2Fabc123/invoke"
    result = CommonUtils.encode_bedrock_runtime_modelid_arn(endpoint)
    assert result == expected

    # Test provisioned-model ARN
    endpoint = "model/arn:aws:bedrock:us-east-1:123456789012:provisioned-model/test-model/converse"
    expected = "model/arn:aws:bedrock:us-east-1:123456789012:provisioned-model%2Ftest-model/converse"
    result = CommonUtils.encode_bedrock_runtime_modelid_arn(endpoint)
    assert result == expected


def test_encode_bedrock_runtime_modelid_arn_no_arn():
    # Test regular model ID (no ARN)
    endpoint = "model/anthropic.claude-3-sonnet-20240229-v1:0/converse"
    result = CommonUtils.encode_bedrock_runtime_modelid_arn(endpoint)
    assert result == endpoint


def test_encode_bedrock_runtime_modelid_arn_edge_cases():
    # Test multiple ARN types (should only encode first match)
    endpoint = "model/arn:aws:bedrock:us-east-1:123456789012:application-inference-profile/test1/converse"
    expected = "model/arn:aws:bedrock:us-east-1:123456789012:application-inference-profile%2Ftest1/converse"
    result = CommonUtils.encode_bedrock_runtime_modelid_arn(endpoint)
    assert result == expected

    # Test ARN with special characters in resource ID
    endpoint = "model/arn:aws:bedrock:us-east-1:123456789012:application-inference-profile/test-profile.v1/invoke"
    expected = "model/arn:aws:bedrock:us-east-1:123456789012:application-inference-profile%2Ftest-profile.v1/invoke"
    result = CommonUtils.encode_bedrock_runtime_modelid_arn(endpoint)
    assert result == expected


def test_encode_bedrock_runtime_modelid_arn_partition_arns() -> None:
    endpoint = "model/arn:aws-cn:bedrock:cn-north-1:123456789012:application-inference-profile/r742sbn2zckd/converse"
    expected = "model/arn:aws-cn:bedrock:cn-north-1:123456789012:application-inference-profile%2Fr742sbn2zckd/converse"
    assert CommonUtils.encode_bedrock_runtime_modelid_arn(endpoint) == expected

    endpoint = "model/arn:aws-us-gov:bedrock:us-gov-west-1:123456789012:inference-profile/test-profile/invoke"
    expected = "model/arn:aws-us-gov:bedrock:us-gov-west-1:123456789012:inference-profile%2Ftest-profile/invoke"
    assert CommonUtils.encode_bedrock_runtime_modelid_arn(endpoint) == expected


def test_assert_passthrough_body_fidelity_allows_absent_managed_files_hook() -> None:
    from token_iq.gateway.proxy.pass_through_endpoints.common_utils import (
        assert_passthrough_body_fidelity,
    )

    assert_passthrough_body_fidelity(None)


def test_assert_passthrough_body_fidelity_rejects_registered_managed_files_hook() -> None:
    """A registered managed_files hook enables the managed-id rewriter, which
    swaps provider IDs out of response bodies, so startup must refuse it."""
    from token_iq.gateway.integrations.custom_logger import CustomLogger
    from token_iq.gateway.proxy.pass_through_endpoints.common_utils import (
        assert_passthrough_body_fidelity,
    )

    with pytest.raises(ValueError, match="managed_files") as excinfo:
        assert_passthrough_body_fidelity(CustomLogger())

    assert "managed_files" in str(excinfo.value)


def test_proxy_startup_refuses_a_registered_managed_files_hook() -> None:
    """Drive the real startup path: a registered hook must abort startup.

    Asserting on `startup_event` itself rather than the helper is what proves
    the guard is actually wired in, so deleting the call fails this test.
    """
    from token_iq.gateway.integrations.custom_logger import CustomLogger
    from token_iq.gateway.proxy.utils import ProxyLogging

    proxy_logging = ProxyLogging(user_api_key_cache=DualCache())
    with patch.object(
        ProxyLogging, "_init_litellm_callbacks", lambda self, llm_router=None: None
    ):
        proxy_logging.proxy_hook_mapping["managed_files"] = CustomLogger()
        with pytest.raises(ValueError, match="managed_files") as excinfo:
            proxy_logging.startup_event(llm_router=None, redis_usage_cache=None)

    assert "managed_files" in str(excinfo.value)


@pytest.mark.asyncio
async def test_proxy_startup_succeeds_without_the_managed_files_hook() -> None:
    """The happy path must still start, so the guard cannot pass by always raising.

    Async because `startup_event` schedules the Slack daily report with
    `asyncio.create_task`, which needs a running loop.
    """
    from token_iq.gateway.proxy.utils import ProxyLogging

    proxy_logging = ProxyLogging(user_api_key_cache=DualCache())
    with patch.object(
        ProxyLogging, "_init_litellm_callbacks", lambda self, llm_router=None: None
    ):
        proxy_logging.proxy_hook_mapping.pop("managed_files", None)
        proxy_logging.startup_event(llm_router=None, redis_usage_cache=None)
