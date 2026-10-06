from typing_extensions import TypedDict

from token_iq.gateway.llms.custom_llm import CustomLLM


class CustomLLMItem(TypedDict):
    provider: str
    custom_handler: CustomLLM
