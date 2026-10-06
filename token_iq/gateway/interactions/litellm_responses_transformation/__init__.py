"""
Bridge module for connecting Interactions API to Responses API via litellm.responses().
"""

from token_iq.gateway.interactions.litellm_responses_transformation.handler import (
    LiteLLMResponsesInteractionsHandler,
)
from token_iq.gateway.interactions.litellm_responses_transformation.transformation import (
    LiteLLMResponsesInteractionsConfig,
)

__all__ = [
    "LiteLLMResponsesInteractionsConfig",  # Transformation config class (not BaseInteractionsAPIConfig)
    "LiteLLMResponsesInteractionsHandler",
]
