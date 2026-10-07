"""Tests for scripts/rename/rename_identifiers.py.

The pass renames 1,316 names across 4,706 places. Two things make it dangerous. A name can be written in
seven different syntactic positions, and each sits at a different offset from the node that holds it, so
a position handled wrongly either misses silently or cuts the wrong span out of a line. And `litellm` is
a substring of names belonging to phases 7 to 9, which outnumber the identifiers: of the rows this pass
does not touch, 383 appear in a `.py` file only inside a string.

What gets renamed is not decided here. It is read from `docs/plans/phase-6-identifier-scope.csv`, and
these tests pass their own small map so they say what a rule does rather than what this checkout holds.
"""

import importlib.util
import sys
from pathlib import Path
from typing import Final

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MODULE_PATH = _REPO_ROOT / "scripts" / "rename" / "rename_identifiers.py"
_spec = importlib.util.spec_from_file_location("rename_identifiers", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
rename_identifiers = importlib.util.module_from_spec(_spec)
sys.modules["rename_identifiers"] = rename_identifiers
_spec.loader.exec_module(rename_identifiers)


WANTED: Final = {
    "LiteLLMRoutes": "GatewayRoutes",
    "LiteLLMLoggingObj": "GatewayLoggingObj",
    "_add_litellm_params_to_vector_stores": "_add_gateway_params_to_vector_stores",
    "litellm_judge_name": "gateway_judge_name",
}


def rewrite(text: str) -> str:
    found, _ = rename_identifiers.rewrite(text, WANTED)
    return found


# --- every position a Python name can occupy -----------------------------------------------------


@pytest.mark.parametrize(
    ("before", "after"),
    [
        # A reference.
        ("x = LiteLLMRoutes.openai_routes", "x = GatewayRoutes.openai_routes"),
        # A definition.
        ("class LiteLLMRoutes(enum.Enum): ...", "class GatewayRoutes(enum.Enum): ..."),
        (
            "def _add_litellm_params_to_vector_stores(x): ...",
            "def _add_gateway_params_to_vector_stores(x): ...",
        ),
        (
            "async def _add_litellm_params_to_vector_stores(x): ...",
            "async def _add_gateway_params_to_vector_stores(x): ...",
        ),
        # An attribute.
        ("obj.LiteLLMRoutes = 1", "obj.GatewayRoutes = 1"),
        ("value = self.litellm_judge_name", "value = self.gateway_judge_name"),
        # A parameter and a keyword argument at a call site.
        ("def f(litellm_judge_name=None): ...", "def f(gateway_judge_name=None): ..."),
        ("f(litellm_judge_name=1)", "f(gateway_judge_name=1)"),
        # An import, named and aliased.
        ("from x import LiteLLMRoutes", "from x import GatewayRoutes"),
        ("from x import y as LiteLLMRoutes", "from x import y as GatewayRoutes"),
        ("from x import LiteLLMRoutes as z", "from x import GatewayRoutes as z"),
    ],
)
def test_each_position_is_renamed(before: str, after: str) -> None:
    assert rewrite(before) == after


def test_an_annotated_parameter_keeps_its_annotation() -> None:
    """A parameter's own span runs to the end of its annotation, so replacing the whole span would eat
    the annotation with it."""
    assert rewrite("def f(litellm_judge_name: str | None = None): ...") == (
        "def f(gateway_judge_name: str | None = None): ..."
    )


def test_a_class_written_as_a_string_is_renamed() -> None:
    """A forward reference is resolved against module globals when something asks for it, and
    `"LiteLLMLoggingObj"` appears 172 times that way."""
    assert rewrite('def f() -> "LiteLLMLoggingObj": ...') == 'def f() -> "GatewayLoggingObj": ...'


def test_a_class_at_the_end_of_a_dotted_string_is_renamed() -> None:
    """A patch target naming the class. The module part was moved by an earlier pass; this is the name."""
    assert rewrite('patch("token_iq.gateway.x.LiteLLMLoggingObj")') == ('patch("token_iq.gateway.x.GatewayLoggingObj")')


def test_a_snake_case_name_written_as_a_string_is_left_alone() -> None:
    """The scope artifact defers every snake_case name that is written as a string at all, because that
    is how a caller passes it. Were one to reach here anyway, it is still not renamed."""
    assert rewrite('kwargs.get("litellm_judge_name")') == 'kwargs.get("litellm_judge_name")'


# --- what must not move -------------------------------------------------------------------------


@pytest.mark.parametrize(
    "untouched",
    [
        # Not in the map, so not this phase's: a config key, an environment variable, a database model,
        # a span attribute.
        'params = {"litellm_params": {}}',
        'key = os.getenv("LITELLM_MASTER_KEY")',
        "class LiteLLM_TeamTable(BaseModel): ...",
        'span.set_attribute("litellm.trace_id", trace_id)',
        # Prose.
        "# LiteLLMRoutes is the route table",
        '"""See LiteLLMRoutes for the list."""',
        # A longer name that merely contains one in the map.
        "x = LiteLLMRoutesExtra.thing",
    ],
)
def test_what_this_pass_must_not_touch(untouched: str) -> None:
    assert rewrite(untouched) == untouched


def test_a_name_in_a_comment_is_left_alone_while_the_code_beside_it_moves() -> None:
    before = "x = LiteLLMRoutes.a  # LiteLLMRoutes again"
    assert rewrite(before) == "x = GatewayRoutes.a  # LiteLLMRoutes again"


# --- the pass itself ----------------------------------------------------------------------------


def test_two_names_on_one_line_both_move() -> None:
    """Edited back to front, so the first edit does not shift the second one's offsets."""
    assert rewrite("f(LiteLLMRoutes, LiteLLMLoggingObj)") == "f(GatewayRoutes, GatewayLoggingObj)"


def test_a_non_ascii_character_earlier_on_the_line_does_not_shift_the_edit() -> None:
    """`col_offset` is a byte offset into the line's UTF-8, and 1,207 files hold a line with a non-ASCII
    character on it."""
    before = 'log("café 你好", LiteLLMRoutes.a)'

    found = rewrite(before)
    assert found == 'log("café 你好", GatewayRoutes.a)'
    assert "café 你好" in found


def test_a_separator_python_does_not_count_as_a_line_break_does_not_shift_the_edit() -> None:
    """`str.splitlines` breaks on U+2028, U+2029, a form feed and four more that the tokenizer does not."""
    before = 'x = "a' + chr(0x2028) + 'b"\ny = LiteLLMRoutes.a\n'

    assert rewrite(before).splitlines()[-1] == "y = GatewayRoutes.a"


def test_a_file_that_does_not_parse_is_left_exactly_as_it_was() -> None:
    """Some committed files are deliberately invalid Python, as fixtures for other tests."""
    assert rewrite("def (\n") == "def (\n"


def test_a_file_with_nothing_to_change_is_not_rewritten(tmp_path: Path) -> None:
    quiet = tmp_path / "quiet.py"
    _ = quiet.write_text("x = 1\n", encoding="utf-8")

    totals, broken = rename_identifiers.run([quiet], WANTED, write=True)

    assert broken == ()
    assert "files changed" not in totals
    assert quiet.read_text(encoding="utf-8") == "x = 1\n"


def test_a_dry_run_changes_nothing_on_disk(tmp_path: Path) -> None:
    source = tmp_path / "mod.py"
    _ = source.write_text("x = LiteLLMRoutes.a\n", encoding="utf-8")

    totals, _broken = rename_identifiers.run([source], WANTED, write=False)

    assert totals["files changed"] == 1
    assert source.read_text(encoding="utf-8") == "x = LiteLLMRoutes.a\n"


def test_a_rewritten_file_keeps_its_final_newline(tmp_path: Path) -> None:
    source = tmp_path / "mod.py"
    _ = source.write_text("x = LiteLLMRoutes.a\ny = 2\n", encoding="utf-8")

    _totals, _broken = rename_identifiers.run([source], WANTED, write=True)

    assert source.read_text(encoding="utf-8") == "x = GatewayRoutes.a\ny = 2\n"


def test_a_rewrite_that_would_not_parse_leaves_the_file_as_it_was(tmp_path: Path) -> None:
    source = tmp_path / "mod.py"
    _ = source.write_text("x = LiteLLMRoutes.a\n", encoding="utf-8")

    def destructive(text: str, wanted: object) -> tuple[str, dict[str, int]]:
        return "def (", {"broken on purpose": 1}

    totals, broken = rename_identifiers.run([source], WANTED, write=True, rewriter=destructive)

    assert broken and broken[0].endswith("mod.py")
    assert "files changed" not in totals
    assert source.read_text(encoding="utf-8") == "x = LiteLLMRoutes.a\n"


def test_the_pass_leaves_its_own_source_and_the_artifact_it_reads_alone() -> None:
    """It would otherwise rename the names in its own map, and then the names it looks for would be the
    names it replaces them with."""
    listed = {path.name for path in rename_identifiers.tracked()}

    assert "rename_identifiers.py" not in listed
    assert "scope_identifiers.py" not in listed
    assert "dump_route_table.py" in listed, "the filter is too wide and is skipping other files"


def test_what_gets_renamed_comes_from_the_committed_artifact() -> None:
    """Read rather than listed, so changing the scope means changing a file a reviewer can read."""
    wanted = rename_identifiers.renames()

    assert wanted, "the scope artifact named nothing for this phase"
    assert wanted.get("LiteLLMRoutes") == "GatewayRoutes"
    # The four that would each have been a silent change if the scope had got them wrong.
    for deferred in ("litellm_provider", "litellm_logging_obj", "litellm_credential_name", "token_iq_migrations"):
        assert deferred not in wanted, f"{deferred} is in scope, and something outside this repository reads it"


def test_a_span_that_does_not_land_on_the_name_writes_nothing() -> None:
    """The guard, with a finder injected for the purpose. Its alternative is cutting an arbitrary span
    out of a line and splicing a name into the gap, which is how a rename corrupts a file rather than
    just missing one."""

    def wrong(tree: object, wanted: object, text: str) -> tuple[object, ...]:
        # Column 0 of a line whose name starts at column 4.
        return (rename_identifiers.Span(line=1, start=0, end=13, old="LiteLLMRoutes", new="GatewayRoutes"),)

    before = "x = LiteLLMRoutes.a"
    found, counts = rename_identifiers.rewrite(before, WANTED, finder=wrong)

    assert found == before
    assert not counts


def test_a_rename_that_changes_length_does_not_shift_the_one_beside_it() -> None:
    """Every rename this phase makes happens to be the same length, because `litellm` and `gateway` are
    both seven characters. The pass must not depend on that: edited back to front, so the first edit
    cannot move the second one's offsets."""
    longer = {"LiteLLMRoutes": "AMuchLongerGatewayRoutesName", "LiteLLMLoggingObj": "G"}
    found, _ = rename_identifiers.rewrite("f(LiteLLMRoutes, LiteLLMLoggingObj)", longer)

    assert found == "f(AMuchLongerGatewayRoutesName, G)"


def test_every_rename_this_phase_makes_is_the_same_length() -> None:
    """Worth stating, because it is why the pass is forgiving of an offset mistake rather than
    catastrophic: the line's length never changes, so a wrong span cannot run off the end of it."""
    wanted = rename_identifiers.renames()

    assert wanted
    assert all(len(old) == len(new) for old, new in wanted.items()), {
        old: new for old, new in wanted.items() if len(old) != len(new)
    }


@pytest.mark.parametrize(
    ("before", "after"),
    [
        (
            "class LiteLLMRoutes:\n    def method(self):\n        return 1\n",
            "class GatewayRoutes:\n    def method(self):\n        return 1\n",
        ),
        (
            "def _add_litellm_params_to_vector_stores(x):\n    return x\n",
            "def _add_gateway_params_to_vector_stores(x):\n    return x\n",
        ),
    ],
)
def test_a_definition_with_a_body_is_renamed(before: str, after: str) -> None:
    """A class or a function ends where its body ends, so asking whether the node sits on one line
    rejects every definition in the repository while its references are renamed anyway. That is a tree
    that does not import, and the first version of this pass did exactly it: 756 of 1,316 names looked
    unreachable and the audit is what said so."""
    assert rewrite(before) == after


def test_a_call_spread_over_several_lines_has_its_keyword_renamed() -> None:
    before = "f(\n    litellm_judge_name=1,\n)\n"
    assert rewrite(before) == "f(\n    gateway_judge_name=1,\n)\n"


def test_an_attribute_on_a_chain_spread_over_several_lines_is_renamed() -> None:
    before = "value = (\n    obj.litellm_judge_name\n)\n"
    assert rewrite(before) == "value = (\n    obj.gateway_judge_name\n)\n"


def test_the_audit_names_what_no_file_writes(tmp_path: Path) -> None:
    """The audit is what caught the definition bug: 756 of 1,316 names looked unreachable because every
    class and function definition was being skipped. It is asked about a tree built here rather than the
    repository, because the answer there changes the moment the pass runs."""
    source = tmp_path / "m.py"
    _ = source.write_text("x = LiteLLMRoutes.a\n", encoding="utf-8")

    missing = rename_identifiers.unreachable([source], {"LiteLLMRoutes": "GatewayRoutes", "NotHere": "Nope"})

    assert missing == ("NotHere",)


def test_a_snake_case_name_inside_a_module_path_is_renamed() -> None:
    """A patch target naming an internal function. The function itself is renamed, so the string that
    reaches it has to follow. 47 patch targets needed this, and the gate named every one.

    Safe because the path already names the engine's new home: inside such a path a segment is a module,
    a class or a function, never a field."""
    assert rewrite('patch("token_iq.gateway.proxy.x.litellm_judge_name")') == (
        'patch("token_iq.gateway.proxy.x.gateway_judge_name")'
    )


def test_a_dotted_string_that_is_not_a_module_path_is_left_alone() -> None:
    """Outside a path naming the engine, a dotted string could be anything: a span name, a metric, a
    nested field in someone's payload."""
    assert rewrite('tracer.trace("metadata.litellm_judge_name")') == 'tracer.trace("metadata.litellm_judge_name")'
    assert rewrite('x = "other.package.litellm_judge_name"') == 'x = "other.package.litellm_judge_name"'


def test_several_renamed_segments_in_one_path_all_move() -> None:
    assert rewrite('patch("token_iq.gateway.LiteLLMRoutes.litellm_judge_name")') == (
        'patch("token_iq.gateway.GatewayRoutes.gateway_judge_name")'
    )


@pytest.mark.parametrize(
    ("before", "after"),
    [
        (
            "def f():\n    global litellm_judge_name\n    litellm_judge_name = 1\n",
            "def f():\n    global gateway_judge_name\n    gateway_judge_name = 1\n",
        ),
        (
            "def outer():\n    litellm_judge_name = 1\n    def inner():\n        nonlocal litellm_judge_name\n",
            "def outer():\n    gateway_judge_name = 1\n    def inner():\n        nonlocal gateway_judge_name\n",
        ),
    ],
)
def test_a_declared_global_or_nonlocal_is_renamed(before: str, after: str) -> None:
    """These hold their names as plain strings rather than as `Name` nodes. Missing one leaves a function
    declaring the old name while assigning the new one, which makes the assignment local: the read then
    raises UnboundLocalError on the first call, and nothing before that point complains."""
    assert rewrite(before) == after


def test_a_caught_exception_bound_to_a_renamed_name_is_renamed() -> None:
    """`except E as x` also holds `x` as a plain string."""
    assert rewrite("try:\n    pass\nexcept ValueError as litellm_judge_name:\n    pass\n") == (
        "try:\n    pass\nexcept ValueError as gateway_judge_name:\n    pass\n"
    )


def test_a_match_capture_bound_to_a_renamed_name_is_renamed() -> None:
    assert rewrite("match x:\n    case [litellm_judge_name]:\n        pass\n") == (
        "match x:\n    case [gateway_judge_name]:\n        pass\n"
    )


def test_a_parametrize_argname_is_renamed() -> None:
    """pytest reads its parameter names out of a comma-separated string. Renaming the function's
    parameter without this one makes pytest say the function uses no argument by that name, and the
    whole file stops collecting: three files did, and the collection count is what showed it."""
    before = '@pytest.mark.parametrize("env_curve,litellm_judge_name", [(1, 2)])\ndef t(env_curve, litellm_judge_name): ...\n'

    assert rewrite(before) == (
        '@pytest.mark.parametrize("env_curve,gateway_judge_name", [(1, 2)])\ndef t(env_curve, gateway_judge_name): ...\n'
    )


def test_parametrize_argnames_given_as_a_list_are_renamed() -> None:
    before = '@pytest.mark.parametrize(["litellm_judge_name"], [(1,)])\ndef t(litellm_judge_name): ...\n'

    assert (
        rewrite(before) == '@pytest.mark.parametrize(["gateway_judge_name"], [(1,)])\ndef t(gateway_judge_name): ...\n'
    )


def test_a_parametrize_value_is_not_mistaken_for_a_name() -> None:
    """Only the first argument holds names. The rest are the values, and a value that happens to read
    like a name is data."""
    before = '@pytest.mark.parametrize("x", ["litellm_judge_name"])\ndef t(x): ...\n'

    assert rewrite(before) == before
