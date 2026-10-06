"""Move the engine's test tree to `tests/gateway/`, and point everything that names it at the new path.

Phase 6 asks for `tests/test_litellm/` to become `tests/gateway/`, mirroring `token_iq/gateway/`, with
the CI shards, the coverage roots and the path-keyed budget files following it. The tree is 1,887 files
and 53 other files name the path, so the move is `git mv` and the rest is this.

    python scripts/rename/move_test_tree.py --dry-run
    python scripts/rename/move_test_tree.py --apply
    git mv tests/test_litellm tests/gateway
    git mv tests/gateway/litellm_core_utils tests/gateway/core_utils

The inner directory moves too, because the mirror is the point: the engine's `litellm_core_utils` became
`core_utils` when the package moved, and a mirror that does not mirror is worse than no convention.

The historical record is deliberately left alone. `docs/decisions/`, `docs/plans/`, `docs/specs/` and
`docs/status.md` say what was true when they were written, and rewriting a path in them would make them
describe a layout that never existed. The same goes for the product blueprint, which is a snapshot.
"""

from __future__ import annotations

import argparse
import io
import pathlib
import re
import subprocess
import sys
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from types import MappingProxyType
from typing import Final

from pydantic import BaseModel

REPO: Final = pathlib.Path(__file__).resolve().parents[2]

MOVES: Final[Mapping[str, str]] = MappingProxyType(
    {
        # Ordered longest first, so the inner directory is rewritten before the outer one reaches it.
        "tests/test_litellm/litellm_core_utils": "tests/gateway/core_utils",
        "tests.test_litellm.litellm_core_utils": "tests.gateway.core_utils",
        "tests/test_litellm": "tests/gateway",
        "tests.test_litellm": "tests.gateway",
    }
)

HISTORICAL: Final[tuple[str, ...]] = (
    # Each of these says what was true when it was written. Rewriting a path in one makes it describe a
    # layout that never existed, which is worse than it naming an old one.
    "docs/decisions/",
    "docs/plans/",
    "docs/specs/",
    "docs/status.md",
    "docs/product/token-iq-product-blueprint.html",
    "CHANGELOG.md",
)


class Options(BaseModel):
    apply: bool = False
    dry_run: bool = False


def tracked() -> tuple[pathlib.Path, ...]:
    out: Final = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True).stdout
    # The tree itself is included. 43 files inside it name the path, and some of those are imports
    # rather than comments: excluding them would move the files and leave them importing a tree that is
    # no longer there.
    return tuple(
        REPO / line for line in out.splitlines() if line and not any(line.startswith(prefix) for prefix in HISTORICAL)
    )


def named(path: pathlib.Path) -> str:
    return path.relative_to(REPO).as_posix() if path.is_relative_to(REPO) else path.as_posix()


def rewrite(text: str) -> tuple[str, Mapping[str, int]]:
    """Each path, longest first, so the inner directory is not swallowed by the outer one."""
    counts: dict[str, int] = {}  # rebind-ok: a tally built while folding the moves over the text
    current = text  # rebind-ok: the fold's accumulator
    for old, new in MOVES.items():
        # A word boundary at the end, so `tests/test_litellm_extra` is not rewritten into a path that
        # does not exist. Nothing is named that today, and a rule that would get it wrong is worse.
        current, fired = re.subn(rf"{re.escape(old)}(?![\w])", new, current)
        if fired:
            counts[old] = fired
    return current, MappingProxyType(counts)


Rewriter = Callable[[str], tuple[str, Mapping[str, int]]]


def run(
    paths: Iterable[pathlib.Path], *, write: bool, rewriter: Rewriter = rewrite
) -> tuple[Counter[str], tuple[str, ...]]:
    totals: Counter[str] = Counter()  # rebind-ok: a tally across files
    skipped: list[str] = []  # rebind-ok: files that are not text
    for path in paths:
        try:
            before = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            skipped.append(named(path))
            continue
        after, counts = rewriter(before)
        if after == before:
            continue
        totals.update(counts)
        totals["files changed"] += 1
        if write:
            _ = path.write_text(after, encoding="utf-8", newline="")
    return totals, tuple(skipped)


def _print_utf8() -> None:
    stream: Final = sys.stdout
    if isinstance(stream, io.TextIOWrapper):
        stream.reconfigure(encoding="utf-8", errors="replace")


def main(argv: Sequence[str] | None = None) -> int:
    parser: Final = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--apply", action="store_true", help="write the rewrites")
    _ = parser.add_argument("--dry-run", action="store_true", help="report and change nothing")
    options: Final = Options.model_validate(vars(parser.parse_args(argv)))
    _print_utf8()
    if options.apply == options.dry_run:
        sys.stderr.write("pass exactly one of --apply and --dry-run\n")
        return 2

    totals, skipped = run(tracked(), write=options.apply)
    files: Final = totals.pop("files changed", 0)
    report: Final = (
        f"{sum(totals.values())} reference(s) in {files} file(s)",
        *(f"{count:>7}  {name}" for name, count in totals.most_common()),
    )
    sys.stdout.write("\n".join(report) + "\n")
    if skipped:
        sys.stdout.write(f"{len(skipped)} file(s) are not text and were not read\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
