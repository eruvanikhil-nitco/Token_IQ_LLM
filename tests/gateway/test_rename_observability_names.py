"""Tests for scripts/rename/rename_observability_names.py.

These names reach a customer's traces and dashboards, so renaming them breaks queries the same way the
Prometheus rename does, and the notes have to list them.

The failure to guard against is renaming too much. The same pattern over the test tree matches 42 strings
that are not observability names: module paths like `litellm.caching.caching`, engine attributes like
`litellm.drop_params`, and two hostnames. So the set comes from the engine and only those exact names move.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MODULE_PATH = _REPO_ROOT / "scripts" / "rename" / "rename_observability_names.py"
_spec = importlib.util.spec_from_file_location("rename_observability_names", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
rename_observability_names = importlib.util.module_from_spec(_spec)
sys.modules["rename_observability_names"] = rename_observability_names
_spec.loader.exec_module(rename_observability_names)

SOME = ("litellm.team.metadata", "litellm.llm_api.request_count", "litellm.call_id")


def moved(text: str, names: tuple[str, ...] = SOME) -> str:
    found, _count = rename_observability_names.rewrite(text, names)
    return found


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ('span.set_attribute("litellm.call_id", x)', 'span.set_attribute("token_iq.call_id", x)'),
        ('TEAM_METADATA_ATTRIBUTE = "litellm.team.metadata"', 'TEAM_METADATA_ATTRIBUTE = "token_iq.team.metadata"'),
        ('"metric": "litellm.llm_api.request_count"', '"metric": "token_iq.llm_api.request_count"'),
    ],
)
def test_an_observability_name_moves(before: str, after: str) -> None:
    assert moved(before) == after


@pytest.mark.parametrize(
    "value",
    ["litellm.caching.caching", "litellm.drop_params", "litellm.ai", "litellm.example.com", "litellm_params"],
)
def test_something_that_is_not_an_observability_name_is_left_alone(value: str) -> None:
    """A module path, an engine attribute, two hostnames and a config key. The pattern over a test file would
    match four of the five; the set read from the engine contains none of them."""
    assert moved(f'x = "{value}"') == f'x = "{value}"'


def test_a_longer_name_is_not_eaten_by_a_shorter_one() -> None:
    """`litellm.team` is a prefix of `litellm.team.metadata`, so the alternation is ordered longest first."""
    names = ("litellm.team.metadata", "litellm.team")

    assert moved('"litellm.team.metadata"', names) == '"token_iq.team.metadata"'
    assert moved('"litellm.team"', names) == '"token_iq.team"'


def test_the_names_are_read_out_of_the_engine() -> None:
    """Listed here the set would drift, and a name the engine sends that the notes never mention is a trace
    query a customer cannot fix."""
    names = rename_observability_names.every_name()

    assert "token_iq.team.metadata" in names
    assert "litellm.caching.caching" not in names, "a module path got into the set"
    assert "token_iq.caching.caching" not in names, "a module path got into the set"


def test_no_name_is_still_under_the_old_prefix() -> None:
    """The invariant the rename leaves behind, and what makes a later run a no-op rather than a disaster."""
    assert rename_observability_names.observability_names() == ()


def test_the_set_is_ordered_longest_first() -> None:
    names = rename_observability_names.every_name()

    assert [len(name) for name in names] == sorted((len(name) for name in names), reverse=True)


def test_no_name_is_also_a_module_path() -> None:
    """The precondition for renaming by text. One of these would move as an attribute name and break as an
    import, and the pass refuses to run rather than guess which."""
    assert rename_observability_names.module_paths() == ()


def test_the_module_check_can_actually_tell() -> None:
    """Said against a module that exists and one that does not, because the check reading `()` today is also
    what a check that always says `()` reads."""
    assert rename_observability_names._imports("token_iq.gateway.caching.caching")
    assert not rename_observability_names._imports("token_iq.gateway.this_is_not_a_module")


def test_a_run_with_nothing_left_to_rename_changes_nothing() -> None:
    """Which is what a second run is. An alternation of nothing matches the empty string everywhere."""
    assert rename_observability_names.rewrite('x = "anything"', ()) == ('x = "anything"', 0)


def test_the_standard_attributes_are_left_alone() -> None:
    """`gen_ai.*` is a standard rather than ours, and the plan says to keep it."""
    before = 'span.set_attribute("gen_ai.request.model", model)'

    assert moved(before) == before


def test_the_records_and_the_built_dashboard_are_out_of_scope() -> None:
    listed = {rename_observability_names.named(path) for path in rename_observability_names.tracked()}

    assert "docs/status.md" not in listed
    assert "CHANGELOG.md" not in listed
    assert not any(name.startswith("token_iq/gateway/proxy/_experimental/out/") for name in listed)
    assert "token_iq/gateway/integrations/opentelemetry.py" in listed, "the filter is too wide"


def test_this_pass_and_its_tests_are_out_of_scope() -> None:
    listed = {rename_observability_names.named(path) for path in rename_observability_names.tracked()}

    assert "scripts/rename/rename_observability_names.py" not in listed
    assert "tests/gateway/test_rename_observability_names.py" not in listed
