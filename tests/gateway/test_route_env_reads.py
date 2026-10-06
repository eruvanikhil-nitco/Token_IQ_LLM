"""Tests for scripts/rename/route_env_reads.py.

What this pass changes is where 100 reads go and which name they ask for. Getting it wrong is quiet: the
proxy starts, reads nothing, and behaves as though the operator had never set the variable.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MODULE_PATH = _REPO_ROOT / "scripts" / "rename" / "route_env_reads.py"
_spec = importlib.util.spec_from_file_location("route_env_reads", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
route_env_reads = importlib.util.module_from_spec(_spec)
sys.modules["route_env_reads"] = route_env_reads
_spec.loader.exec_module(route_env_reads)

IMPORT = "from token_iq.gateway import compat"


def rewrite(text: str) -> str:
    found, _ = route_env_reads.rewrite(text)
    return found


def body(text: str) -> str:
    """The rewritten module without the import line, so a case can state one thing."""
    return "\n".join(line for line in rewrite(text).split("\n") if line != IMPORT)


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ('os.getenv("LITELLM_SALT_KEY")', 'compat.env("TOKEN_IQ_SALT_KEY")'),
        ('os.getenv("LITELLM_SALT_KEY", None)', 'compat.env("TOKEN_IQ_SALT_KEY", None)'),
        ('os.getenv("LITELLM_MODE", "production")', 'compat.env("TOKEN_IQ_MODE", "production")'),
        ('os.environ.get("LITELLM_LOG")', 'compat.env("TOKEN_IQ_LOG")'),
        ('getenv("LITELLM_LOG")', 'compat.env("TOKEN_IQ_LOG")'),
    ],
)
def test_each_way_of_reading_is_repointed(before: str, after: str) -> None:
    assert body(f"import os\n{before}\n").endswith(f"{after}\n")


def test_both_the_reader_and_the_name_change() -> None:
    """Changing one without the other is the failure that matters: `compat.env("LITELLM_SALT_KEY")` reads
    nothing, because the helper only knows how to fall back from the new spelling to the old."""
    found = body('import os\nkey = os.environ.get("LITELLM_SALT_KEY", None)\n')

    assert "compat.env" in found
    assert "TOKEN_IQ_SALT_KEY" in found
    assert "LITELLM_SALT_KEY" not in found
    assert "os.environ.get" not in found


def test_a_variable_that_was_never_renamed_is_left_alone() -> None:
    assert body('import os\nx = os.getenv("AWS_REGION_NAME")\n') == 'import os\nx = os.getenv("AWS_REGION_NAME")\n'


def test_a_read_through_a_variable_is_left_alone() -> None:
    """It cannot be rewritten without knowing what the variable holds. The audit names these instead."""
    before = "import os\nx = os.getenv(secret_name)\n"
    assert body(before) == before


def test_a_subscript_is_left_for_a_person() -> None:
    """It raises when the variable is absent where the helper returns a default, so swapping one for the
    other changes what happens on a missing variable. That is a decision about the call site."""
    before = 'import os\nx = os.environ["LITELLM_MODE"]\n'
    assert body(before) == before


def test_the_import_is_added_once() -> None:
    found = rewrite('import os\na = os.getenv("LITELLM_LOG")\nb = os.getenv("LITELLM_MODE")\n')

    assert found.count(IMPORT) == 1


def test_the_import_lands_after_the_ones_already_there() -> None:
    """Among the other absolute imports, so the formatter has nothing to move."""
    found = rewrite('import os\nimport sys\n\nx = os.getenv("LITELLM_LOG")\n')
    lines = found.split("\n")

    assert lines[:3] == ["import os", "import sys", IMPORT]


def test_a_module_with_nothing_to_change_gets_no_import() -> None:
    before = 'import os\nx = os.getenv("AWS_REGION_NAME")\n'
    assert IMPORT not in rewrite(before)


def test_an_import_already_there_is_not_added_again() -> None:
    before = f'import os\n{IMPORT}\nx = os.getenv("LITELLM_LOG")\n'

    assert rewrite(before).count(IMPORT) == 1


def test_two_reads_on_one_line_both_move() -> None:
    """Edited back to front, so the first edit does not shift the second one's offsets, and
    `os.environ.get` and `compat.env` are different lengths."""
    found = body('import os\nx = os.environ.get("LITELLM_LOG") or os.getenv("LITELLM_MODE")\n')

    assert found.endswith('x = compat.env("TOKEN_IQ_LOG") or compat.env("TOKEN_IQ_MODE")\n')


def test_a_read_spread_over_several_lines_is_repointed() -> None:
    before = 'import os\nx = os.getenv(\n    "LITELLM_SALT_KEY",\n    None,\n)\n'

    assert body(before) == 'import os\nx = compat.env(\n    "TOKEN_IQ_SALT_KEY",\n    None,\n)\n'


def test_a_non_ascii_character_earlier_on_the_line_does_not_shift_the_edit() -> None:
    """`col_offset` is a byte offset into the line's UTF-8."""
    before = 'import os\nx = log("café", os.getenv("LITELLM_LOG"))\n'

    assert body(before) == 'import os\nx = log("café", compat.env("TOKEN_IQ_LOG"))\n'


def test_a_file_that_does_not_parse_is_left_exactly_as_it_was() -> None:
    assert rewrite("def (\n") == "def (\n"


def test_the_compat_module_is_out_of_scope() -> None:
    """It is the one place the old name belongs, and pointing it at itself would be a cycle."""
    listed = {route_env_reads.named(path) for path in route_env_reads.tracked()}

    assert "token_iq/gateway/compat.py" not in listed
    assert "token_iq/gateway/constants.py" in listed, "the filter is too wide"


def test_tests_are_out_of_scope() -> None:
    """A test sets the environment itself and says which spelling it means, so rewriting one would
    change what it is testing."""
    listed = {route_env_reads.named(path) for path in route_env_reads.tracked()}

    assert not any(name.startswith("tests/") for name in listed)


def test_a_dry_run_changes_nothing_on_disk(tmp_path: Path) -> None:
    source = tmp_path / "mod.py"
    _ = source.write_text('import os\nx = os.getenv("LITELLM_LOG")\n', encoding="utf-8")

    totals, _broken = route_env_reads.run([source], write=False)

    assert totals["files changed"] == 1
    assert source.read_text(encoding="utf-8") == 'import os\nx = os.getenv("LITELLM_LOG")\n'


def test_a_rewrite_that_would_not_parse_leaves_the_file_as_it_was(tmp_path: Path) -> None:
    source = tmp_path / "mod.py"
    _ = source.write_text('import os\nx = os.getenv("LITELLM_LOG")\n', encoding="utf-8")

    def destructive(text: str) -> tuple[str, dict[str, int]]:
        return "def (", {"broken on purpose": 1}

    totals, broken = route_env_reads.run([source], write=True, rewriter=destructive)

    assert broken and broken[0].endswith("mod.py")
    assert "files changed" not in totals
    assert source.read_text(encoding="utf-8") == 'import os\nx = os.getenv("LITELLM_LOG")\n'


def test_the_import_lands_before_the_first_use_not_after_the_last_import() -> None:
    """`__init__.py` reads one of these variables on line 26 and goes on importing until line 1470.
    Putting the import after the last one in the file left the name undefined where it was wanted, and
    the package would not import at all."""
    before = 'import os\n\nx = os.getenv("LITELLM_MODE")\n\nimport json\n'

    found = rewrite(before).split("\n")

    assert found.index(IMPORT) < found.index('x = compat.env("TOKEN_IQ_MODE")')


def test_the_future_import_stays_first() -> None:
    """It has to be the first statement after the docstring, so the compat import goes under it."""
    before = 'from __future__ import annotations\n\nx = os.getenv("LITELLM_MODE")\n'

    found = rewrite(before).split("\n")

    assert found[0] == "from __future__ import annotations"
    assert found.index(IMPORT) < found.index('x = compat.env("TOKEN_IQ_MODE")')


def test_a_use_before_any_import_gets_the_import_above_it() -> None:
    before = 'x = os.getenv("LITELLM_MODE")\nimport json\n'

    found = rewrite(before).split("\n")

    assert found.index(IMPORT) < found.index('x = compat.env("TOKEN_IQ_MODE")')
