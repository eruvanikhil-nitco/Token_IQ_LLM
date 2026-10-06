"""A2A Protocol handler for Unified Guardrails."""

from typing import Final

from token_iq.gateway.llms.a2a.chat.guardrail_translation.handler import A2AGuardrailHandler
from token_iq.gateway.types.utils import CallTypes

guardrail_translation_mappings: Final = {
    CallTypes.send_message: A2AGuardrailHandler,
    CallTypes.asend_message: A2AGuardrailHandler,
}

__all__ = ["guardrail_translation_mappings"]
