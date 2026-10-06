from token_iq.gateway.core_utils.llm_cost_calc.utils import generic_cost_per_token
from token_iq.gateway.types.utils import Usage


def cost_per_token(model: str, usage: Usage) -> tuple[float, float]:
    return generic_cost_per_token(model=model, usage=usage, custom_llm_provider="tencent")
