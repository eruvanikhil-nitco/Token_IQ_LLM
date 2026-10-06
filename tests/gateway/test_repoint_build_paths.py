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
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MODULE_PATH = _REPO_ROOT / "scripts" / "rename" / "repoint_build_paths.py"
_spec = importlib.util.spec_from_file_location("repoint_build_paths", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
repoint_build_paths = importlib.util.module_from_spec(_spec)
sys.modules["repoint_build_paths"] = repoint_build_paths
_spec.loader.exec_module(repoint_build_paths)


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
        "COPY ui/litellm-dashboard/package.json ./",
        "COPY litellm-proxy-extras/pyproject.toml litellm-proxy-extras/",
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

    totals, _skipped = repoint_build_paths.run([source], write=False, rewriter=lambda text: rewrite_counted(text))

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
    assert repoint_build_paths._without_glob("router_strategy/complexity_router/artifacts/*.json") == (
        "router_strategy/complexity_router/artifacts"
    )
    assert repoint_build_paths._without_glob("proxy/_experimental/out/**") == "proxy/_experimental/out"
    assert repoint_build_paths._without_glob("proxy/schema.prisma") == "proxy/schema.prisma"
