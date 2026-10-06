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


# --- config keys ---------------------------------------------------------------------------------


def test_a_config_using_the_new_key_names_is_understood() -> None:
    """The point of the phase. A customer who has migrated their file gets the same proxy."""
    found = compat.config({"gateway_settings": {"drop_params": True}}, warn=lambda _m: None)

    assert found == {"litellm_settings": {"drop_params": True}}


def test_a_config_using_the_old_key_names_still_works() -> None:
    """The other point. A customer who has not touched their file gets the same proxy too."""
    found = compat.config({"litellm_settings": {"drop_params": True}}, warn=lambda _m: None)

    assert found == {"litellm_settings": {"drop_params": True}}


def test_the_model_block_is_found_inside_the_model_list() -> None:
    """`litellm_params` sits one level down inside each entry, and a customer may have a hundred of
    them. Normalising only the top level would leave every model unconfigured."""
    loaded = {"model_list": [{"model_name": "gpt-4o", "model_params": {"model": "openai/gpt-4o"}}]}

    found = compat.config(loaded, warn=lambda _m: None)

    assert found == {"model_list": [{"model_name": "gpt-4o", "litellm_params": {"model": "openai/gpt-4o"}}]}


def test_a_key_nested_arbitrarily_deep_is_still_found() -> None:
    """A customer's file nests as far as they like, and a renamed key is renamed wherever it is."""
    loaded = {"a": {"b": [{"c": {"model_params": {"model": "x"}}}]}}

    found = compat.config(loaded, warn=lambda _m: None)

    assert found == {"a": {"b": [{"c": {"litellm_params": {"model": "x"}}}]}}


def test_using_an_old_key_says_what_to_change() -> None:
    said: list[str] = []  # rebind-ok: a spy recording what was said

    _ = compat.config({"litellm_settings": {}}, warn=said.append)

    assert len(said) == 1
    assert "litellm_settings" in said[0]
    assert "gateway_settings" in said[0]


def test_using_a_new_key_says_nothing() -> None:
    said: list[str] = []  # rebind-ok: a spy recording what was said

    _ = compat.config({"gateway_settings": {}}, warn=said.append)

    assert said == []


def test_the_warning_fires_once_however_many_models_use_the_old_name() -> None:
    """A file with fifty models would otherwise print fifty identical lines."""
    said: list[str] = []  # rebind-ok: a spy recording what was said
    loaded = {"model_list": [{"litellm_params": {"model": f"m{n}"}} for n in range(50)]}

    _ = compat.config(loaded, warn=said.append)

    assert len(said) == 1


def test_everything_else_in_the_config_is_passed_through_unchanged() -> None:
    """A renamed key is two keys out of a file that holds a customer's whole deployment."""
    loaded = {
        "general_settings": {"master_key": "sk-x"},
        "router_settings": {"routing_strategy": "simple-shuffle"},
        "environment_variables": {"OPENAI_API_KEY": "sk-y"},
    }

    assert compat.config(loaded, warn=lambda _m: None) == loaded


def test_a_value_that_merely_reads_like_a_key_is_untouched() -> None:
    """Only a key is renamed. `litellm_params` as somebody's model name or tag is their data."""
    loaded = {"general_settings": {"note": "litellm_params", "tags": ["litellm_settings"]}}

    assert compat.config(loaded, warn=lambda _m: None) == loaded


def test_an_empty_config_is_returned_as_one() -> None:
    assert compat.config({}, warn=lambda _m: None) == {}


def test_the_result_is_a_plain_dict_the_proxy_can_edit() -> None:
    """`get_config` is annotated to return one, its caller rebinds it, and the printed copy has a key
    popped out of it. A read-only view here would be a change to all of them."""
    found = compat.config({"model_list": [{"model_params": {}}]}, warn=lambda _m: None)

    found["general_settings"] = {}
    assert isinstance(found["model_list"], list)
    found["model_list"].append({})


# --- Request headers -------------------------------------------------------------------------------
#
# The stake here is higher than the environment's. A variable read under the wrong name leaves one
# feature unconfigured; `x-litellm-api-key` not being accepted 401s every request a customer's client
# makes, and the client is their code, not their config file.


def test_a_caller_still_sending_the_old_header_is_understood() -> None:
    sent = {"x-litellm-tags": "team-a,prod"}

    assert compat.header(sent, "x-token-iq-tags", warn=lambda _m: None) == "team-a,prod"


def test_the_new_header_wins_when_a_caller_sends_both() -> None:
    sent = {"x-token-iq-tags": "new", "x-litellm-tags": "old"}

    assert compat.header(sent, "x-token-iq-tags", warn=lambda _m: None) == "new"


def test_the_default_comes_back_when_the_header_was_not_sent() -> None:
    assert compat.header({}, "x-token-iq-call-id", "generated") == "generated"


def test_a_header_that_was_never_renamed_has_no_fallback() -> None:
    """`x-api-key` is Anthropic's, not ours. Inventing `x-litellm-api-key` as its old spelling would make
    one provider's credential header authenticate as another."""
    assert compat.header({"x-api-key": "sk-ant"}, "x-api-key") == "sk-ant"
    assert compat.old_header_for("x-api-key") is None


@pytest.mark.parametrize("stored", ["x-token-iq-model", "x-litellm-model"])
def test_the_name_asked_for_is_matched_whatever_its_case(stored: str) -> None:
    """Header names are case-insensitive in HTTP, so a lookup that is not would accept a request from one
    client and reject the identical request from another. Both spellings have to be found that way, since
    a mixed-case name reaches the new one through a plain lookup and the old one through `old_header_for`.
    """
    assert compat.header({stored: "gpt-4o"}, "X-Token-IQ-Model", warn=lambda _m: None) == "gpt-4o"


def test_the_old_spelling_of_a_header_is_the_prefix_and_nothing_else() -> None:
    assert compat.old_header_for("x-token-iq-attempted-fallbacks") == "x-litellm-attempted-fallbacks"
    assert compat.old_header_for("X-Token-IQ-Trace-Id") == "x-litellm-trace-id"


def test_a_header_value_that_is_not_a_string_comes_back_as_it_was() -> None:
    """`x-token-iq-tags` is read from a dict whose values may be a list, and the caller branches on which."""
    sent: dict[str, object] = {"x-litellm-tags": ["team-a", "prod"]}

    assert compat.header(sent, "x-token-iq-tags", warn=lambda _m: None) == ["team-a", "prod"]


def test_an_old_header_says_what_to_change() -> None:
    said: list[str] = []  # rebind-ok: a spy recording what was said

    _ = compat.header({"x-litellm-tags": "a"}, "x-token-iq-tags", warn=said.append)

    assert len(said) == 1
    assert "x-litellm-tags" in said[0]
    assert "x-token-iq-tags" in said[0]


def test_a_new_header_says_nothing() -> None:
    said: list[str] = []  # rebind-ok: a spy recording what was said

    _ = compat.header({"x-token-iq-tags": "a"}, "x-token-iq-tags", warn=said.append)

    assert said == []


def test_the_warning_fires_once_however_many_requests_send_the_old_header() -> None:
    """A header arrives on every request, so warning per read would be a line per request forever."""
    said: list[str] = []  # rebind-ok: a spy recording what was said

    for _ in range(50):
        _ = compat.header({"x-litellm-tags": "a"}, "x-token-iq-tags", warn=said.append)

    assert len(said) == 1


def test_both_spellings_of_a_list_are_offered_new_first() -> None:
    """Order matters where the caller stops at the first header it finds: the migrated name has to win."""
    assert compat.both_spellings(["x-token-iq-customer-id", "x-token-iq-end-user-id"]) == (
        "x-token-iq-customer-id",
        "x-litellm-customer-id",
        "x-token-iq-end-user-id",
        "x-litellm-end-user-id",
    )


def test_a_list_entry_that_was_never_renamed_is_listed_once() -> None:
    assert compat.both_spellings(["x-mcp-auth"]) == ("x-mcp-auth",)


@pytest.mark.parametrize(
    "name",
    ["x-token-iq-model", "X-Token-IQ-Model", "x-litellm-model", "X-LiteLLM-Attempted-Fallbacks"],
)
def test_the_engines_own_headers_are_recognised_under_either_prefix(name: str) -> None:
    """Used to strip them off a forwarded request and to tell them from a provider's. Missing the old
    prefix would let a caller claim to be the proxy by using the name the proxy used to use."""
    assert compat.is_gateway_header(name)


@pytest.mark.parametrize("name", ["x-api-key", "authorization", "x-token-iq", "x-mcp-auth", "litellm-model"])
def test_everything_else_is_not_one_of_the_engines_headers(name: str) -> None:
    assert not compat.is_gateway_header(name)


def test_the_two_spellings_of_the_key_header_agree_with_the_prefix_rule() -> None:
    """They are spelled out for FastAPI rather than derived, so nothing else checks they match."""
    assert compat.old_header_for(compat.NEW_API_KEY_HEADER) == compat.OLD_API_KEY_HEADER


def test_an_empty_new_header_is_a_value_and_not_an_absence() -> None:
    """A client that deliberately sends the header empty means empty. Falling through to the old spelling
    would hand it a value it had just cleared."""
    sent = {"x-token-iq-tags": "", "x-litellm-tags": "old"}

    assert compat.header(sent, "x-token-iq-tags", warn=lambda _m: None) == ""
