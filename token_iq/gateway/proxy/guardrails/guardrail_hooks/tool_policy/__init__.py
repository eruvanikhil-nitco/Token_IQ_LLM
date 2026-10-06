from typing import Final

from token_iq import gateway as litellm
from token_iq.gateway.types.guardrails import Guardrail, LitellmParams


def initialize_guardrail(litellm_params: LitellmParams, guardrail: Guardrail):
    from token_iq.gateway.proxy.guardrails.guardrail_hooks.tool_policy.tool_policy_guardrail import (
        ToolPolicyGuardrail,
    )

    _callback: Final = ToolPolicyGuardrail(
        guardrail_name=guardrail.get("guardrail_name", "tool_policy"),
        event_hook=litellm_params.mode,
        default_on=litellm_params.default_on,
    )
    litellm.logging_callback_manager.add_litellm_callback(_callback)
    return _callback
