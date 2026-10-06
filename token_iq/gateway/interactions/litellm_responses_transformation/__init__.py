"""
Bridge module for connecting Interactions API to Responses API via litellm.responses().
"""

from token_iq.gateway.interactions.litellm_responses_transformation.handler import (
    GatewayResponsesInteractionsHandler,
)
from token_iq.gateway.interactions.litellm_responses_transformation.transformation import (
    GatewayResponsesInteractionsConfig,
)

__all__ = [
    "GatewayResponsesInteractionsConfig",  # Transformation config class (not BaseInteractionsAPIConfig)
    "GatewayResponsesInteractionsHandler",
]
