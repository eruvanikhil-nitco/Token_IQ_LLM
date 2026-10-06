from typing import TYPE_CHECKING, Final

from token_iq.gateway.types.guardrails import SupportedGuardrailIntegrations

from .dynamoai import DynamoAIGuardrails

if TYPE_CHECKING:
    from token_iq.gateway.types.guardrails import Guardrail, LitellmParams


def initialize_guardrail(litellm_params: "LitellmParams", guardrail: "Guardrail"):
    from token_iq import gateway

    _dynamoai_callback: Final = DynamoAIGuardrails(
        api_base=litellm_params.api_base,
        api_key=litellm_params.api_key,
        guardrail_name=guardrail.get("guardrail_name", ""),
        event_hook=litellm_params.mode,
        default_on=litellm_params.default_on,
    )
    gateway.logging_callback_manager.add_litellm_callback(_dynamoai_callback)

    return _dynamoai_callback


guardrail_initializer_registry: Final = {
    SupportedGuardrailIntegrations.DYNAMOAI.value: initialize_guardrail,
}


guardrail_class_registry: Final = {
    SupportedGuardrailIntegrations.DYNAMOAI.value: DynamoAIGuardrails,
}
