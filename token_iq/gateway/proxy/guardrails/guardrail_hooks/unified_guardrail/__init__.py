from typing import Final

from token_iq.gateway.llms.openai.chat.guardrail_translation.handler import (
    OpenAIChatCompletionsHandler,
)
from token_iq.gateway.types.utils import CallTypes

endpoint_translation_mappings: Final = {
    CallTypes.completion: OpenAIChatCompletionsHandler,
    CallTypes.acompletion: OpenAIChatCompletionsHandler,
}

__all__ = ["endpoint_translation_mappings"]
