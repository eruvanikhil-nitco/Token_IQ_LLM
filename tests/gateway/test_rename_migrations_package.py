"""Tests for scripts/rename/rename_migrations_package.py.

Two things must not move, and both fail in ways that are hard to see from the diff.

Prisma records which migrations it has applied by directory name in `_prisma_migrations`. A renamed
directory looks unapplied, so the next boot runs it again against a schema that already has it, and the
proxy does that before it serves traffic.

`dist/` holds wheels and tarballs of versions already published. Rewriting bytes inside one corrupts an
artifact that a rename cannot reach anyway.
"""

import importlib.util
import re
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MODULE_PATH = _REPO_ROOT / "scripts" / "rename" / "rename_migrations_package.py"
_spec = importlib.util.spec_from_file_location("rename_migrations_package", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
rename_migrations_package = importlib.util.module_from_spec(_spec)
sys.modules["rename_migrations_package"] = rename_migrations_package
_spec.loader.exec_module(rename_migrations_package)

MIGRATIONS = _REPO_ROOT / "token-iq-migrations" / "token_iq_migrations" / "migrations"


def moved(text: str) -> str:
    found, _count = rename_migrations_package.rewrite(text)
    return found


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ("import token_iq_migrations", "import token_iq_migrations"),
        ("import litellm_proxy_extras", "import token_iq_migrations"),
        ('"litellm-proxy-extras==0.4.92"', '"token-iq-migrations==0.4.92"'),
        ("COPY litellm-proxy-extras/pyproject.toml", "COPY token-iq-migrations/pyproject.toml"),
        ("from litellm_proxy_extras.utils import x", "from token_iq_migrations.utils import x"),
    ],
)
def test_both_names_move(before: str, after: str) -> None:
    assert moved(before) == after


def test_a_name_that_merely_contains_litellm_is_left_alone() -> None:
    assert moved("litellm_params = {}") == "litellm_params = {}"


# --- what the rename must not reach ----------------------------------------------------------------


def test_the_published_artifacts_are_out_of_scope() -> None:
    """179 wheels and tarballs of versions already on an index. A rename cannot reach a published artifact,
    and rewriting bytes inside one only corrupts it."""
    listed = {rename_migrations_package.named(path) for path in rename_migrations_package.tracked()}

    assert not any(name.startswith("token-iq-migrations/dist/") for name in listed)
    assert "token-iq-migrations/pyproject.toml" in listed, "the filter is too wide"


def test_the_records_that_keep_the_old_name_are_out_of_scope() -> None:
    listed = {rename_migrations_package.named(path) for path in rename_migrations_package.tracked()}

    assert "docs/status.md" not in listed
    assert "CHANGELOG.md" not in listed


def test_only_this_pass_and_its_tests_exclude_themselves() -> None:
    """The earlier passes name the package in their skip lists, and leaving one pointing at a directory
    that no longer exists would quietly widen its scope, so they are in."""
    listed = {rename_migrations_package.named(path) for path in rename_migrations_package.tracked()}

    assert "scripts/rename/rename_migrations_package.py" not in listed
    assert "tests/gateway/test_rename_migrations_package.py" not in listed
    assert "scripts/rename/route_env_reads.py" in listed


# --- the state of the repository after the run ------------------------------------------------------


def test_nothing_in_scope_still_names_the_old_package() -> None:
    """Which is also the check that the run finished rather than merely ran."""
    left = rename_migrations_package.left_behind(rename_migrations_package.tracked())

    assert dict(left) == {}


def test_the_migration_directories_keep_their_names() -> None:
    """Prisma tracks an applied migration by directory name. Rename one and the next boot runs it again
    against a schema that already has it, before the proxy serves anything.

    Asserted against Prisma's own naming rather than against git history, so this keeps meaning something
    after the rename is committed: a directory the pass had touched would carry the package name or lose
    the timestamp Prisma writes.
    """
    names = sorted(path.name for path in MIGRATIONS.iterdir() if path.is_dir())

    assert len(names) == 177
    assert (MIGRATIONS / "migration_lock.toml").exists()
    # 14 digits is what `prisma migrate dev` writes; one of these was named by hand with 8.
    assert [name for name in names if not re.fullmatch(r"\d{8,14}_.+", name)] == []
    assert [name for name in names if "token_iq" in name or "token-iq" in name] == []


def test_no_migration_sql_was_rewritten() -> None:
    """The names inside them are real tables, which phase 8 step 1 deliberately leaves where they are."""
    sql = (MIGRATIONS / "20250326162113_baseline" / "migration.sql").read_text(encoding="utf-8")

    assert 'CREATE TABLE IF NOT EXISTS "LiteLLM_BudgetTable"' in sql
