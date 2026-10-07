"""Rename the migrations package: `litellm-proxy-extras` becomes `token-iq-migrations`.

Phase 8's other half. The distribution, the Python package inside it and every reference to either move.
The directories are moved with `git mv` so the history follows them; this rewrites the names in the files.

    python scripts/rename/rename_migrations_package.py --audit
    python scripts/rename/rename_migrations_package.py --dry-run
    python scripts/rename/rename_migrations_package.py --apply

Two things stay, and both matter.

The 178 directories under `migrations/` keep their names. Prisma records which migrations it has applied
by directory name in `_prisma_migrations`, so renaming one makes it look unapplied and the next boot tries
to run it again against a schema that already has it.

`dist/` keeps its names too. Those are 179 wheels and tarballs of versions already published, and a
published artifact is not something a rename can reach. They are why a plain count of files naming the old
package says 188 when the work is nine.
"""

from __future__ import annotations

import argparse
import io
import pathlib
import subprocess
import sys
from collections import Counter
from collections.abc import Iterable, Sequence
from typing import Final

from pydantic import BaseModel

REPO: Final = pathlib.Path(__file__).resolve().parents[2]

NAMES: Final[tuple[tuple[str, str], ...]] = (
    ("litellm_proxy_extras", "token_iq_migrations"),
    ("litellm-proxy-extras", "token-iq-migrations"),
)
"""The Python package and the distribution. Longest first is not needed: neither contains the other."""

SKIP: Final[tuple[str, ...]] = (
    # Wheels and tarballs of versions already on an index. A rename cannot reach a published artifact, and
    # rewriting the bytes of one would only corrupt it.
    "token-iq-migrations/dist/",
    "litellm-proxy-extras/dist/",
    # The record of how this happened keeps the old names, per docs/decisions/0023-remove-litellm-names.md.
    "docs/decisions/",
    "docs/plans/",
    "docs/specs/",
    "docs/status.md",
    "CHANGELOG.md",
)

ITS_OWN_FILES: Final[frozenset[str]] = frozenset(
    {
        "scripts/rename/rename_migrations_package.py",
        "tests/gateway/test_rename_migrations_package.py",
    }
)
"""Only this pass and its tests. The earlier passes name the package in their skip lists, and leaving those
pointing at a directory that no longer exists would quietly widen their scope, so they are in."""


class Options(BaseModel):
    """The command line, typed. `parse_args` hands back `Any` for every flag."""

    apply: bool = False
    dry_run: bool = False
    audit: bool = False


def tracked() -> tuple[pathlib.Path, ...]:
    listed: Final = subprocess.run(
        ("git", "ls-files"), cwd=REPO, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    return tuple(REPO / name for name in listed if name and not name.startswith(SKIP) and name not in ITS_OWN_FILES)


def named(path: pathlib.Path) -> str:
    try:
        return path.relative_to(REPO).as_posix()
    except ValueError:
        return path.name


def rewrite(text: str) -> tuple[str, int]:
    """The text with both names moved on, and how many moved."""
    moved = 0  # rebind-ok: a tally for the return value
    rewritten = text  # rebind-ok: one replacement per name
    for old, new in NAMES:
        moved += rewritten.count(old)
        rewritten = rewritten.replace(old, new)
    return rewritten, moved


def run(paths: Iterable[pathlib.Path], *, write: bool) -> Counter[str]:
    """Every file rewritten, with a tally per file."""
    totals: Counter[str] = Counter()  # rebind-ok: a tally across files
    for path in paths:
        try:
            before = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        after, moved = rewrite(before)
        if not moved:
            continue
        totals[named(path)] = moved
        if write:
            _ = path.write_text(after, encoding="utf-8")
    return totals


def left_behind(paths: Iterable[pathlib.Path]) -> Counter[str]:
    """What still names the old package after a run, which should be nothing in scope."""
    return run(paths, write=False)


def main(argv: Sequence[str] | None = None, out: io.TextIOBase | None = None) -> int:
    parser: Final = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--apply", action="store_true", help="write the changes")
    _ = parser.add_argument("--dry-run", action="store_true", help="say what would change")
    _ = parser.add_argument("--audit", action="store_true", help="list what is out of scope and why")
    options: Final = Options.model_validate(vars(parser.parse_args(argv)))
    say: Final = out or sys.stdout

    if sum((options.apply, options.dry_run, options.audit)) != 1:
        print("pass exactly one of --apply, --dry-run and --audit", file=say)
        return 2

    if options.audit:
        listed: Final = subprocess.run(
            ("git", "ls-files"), cwd=REPO, capture_output=True, text=True, check=True
        ).stdout.splitlines()
        out_of_scope: Final = Counter(
            next((reason for reason in SKIP if name.startswith(reason)), "")
            for name in listed
            if name.startswith(SKIP) and any(old in name for old, _new in NAMES)
        )
        for reason, count in out_of_scope.most_common():
            print(f"{count:>5}  file(s) under {reason}", file=say)
        print("\nnothing under those is renamed: see this file's docstring for why", file=say)
        return 0

    totals: Final = run(tracked(), write=options.apply)
    for name, count in sorted(totals.items()):
        print(f"{count:>5}  {name}", file=say)
    print(f"\n{sum(totals.values())} mention(s) in {len(totals)} file(s)", file=say)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
