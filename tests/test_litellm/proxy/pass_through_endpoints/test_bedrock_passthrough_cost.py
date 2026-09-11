from __future__ import annotations

import json

import httpx
import pytest

from litellm.proxy.pass_through_endpoints.success_handler import PassThroughEndpointLogging

CONVERSE_BODY = {
    "output": {"message": {"role": "assistant", "content": [{"text": "hello"}]}},
    "stopReason": "end_turn",
    "usage": {"inputTokens": 11, "outputTokens": 4, "totalTokens": 15},
}

INVOKE_BODY = {
    "id": "msg_bdrk_01",
    "type": "message",
    "role": "assistant",
    "model": "claude-3-5-sonnet-20241022",
    "content": [{"type": "text", "text": "hello"}],
    "stop_reason": "end_turn",
    "usage": {"input_tokens": 11, "output_tokens": 4},
}


def _logging_obj(call_id: str, *, stream: bool = False):
    from litellm.litellm_core_utils.litellm_logging import Logging

    return Logging(
        model="anthropic.claude-3-5-sonnet-20241022-v2:0",
        messages=[],
        stream=stream,
        call_type="pass_through_endpoint",
        start_time=None,
        litellm_call_id=call_id,
        function_id="test",
    )


def test_bedrock_is_recognised_by_the_success_handler():
    """Without this the reply falls through to the untyped default, and a Bedrock
    request that succeeded and was billed by AWS records zero tokens and zero cost."""
    handler = PassThroughEndpointLogging()
    assert handler.is_bedrock_route("bedrock") is True
    assert handler.is_bedrock_route("openai") is False
    assert handler.is_bedrock_route(None) is False


@pytest.mark.parametrize(
    "endpoint,body,expected_prompt,expected_completion",
    [
        ("model/anthropic.claude-3-5-sonnet-20241022-v2:0/converse", CONVERSE_BODY, 11, 4),
        ("model/anthropic.claude-3-5-sonnet-20241022-v2:0/invoke", INVOKE_BODY, 11, 4),
    ],
)
def test_usage_is_read_from_both_bedrock_response_shapes(endpoint, body, expected_prompt, expected_completion):
    """Bedrock answers in two different shapes depending on the API used, and the
    courier route must price both."""
    from litellm.llms.bedrock.passthrough.transformation import BedrockPassthroughConfig

    result = BedrockPassthroughConfig().logging_non_streaming_response(
        model="anthropic.claude-3-5-sonnet-20241022-v2:0",
        custom_llm_provider="bedrock",
        httpx_response=httpx.Response(200, content=json.dumps(body).encode()),
        request_data={},
        logging_obj=_logging_obj("test-bedrock-cost"),
        endpoint=endpoint,
    )

    assert result is not None, f"no usage read from the {endpoint.rsplit('/', 1)[-1]} shape"
    assert result.usage.prompt_tokens == expected_prompt
    assert result.usage.completion_tokens == expected_completion
