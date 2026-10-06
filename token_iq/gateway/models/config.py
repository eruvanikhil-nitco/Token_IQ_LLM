"""
Config table model.

Canonical definition for ``litellm_config``. Re-exported from
``litellm.proxy._types`` for backwards compatibility.
"""

from token_iq.gateway.types.llms.base import GatewayPydanticObjectBase


class LiteLLM_Config(GatewayPydanticObjectBase):
    param_name: str
    param_value: dict
