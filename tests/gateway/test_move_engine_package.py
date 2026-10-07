"""Tests for scripts/rename/move_engine_package.py.

This script edits roughly four thousand files in one pass, so a rule that is slightly wrong is not a
small problem: it is wrong in thousands of places at once and the diff is far too large to read. Each
rule is therefore exercised on text it must change and on text it must leave, with the near misses
written out, because those are what a regex over a whole repository actually gets wrong.

Both questions the pass asks about the world, whether a name is importable and whether a path exists,
are injected. The pass runs while the package is being moved out from under it, so a test that asked
this machine would be evidence about the checkout rather than about the rule.
"""

import importlib.util
import sys
from pathlib import Path
from typing import Final

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MODULE_PATH = _REPO_ROOT / "scripts" / "rename" / "move_engine_package.py"
_spec = importlib.util.spec_from_file_location("move_engine_package", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
move_engine_package = importlib.util.module_from_spec(_spec)
sys.modules["move_engine_package"] = move_engine_package
_spec.loader.exec_module(move_engine_package)


MODULES: Final = frozenset(
    {
        # The module names these tests say exist.
        "litellm",
        "litellm.proxy",
        "litellm.proxy.proxy_server",
        "litellm.proxy.management_endpoints",
        "litellm.proxy.management_endpoints.key_management_endpoints",
        "litellm.caching.caching",
        "litellm.responses.main",
        "litellm._logging",
        "litellm._lazy_imports_registry",
    }
)


def rewrite(text: str, *, whole_file: bool = False, on_disk: bool = True) -> str:
    """The script's whole pass over one file's text, with both questions about the world injected."""
    found, _ = move_engine_package.rewrite(
        text,
        whole_file=whole_file,
        can_import=lambda dotted: dotted in MODULES,
        on_disk=lambda _relative: on_disk,
    )
    return found


# --- imports -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("before", "after"),
    [
        (
            "from litellm.proxy._types import UserAPIKeyAuth",
            "from token_iq.gateway.proxy._types import UserAPIKeyAuth",
        ),
        ("from litellm import completion", "from token_iq.gateway import completion"),
        ("import litellm as ll", "from token_iq import gateway as ll"),
    ],
)
def test_each_import_shape_is_rewritten(before: str, after: str) -> None:
    assert rewrite(before) == after


def test_importing_the_package_keeps_binding_the_old_name() -> None:
    """The 58,000 `litellm.<attr>` uses are untouched by this half, so the name they read has to go on
    being bound. Renaming it is the second half, and it is a local-name rename once this lands."""
    assert rewrite("import litellm") == "from token_iq import gateway as litellm"


def test_importing_a_submodule_keeps_the_submodule_and_the_old_name() -> None:
    """`import litellm.utils` binds `litellm`, and callers then write `litellm.utils.foo`. Importing
    only the submodule would bind `token_iq` instead and every one of those calls would break."""
    assert rewrite("import litellm.utils") == "import token_iq.gateway.utils\nfrom token_iq import gateway as litellm"


def test_a_submodule_imported_under_another_name_needs_no_old_binding() -> None:
    """`import litellm.constants as _c` binds only `_c`, so nothing in the module reads the old name
    and adding a binding for it would be an unused import."""
    assert rewrite("import litellm.constants as _c") == "import token_iq.gateway.constants as _c"
    assert rewrite("    import litellm.proxy.proxy_server as proxy_server") == (
        "    import token_iq.gateway.proxy.proxy_server as proxy_server"
    )


def test_an_indented_import_keeps_its_indentation() -> None:
    """Most of these are inside functions, deliberately, to keep import time down. A rule that
    discards the indentation produces a file that does not parse."""
    assert rewrite("    import litellm") == "    from token_iq import gateway as litellm"
    assert rewrite("        import litellm.utils") == (
        "        import token_iq.gateway.utils\n        from token_iq import gateway as litellm"
    )


def test_an_import_with_trailing_whitespace_is_still_rewritten() -> None:
    """Anchoring on `$` alone misses it. What was on the line is kept rather than tidied: this pass
    changes imports, and the formatter is what removes trailing space."""
    assert rewrite("import litellm.utils  ") == (
        "import token_iq.gateway.utils  \nfrom token_iq import gateway as litellm"
    )


def test_an_import_kept_for_its_side_effect_keeps_the_comment_saying_so() -> None:
    """Fourteen of these carry a `# noqa` that is the only thing stopping the linter deleting them. A
    rule anchored on end of line alone skips every one, and the import never moves."""
    assert rewrite("import litellm  # noqa: E402,F401") == "from token_iq import gateway as litellm  # noqa: E402,F401"


def test_an_import_inside_a_longer_name_is_not_rewritten() -> None:
    """`import token_iq_migrations` starts with the old name and is a different package."""
    assert rewrite("import token_iq_migrations") == "import token_iq_migrations"
    assert rewrite("from token_iq_migrations import x") == "from token_iq_migrations import x"


# --- the inner package -------------------------------------------------------------------------


def test_the_inner_package_takes_the_absolute_path_in_an_import() -> None:
    assert rewrite("from litellm.litellm_core_utils.core_helpers import x") == (
        "from token_iq.gateway.core_utils.core_helpers import x"
    )


def test_the_inner_package_is_renamed_in_place_inside_an_expression() -> None:
    """The failure this prevents: the rule was unanchored and put the absolute new path into ordinary
    code, naming a package the module never imported. `token_iq` is not bound there, so the only sign
    is a NameError when that line finally runs, which for a test helper can be much later."""
    assert rewrite('patch.object(litellm.litellm_core_utils.litellm_logging, "x")') == (
        'patch.object(litellm.core_utils.litellm_logging, "x")'
    )


def test_a_relative_import_of_the_inner_package_is_rewritten_too() -> None:
    assert rewrite("from .litellm_core_utils import x") == "from .core_utils import x"
    assert rewrite("from ..litellm_core_utils.foo import x") == "from ..core_utils.foo import x"


def test_a_longer_name_starting_with_the_inner_package_is_not_rewritten() -> None:
    """Without the word boundary the rule eats the start of any longer identifier, leaving something
    that neither reads nor resolves."""
    assert rewrite("from litellm.litellm_core_utils_vendor import x") == (
        "from token_iq.gateway.litellm_core_utils_vendor import x"
    )


# --- dotted strings ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "call",
    [
        'patch("litellm.proxy.proxy_server.prisma_client")',
        'mock.patch("litellm.proxy.proxy_server.prisma_client")',
        'importlib.import_module("litellm.proxy.proxy_server")',
        'resources.files("litellm.proxy.proxy_server")',
        'register(module_path="litellm.proxy.proxy_server")',
        # 1,348 of these. monkeypatch.setattr resolves a dotted string exactly as patch does.
        'monkeypatch.setattr("litellm.proxy.proxy_server.prisma_client", f)',
        'monkeypatch.setitem(sys.modules, "litellm.proxy.proxy_server", fake)',
        'pytest.importorskip("litellm.proxy.proxy_server")',
        # A stand-in registered under a real module's name. Leaving the name behind registers a module
        # nothing imports, and the code under test loads the real one instead.
        'mod = types.ModuleType("litellm.proxy.proxy_server")',
        'fake = ModuleType("litellm.proxy.proxy_server")',
        # Tests alias patch, and the alias means the same thing.
        '_patch("litellm.proxy.proxy_server.prisma_client")',
    ],
)
def test_a_dotted_string_in_a_resolving_position_is_rewritten(call: str) -> None:
    """A `mock.patch` target and its relatives. 1,246 name one attribute of the proxy server alone,
    and each is resolved lazily, so a missed one goes green having patched nothing."""
    assert rewrite(call) == call.replace("litellm.proxy", "token_iq.gateway.proxy")


def test_a_lookup_in_the_import_cache_is_rewritten() -> None:
    assert rewrite('sys.modules["litellm"]') == 'sys.modules["token_iq.gateway"]'
    assert rewrite('sys.modules.get("litellm.proxy.proxy_server")') == (
        'sys.modules.get("token_iq.gateway.proxy.proxy_server")'
    )


def test_the_anchor_a_relative_import_resolves_against_moves() -> None:
    """`package=` is passed on every call the lazy-import machinery makes. Leaving it behind let the
    package import and then fail on the first attribute anyone asked for."""
    assert rewrite('importlib.import_module(path, package="litellm")') == (
        'importlib.import_module(path, package="token_iq.gateway")'
    )


def test_the_bare_package_name_is_left_alone_outside_a_resolving_position() -> None:
    """It is also a provider name, a tracer name and a log prefix, and there are 378 of them."""
    assert rewrite('custom_llm_provider = "litellm"') == 'custom_llm_provider = "litellm"'
    assert rewrite('LITELLM_TRACER_NAME = "litellm"') == 'LITELLM_TRACER_NAME = "litellm"'


def test_a_module_path_held_in_a_constant_moves() -> None:
    """47 of these. A test names the module under test once and builds its patch targets from it, so
    the constant is a reference even though nothing around it says so."""
    before = '_KM: Final = "litellm.proxy.management_endpoints.key_management_endpoints"'
    assert rewrite(before) == '_KM: Final = "token_iq.gateway.proxy.management_endpoints.key_management_endpoints"'


def test_a_class_resolved_through_a_logging_config_moves() -> None:
    """dictConfig resolves this through its "()" key, so neither a call nor an import is anywhere near
    it. Missing it turns JSON logging into a crash at start-up."""
    before = 'json_formatter_class: Final = "litellm._logging.JsonFormatter"'
    assert rewrite(before) == 'json_formatter_class: Final = "token_iq.gateway._logging.JsonFormatter"'


def test_a_nested_attribute_of_a_module_moves_from_an_ambiguous_position() -> None:
    """Eight of these sit in a conditional expression handed to patch. The whole path is not a module
    but its parent is, and three segments is what tells it from a two-segment field name."""
    before = 'target = "litellm.responses.main.responses" if flag else other'
    assert rewrite(before) == 'target = "token_iq.gateway.responses.main.responses" if flag else other'


def test_a_module_path_in_a_bare_tuple_moves_because_a_module_is_in_the_name() -> None:
    """A tuple element is a position context cannot settle: some hold module paths, others hold a
    customer's field names, spelled identically. The name itself is what answers it."""
    before = 'REGISTRY = {"Cache": ("litellm.caching.caching", "Cache")}'
    assert rewrite(before) == 'REGISTRY = {"Cache": ("token_iq.gateway.caching.caching", "Cache")}'


def test_a_registry_file_has_every_dotted_path_rewritten() -> None:
    """Three files are tables of module paths held in bare tuples and dicts, and a few of their entries
    name something no longer importable. They are named in the script one file at a time."""
    before = 'REGISTRY = {"Gone": ("litellm.removed.module", "Gone")}'
    assert rewrite(before, whole_file=True) == 'REGISTRY = {"Gone": ("token_iq.gateway.removed.module", "Gone")}'


@pytest.mark.parametrize(
    "left_alone",
    [
        # Every one of these resolves to something real, which is why resolving cannot be the test.
        'safe_set_attribute(span, "litellm.trace_id", str(trace_id))',
        'metrics = [{"metric": "litellm.llm_api.latency"}]',
        'with tracer.trace("litellm.proxy.auth.budget_checks"):',
        'call_type = kwargs.get("call_type", "litellm.completion")',
        # A sentinel a caller passes as mock_response to force an error. Renaming it breaks a
        # documented way of calling the engine, which is phase 7's problem and not this pass's.
        'if mock_response == "litellm.RateLimitError":',
        # A forward reference, which still resolves here because the old name stays bound.
        'def _config() -> "litellm.DashScopeChatConfig":',
        # A health endpoint's own response fields. `litellm.request_timeout` is a real setting on the
        # package, so asking whether it resolves says yes. Two segments is what saves it.
        'settings = {"litellm.request_timeout": timeout}',
        'assert settings["litellm.request_timeout"] == timeout',
        'CALL_ID_TAG = "litellm.call_id"',
        'assert "litellm.ai" not in got',
    ],
)
def test_a_dotted_string_that_is_data_is_left_alone(left_alone: str) -> None:
    assert rewrite(left_alone) == left_alone


def test_a_module_path_completed_at_runtime_is_rewritten_by_name() -> None:
    """The failure the discovery dump exists to catch. This literal is a prefix the code concatenates a
    directory name onto, so no rule about dotted paths can see it, and leaving it turns every guardrail
    off while the code still compiles and lints."""
    before = '                module_path = "litellm." + rel_path.replace(os.sep, ".")'
    assert rewrite(before) == '                module_path = "token_iq.gateway." + rel_path.replace(os.sep, ".")'


def test_the_registry_f_strings_are_rewritten() -> None:
    assert rewrite('module_path = f"litellm.proxy.guardrails.guardrail_hooks.{item}"') == (
        'module_path = f"token_iq.gateway.proxy.guardrails.guardrail_hooks.{item}"'
    )


# --- paths on disk -----------------------------------------------------------------------------


def test_a_path_to_a_file_that_is_really_there_moves() -> None:
    """A test reads the loader's own source to check what is in it. The path is text in a string, so no
    rule about modules sees it, and leaving it behind turns the test into a FileNotFoundError."""
    before = 'source = pathlib.Path("litellm/litellm_core_utils/get_model_cost_map.py")'
    assert rewrite(before) == 'source = pathlib.Path("token_iq/gateway/core_utils/get_model_cost_map.py")'


def test_a_path_to_something_that_is_not_there_is_left_alone() -> None:
    """`litellm/a.py` and `litellm/foo.py` are invented paths in fixtures, and there are dozens. Asking
    whether the path exists is what tells them from the real ones."""
    assert rewrite('open("litellm/a.py")', on_disk=False) == 'open("litellm/a.py")'


def test_a_path_that_merely_ends_in_the_package_name_is_not_rewritten() -> None:
    """`tests/litellm/...` and `my_litellm/...` both contain the folder name without being it. Without
    the boundary the rule rewrites the tail and leaves a path that points nowhere."""
    assert rewrite('open("tests/litellm/fixture.json")') == 'open("tests/litellm/fixture.json")'
    assert rewrite('open("my_litellm/thing.py")') == 'open("my_litellm/thing.py")'


def test_a_path_inside_a_longer_folder_name_is_not_rewritten() -> None:
    assert rewrite('open("token-iq-migrations/setup.py")') == 'open("token-iq-migrations/setup.py")'


def test_whether_a_path_is_really_there_is_answered_from_the_tree(tmp_path: Path) -> None:
    """The injected predicate is what every rule above is tested against, so the real one needs its own
    case. It is asked about a tree built here rather than about the package, which would only answer
    while the package was still in its old place and make this a test of when it ran."""
    _ = (tmp_path / "there.py").write_text("x = 1" + chr(10), encoding="utf-8")

    assert move_engine_package._on_disk("there.py", tmp_path) is True
    assert move_engine_package._on_disk("not_there.py", tmp_path) is False


# --- what this pass must not touch --------------------------------------------------------------


@pytest.mark.parametrize(
    "untouched",
    [
        'litellm_params = {"model": "gpt-4o"}',
        "settings = gateway_settings or litellm_settings",
        "# litellm is the engine this was forked from",
        'LITELLM_MASTER_KEY = os.getenv("LITELLM_MASTER_KEY")',
        'headers = {"x-litellm-model-id": model_id}',
        "class LiteLLM_TeamTable(BaseModel):",
    ],
)
def test_what_this_pass_must_not_touch(untouched: str) -> None:
    assert rewrite(untouched) == untouched


# --- the pass itself ---------------------------------------------------------------------------


def test_every_question_about_the_world_is_settled_before_anything_is_written(tmp_path: Path) -> None:
    """The defect this guards: `find_spec` on a submodule imports its parent, so asking halfway through
    a run makes the engine import itself through paths that do not exist yet. The answer comes back
    False and every reference after that point is silently left behind, with the route table, the
    registries and the public surface all still looking clean.
    """
    asked: list[str] = []  # rebind-ok: a spy recording what the pass asked
    source = tmp_path / "mod.py"
    _ = source.write_text('_T = "litellm.proxy.proxy_server.llm_router"\n', encoding="utf-8")

    def recording(name: str) -> bool:
        asked.append(name)
        return name in MODULES

    _totals, _broken = move_engine_package.run([source], write=True, can_import=recording)

    assert source.read_text(encoding="utf-8") == '_T = "token_iq.gateway.proxy.proxy_server.llm_router"\n'
    assert asked, "the pass asked nothing, so the rule that needs an answer never ran"


def test_a_file_with_nothing_to_change_is_not_rewritten(tmp_path: Path) -> None:
    quiet = tmp_path / "quiet.py"
    _ = quiet.write_text("x = 1\n", encoding="utf-8")

    totals, broken = move_engine_package.run([quiet], write=True, can_import=lambda _n: False)

    assert broken == ()
    assert "files changed" not in totals
    assert quiet.read_text(encoding="utf-8") == "x = 1\n"


def test_a_dry_run_changes_nothing_on_disk(tmp_path: Path) -> None:
    source = tmp_path / "mod.py"
    _ = source.write_text("import litellm\n", encoding="utf-8")

    totals, _broken = move_engine_package.run([source], write=False, can_import=lambda _n: False)

    assert totals["files changed"] == 1
    assert source.read_text(encoding="utf-8") == "import litellm\n"


def test_a_rewritten_file_keeps_its_final_newline(tmp_path: Path) -> None:
    r"""The rules anchor on end of line, and `\s*$` eats the newline itself. Writing a file with its
    last line break stripped would have done that to every one of the 1,614 files that import the
    package, and the only complaint would have come from the formatter."""
    source = tmp_path / "mod.py"
    _ = source.write_text("import litellm\nx = 1\n", encoding="utf-8")

    _totals, _broken = move_engine_package.run([source], write=True, can_import=lambda _n: False)

    found = source.read_text(encoding="utf-8")
    assert found.endswith("\n")
    assert found.count("\n") == 2


def test_two_imports_on_consecutive_lines_both_survive(tmp_path: Path) -> None:
    r"""`^([ \t]*)` rather than `^(\s*)`: under MULTILINE, `\s*` matches across a line break, so a run
    of imports collapses into one rewrite and the rest are swallowed."""
    source = tmp_path / "mod.py"
    _ = source.write_text("import litellm\nimport litellm.utils\n", encoding="utf-8")

    _totals, _broken = move_engine_package.run([source], write=True, can_import=lambda _n: False)

    assert source.read_text(encoding="utf-8") == (
        "from token_iq import gateway as litellm\n"
        "import token_iq.gateway.utils\n"
        "from token_iq import gateway as litellm\n"
    )


def test_a_rewrite_that_would_not_parse_leaves_the_file_as_it_was(tmp_path: Path) -> None:
    """The guard, exercised with a rewriter injected for the purpose. Four thousand files are written in
    one pass, so one coming out unparseable has to stop at that file and be named rather than be
    written and found later by whatever runs next."""
    source = tmp_path / "mod.py"
    _ = source.write_text("import litellm\n", encoding="utf-8")

    def destructive(text: str, *, whole_file: bool = False, can_import: object = None) -> tuple[str, dict[str, int]]:
        return "def (", {"broken on purpose": 1}

    totals, broken = move_engine_package.run([source], write=True, rewriter=destructive, can_import=lambda _n: False)

    assert broken and broken[0].endswith("mod.py")
    assert "files changed" not in totals
    assert source.read_text(encoding="utf-8") == "import litellm\n"


def test_the_pass_leaves_its_own_source_alone() -> None:
    """It rewrote itself once. Every literal it looks for became the thing it replaces them with, after
    which it matched nothing anywhere and reported a clean run over four thousand files."""
    listed = {path.name for path in move_engine_package.tracked("scripts/rename/*.py")}

    assert "move_engine_package.py" not in listed
    assert "dump_route_table.py" in listed, "the filter is too wide and is skipping other files"


def test_an_asgi_target_takes_the_absolute_path() -> None:
    """The string uvicorn and gunicorn import a server by. Nothing imports this one: a worker reads it
    and resolves it itself, so it cannot carry the bound name. Missing it means the engine imports
    cleanly, serves 589 routes when imported directly, and refuses to start from the command line."""
    assert rewrite('"app": "litellm.proxy.proxy_server:app",') == '"app": "token_iq.gateway.proxy.proxy_server:app",'
    assert rewrite("gunicorn litellm.proxy.proxy_server:app --workers 4") == (
        "gunicorn token_iq.gateway.proxy.proxy_server:app --workers 4"
    )


@pytest.mark.parametrize(
    "left_alone",
    [
        # Also `name:name`, and both belong to phase 9. Requiring a dot before the colon separates them
        # from an ASGI target.
        'PREFIX = "litellm:vcr:cassette:"',
        'unified_id = "litellm_proxy:test_batch"',
    ],
)
def test_a_colon_separated_key_that_is_not_an_asgi_target_is_left_alone(left_alone: str) -> None:
    assert rewrite(left_alone) == left_alone


def test_a_separator_python_does_not_count_as_a_line_break_does_not_shift_the_edit() -> None:
    """`str.splitlines` also breaks on U+2028, U+2029, a form feed and four more, which the tokenizer
    does not. Three files hold one inside a string literal, and every literal after it was written to
    the wrong line, where the replacement found nothing: fourteen patch targets in one file stayed
    behind while the count said they had moved."""
    before = 'x = "a' + chr(0x2028) + 'b"\npatch("litellm.proxy.proxy_server.thing")\n'

    assert rewrite(before).splitlines()[-1] == 'patch("token_iq.gateway.proxy.proxy_server.thing")'


def test_a_non_ascii_character_earlier_on_the_line_does_not_shift_the_edit() -> None:
    """`col_offset` is a byte offset into the line's UTF-8, so indexing it as characters lands in the
    wrong place on any line holding a non-ASCII character before the literal. 1,207 files have one."""
    before = 'patch("café 你好", "litellm.proxy.proxy_server.thing")'

    found = rewrite(before)
    assert found == before.replace("litellm.proxy", "token_iq.gateway.proxy")
    assert "café 你好" in found
