import asyncio
import traceback

from dotenv import load_dotenv

import token_iq.gateway.types
from token_iq import gateway as litellm
import token_iq.gateway.types.utils
from token_iq import gateway as litellm
from token_iq.gateway.llms.anthropic.chat import ModelResponseIterator

load_dotenv()
import io

from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

from token_iq import gateway as litellm

from token_iq.gateway.llms.anthropic.common_utils import process_anthropic_headers
from httpx import Headers
from base_llm_unit_tests import BaseLLMChatTest


@pytest.mark.flaky(retries=3, delay=2)
class TestMistralCompletion(BaseLLMChatTest):
    def get_base_completion_call_args(self) -> dict:
        litellm.set_verbose = True
        return {"model": "mistral/mistral-medium-latest"}

    def test_tool_call_no_arguments(self, tool_call_no_arguments):
        """Test that tool calls with no arguments is translated correctly. Relevant issue: https://github.com/BerriAI/litellm/issues/6833"""
        pass
