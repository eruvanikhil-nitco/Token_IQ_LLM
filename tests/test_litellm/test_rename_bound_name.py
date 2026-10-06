"""Tests for scripts/rename/rename_bound_name.py.

The pass renames the name every module binds the engine to. It touches 1,624 files, and the thing that
makes it dangerous is that `litellm` is a substring of names that are not it: `litellm_params` is a
config key, `LITELLM_MASTER_KEY` an environment variable, `LiteLLM_TeamTable` a database model, and
`"litellm.trace_id"` an OpenTelemetry attribute. Each belongs to a later phase, so each is written out
below as text the pass must leave exactly as it is.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MODULE_PATH = _REPO_ROOT / "scripts" / "rename" / "rename_bound_name.py"
_spec = importlib.util.spec_from_file_location("rename_bound_name", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
rename_bound_name = importlib.util.module_from_spec(_spec)
sys.modules["rename_bound_name"] = rename_bound_name
_spec.loader.exec_module(rename_bound_name)


def rewrite(text: str) -> str:
    found, _ = rename_bound_name.rewrite(text)
    return found


# --- the import that binds it --------------------------------------------------------------------


def test_the_alias_goes() -> None:
    assert rewrite("from token_iq import gateway as litellm") == "from token_iq import gateway"


def test_the_alias_goes_but_the_comment_stays() -> None:
    """A `# noqa` on one of these is the only thing stopping the linter deleting an import kept for its
    side effect."""
    assert rewrite("from token_iq import gateway as litellm  # noqa: F401") == (
        "from token_iq import gateway  # noqa: F401"
    )


def test_an_indented_import_keeps_its_indentation() -> None:
    assert rewrite("    from token_iq import gateway as litellm") == "    from token_iq import gateway"


def test_the_private_alias_is_renamed_rather_than_dropped() -> None:
    """Six modules bind it as `_litellm`, which says the module means it to be private. Dropping the
    alias would bind `gateway` publicly instead of renaming what was asked for."""
    assert rewrite("from token_iq import gateway as _litellm") == "from token_iq import gateway as _gateway"


# --- where the name is used ----------------------------------------------------------------------


def test_an_attribute_read_through_the_name_is_renamed() -> None:
    assert rewrite("cost = litellm.completion_cost(response)") == "cost = gateway.completion_cost(response)"


def test_a_whole_chain_moves_with_its_base() -> None:
    """Only the base of the chain is the bound name, so renaming the base is the whole job."""
    assert rewrite("litellm.proxy.proxy_server.prisma_client = client") == (
        "gateway.proxy.proxy_server.prisma_client = client"
    )


def test_the_name_passed_as_a_value_is_renamed() -> None:
    assert rewrite("resources.files(litellm).joinpath('x')") == "resources.files(gateway).joinpath('x')"


def test_assigning_to_the_name_is_renamed_too() -> None:
    """One file reloads the module and rebinds it. Renaming the read without the write would leave the
    two halves of that disagreeing."""
    assert rewrite("litellm = importlib.reload(module)") == "gateway = importlib.reload(module)"


def test_the_private_name_is_renamed_where_it_is_used() -> None:
    assert rewrite("_litellm.completion(**kwargs)") == "_gateway.completion(**kwargs)"


# --- what must not move -------------------------------------------------------------------------


@pytest.mark.parametrize(
    "untouched",
    [
        # A config key, phase 7's.
        'params = {"litellm_params": {"model": "gpt-4o"}}',
        "settings = litellm_settings or {}",
        # An environment variable, phase 7's.
        'key = os.getenv("LITELLM_MASTER_KEY")',
        # A request header, phase 7's.
        'headers = {"x-litellm-model-id": model_id}',
        # A database model, phase 8's.
        "class LiteLLM_TeamTable(BaseModel):",
        # A metric and a span attribute, phase 9's.
        'span.set_attribute("litellm.trace_id", trace_id)',
        '{"metric": "litellm.llm_api.latency"}',
        # A patch target, which names the module by its absolute path and not by what anything binds.
        'patch("token_iq.gateway.proxy.proxy_server.prisma_client")',
        # Prose.
        "# litellm is the engine this was forked from",
        '"""Read the docs at docs.litellm.ai for the upstream behaviour."""',
        # An identifier that merely starts with it.
        "logger = litellm_logging.get_logger()",
        "from token_iq.gateway.core_utils import litellm_logging",
    ],
)
def test_what_this_pass_must_not_touch(untouched: str) -> None:
    assert rewrite(untouched) == untouched


def test_a_sentinel_a_caller_passes_is_left_alone() -> None:
    """`mock_response="litellm.RateLimitError"` is a documented way of calling the engine. Renaming it
    breaks that call, and it is phase 7's to decide."""
    assert rewrite('if mock_response == "litellm.RateLimitError":') == 'if mock_response == "litellm.RateLimitError":'


# --- the awkward few ----------------------------------------------------------------------------


def test_a_forward_reference_in_an_annotation_is_renamed() -> None:
    """It is resolved against the module's globals when something asks for it, so it reads the bound
    name. There are nine, and every other string holding the old name belongs to a later phase."""
    assert rewrite('def _router() -> "litellm.Router": ...') == 'def _router() -> "gateway.Router": ...'
    assert rewrite('x: "litellm.Usage" = make()') == 'x: "gateway.Usage" = make()'


def test_a_string_that_looks_like_an_annotation_but_is_not_one_is_left_alone() -> None:
    """The same text in a call argument is data. Only the annotation position makes it a reference."""
    assert rewrite('log("litellm.Router")') == 'log("litellm.Router")'


def test_a_re_exported_name_is_renamed_with_its_consumers() -> None:
    """One shared test module re-exports the engine under the bound name, and two tests import it from
    there. Renaming the binding without the re-export leaves those two importing a name nobody has."""
    assert rewrite("from tests.helpers import litellm") == "from tests.helpers import gateway"


def test_an_all_entry_naming_the_bound_name_is_renamed() -> None:
    """The re-export is only reachable because `__all__` lists it."""
    assert rewrite('__all__ = ["json", "litellm", "os"]') == '__all__ = ["json", "gateway", "os"]'


def test_a_list_of_strings_that_is_not_all_is_left_alone() -> None:
    assert rewrite('names = ["json", "litellm", "os"]') == 'names = ["json", "litellm", "os"]'


def test_the_one_multi_target_import_is_split() -> None:
    """No rule splits a multi-target import, and there is exactly one. It is named rather than matched,
    so a reviewer reads the line that changes."""
    assert rewrite("import pytest, litellm") == "import pytest\nfrom token_iq import gateway"


# --- the pass itself ----------------------------------------------------------------------------


def test_a_non_ascii_character_earlier_on_the_line_does_not_shift_the_edit() -> None:
    """`col_offset` is a byte offset into the line's UTF-8. Indexing it as characters lands in the wrong
    place on any line holding a non-ASCII character before the name, and 1,207 files have one."""
    before = 'log("café 你好", litellm.api_base)'

    found = rewrite(before)
    assert found == 'log("café 你好", gateway.api_base)'
    assert "café 你好" in found


def test_a_separator_python_does_not_count_as_a_line_break_does_not_shift_the_edit() -> None:
    """`str.splitlines` also breaks on U+2028, U+2029, a form feed and four more, which the tokenizer
    does not. Three files hold one inside a string literal."""
    before = 'x = "a' + chr(0x2028) + 'b"\ny = litellm.api_base\n'

    assert rewrite(before).splitlines()[-1] == "y = gateway.api_base"


def test_a_file_with_nothing_to_change_is_not_rewritten(tmp_path: Path) -> None:
    quiet = tmp_path / "quiet.py"
    _ = quiet.write_text("x = 1\n", encoding="utf-8")

    totals, broken = rename_bound_name.run([quiet], write=True)

    assert broken == ()
    assert "files changed" not in totals
    assert quiet.read_text(encoding="utf-8") == "x = 1\n"


def test_a_dry_run_changes_nothing_on_disk(tmp_path: Path) -> None:
    source = tmp_path / "mod.py"
    _ = source.write_text("from token_iq import gateway as litellm\n", encoding="utf-8")

    totals, _broken = rename_bound_name.run([source], write=False)

    assert totals["files changed"] == 1
    assert source.read_text(encoding="utf-8") == "from token_iq import gateway as litellm\n"


def test_a_rewritten_file_keeps_its_final_newline(tmp_path: Path) -> None:
    source = tmp_path / "mod.py"
    _ = source.write_text("from token_iq import gateway as litellm\nx = litellm.api_base\n", encoding="utf-8")

    _totals, _broken = rename_bound_name.run([source], write=True)

    found = source.read_text(encoding="utf-8")
    assert found == "from token_iq import gateway\nx = gateway.api_base\n"


def test_a_rewrite_that_would_not_parse_leaves_the_file_as_it_was(tmp_path: Path) -> None:
    """1,624 files are written in one pass, so one coming out unparseable has to stop at that file and
    be named rather than be written and found later by whatever runs next."""
    source = tmp_path / "mod.py"
    _ = source.write_text("from token_iq import gateway as litellm\n", encoding="utf-8")

    def destructive(text: str) -> tuple[str, dict[str, int]]:
        return "def (", {"broken on purpose": 1}

    totals, broken = rename_bound_name.run([source], write=True, rewriter=destructive)

    assert broken and broken[0].endswith("mod.py")
    assert "files changed" not in totals
    assert source.read_text(encoding="utf-8") == "from token_iq import gateway as litellm\n"


def test_the_pass_leaves_its_own_source_alone() -> None:
    """It would otherwise turn every spelling it looks for into the thing it replaces them with, after
    which it matches nothing anywhere and reports a clean run."""
    listed = {path.name for path in rename_bound_name.tracked()}

    assert "rename_bound_name.py" not in listed
    assert "move_engine_package.py" in listed, "the filter is too wide and is skipping other files"


def test_a_name_imported_under_an_alias_is_not_renamed() -> None:
    """Only the unaliased form is a re-export of the bound name. An aliased one binds something the
    importing module chose, and the exporting module still calls the thing `litellm`, so renaming the
    imported name would ask for something that is not there. There are none today, and the guard is
    what keeps the rule from inventing one."""
    assert rewrite("from somewhere import litellm as ll") == "from somewhere import litellm as ll"
