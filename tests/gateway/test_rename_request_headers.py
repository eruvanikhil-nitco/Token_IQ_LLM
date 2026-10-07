"""Tests for scripts/rename/rename_request_headers.py.

Two different failures to guard. A rename that misses an emit site leaves the engine sending a header
nobody reads any more, which a test notices. A read pointed at the helper under the wrong name reads
nothing and the proxy behaves as though the caller had never sent it, which nothing notices.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MODULE_PATH = _REPO_ROOT / "scripts" / "rename" / "rename_request_headers.py"
_spec = importlib.util.spec_from_file_location("rename_request_headers", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
rename_request_headers = importlib.util.module_from_spec(_spec)
sys.modules["rename_request_headers"] = rename_request_headers
_spec.loader.exec_module(rename_request_headers)

IMPORT = "from token_iq.gateway import compat"


def engine(text: str) -> str:
    """The file as this pass would leave it, as if it were under `token_iq/`."""
    found, _counts, _mentions = rename_request_headers.rewrite(text, "token_iq/gateway/x.py", route_reads=True)
    return found


def body(text: str) -> str:
    """The same without the import line, so a case can state one thing."""
    return "\n".join(line for line in engine(text).split("\n") if line != IMPORT)


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ('headers["x-litellm-model-group"] = g', 'headers["x-token-iq-model-group"] = g'),
        ('headers["X-LiteLLM-Trace-Id"] = t', 'headers["x-token-iq-trace-id"] = t'),
        ("headers['x-litellm-cache-key'] = k", "headers['x-token-iq-cache-key'] = k"),
        ('return {"x-litellm-call-id": c}', 'return {"x-token-iq-call-id": c}'),
        ('found = name == "x-litellm-tags"', 'found = name == "x-token-iq-tags"'),
    ],
)
def test_a_header_the_engine_sends_is_renamed(before: str, after: str) -> None:
    assert body(before) == after


def test_the_mixed_case_spelling_is_put_in_lower_case() -> None:
    """One header, however it is cased, and lower case is what goes on an HTTP/2 wire."""
    assert body('h["X-LiteLLM-Key-Alias"] = a') == 'h["x-token-iq-key-alias"] = a'


def test_a_read_is_routed_through_the_helper() -> None:
    assert body('x = request.headers.get("x-litellm-tags")') == 'x = compat.header(request.headers, "x-token-iq-tags")'


def test_a_read_keeps_its_default() -> None:
    before = 'x = request.headers.get("x-litellm-call-id", str(uuid.uuid4()))'

    assert body(before) == 'x = compat.header(request.headers, "x-token-iq-call-id", str(uuid.uuid4()))'


def test_a_read_from_a_plain_name_is_routed() -> None:
    assert (
        body('x = headers.get("x-litellm-timeout", None)') == 'x = compat.header(headers, "x-token-iq-timeout", None)'
    )


def test_a_get_with_more_than_a_default_is_left_alone() -> None:
    """Not a mapping read of a header. Rewriting it would change what the extra arguments mean."""
    before = 'x = thing.get("x-litellm-tags", None, strict=True)'

    assert "compat.header" not in body(before)


def test_a_get_of_something_else_is_left_alone() -> None:
    before = 'x = headers.get("authorization")'

    assert body(before) == before


def test_a_literal_that_merely_mentions_the_prefix_is_left_alone() -> None:
    """`llm_provider-x-litellm-response-cost` is a different key, built by prefixing a provider's header.
    Renaming its tail silently would stop the engine reading a cost an upstream proxy reported."""
    before = 'x = h["llm_provider-x-litellm-response-cost"]'

    assert body(before) == before


def test_a_literal_that_mentions_the_prefix_is_reported_instead() -> None:
    _found, _counts, mentions = rename_request_headers.rewrite(
        'raise ValueError("send an x-litellm-session-id header")', "token_iq/gateway/x.py"
    )

    assert [m.value for m in mentions] == ["send an x-litellm-session-id header"]


def test_a_renamed_literal_is_not_also_reported() -> None:
    _found, _counts, mentions = rename_request_headers.rewrite('h["x-litellm-tags"] = t', "token_iq/gateway/x.py")

    assert mentions == ()


def test_a_segment_of_an_f_string_is_renamed_without_breaking_it() -> None:
    """The literal is edited inside its own source text, so the braces and the quotes survive."""
    before = 'h[f"x-litellm-key-remaining-requests-{group}"] = r'

    assert body(before) == 'h[f"x-token-iq-key-remaining-requests-{group}"] = r'


def test_a_bare_prefix_concatenated_onto_something_is_renamed() -> None:
    """The shape that broke silently in phase 6: a prefix something builds a name out of."""
    assert body('h[f"x-litellm-{k}"] = v') == 'h[f"x-token-iq-{k}"] = v'


def test_a_non_ascii_character_earlier_on_the_line_does_not_shift_the_edit() -> None:
    """`col_offset` is a byte offset into the line's UTF-8."""
    before = 'h = log("café", {"x-litellm-tags": t})'

    assert body(before) == 'h = log("café", {"x-token-iq-tags": t})'


def test_two_headers_on_one_line_both_move() -> None:
    """Edited back to front, and the new name is longer than the old one."""
    before = 'h = {"x-litellm-tags": t, "x-litellm-model": m}'

    assert body(before) == 'h = {"x-token-iq-tags": t, "x-token-iq-model": m}'


def test_a_rename_and_a_read_on_one_line_both_move() -> None:
    before = 'h = {"x-litellm-tags": request.headers.get("x-litellm-model")}'

    assert body(before) == 'h = {"x-token-iq-tags": compat.header(request.headers, "x-token-iq-model")}'


def test_the_import_is_added_once_before_the_first_read() -> None:
    before = 'import os\n\na = h.get("x-litellm-tags")\nb = h.get("x-litellm-model")\n'

    found = engine(before).split("\n")

    assert found.count(IMPORT) == 1
    assert found.index(IMPORT) < found.index('a = compat.header(h, "x-token-iq-tags")')


def test_an_import_further_down_the_file_does_not_pull_the_helper_past_the_first_read() -> None:
    """`__init__.py` reads on line 26 and goes on importing until line 1470. Putting the import after the
    last one in the file left the name undefined where it was wanted, and the package would not load."""
    before = 'import os\n\na = h.get("x-litellm-tags")\n\nimport json\n'

    found = engine(before).split("\n")

    assert found.index(IMPORT) < found.index('a = compat.header(h, "x-token-iq-tags")')


def test_a_file_with_only_renames_gets_no_import() -> None:
    assert IMPORT not in engine('h["x-litellm-tags"] = t\n')


def test_a_file_that_does_not_parse_is_left_exactly_as_it_was() -> None:
    assert engine("def (\n") == "def (\n"


@pytest.mark.parametrize(
    ("name", "routed"),
    [("token_iq/gateway/x.py", True), ("tests/gateway/test_x.py", False), ("enterprise/x.py", False)],
)
def test_only_the_engines_own_reads_are_pointed_at_the_helper(name: str, routed: bool) -> None:
    """A test says which spelling it means, so routing one through the helper would change what it tests.
    The names it asserts on still move, because a response carries the new one."""
    assert rename_request_headers.routes_reads(name) is routed


def test_a_file_outside_the_engine_has_its_names_moved_and_its_reads_left_alone(tmp_path: Path) -> None:
    """Through `run`, so what is under test is that the decision is the one acted on."""
    source = tmp_path / "test_x.py"
    _ = source.write_text('assert r.headers.get("x-litellm-call-id")\n', encoding="utf-8")

    _totals, _broken, _mentions = rename_request_headers.run([source], write=True, reads_in=lambda _name: False)

    assert source.read_text(encoding="utf-8") == 'assert r.headers.get("x-token-iq-call-id")\n'


def test_a_file_inside_the_engine_has_its_reads_routed(tmp_path: Path) -> None:
    source = tmp_path / "mod.py"
    _ = source.write_text('x = r.headers.get("x-litellm-call-id")\n', encoding="utf-8")

    _totals, _broken, _mentions = rename_request_headers.run([source], write=True, reads_in=lambda _name: True)

    assert 'compat.header(r.headers, "x-token-iq-call-id")' in source.read_text(encoding="utf-8")


def test_this_pass_and_its_tests_are_out_of_scope() -> None:
    """Both name the old spelling on purpose. Letting the pass rewrite itself turns every literal it looks
    for into the thing it replaces them with, after which it matches nothing and reports a clean run."""
    listed = {rename_request_headers.named(path) for path in rename_request_headers.tracked()}

    assert "scripts/rename/rename_request_headers.py" not in listed
    assert "tests/gateway/test_rename_request_headers.py" not in listed
    assert "token_iq/gateway/compat.py" not in listed
    assert "token_iq/gateway/constants.py" in listed, "the filter is too wide"


def test_the_tests_that_prove_the_old_name_still_works_are_out_of_scope() -> None:
    """These two are the only coverage that a caller sending the old name is understood, and both sides of
    every assertion in them name a spelling. Renaming the names moved both sides together, which left all
    55 cases green while they tested nothing. Caught by reading the diff, not by running them."""
    listed = {rename_request_headers.named(path) for path in rename_request_headers.tracked()}

    assert "tests/gateway/test_compat.py" not in listed
    assert "tests/gateway/proxy/test_upgrade_keeps_working.py" not in listed


def test_a_dry_run_changes_nothing_on_disk(tmp_path: Path) -> None:
    source = tmp_path / "mod.py"
    _ = source.write_text('h["x-litellm-tags"] = t\n', encoding="utf-8")

    totals, _broken, _mentions = rename_request_headers.run([source], write=False)

    assert totals["header renamed"] == 1
    assert source.read_text(encoding="utf-8") == 'h["x-litellm-tags"] = t\n'


def test_a_rewrite_that_would_not_parse_leaves_the_file_as_it_was(tmp_path: Path) -> None:
    source = tmp_path / "mod.py"
    _ = source.write_text('h["x-litellm-tags"] = t\n', encoding="utf-8")

    def destructive(text: str, path: str, reads: bool) -> tuple[str, dict[str, int], tuple[object, ...]]:
        return "def (", {"broken on purpose": 1}, ()

    totals, broken, _mentions = rename_request_headers.run([source], write=True, rewriter=destructive)

    assert broken and broken[0].endswith("mod.py")
    assert "files changed" not in totals
    assert source.read_text(encoding="utf-8") == 'h["x-litellm-tags"] = t\n'
