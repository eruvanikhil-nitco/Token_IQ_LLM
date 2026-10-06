from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Final

import httpx

from token_iq.gateway.llms.base_llm.passthrough.transformation import BasePassthroughConfig
from token_iq.gateway.secret_managers.main import get_secret_str
from token_iq.gateway.types.llms.openai import AllMessageValues

if TYPE_CHECKING:
    from httpx import URL, Response

    from token_iq.gateway.core_utils.litellm_logging import Logging as GatewayLoggingObj
    from token_iq.gateway.types.utils import CostResponseTypes

OPENROUTER_API_BASE: Final = "https://openrouter.ai/api/v1"


class OpenRouterPassthroughConfig(BasePassthroughConfig):
    """Courier support for OpenRouter.

    OpenRouter speaks OpenAI's wire format, so reading a response back is the existing
    chat config's job rather than a second parser written here. OpenRouter also prices
    its own requests and reports the figure in `usage.cost`, which the shared cost path
    treats as authoritative, so the gateway records what OpenRouter billed instead of
    re-deriving it from the price map.
    """

    def is_streaming_request(self, endpoint: str, request_data: Mapping[str, object]) -> bool:
        return bool(request_data.get("stream", False))

    def get_complete_url(
        self,
        api_base: str | None,
        api_key: str | None,
        model: str,
        endpoint: str,
        request_query_params: Mapping[str, object] | None,
        litellm_params: Mapping[str, object],
    ) -> tuple[URL, str]:
        base_target_url: Final = self.get_api_base(api_base)
        if base_target_url is None:
            raise ValueError("OpenRouter api base not found")
        return httpx.URL(f"{base_target_url}/{endpoint.lstrip('/')}"), base_target_url

    def validate_environment(
        self,
        headers: dict,  # mutable-ok: base class contract mutates in place for httpx
        model: str,
        messages: Sequence[AllMessageValues],
        optional_params: Mapping[str, object],
        litellm_params: Mapping[str, object],
        api_key: str | None = None,
        api_base: str | None = None,
    ) -> dict:  # mutable-ok: base class contract returns dict for httpx
        resolved_key: Final = self.get_api_key(api_key)
        if resolved_key is None:
            raise ValueError("OpenRouter api key not found")
        headers["Authorization"] = f"Bearer {resolved_key}"  # rebind-ok: base class mutates headers in place
        headers["Content-Type"] = "application/json"  # rebind-ok: base class mutates headers in place
        return headers

    def logging_non_streaming_response(
        self,
        model: str,
        custom_llm_provider: str,
        httpx_response: Response,
        request_data: Mapping[str, object],
        logging_obj: GatewayLoggingObj,
        endpoint: str,
    ) -> CostResponseTypes | None:
        from token_iq.gateway import encoding
        from token_iq.gateway.types.utils import LlmProviders, ModelResponse
        from token_iq.gateway.utils import ProviderConfigManager

        if "completions" not in endpoint:
            return None

        chat_config: Final = ProviderConfigManager.get_provider_chat_config(
            provider=LlmProviders(custom_llm_provider),
            model=model,
        )
        if chat_config is None:
            raise ValueError(f"No OpenRouter chat config found for model: {model}")

        raw_messages: Final = request_data.get("messages")
        return chat_config.transform_response(
            model=model,
            messages=list(raw_messages) if isinstance(raw_messages, list) else [],  # mutable-ok: callee wants a list
            raw_response=httpx_response,
            model_response=ModelResponse(),
            logging_obj=logging_obj,
            optional_params={},  # mutable-ok: empty kwarg required by transform_response
            litellm_params={},  # mutable-ok: empty kwarg required by transform_response
            api_key="",
            request_data=dict(request_data),  # mutable-ok: callee wants a dict
            encoding=encoding,
        )

    @staticmethod
    def get_api_base(api_base: str | None = None) -> str | None:
        return api_base or get_secret_str("OPENROUTER_API_BASE") or OPENROUTER_API_BASE

    @staticmethod
    def get_api_key(api_key: str | None = None) -> str | None:
        return api_key or get_secret_str("OPENROUTER_API_KEY")

    @staticmethod
    def get_base_model(model: str) -> str | None:
        return model

    def get_models(
        self, api_key: str | None = None, api_base: str | None = None
    ) -> list[str]:  # mutable-ok: base class contract returns list
        return list(super().get_models(api_key, api_base))
