from __future__ import annotations

import httpx
import pytest

from token_iq.gateway.llms.openrouter.passthrough.transformation import OpenRouterPassthroughConfig

DEFAULT_BASE = "https://openrouter.ai/api/v1"


def test_api_base_defaults_to_openrouter():
    """The generic pass-through factory 404s a provider whose api base is None,
    which is the only reason OpenRouter had no courier route."""
    assert OpenRouterPassthroughConfig.get_api_base() == DEFAULT_BASE


def test_explicit_api_base_wins():
    assert OpenRouterPassthroughConfig.get_api_base("https://proxy.internal/v1") == "https://proxy.internal/v1"


def test_env_api_base_overrides_the_default(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_BASE", "https://env.example/v1")
    assert OpenRouterPassthroughConfig.get_api_base() == "https://env.example/v1"


def test_complete_url_joins_the_endpoint_without_doubling_slashes():
    url, base = OpenRouterPassthroughConfig().get_complete_url(
        api_base=None,
        api_key="sk-or-test",
        model="openai/gpt-4o-mini",
        endpoint="/chat/completions",
        request_query_params=None,
        litellm_params={},
    )
    assert base == DEFAULT_BASE
    assert url == httpx.URL(f"{DEFAULT_BASE}/chat/completions")


@pytest.mark.parametrize(
    "request_data,expected",
    [({"stream": True}, True), ({"stream": False}, False), ({}, False)],
)
def test_streaming_is_read_from_the_body(request_data, expected):
    assert OpenRouterPassthroughConfig().is_streaming_request("/chat/completions", request_data) is expected
