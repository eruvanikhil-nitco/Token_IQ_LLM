"""Tests for scripts/rename/move_engine_package.py.

This script edits roughly four thousand files in one pass, so a rule that is slightly wrong is not a
small problem: it is wrong in thousands of places at once and the diff is far too large to read. Each
rule is therefore exercised on text it must change and on text it must leave, with the near misses
written out, because those are what a regex over a whole repository actually gets wrong.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MODULE_PATH = _REPO_ROOT / "scripts" / "rename" / "move_engine_package.py"
_spec = importlib.util.spec_from_file_location("move_engine_package", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
move_engine_package = importlib.util.module_from_spec(_spec)
sys.modules["move_engine_package"] = move_engine_package
_spec.loader.exec_module(move_engine_package)


def rewrite(text: str, *, whole_file: bool = False) -> str:
    """The script's whole pass over one file's text. `whole_file` is the registry-file treatment,
    where every dotted literal is a module path because the file holds nothing else."""
    found, _ = move_engine_package.rewrite(text, whole_file=whole_file)
    return found


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
    """The 58,000 `litellm.<attr>` uses are untouched by this half, so the name they read has to go
    on being bound. Renaming it is the second half, and it is a local-name rename once this lands."""
    assert rewrite("import litellm") == "from token_iq import gateway as litellm"


def test_importing_a_submodule_keeps_the_submodule_and_the_old_name() -> None:
    """`import litellm.utils` binds `litellm`, and callers then write `litellm.utils.foo`. Importing
    only the submodule would bind `token_iq` instead and every one of those calls would break."""
    assert rewrite("import litellm.utils") == ("import token_iq.gateway.utils\nfrom token_iq import gateway as litellm")


def test_an_indented_import_keeps_its_indentation() -> None:
    """Most of these are inside functions, deliberately, to keep import time down. A rule that
    discards the indentation produces a file that does not parse."""
    assert rewrite("    import litellm") == "    from token_iq import gateway as litellm"
    assert rewrite("        import litellm.utils") == (
        "        import token_iq.gateway.utils\n        from token_iq import gateway as litellm"
    )


def test_the_inner_package_loses_its_redundant_prefix() -> None:
    assert rewrite("from litellm.litellm_core_utils.core_helpers import x") == (
        "from token_iq.gateway.core_utils.core_helpers import x"
    )


def test_a_relative_import_of_the_inner_package_is_rewritten_too() -> None:
    assert rewrite("from .litellm_core_utils import x") == "from .core_utils import x"
    assert rewrite("from ..litellm_core_utils.foo import x") == "from ..core_utils.foo import x"


@pytest.mark.parametrize(
    "untouched",
    [
        # The near misses. Each of these contains the old name and must come out unchanged, because
        # it is either a different identifier or a later phase's business.
        'litellm_params = {"model": "gpt-4o"}',
        "settings = gateway_settings or litellm_settings",
        "# litellm is the engine this was forked from",
        'LITELLM_MASTER_KEY = os.getenv("LITELLM_MASTER_KEY")',
        'span.set_attribute("litellm.trace_id", trace_id)',
        'headers = {"x-litellm-model-id": model_id}',
        "class LiteLLM_TeamTable(BaseModel):",
    ],
)
def test_what_this_pass_must_not_touch(untouched: str) -> None:
    assert rewrite(untouched) == untouched


def test_an_import_inside_a_longer_name_is_not_rewritten() -> None:
    """`import litellm_proxy_extras` starts with the old name and is a different package."""
    assert rewrite("import litellm_proxy_extras") == "import litellm_proxy_extras"
    assert rewrite("from litellm_proxy_extras import x") == "from litellm_proxy_extras import x"


@pytest.mark.parametrize(
    "call",
    [
        'patch("litellm.proxy.proxy_server.prisma_client")',
        'mock.patch("litellm.proxy.proxy_server.prisma_client")',
        'importlib.import_module("litellm.proxy.proxy_server.prisma_client")',
        'resources.files("litellm.proxy.proxy_server.prisma_client")',
        'register(module_path="litellm.proxy.proxy_server.prisma_client")',
    ],
)
def test_a_dotted_string_in_a_resolving_position_is_rewritten(call: str) -> None:
    """A `mock.patch` target and its relatives. 1,246 of them name one attribute of the proxy server
    alone, and each is resolved lazily, so a missed one goes green having patched nothing."""
    assert rewrite(call) == call.replace("litellm.proxy", "token_iq.gateway.proxy")


def test_a_lookup_in_the_import_cache_is_rewritten() -> None:
    assert rewrite('sys.modules["litellm.utils"]') == 'sys.modules["token_iq.gateway.utils"]'
    assert rewrite('sys.modules.get("litellm.proxy.proxy_server")') == (
        'sys.modules.get("token_iq.gateway.proxy.proxy_server")'
    )


@pytest.mark.parametrize(
    "left_alone",
    [
        # Every one of these resolves to something real, which is why resolving cannot be the test.
        # An OpenTelemetry attribute, phase 9's.
        'safe_set_attribute(span, "litellm.trace_id", str(trace_id))',
        # A Datadog metric name, phase 9's.
        '{"metric": "litellm.llm_api.latency"}',
        # A Datadog span name that happens to be spelled like a module path.
        'with tracer.trace("litellm.proxy.auth.budget_checks"):',
        # A call_type value that is logged, not imported.
        'call_type = kwargs.get("call_type", "litellm.completion")',
        # A sentinel a caller passes as mock_response to force an error. Renaming it breaks a
        # documented way of calling the engine, which is phase 7's problem and not this pass's.
        'if mock_response == "litellm.RateLimitError":',
        # A forward reference, which still resolves in this half because the old name stays bound.
        'def _config() -> "litellm.DashScopeChatConfig":',
        # A health-endpoint response field.
        '{"litellm.callbacks": callbacks}',
    ],
)
def test_a_dotted_string_that_is_data_is_left_alone(left_alone: str) -> None:
    assert rewrite(left_alone) == left_alone


def test_a_registry_file_has_every_dotted_path_rewritten() -> None:
    """Three files are tables of module paths held in bare tuples and dicts, with no call around them
    for a context rule to read. They are named in the script one file at a time."""
    before = 'REGISTRY = {"Cache": ("litellm.caching.caching", "Cache")}'
    assert rewrite(before, whole_file=True) == ('REGISTRY = {"Cache": ("token_iq.gateway.caching.caching", "Cache")}')


def test_a_registry_path_is_not_rewritten_in_an_ordinary_file() -> None:
    """The same text outside a registry file stays, because there it could be anything."""
    before = 'REGISTRY = {"Cache": ("litellm.caching.caching", "Cache")}'
    assert rewrite(before) == before


def test_a_module_path_completed_at_runtime_is_rewritten_by_name() -> None:
    """The failure the discovery dump exists to catch. This literal is a prefix the code concatenates
    a directory name onto, so no rule about dotted paths can see it, and leaving it turns every
    guardrail off while the code still compiles and lints."""
    before = '                module_path = "litellm." + rel_path.replace(os.sep, ".")'
    assert rewrite(before) == '                module_path = "token_iq.gateway." + rel_path.replace(os.sep, ".")'


def test_the_registry_f_strings_are_rewritten() -> None:
    assert rewrite('module_path = f"litellm.proxy.guardrails.guardrail_hooks.{item}"') == (
        'module_path = f"token_iq.gateway.proxy.guardrails.guardrail_hooks.{item}"'
    )


def test_a_file_the_rewrite_would_break_is_reported_rather_than_written(tmp_path: Path) -> None:
    """A guard on the pass itself. If a rule ever produces something that does not parse, the file is
    left as it was and named, instead of four thousand files being written with one of them broken."""
    good = tmp_path / "good.py"
    _ = good.write_text("import litellm\n", encoding="utf-8")

    totals, broken = move_engine_package.run([good], write=True)

    assert broken == ()
    assert totals["files changed"] == 1
    assert good.read_text(encoding="utf-8") == "from token_iq import gateway as litellm\n"


def test_a_file_with_nothing_to_change_is_not_rewritten(tmp_path: Path) -> None:
    quiet = tmp_path / "quiet.py"
    _ = quiet.write_text("x = 1\n", encoding="utf-8")

    totals, broken = move_engine_package.run([quiet], write=True)

    assert broken == ()
    assert "files changed" not in totals
    assert quiet.read_text(encoding="utf-8") == "x = 1\n"


def test_a_dry_run_changes_nothing_on_disk(tmp_path: Path) -> None:
    source = tmp_path / "mod.py"
    _ = source.write_text("import litellm\n", encoding="utf-8")

    totals, _broken = move_engine_package.run([source], write=False)

    assert totals["files changed"] == 1
    assert source.read_text(encoding="utf-8") == "import litellm\n"


def test_a_rewritten_file_keeps_its_final_newline(tmp_path: Path) -> None:
    r"""The rules anchor on end of line, and `\s*$` eats the newline itself. Writing a file with its
    last line break stripped would have done that to every one of the 1,614 files that import the
    package, and the only complaint would have come from the formatter."""
    source = tmp_path / "mod.py"
    _ = source.write_text("import litellm\nx = 1\n", encoding="utf-8")

    _totals, _broken = move_engine_package.run([source], write=True)

    found = source.read_text(encoding="utf-8")
    assert found.endswith("\n")
    assert found.count("\n") == 2


def test_two_imports_on_consecutive_lines_both_survive(tmp_path: Path) -> None:
    r"""`^([ \t]*)` rather than `^(\s*)`: under MULTILINE, `\s*` matches across a line break, so a run
    of imports collapses into one rewrite and the rest are swallowed."""
    source = tmp_path / "mod.py"
    _ = source.write_text("import litellm\nimport litellm.utils\n", encoding="utf-8")

    _totals, _broken = move_engine_package.run([source], write=True)

    assert source.read_text(encoding="utf-8") == (
        "from token_iq import gateway as litellm\n"
        "import token_iq.gateway.utils\n"
        "from token_iq import gateway as litellm\n"
    )


def test_an_import_with_trailing_whitespace_is_still_rewritten() -> None:
    """Anchoring on `$` alone misses it, and a missed import leaves a module pointing at a package
    that is no longer there. What was on the line is kept rather than tidied: this pass changes
    imports, and the formatter is what removes trailing space."""
    assert rewrite("import litellm.utils  ") == (
        "import token_iq.gateway.utils  \nfrom token_iq import gateway as litellm"
    )


def test_an_import_kept_for_its_side_effect_keeps_the_comment_saying_so() -> None:
    """Fourteen of these carry a `# noqa` that is the only thing stopping the linter deleting them.
    A rule anchored on end of line alone skips every one, and the import never moves."""
    assert rewrite("import litellm  # noqa: E402,F401") == (
        "from token_iq import gateway as litellm  # noqa: E402,F401"
    )
    assert rewrite("import litellm.caching.caching  # must not import redis at module top") == (
        "import token_iq.gateway.caching.caching  # must not import redis at module top\n"
        "from token_iq import gateway as litellm"
    )


def test_a_longer_name_starting_with_the_inner_package_is_not_rewritten() -> None:
    """Without the word boundary the rule eats the start of any longer identifier, leaving something
    that neither reads nor resolves."""
    assert rewrite("from litellm.litellm_core_utils_vendor import x") == (
        "from token_iq.gateway.litellm_core_utils_vendor import x"
    )


def test_a_rewrite_that_would_not_parse_leaves_the_file_as_it_was(tmp_path: Path) -> None:
    """The guard, exercised with a rewriter injected for the purpose. Four thousand files are written
    in one pass, so one of them coming out unparseable has to stop at that file and be named rather
    than be written and found later by whatever runs next."""
    source = tmp_path / "mod.py"
    _ = source.write_text("import litellm\n", encoding="utf-8")

    def destructive(text: str, *, whole_file: bool = False) -> tuple[str, dict[str, int]]:
        return "def (", {"broken on purpose": 1}

    totals, broken = move_engine_package.run([source], write=True, rewriter=destructive)

    assert broken == ("mod.py",) or broken[0].endswith("mod.py")
    assert "files changed" not in totals
    assert source.read_text(encoding="utf-8") == "import litellm\n"


def test_a_submodule_imported_under_another_name_needs_no_old_binding() -> None:
    """`import litellm.constants as _c` binds only `_c`, so nothing in the module reads the old name
    and adding a binding for it would be an unused import."""
    assert rewrite("import litellm.constants as _c") == "import token_iq.gateway.constants as _c"
    assert rewrite("    import litellm.proxy.proxy_server as proxy_server") == (
        "    import token_iq.gateway.proxy.proxy_server as proxy_server"
    )


def test_the_aliased_form_is_matched_before_the_plain_one() -> None:
    """Rule order. The unaliased rule anchors on end of line, so it cannot take an aliased import,
    but if it ever stopped anchoring it would produce `import token_iq.gateway.constants` and leave
    `as _c` stranded on the line after."""
    assert "as _c" in rewrite("import litellm.constants as _c")
    assert rewrite("import litellm.constants as _c").count("\n") == 0
