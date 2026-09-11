from __future__ import annotations

from litellm.llms.openrouter.passthrough.transformation import OpenRouterPassthroughConfig
from litellm.types.utils import LlmProviders
from litellm.utils import ProviderConfigManager


def test_openrouter_resolves_to_its_passthrough_config():
    """The generic factory looks the provider up here; without an entry it 404s."""
    config = ProviderConfigManager.get_provider_passthrough_config(
        provider=LlmProviders.OPENROUTER,
        model="openai/gpt-4o-mini",
    )
    assert isinstance(config, OpenRouterPassthroughConfig)


def test_openrouter_reports_an_api_base_to_the_factory():
    """`llm_passthrough_factory_proxy_route` raises a 404 when this is None."""
    config = ProviderConfigManager.get_provider_passthrough_config(
        provider=LlmProviders.OPENROUTER,
        model="openai/gpt-4o-mini",
    )
    assert config is not None
    assert config.get_api_base() == "https://openrouter.ai/api/v1"


def test_the_courier_route_is_mounted():
    from litellm.proxy.proxy_server import app

    paths = {route.path for route in app.routes if hasattr(route, "path")}
    assert "/openrouter/{endpoint:path}" in paths
