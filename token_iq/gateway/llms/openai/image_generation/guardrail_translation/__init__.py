"""OpenAI Image Generation handler for Unified Guardrails."""

from typing import Final

from token_iq.gateway.llms.openai.image_generation.guardrail_translation.handler import (
    OpenAIImageGenerationHandler,
)
from token_iq.gateway.types.utils import CallTypes

guardrail_translation_mappings: Final = {
    CallTypes.image_generation: OpenAIImageGenerationHandler,
    CallTypes.aimage_generation: OpenAIImageGenerationHandler,
}

__all__ = ["OpenAIImageGenerationHandler", "guardrail_translation_mappings"]
