from token_iq.gateway.llms.base_llm.image_generation.transformation import (
    BaseImageGenerationConfig,
)

from .transformation import DashScopeImageGenerationConfig

__all__ = ["DashScopeImageGenerationConfig"]


def get_dashscope_image_generation_config(model: str) -> BaseImageGenerationConfig:
    return DashScopeImageGenerationConfig()
