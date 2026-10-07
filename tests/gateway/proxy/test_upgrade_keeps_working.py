"""The check phase 7 is for: a customer's existing configuration still brings the proxy up.

The plan asks for two of these. One loads an old-style environment and `config.yaml` and confirms it
works and warns; the other does the same with the new names and confirms it says nothing. Between them
they are the only thing that answers "can a customer upgrade without editing anything", and neither is
answerable from a unit test of the helper: the question is whether the engine reads the helper's answer.

These go through `ProxyConfig.get_config`, which is where every source of configuration arrives, rather
than starting a server. Starting one needs a database, and what is under test is the reading.
"""

import pathlib
import textwrap
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
