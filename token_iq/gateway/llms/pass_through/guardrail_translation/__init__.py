"""Pass-Through Endpoint guardrail translation handler."""

from typing import Final

from token_iq.gateway.llms.pass_through.guardrail_translation.handler import (
    LlmPassthroughRouteHandler,
    PassThroughEndpointHandler,
)
from token_iq.gateway.types.utils import CallTypes

guardrail_translation_mappings: Final = {
    CallTypes.pass_through: PassThroughEndpointHandler,
    CallTypes.allm_passthrough_route: LlmPassthroughRouteHandler,
}

__all__ = [
    "LlmPassthroughRouteHandler",
    "PassThroughEndpointHandler",
    "guardrail_translation_mappings",
]
