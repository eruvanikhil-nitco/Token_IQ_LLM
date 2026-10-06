from typing import TYPE_CHECKING, Final

from token_iq.gateway.types.guardrails import SupportedGuardrailIntegrations

from .panw_prisma_airs import PanwPrismaAirsHandler

if TYPE_CHECKING:
    from token_iq.gateway.types.guardrails import Guardrail, LitellmParams


def initialize_guardrail(litellm_params: "LitellmParams", guardrail: "Guardrail"):
    from token_iq import gateway as litellm

    guardrail_name: Final = guardrail.get("guardrail_name")

    # Note: api_key and profile_name can be None - handler will use env vars or API key's linked profile
    if not guardrail_name:
        raise ValueError("PANW Prisma AIRS: guardrail_name is required")

    _panw_callback: Final = PanwPrismaAirsHandler(
        **{
            **litellm_params.model_dump(exclude_unset=True),
            "guardrail_name": guardrail_name,
            "event_hook": litellm_params.mode,
            "default_on": litellm_params.default_on or False,
        }
    )
    litellm.logging_callback_manager.add_litellm_callback(_panw_callback)

    return _panw_callback


guardrail_initializer_registry: Final = {
    SupportedGuardrailIntegrations.PANW_PRISMA_AIRS.value: initialize_guardrail,
}


guardrail_class_registry: Final = {
    SupportedGuardrailIntegrations.PANW_PRISMA_AIRS.value: PanwPrismaAirsHandler,
}
