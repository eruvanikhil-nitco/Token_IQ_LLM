from base_llm_unit_tests import BaseLLMChatTest
import pytest

from token_iq import gateway


class TestBedrockTestSuite(BaseLLMChatTest):
    def test_tool_call_no_arguments(self, tool_call_no_arguments):
        pass

    def get_base_completion_call_args(self) -> dict:
        gateway._turn_on_debug()
        return {
            "model": "bedrock/converse/us.meta.llama3-3-70b-instruct-v1:0",
        }
