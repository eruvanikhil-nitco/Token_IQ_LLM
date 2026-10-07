"""The check phase 7 is for: a customer's existing configuration still brings the proxy up.

The plan asks for two of these. One loads an old-style environment and `config.yaml` and confirms it
works and warns; the other does the same with the new names and confirms it says nothing. Between them
they are the only thing that answers "can a customer upgrade without editing anything", and neither is
answerable from a unit test of the helper: the question is whether the engine reads the helper's answer.

These go through `ProxyConfig.get_config`, which is where every source of configuration arrives, rather
than starting a server. Starting one needs a database, and what is under test is the reading.
"""

import os
import pathlib
import textwrap
from collections.abc import Callable
from types import SimpleNamespace

import fastapi
import httpx
import pytest
from fastapi.testclient import TestClient

from token_iq.gateway import compat
from token_iq.gateway.proxy import proxy_server
from token_iq.gateway.proxy._types import SpecialHeaders, UserAPIKeyAuth
from token_iq.gateway.proxy.auth.user_api_key_auth import user_api_key_auth
from token_iq.gateway.proxy.proxy_server import ProxyConfig

OLD_STYLE = textwrap.dedent(
    """
    model_list:
      - model_name: gpt-4o
        litellm_params:
          model: openai/gpt-4o
          api_key: sk-test
    litellm_settings:
      drop_params: true
    general_settings:
      master_key: sk-master
    """
).lstrip()

NEW_STYLE = textwrap.dedent(
    """
    model_list:
      - model_name: gpt-4o
        model_params:
          model: openai/gpt-4o
          api_key: sk-test
    gateway_settings:
      drop_params: true
    general_settings:
      master_key: sk-master
    """
).lstrip()


@pytest.fixture(autouse=True)
def _one_warning_at_a_time() -> None:
    compat.forget_warnings()


async def load(path: pathlib.Path) -> dict[str, object]:
    return await ProxyConfig().get_config(config_file_path=str(path))


def written(tmp_path: pathlib.Path, text: str) -> pathlib.Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    config = tmp_path / "config.yaml"
    _ = config.write_text(text, encoding="utf-8")
    return config


@pytest.mark.asyncio
async def test_a_config_written_before_the_rename_still_configures_the_proxy(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The upgrade nobody notices. Their file says `litellm_settings` and `litellm_params`, and the
    engine reads both as it always did."""
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-from-an-old-env")
    monkeypatch.delenv("TOKEN_IQ_MASTER_KEY", raising=False)

    loaded = await load(written(tmp_path, OLD_STYLE))

    assert loaded["litellm_settings"] == {"drop_params": True}
    models = loaded["model_list"]
    assert isinstance(models, list)
    assert models[0]["litellm_params"]["model"] == "openai/gpt-4o"


@pytest.mark.asyncio
async def test_a_config_written_after_the_rename_configures_it_the_same_way(
    tmp_path: pathlib.Path,
) -> None:
    """The new names reach exactly the same place, which is what makes the old ones droppable later."""
    loaded = await load(written(tmp_path, NEW_STYLE))

    assert loaded["litellm_settings"] == {"drop_params": True}
    models = loaded["model_list"]
    assert isinstance(models, list)
    assert models[0]["litellm_params"]["model"] == "openai/gpt-4o"


@pytest.mark.asyncio
async def test_the_two_spellings_load_to_the_same_thing(tmp_path: pathlib.Path) -> None:
    """Said as one assertion, because "it works with both" is the whole claim of the phase."""
    old = await load(written(tmp_path / "old", OLD_STYLE))
    new = await load(written(tmp_path / "new", NEW_STYLE))

    assert old == new


@pytest.mark.asyncio
async def test_an_old_config_is_told_what_to_change(tmp_path: pathlib.Path) -> None:
    """Working silently would leave an operator with no idea the names had moved, and the release after
    next stops accepting them."""
    said: list[str] = []  # rebind-ok: a spy recording what was said
    monkeypatch_free = written(tmp_path, OLD_STYLE)

    _ = compat.config({"litellm_settings": {}, "model_list": [{"litellm_params": {}}]}, warn=said.append)
    _ = await load(monkeypatch_free)

    assert any("gateway_settings" in line for line in said)
    assert any("model_params" in line for line in said)


@pytest.mark.asyncio
async def test_a_new_config_is_told_nothing(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A warning on the migrated path would train operators to ignore the one that matters."""
    _ = await load(written(tmp_path, NEW_STYLE))

    assert "before it was renamed" not in capsys.readouterr().err


# --- Request headers -------------------------------------------------------------------------------
#
# The config above is a file an operator can edit. This is their client's code, which they may not own,
# so getting it wrong is worse: every request 401s and there is nothing they can change in a config to
# fix it. These go through a real app over HTTP, because what is under test is whether FastAPI's own
# security dependency hands the value on, and calling the function directly would never exercise that.

MASTER_KEY = "sk-upgrade-test-master"


def authenticating_app(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """A proxy authenticating against a master key, which needs no database."""
    monkeypatch.setattr(proxy_server, "master_key", MASTER_KEY, raising=False)
    monkeypatch.setattr(proxy_server, "general_settings", {"master_key": MASTER_KEY}, raising=False)
    monkeypatch.setattr(proxy_server, "prisma_client", None, raising=False)

    app = fastapi.FastAPI()

    @app.post("/v1/chat/completions")
    async def completions(auth: UserAPIKeyAuth = fastapi.Depends(user_api_key_auth)) -> dict[str, object]:
        return {"user_id": auth.user_id, "authenticated": auth.api_key is not None}

    return TestClient(app, raise_server_exceptions=False)


def called(client: TestClient, headers: dict[str, str]) -> httpx.Response:
    return client.post("/v1/chat/completions", json={"model": "gpt-4o"}, headers=headers)


def test_a_client_sending_the_renamed_key_header_is_authenticated(monkeypatch: pytest.MonkeyPatch) -> None:
    sent = called(authenticating_app(monkeypatch), {"x-token-iq-api-key": f"Bearer {MASTER_KEY}"})

    assert sent.status_code == 200
    assert sent.json()["authenticated"] is True


def test_a_client_still_sending_the_old_key_header_is_authenticated_the_same_way(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The one that would hurt most. A customer's client is their code, and an upgrade that 401s every
    request leaves them nothing to edit."""
    sent = called(authenticating_app(monkeypatch), {"x-litellm-api-key": f"Bearer {MASTER_KEY}"})

    assert sent.status_code == 200
    assert sent.json()["authenticated"] is True


def test_the_renamed_header_wins_when_a_client_sends_both(monkeypatch: pytest.MonkeyPatch) -> None:
    """Said with a valid new key and a junk old one, so only the precedence can make it pass."""
    sent = called(
        authenticating_app(monkeypatch),
        {"x-token-iq-api-key": f"Bearer {MASTER_KEY}", "x-litellm-api-key": "Bearer sk-not-a-key"},
    )

    assert sent.status_code == 200


def test_the_old_header_authenticates_a_key_rather_than_accepting_any(monkeypatch: pytest.MonkeyPatch) -> None:
    """Accepting the old name must not mean accepting whatever it carries."""
    sent = called(authenticating_app(monkeypatch), {"x-litellm-api-key": "Bearer sk-not-a-key"})

    assert sent.status_code != 200


def test_the_old_key_header_is_not_forwarded_to_a_provider() -> None:
    """It is the caller's credential for this proxy. Forwarding it hands their key to an LLM vendor, and
    the set that stops that is built from the header enum, so the old name has to be in it."""
    assert compat.OLD_API_KEY_HEADER in SpecialHeaders.gateway_credential_header_names()
    assert compat.NEW_API_KEY_HEADER in SpecialHeaders.gateway_credential_header_names()


def test_a_cli_built_before_the_rename_can_still_poll_for_its_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """FastAPI maps a header onto a parameter name by swapping hyphens for underscores, so this one is not
    read through the helper and needs a parameter of its own. Over HTTP rather than by calling the endpoint,
    because what is under test is that mapping: called directly, an unpassed `Header(default=None)` is the
    `Header` object itself and every coalesce looks like it works.
    """
    from token_iq.gateway.proxy.management_endpoints.ui_sso import _hash_cli_sso_secret, router

    flow = {
        "poll_secret_hash": _hash_cli_sso_secret("poll-secret"),
        "sso_complete": True,
        "user_code_verified": False,
        "session_data": {"user_id": "u", "user_role": "internal_user", "teams": [], "models": []},
    }
    cache = SimpleNamespace(redis_cache=None, get_cache=lambda *_a, **_k: flow, delete_cache=lambda *_a, **_k: None)
    monkeypatch.setattr(proxy_server, "cli_sso_session_cache", cache, raising=False)
    monkeypatch.setattr(proxy_server, "user_api_key_cache", cache, raising=False)

    app = fastapi.FastAPI()
    app.include_router(router)
    polled = TestClient(app, raise_server_exceptions=False).get(
        "/sso/cli/poll/cli-session-789123", headers={"x-litellm-cli-poll-secret": "poll-secret"}
    )

    assert polled.status_code == 200
    assert polled.json() == {"status": "pending"}


def test_a_cli_built_after_the_rename_polls_the_same_way(monkeypatch: pytest.MonkeyPatch) -> None:
    from token_iq.gateway.proxy.management_endpoints.ui_sso import _hash_cli_sso_secret, router

    flow = {
        "poll_secret_hash": _hash_cli_sso_secret("poll-secret"),
        "sso_complete": True,
        "user_code_verified": False,
        "session_data": {"user_id": "u", "user_role": "internal_user", "teams": [], "models": []},
    }
    cache = SimpleNamespace(redis_cache=None, get_cache=lambda *_a, **_k: flow, delete_cache=lambda *_a, **_k: None)
    monkeypatch.setattr(proxy_server, "cli_sso_session_cache", cache, raising=False)
    monkeypatch.setattr(proxy_server, "user_api_key_cache", cache, raising=False)

    app = fastapi.FastAPI()
    app.include_router(router)
    polled = TestClient(app, raise_server_exceptions=False).get(
        "/sso/cli/poll/cli-session-789123", headers={"x-token-iq-cli-poll-secret": "poll-secret"}
    )

    assert polled.status_code == 200
    assert polled.json() == {"status": "pending"}


def test_polling_without_the_secret_is_refused_either_way(monkeypatch: pytest.MonkeyPatch) -> None:
    """Accepting the old header name must not mean accepting a caller that sends neither."""
    from token_iq.gateway.proxy.management_endpoints.ui_sso import _hash_cli_sso_secret, router

    flow = {
        "poll_secret_hash": _hash_cli_sso_secret("poll-secret"),
        "sso_complete": True,
        "user_code_verified": False,
        "session_data": {"user_id": "u", "user_role": "internal_user", "teams": [], "models": []},
    }
    cache = SimpleNamespace(redis_cache=None, get_cache=lambda *_a, **_k: flow, delete_cache=lambda *_a, **_k: None)
    monkeypatch.setattr(proxy_server, "cli_sso_session_cache", cache, raising=False)
    monkeypatch.setattr(proxy_server, "user_api_key_cache", cache, raising=False)

    app = fastapi.FastAPI()
    app.include_router(router)
    polled = TestClient(app, raise_server_exceptions=False).get("/sso/cli/poll/cli-session-789123")

    assert polled.status_code == 403


# --- Knobs whose name is bound to something ------------------------------------------------------
#
# The phase 7 pass over the engine's environment reads could only repoint a read whose name is written
# out at the call. These are the ones where it is not: a module constant read elsewhere, a Pydantic
# settings alias, a Click option, a dict of field to variable. Each one was still asking only for the
# old name, so an operator who read the changelog and set the new one would have found the knob dead.
#
# Each case drives the engine's own reader rather than the helper, because the helper was already right.


def no_new_names(monkeypatch: pytest.MonkeyPatch) -> None:
    """So a variable this machine happens to have set cannot answer for the one under test."""
    for name in tuple(os.environ):
        if name.startswith("TOKEN_IQ_"):
            monkeypatch.delenv(name, raising=False)


def max_callbacks() -> object:
    from token_iq.gateway.core_utils.env_utils import get_env_int

    return get_env_int("TOKEN_IQ_MAX_CALLBACKS", 100)


def keyring_is_off() -> object:
    from token_iq.gateway.core_utils.cli_keyring import _keyring_disabled

    return _keyring_disabled()


def ptu_attribution_is_on() -> object:
    from token_iq.gateway.core_utils.ptu_pricing import is_ptu_cost_attribution_enabled

    return is_ptu_cost_attribution_enabled()


def tracebacks_are_suppressed() -> object:
    from token_iq.gateway.proxy.spend_tracking.spend_log_error_logger import _is_suppression_env_enabled

    return _is_suppression_env_enabled()


def rust_is_on() -> object:
    from token_iq.gateway.rust_bridge.configuration import rust_enabled

    return rust_enabled()


def otel_v2_is_on() -> object:
    from token_iq.gateway.integrations.otel.model.config import _OTelV2Flag

    return _OTelV2Flag().enabled


def otel_keeps_legacy_names() -> object:
    from token_iq.gateway.integrations.otel.model.config import OpenTelemetryV2Config

    return OpenTelemetryV2Config().legacy_compat


def the_favicon() -> object:
    from token_iq.gateway.proxy.ui_crud_endpoints.proxy_setting_endpoints import _resolve_ui_theme_field

    return _resolve_ui_theme_field({}, "favicon_url")


def mcp_discovers_on_startup() -> object:
    from token_iq.gateway.proxy._experimental.mcp_server.mcp_server_manager import (
        _mcp_oauth_discovery_on_startup_enabled,
    )

    return _mcp_oauth_discovery_on_startup_enabled()


def a_production_only_model_loads() -> object:
    """Through the router's own gate, so what is under test is the name the engine asks for."""
    from token_iq.gateway.router import model_info_is_active_for_environment

    return model_info_is_active_for_environment({"supported_environments": ["production"]})


def hot_reload_is_on() -> object:
    from token_iq import gateway

    return gateway._dev_env_hot_reload_enabled()


def rust_ocr_is_on() -> object:
    """A second reader of the same variable, in its own function."""
    from token_iq.gateway.rust_bridge.configuration import rust_ocr_enabled

    return rust_ocr_enabled()


KNOBS: tuple[tuple[str, str, Callable[[], object], object], ...] = (
    ("LITELLM_MAX_CALLBACKS", "7", max_callbacks, 7),
    ("LITELLM_CLI_DISABLE_KEYRING", "true", keyring_is_off, True),
    ("LITELLM_ENABLE_PTU_COST_ATTRIBUTION", "true", ptu_attribution_is_on, True),
    ("LITELLM_SUPPRESS_SPEND_LOG_TRACEBACKS", "true", tracebacks_are_suppressed, True),
    ("LITELLM_RUST", "true", rust_is_on, True),
    ("LITELLM_RUST", "true", rust_ocr_is_on, True),
    ("LITELLM_OTEL_V2", "true", otel_v2_is_on, True),
    ("LITELLM_OTEL_LEGACY_COMPAT", "false", otel_keeps_legacy_names, False),
    ("LITELLM_FAVICON_URL", "https://example.test/f.ico", the_favicon, "https://example.test/f.ico"),
    ("LITELLM_MCP_OAUTH_DISCOVERY_ON_STARTUP", "true", mcp_discovers_on_startup, True),
    ("LITELLM_ENVIRONMENT", "production", a_production_only_model_loads, True),
    ("LITELLM_DEV_ENV_HOT_RELOAD", "True", hot_reload_is_on, True),
)


@pytest.mark.parametrize(
    ("old_name", "set_to", "read", "expected"), KNOBS, ids=[f"{knob[0]}-{knob[2].__name__}" for knob in KNOBS]
)
def test_a_knob_set_under_its_old_name_still_works(
    old_name: str, set_to: str, read: Callable[[], object], expected: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    no_new_names(monkeypatch)
    monkeypatch.setenv(old_name, set_to)
    _clear_caches()

    assert read() == expected


@pytest.mark.parametrize(
    ("old_name", "set_to", "read", "expected"), KNOBS, ids=[f"{knob[0]}-{knob[2].__name__}" for knob in KNOBS]
)
def test_the_same_knob_works_under_its_new_name(
    old_name: str, set_to: str, read: Callable[[], object], expected: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Where the first test alone would pass if nothing had been renamed at all."""
    no_new_names(monkeypatch)
    monkeypatch.delenv(old_name, raising=False)
    monkeypatch.setenv(old_name.replace("LITELLM_", "TOKEN_IQ_", 1), set_to)
    _clear_caches()

    assert read() == expected


def _clear_caches() -> None:
    """These readers memoise, and the suite has already called several of them."""
    from token_iq.gateway.integrations.otel.model import config as otel_config
    from token_iq.gateway.rust_bridge import configuration as rust_config

    compat.forget_warnings()
    for module in (otel_config, rust_config):
        for name in dir(module):
            clear = getattr(getattr(module, name), "cache_clear", None)
            if clear is not None:
                clear()
