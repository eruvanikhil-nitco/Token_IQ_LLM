from typing import TYPE_CHECKING, Final

from token_iq.gateway.proxy.guardrails.guardrail_hooks.onyx.onyx import OnyxGuardrail
from token_iq.gateway.types.guardrails import SupportedGuardrailIntegrations

if TYPE_CHECKING:
    from token_iq.gateway.types.guardrails import Guardrail, LitellmParams


def initialize_guardrail(litellm_params: "LitellmParams", guardrail: "Guardrail"):
    from token_iq import gateway

    _onyx_callback: Final = OnyxGuardrail(
        api_base=litellm_params.api_base,
        api_key=litellm_params.api_key,
        guardrail_name=guardrail.get("guardrail_name", ""),
        event_hook=litellm_params.mode,
        default_on=litellm_params.default_on,
    )
    gateway.logging_callback_manager.add_litellm_callback(_onyx_callback)

    return _onyx_callback


guardrail_initializer_registry: Final = {
    SupportedGuardrailIntegrations.ONYX.value: initialize_guardrail,
}


guardrail_class_registry: Final = {
    SupportedGuardrailIntegrations.ONYX.value: OnyxGuardrail,
}
