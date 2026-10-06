"""Tests for scripts/rename/move_test_tree.py.

The move itself is `git mv`. What this script does is point 95 files at the new path, and the two things
it can get wrong are order and scope: rewriting the outer directory first swallows the inner one, and
rewriting the historical record makes it describe a layout that never existed.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MODULE_PATH = _REPO_ROOT / "scripts" / "rename" / "move_test_tree.py"
_spec = importlib.util.spec_from_file_location("move_test_tree", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
move_test_tree = importlib.util.module_from_spec(_spec)
sys.modules["move_test_tree"] = move_test_tree
_spec.loader.exec_module(move_test_tree)


def rewrite(text: str) -> str:
    found, _ = move_test_tree.rewrite(text)
    return found


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ('test-path: "tests/test_litellm/integrations"', 'test-path: "tests/gateway/integrations"'),
        ("pytest tests/test_litellm -x -vv", "pytest tests/gateway -x -vv"),
        ('"tests/test_litellm",', '"tests/gateway",'),
        (
            "from tests.test_litellm.proxy.guardrails import x",
            "from tests.gateway.proxy.guardrails import x",
        ),
    ],
)
def test_the_path_is_rewritten_wherever_it_is_named(before: str, after: str) -> None:
    assert rewrite(before) == after


def test_the_inner_directory_is_rewritten_before_the_outer_one_reaches_it() -> None:
    """The engine's `litellm_core_utils` became `core_utils` when the package moved, so the mirror has to
    follow. Rewriting the outer path first would leave `tests/gateway/litellm_core_utils`, which mirrors
    nothing."""
    assert rewrite('test-path: "tests/test_litellm/litellm_core_utils"') == 'test-path: "tests/gateway/core_utils"'
    assert rewrite("from tests.test_litellm.litellm_core_utils import x") == "from tests.gateway.core_utils import x"


def test_a_longer_name_that_merely_starts_with_the_path_is_left_alone() -> None:
    """Nothing is named that today, and a rule that would rewrite it into a path that does not exist is
    worse than one that leaves it."""
    assert rewrite("tests/test_litellm_extra/x.py") == "tests/test_litellm_extra/x.py"


def test_a_reference_in_a_comment_is_rewritten_too() -> None:
    """A comment naming a path a reader will go and look at is wrong once the path has moved, and 43
    files inside the tree name it that way."""
    assert rewrite("# Current directory when running from tests/test_litellm/prompts") == (
        "# Current directory when running from tests/gateway/prompts"
    )


def test_the_historical_record_is_not_touched() -> None:
    """Each of these says what was true when it was written. A decision record describing a tree at a
    path it never had is worse than one naming the path it did have."""
    listed = {move_test_tree.named(path) for path in move_test_tree.tracked()}

    assert not any(name.startswith("docs/decisions/") for name in listed)
    assert not any(name.startswith("docs/plans/") for name in listed)
    assert "docs/status.md" not in listed
    assert "CHANGELOG.md" not in listed


def test_nothing_under_tests_is_excluded() -> None:
    """The tree itself had to be in scope: 43 files inside it named the path, and some of those were
    imports rather than comments, so excluding them would have moved the files and left them importing a
    tree that is no longer there. Stated as a rule rather than by looking for the old path, which stops
    existing the moment the move runs."""
    assert not any(prefix.startswith("tests") for prefix in move_test_tree.HISTORICAL)

    listed = {move_test_tree.named(path) for path in move_test_tree.tracked()}
    assert any(name.startswith("tests/") for name in listed)


def test_a_file_with_nothing_to_change_is_not_rewritten(tmp_path: Path) -> None:
    quiet = tmp_path / "quiet.yml"
    _ = quiet.write_text("name: x\n", encoding="utf-8")

    totals, skipped = move_test_tree.run([quiet], write=True)

    assert skipped == ()
    assert "files changed" not in totals
    assert quiet.read_text(encoding="utf-8") == "name: x\n"


def test_a_dry_run_changes_nothing_on_disk(tmp_path: Path) -> None:
    source = tmp_path / "ci.yml"
    _ = source.write_text("path: tests/test_litellm\n", encoding="utf-8")

    totals, _skipped = move_test_tree.run([source], write=False)

    assert totals["files changed"] == 1
    assert source.read_text(encoding="utf-8") == "path: tests/test_litellm\n"


def test_a_file_that_is_not_text_is_reported_rather_than_failing(tmp_path: Path) -> None:
    """The tree holds images, fonts and recorded cassettes. Reading one as UTF-8 raises, and the move
    must not stop because of a logo."""
    binary = tmp_path / "logo.jpg"
    _ = binary.write_bytes(b"\xff\xd8\xff\xe0\x9d\x00")

    totals, skipped = move_test_tree.run([binary], write=True)

    assert skipped and skipped[0].endswith("logo.jpg")
    assert "files changed" not in totals
