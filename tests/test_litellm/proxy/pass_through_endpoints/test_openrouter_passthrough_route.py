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


def test_the_factory_registry_resolves_openrouter():
    """`llm_passthrough_factory_proxy_route` looks the provider up via
    get_provider_model_info, not the passthrough registry. Registering in only one
    of the two returns a 404 "Provider openrouter not found" at request time."""
    config = ProviderConfigManager.get_provider_model_info(
        provider=LlmProviders.OPENROUTER,
        model="openai/gpt-4o-mini",
    )
    assert config is not None, "the factory 404s when this is None"
    assert config.get_api_base() == "https://openrouter.ai/api/v1"


def test_the_courier_route_is_mounted():
    from litellm.proxy.proxy_server import app

    paths = {route.path for route in app.routes if hasattr(route, "path")}
    assert "/openrouter/{endpoint:path}" in paths


def test_openrouter_is_recognised_as_openai_compatible_for_cost_extraction():
    """Courier traffic is priced by the success handler, which dispatches on the target
    hostname. OpenRouter serves the OpenAI wire format, but was not in the allow-list,
    so its replies fell through to the untyped default and recorded zero tokens and
    zero cost while OpenRouter itself reported a real charge."""
    from litellm.proxy.pass_through_endpoints.llm_provider_handlers.openai_passthrough_logging_handler import (
        _is_openai_compatible_url,
    )

    assert _is_openai_compatible_url("https://openrouter.ai/api/v1/chat/completions") is True


def test_the_openai_allow_list_still_rejects_unrelated_hosts():
    from litellm.proxy.pass_through_endpoints.llm_provider_handlers.openai_passthrough_logging_handler import (
        _is_openai_compatible_url,
    )

    assert _is_openai_compatible_url("https://example.com/v1/chat/completions") is False
