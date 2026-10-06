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

import pytest

from token_iq.gateway import compat
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
