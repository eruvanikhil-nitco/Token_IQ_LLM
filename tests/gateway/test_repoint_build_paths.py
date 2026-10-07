"""Tests for scripts/rename/repoint_build_paths.py.

The pass that moved the engine read `git ls-files "*.py"`, so everything that is not Python kept naming
the old path. That left the image build copying files that are not there and every CI job generating
Prisma from `litellm/proxy/schema.prisma`, which is the kind of break no Python check sees: the package
imports, the routes are all present, and the build fails.

Three names start with the old one and are each a different thing, so the rule has to leave them: the
dashboard, the migrations package and the Rust crate are renamed by three different phases.
"""

import importlib.util
import sys
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Final

import pytest
from pydantic import BaseModel

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MODULE_PATH = _REPO_ROOT / "scripts" / "rename" / "repoint_build_paths.py"
_spec = importlib.util.spec_from_file_location("repoint_build_paths", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
repoint_build_paths = importlib.util.module_from_spec(_spec)
sys.modules["repoint_build_paths"] = repoint_build_paths
_spec.loader.exec_module(repoint_build_paths)

# A module loaded from a path is `Any`, so every call through it reads as untyped. These name the three
# functions the tests below lean on most, once, instead of at each of the thirty call sites.
Exists = Callable[[str], bool]
rewrite_with: Final[Callable[..., tuple[str, int]]] = repoint_build_paths.rewrite
question_for: Final[Callable[[str, Exists], Exists]] = repoint_build_paths.question_for
holds: Final[Callable[..., bool]] = repoint_build_paths._holds
repo: Final[Path] = repoint_build_paths.REPO
ignore_files: Final[frozenset[str]] = repoint_build_paths.IGNORE_FILES
without_glob: Final[Callable[[str], str]] = repoint_build_paths._without_glob


class Declined(BaseModel, frozen=True):
    """What the audit reports, validated on the way in rather than read off an `Any`."""

    file: str
    line: int
    path: str
    moved_to: str


def declined(paths: Iterable[Path], *, exists: Exists | None = None) -> tuple[Declined, ...]:
    found: Final = (
        repoint_build_paths.declined(paths) if exists is None else repoint_build_paths.declined(paths, exists=exists)
    )
    return tuple(Declined.model_validate(one, from_attributes=True) for one in found)


def always(_relative: str) -> bool:
    return True


def never(_relative: str) -> bool:
    return False


def _only_proxy(folder: str) -> bool:
    return folder == "proxy"


def rewrite(text: str, *, exists: bool = True) -> str:
    found, _ = repoint_build_paths.rewrite(text, exists=lambda _relative: exists)
    return found


@pytest.mark.parametrize(
    ("before", "after"),
    [
        # Every CI job runs this one, so it is the break that matters most.
        (
            "prisma generate --schema litellm/proxy/schema.prisma",
            "prisma generate --schema token_iq/gateway/proxy/schema.prisma",
        ),
        # The image copies a path that is not there any more.
        (
            "COPY --from=builder /app/litellm/proxy/prisma_migration.py /app/",
            "COPY --from=builder /app/token_iq/gateway/proxy/prisma_migration.py /app/",
        ),
        (
            'MIGRATION_SCRIPT="$REPO_ROOT/litellm/proxy/prisma_migration.py"',
            'MIGRATION_SCRIPT="$REPO_ROOT/token_iq/gateway/proxy/prisma_migration.py"',
        ),
        ('  - "litellm/**"', '  - "token_iq/gateway/**"'),
        ("litellm/proxy/_experimental/out/", "token_iq/gateway/proxy/_experimental/out/"),
    ],
)
def test_a_path_that_moved_is_repointed(before: str, after: str) -> None:
    assert rewrite(before) == after


@pytest.mark.parametrize(
    "left_alone",
    [
        # Three different things, each renamed by a different phase: the dashboard is phase 9's, the
        # migrations package is phase 8's, and the crate keeps its name.
        "COPY ui/dashboard/package.json ./",
        "COPY token-iq-migrations/pyproject.toml token-iq-migrations/",
        'manifest-path = "litellm-rust/crates/python-bridge/Cargo.toml"',
        # Not a path into the engine at all.
        "image: ghcr.io/berriai/litellm:main-stable",
        'REDIS_KEY_PREFIX = "litellm:vcr:cassette:"',
    ],
)
def test_a_name_that_merely_starts_with_the_old_one_is_left_alone(left_alone: str) -> None:
    assert rewrite(left_alone) == left_alone


def test_a_path_to_something_that_is_not_there_is_left_alone() -> None:
    """The same question the Python pass asked. Fixtures name invented paths, and a rule that moved
    those would point them at somewhere that does not exist either."""
    assert rewrite("open('litellm/a.py')", exists=False) == "open('litellm/a.py')"


def test_a_glob_is_asked_about_its_directory() -> None:
    """`litellm/**` and `litellm/proxy/_experimental/out/**` are how the wheel and the workflows name a
    tree. Asking whether the literal string with the stars on it exists would always say no."""
    assert rewrite("  - 'litellm/**'") == "  - 'token_iq/gateway/**'"


def test_whether_a_path_is_there_is_answered_from_the_new_tree(tmp_path: Path) -> None:
    """The injected answer is what every rule above is tested against, so the real one needs its own
    case, asked about a tree built here rather than about the repository."""
    _ = (tmp_path / "proxy").mkdir()
    _ = (tmp_path / "proxy" / "schema.prisma").write_text("x", encoding="utf-8")

    assert repoint_build_paths.there("proxy/schema.prisma", tmp_path) is True
    assert repoint_build_paths.there("proxy/missing.prisma", tmp_path) is False


def test_python_is_out_of_scope_because_the_earlier_pass_did_it() -> None:
    listed = {repoint_build_paths.named(path) for path in repoint_build_paths.tracked()}

    assert not any(name.endswith(".py") for name in listed)
    assert "Dockerfile" in listed


def test_the_historical_record_is_not_touched() -> None:
    listed = {repoint_build_paths.named(path) for path in repoint_build_paths.tracked()}

    assert not any(name.startswith("docs/decisions/") for name in listed)
    assert "docs/status.md" not in listed


def test_a_file_that_is_not_text_is_reported_rather_than_failing(tmp_path: Path) -> None:
    binary = tmp_path / "logo.jpg"
    _ = binary.write_bytes(b"\xff\xd8\xff\xe0\x9d\x00")

    totals, skipped = repoint_build_paths.run([binary], write=True)

    assert skipped and skipped[0].endswith("logo.jpg")
    assert "files changed" not in totals


def test_a_dry_run_changes_nothing_on_disk(tmp_path: Path) -> None:
    source = tmp_path / "ci.yml"
    _ = source.write_text("schema: litellm/proxy/schema.prisma\n", encoding="utf-8")

    totals, _skipped = repoint_build_paths.run(
        [source], write=False, rewriter=lambda text, *, exists: rewrite_counted(text)
    )

    assert totals["files changed"] == 1
    assert source.read_text(encoding="utf-8") == "schema: litellm/proxy/schema.prisma\n"


def rewrite_counted(text: str) -> tuple[str, int]:
    return repoint_build_paths.rewrite(text, exists=lambda _relative: True)


def test_a_path_whose_name_merely_ends_in_the_old_one_is_left_alone() -> None:
    """`my-litellm/proxy` and `vendorlitellm/proxy` both contain `litellm/` without being it. The
    existence check would say yes to the tail, so the boundary is the only thing between them and a
    rewrite that points at the wrong tree."""
    assert rewrite("open('my-litellm/proxy/x.py')") == "open('my-litellm/proxy/x.py')"
    assert rewrite("open('vendorlitellm/proxy/x.py')") == "open('vendorlitellm/proxy/x.py')"


def test_a_glob_is_asked_about_the_directory_rather_than_the_stars() -> None:
    """`litellm/**` is how the wheel and the workflows name a tree. Asking whether a path with stars on
    the end exists always says no, so every one of those would be left behind."""
    asked: list[str] = []  # rebind-ok: a spy recording what was asked

    def only_the_directory(relative: str) -> bool:
        asked.append(relative)
        return relative == "proxy"

    found, counted = repoint_build_paths.rewrite("  - 'litellm/proxy/**'", exists=only_the_directory)

    assert found == "  - 'token_iq/gateway/proxy/**'"
    assert counted == 1
    assert "proxy" in asked, f"asked about {asked} rather than the directory"


def test_a_glob_in_the_middle_of_a_path_is_stripped_too() -> None:
    """The wheel names `router_strategy/complexity_router/artifacts/*.json`. Stripping only trailing
    stars leaves the `.json` on the end, so the question becomes whether a file with a star in its name
    exists, which is always no, and the entry stays pointing at a tree that has moved."""
    assert without_glob("router_strategy/complexity_router/artifacts/*.json") == (
        "router_strategy/complexity_router/artifacts"
    )
    assert without_glob("proxy/_experimental/out/**") == "proxy/_experimental/out"
    assert without_glob("proxy/schema.prisma") == "proxy/schema.prisma"


def test_an_ignore_pattern_moves_when_its_folder_is_there() -> None:
    """`.gitignore` names files that are deliberately not in the tree, so the existence check says no to
    every one of them and 32 entries stayed pointing at a folder phase 6 deleted. Runtime junk under the
    new tree then stopped being ignored, which is how a proxy run leaves `application.log` in git status."""
    found, counted = rewrite_with(
        "litellm/proxy/application.log\n",
        exists=question_for(".gitignore", _only_proxy),
    )

    assert found == "token_iq/gateway/proxy/application.log\n"
    assert counted == 1


def test_an_ignore_pattern_whose_folder_is_gone_is_left_for_a_human() -> None:
    """`litellm/tests/langfuse.log` is upstream cruft: the fork has no such folder, so there is nothing to
    point the entry at and inventing one would hide that it is dead."""
    assert rewrite_with(
        "litellm/tests/langfuse.log\n",
        exists=question_for(".gitignore", never),
    ) == ("litellm/tests/langfuse.log\n", 0)


def test_the_folder_question_is_asked_of_the_folder_and_not_the_file() -> None:
    asked: list[str] = []  # rebind-ok: a spy recording what was asked

    def spy(relative: str) -> bool:
        asked.append(relative)
        return True

    assert holds("proxy/db/migrations/*", exists=spy)
    assert asked == ["proxy/db"], f"asked about {asked}"


def test_a_pattern_with_no_folder_at_all_is_left_alone() -> None:
    """A bare `litellm/x` has no folder under the engine to ask about, and claiming the engine root exists
    would move every stray mention in an ignore file."""
    assert not holds("something", exists=always)


def test_the_ignore_rule_applies_to_the_ignore_files_and_nothing_else() -> None:
    """Inverting the question everywhere would rewrite `litellm/a.py` in a fixture, which the whole pass
    exists to avoid."""
    assert ignore_files == frozenset({".gitignore", ".dockerignore"})


def test_the_audit_lists_what_the_rewrite_declines(tmp_path: Path) -> None:
    """Declining is silent, and three stale config entries hid behind it: a ruff suppression, a codecov
    component and a CI step, each naming `litellm_core_utils` after it became `core_utils`."""
    source = tmp_path / "ruff.toml"
    _ = source.write_text('"litellm/litellm_core_utils/x.py" = ["F401"]\n', encoding="utf-8")

    left = declined((source,), exists=never)

    assert len(left) == 1
    assert left[0].path == "litellm/litellm_core_utils/x.py"
    assert left[0].line == 1


def test_the_audit_says_nothing_about_a_path_the_rewrite_would_move(tmp_path: Path) -> None:
    """Otherwise the list is every mention in the repo and a human stops reading it."""
    source = tmp_path / "ruff.toml"
    _ = source.write_text('"litellm/proxy/x.py" = ["F401"]\n', encoding="utf-8")

    assert declined((source,), exists=always) == ()


def test_an_ignore_file_is_asked_the_folder_question_and_others_are_not() -> None:
    """The rewrite and the audit both go through here, which is what keeps them agreeing: an entry a run
    moves must not also be reported as declined. Said against the rule rather than against the real
    `.gitignore`, which holds no old-name entry any more and so answers either way."""
    asked: list[str] = []  # rebind-ok: a spy recording what was asked

    def spy(relative: str) -> bool:
        asked.append(relative)
        return True

    assert question_for(".gitignore", spy)("proxy/application.log")
    assert asked == ["proxy"], f"an ignore file was asked about {asked}"

    assert question_for("ruff.toml", spy)("proxy/schema.prisma")
    assert asked == ["proxy", "proxy/schema.prisma"], f"ruff.toml was asked about {asked}"


def test_the_tree_this_fork_deleted_is_named_by_no_ignore_entry() -> None:
    """The regression. Every one of these was ignoring a path under a folder that is gone, so nothing they
    name could ever match and junk under the new tree was showing up in git status."""
    lines = (repo / ".gitignore").read_text(encoding="utf-8").splitlines()
    stale = tuple(line for line in lines if line.startswith(("litellm/", "tests/litellm/")))

    assert stale == (), f"these ignore a tree that no longer exists: {stale}"
