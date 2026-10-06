"""
LiteLLM A2A - Wrapper for invoking A2A protocol agents.

This module provides a thin wrapper around the official `a2a` SDK that:
- Handles httpx client creation and agent card resolution
- Adds LiteLLM logging via @client decorator
- Matches the A2A SDK interface (SendMessageRequest, SendMessageResponse, etc.)

Example usage (standalone functions with @client decorator):
    ```python
    from token_iq.gateway.a2a_protocol import asend_message
    from a2a.types import SendMessageRequest, MessageSendParams
    from uuid import uuid4

    request = SendMessageRequest(
        id=str(uuid4()),
        params=MessageSendParams(
            message={
                "role": "user",
                "parts": [{"kind": "text", "text": "Hello!"}],
                "messageId": uuid4().hex,
            }
        )
    )
    response = await asend_message(
        base_url="http://localhost:10001",
        request=request,
    )
    print(response.model_dump(mode='json', exclude_none=True))
    ```

Example usage (class-based):
    ```python
    from token_iq.gateway.a2a_protocol import A2AClient

    client = A2AClient(base_url="http://localhost:10001")
    response = await client.send_message(request)
    ```
"""

from token_iq.gateway.a2a_protocol.client import A2AClient
from token_iq.gateway.a2a_protocol.exceptions import (
    A2AAgentCardError,
    A2AConnectionError,
    A2AError,
    A2ALocalhostURLError,
)
from token_iq.gateway.a2a_protocol.main import (
    aget_agent_card,
    asend_message,
    asend_message_streaming,
    create_a2a_client,
    send_message,
)
from token_iq.gateway.types.agents import LiteLLMSendMessageResponse

__all__ = [
    "A2AAgentCardError",
    "A2AClient",
    "A2AConnectionError",
    "A2AError",
    "A2ALocalhostURLError",
    "LiteLLMSendMessageResponse",
    "aget_agent_card",
    "asend_message",
    "asend_message_streaming",
    "create_a2a_client",
    "send_message",
]
