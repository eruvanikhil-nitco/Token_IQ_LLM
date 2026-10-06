"""OpenAI Responses API handler for Unified Guardrails."""

from typing import Final

from token_iq.gateway.llms.openai.responses.guardrail_translation.handler import (
    OpenAIResponsesHandler,
)
from token_iq.gateway.types.utils import CallTypes

guardrail_translation_mappings: Final = {
    CallTypes.responses: OpenAIResponsesHandler,
    CallTypes.aresponses: OpenAIResponsesHandler,
}
__all__ = ["guardrail_translation_mappings"]
