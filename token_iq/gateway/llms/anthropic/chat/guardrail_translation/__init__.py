from typing import Final

from token_iq.gateway.llms.anthropic.chat.guardrail_translation.handler import (
    AnthropicMessagesHandler,
)
from token_iq.gateway.types.utils import CallTypes

guardrail_translation_mappings: Final = {
    CallTypes.anthropic_messages: AnthropicMessagesHandler,
}

__all__ = ["guardrail_translation_mappings"]
