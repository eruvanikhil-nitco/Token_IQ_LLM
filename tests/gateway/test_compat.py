"""The compatibility seam that lets a customer upgrade without editing their configuration.

What this has to get right is an upgrade nobody notices. Their environment says `LITELLM_SALT_KEY`, the
engine now asks for `TOKEN_IQ_SALT_KEY`, and the key still decrypts their stored credentials. Getting it
wrong is not a crash: the proxy starts, reads nothing, and behaves as though the operator had never set
the variable at all.

The environment and the warner are injected, so these say what the rule does rather than what this
machine's environment happens to hold.
"""

import pytest

from token_iq.gateway import compat


@pytest.fixture(autouse=True)
def _one_warning_at_a_time() -> None:
    """Each case starts with nothing already reported, because once-per-name is what is under test."""
    compat.forget_warnings()


def test_the_new_name_is_read() -> None:
    assert compat.env("TOKEN_IQ_SALT_KEY", environ={"TOKEN_IQ_SALT_KEY": "new"}) == "new"


def test_the_old_name_still_works() -> None:
    """The whole point. An operator who has not touched their environment keeps working."""
    assert compat.env("TOKEN_IQ_SALT_KEY", environ={"LITELLM_SALT_KEY": "old"}, warn=lambda _m: None) == "old"


def test_the_new_name_wins_when_both_are_set() -> None:
    """An operator who has already migrated must not be overridden by a variable they forgot to delete."""
    both = {"TOKEN_IQ_SALT_KEY": "new", "LITELLM_SALT_KEY": "old"}

    assert compat.env("TOKEN_IQ_SALT_KEY", environ=both, warn=lambda _m: None) == "new"


def test_the_default_is_returned_when_neither_is_set() -> None:
    assert compat.env("TOKEN_IQ_SALT_KEY", "fallback", environ={}) == "fallback"
    assert compat.env("TOKEN_IQ_SALT_KEY", environ={}) is None


def test_reading_the_new_name_says_nothing() -> None:
    """A warning on the migrated path would train operators to ignore it."""
    said: list[str] = []  # rebind-ok: a spy recording what was said

    _ = compat.env("TOKEN_IQ_SALT_KEY", environ={"TOKEN_IQ_SALT_KEY": "new"}, warn=said.append)

    assert said == []


def test_reading_the_old_name_says_what_to_change() -> None:
    said: list[str] = []  # rebind-ok: a spy recording what was said

    _ = compat.env("TOKEN_IQ_SALT_KEY", environ={"LITELLM_SALT_KEY": "old"}, warn=said.append)

    assert len(said) == 1
    assert "LITELLM_SALT_KEY" in said[0], "the message does not name what they set"
    assert "TOKEN_IQ_SALT_KEY" in said[0], "the message does not name what to set instead"
    assert "removed in the one after next" in said[0], "the message does not say when it stops working"


def test_the_warning_fires_once_per_name_not_once_per_read() -> None:
    """`LITELLM_LOG` is read four times while the proxy starts, and four identical lines teach a reader
    nothing the first one did not."""
    said: list[str] = []  # rebind-ok: a spy recording what was said
    legacy = {"LITELLM_LOG": "DEBUG"}

    for _ in range(4):
        _ = compat.env("TOKEN_IQ_LOG", environ=legacy, warn=said.append)

    assert len(said) == 1


def test_a_second_old_name_gets_its_own_warning() -> None:
    """Once per name, not once per process: an operator with six old variables needs to be told about
    all six."""
    said: list[str] = []  # rebind-ok: a spy recording what was said
    legacy = {"LITELLM_LOG": "DEBUG", "LITELLM_SALT_KEY": "old"}

    _ = compat.env("TOKEN_IQ_LOG", environ=legacy, warn=said.append)
    _ = compat.env("TOKEN_IQ_SALT_KEY", environ=legacy, warn=said.append)

    assert len(said) == 2


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("TOKEN_IQ_SALT_KEY", "LITELLM_SALT_KEY"),
        ("TOKEN_IQ_LOG", "LITELLM_LOG"),
        ("TOKEN_IQ_", "LITELLM_"),
    ],
)
def test_the_old_spelling_is_the_prefix_and_nothing_else(name: str, expected: str) -> None:
    assert compat.old_name_for(name) == expected


@pytest.mark.parametrize("name", ["AWS_REGION_NAME", "OPENAI_API_KEY", "PATH", "TOKENIQ_SALT_KEY"])
def test_a_variable_that_was_never_renamed_has_no_old_spelling(name: str) -> None:
    """Guessing one would invent a fallback nobody asked for, and `AWS_REGION_NAME` is not Token IQ's to
    rename in the first place."""
    assert compat.old_name_for(name) is None


def test_a_variable_that_was_never_renamed_is_read_plainly() -> None:
    said: list[str] = []  # rebind-ok: a spy recording what was said

    found = compat.env("AWS_REGION_NAME", environ={"AWS_REGION_NAME": "eu-west-1"}, warn=said.append)

    assert found == "eu-west-1"
    assert said == []


def test_the_real_environment_is_what_it_reads_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """The injected environment is what every case above uses, so the default needs its own: a helper
    that only ever read a dict handed to it would pass all of them and read nothing in production."""
    monkeypatch.setenv("LITELLM_SALT_KEY", "from-the-process")
    monkeypatch.delenv("TOKEN_IQ_SALT_KEY", raising=False)

    assert compat.env("TOKEN_IQ_SALT_KEY", warn=lambda _m: None) == "from-the-process"


def test_the_empty_string_is_a_value_and_not_an_absence() -> None:
    """An operator who sets a variable to nothing meant nothing, and falling through to the old name
    would quietly override that."""
    both = {"TOKEN_IQ_SALT_KEY": "", "LITELLM_SALT_KEY": "old"}

    assert compat.env("TOKEN_IQ_SALT_KEY", environ=both, warn=lambda _m: None) == ""


def test_the_warning_survives_the_logger_not_being_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    """`_logging` reads two of these variables itself, so the very first warning can fire part-way
    through importing it, when the module object exists but `verbose_logger` does not. Letting that raise
    would turn a deprecation notice into a failure to start."""
    import sys
    import types

    half_imported = types.ModuleType("token_iq.gateway._logging")
    monkeypatch.setitem(sys.modules, "token_iq.gateway._logging", half_imported)

    with pytest.warns(DeprecationWarning, match="LITELLM_SALT_KEY"):
        found = compat.env("TOKEN_IQ_SALT_KEY", environ={"LITELLM_SALT_KEY": "old"})

    assert found == "old"


def test_the_warning_goes_through_the_engines_logger_when_it_is_ready() -> None:
    """The ordinary path. Falling back to `warnings` always would put the notice somewhere an operator
    watching the proxy's log would never see it."""
    said: list[str] = []  # rebind-ok: a spy standing in for the logger

    import token_iq.gateway._logging as logging_module

    original = logging_module.verbose_logger.warning
    try:
        logging_module.verbose_logger.warning = said.append  # pyright: ignore[reportAttributeAccessIssue]  # a spy for one call
        _ = compat.env("TOKEN_IQ_SALT_KEY", environ={"LITELLM_SALT_KEY": "old"})
    finally:
        logging_module.verbose_logger.warning = original  # pyright: ignore[reportAttributeAccessIssue]  # put it back

    assert len(said) == 1
    assert "LITELLM_SALT_KEY" in said[0]
