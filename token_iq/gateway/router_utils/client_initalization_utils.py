import asyncio
from typing import TYPE_CHECKING, Any, Final

from token_iq.gateway.utils import calculate_max_parallel_requests

if TYPE_CHECKING:
    from token_iq.gateway.router import Router as _Router

    GatewayRouter = _Router
else:
    GatewayRouter = Any


class InitalizeCachedClient:
    @staticmethod
    def set_max_parallel_requests_client(litellm_router_instance: GatewayRouter, model: dict):
        litellm_params: Final = model.get("litellm_params", {})
        model_id: Final = model["model_info"]["id"]
        rpm: Final = litellm_params.get("rpm", None)
        tpm: Final = litellm_params.get("tpm", None)
        max_parallel_requests: Final = litellm_params.get("max_parallel_requests", None)
        calculated_max_parallel_requests: Final = calculate_max_parallel_requests(
            rpm=rpm,
            max_parallel_requests=max_parallel_requests,
            tpm=tpm,
            default_max_parallel_requests=litellm_router_instance.default_max_parallel_requests,
        )
        if calculated_max_parallel_requests:
            semaphore: Final = asyncio.Semaphore(calculated_max_parallel_requests)
            cache_key: Final = f"{model_id}_max_parallel_requests_client"
            litellm_router_instance.cache.set_cache(
                key=cache_key,
                value=semaphore,
                local_only=True,
            )
