import json
from datetime import datetime
from unittest.mock import AsyncMock



import httpx
import pytest

from token_iq import gateway
from token_iq.gateway import Choices, Message, ModelResponse
from token_iq.gateway.types.utils import PromptTokensDetails


@pytest.mark.asyncio
async def test_prompt_caching():
    """
    Tests that:
    - prompt_tokens_details is correctly handled and returned as PromptTokensDetails type
    """
    response1 = await gateway.acompletion(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "hi"}],
    )
    print("response1", response1)
    print("response1.usage", response1.usage)
    print("type of prompt_tokens_details", type(response1.usage.prompt_tokens_details))
    assert isinstance(response1.usage.prompt_tokens_details, PromptTokensDetails)
