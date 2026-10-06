"""
Bedrock AgentCore A2A provider.

Preserves JSON-RPC envelopes for AgentCore agents that speak A2A natively,
bypassing the completion bridge that would otherwise strip the envelope.
"""

from token_iq.gateway.a2a_protocol.providers.bedrock_agentcore.config import (
    BedrockAgentCoreA2AConfig,
)
from token_iq.gateway.a2a_protocol.providers.bedrock_agentcore.handler import (
    BedrockAgentCoreA2AHandler,
)
from token_iq.gateway.a2a_protocol.providers.bedrock_agentcore.transformation import (
    BedrockAgentCoreA2ATransformation,
)

__all__ = [
    "BedrockAgentCoreA2AConfig",
    "BedrockAgentCoreA2AHandler",
    "BedrockAgentCoreA2ATransformation",
]
