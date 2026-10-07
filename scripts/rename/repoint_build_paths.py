"""Point everything that is not Python at the engine's new path.

The pass that moved the engine read `git ls-files "*.py"`, so it rewrote Python and nothing else. 93
other files still name `litellm/...`: the Dockerfile copies paths that no longer exist, every CI job
runs `prisma generate --schema litellm/proxy/schema.prisma`, `ruff.toml` and `.gitignore` filter on the
old tree, and the shell entrypoints invoke a script by source path. The image build and every job that
touches the database are broken until this runs.

    python scripts/rename/repoint_build_paths.py --dry-run
    python scripts/rename/repoint_build_paths.py --apply

A path is rewritten only when it points at something that is really there under the new tree, which is
the same question the Python pass asked: `litellm/a.py` in a fixture must not move, and
`litellm/proxy/schema.prisma` must. Three names that merely start with the old one are left alone, and
each is a different thing: `litellm-dashboard` is the UI and phase 9 renames it, `token-iq-migrations`
is the migrations package and phase 8 does, and `litellm-rust` is the crate.

The historical record is untouched, for the reason it always is: it says what was true when it was
written.
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
OLD: Final = "litellm"
NEW: Final = "token_iq/gateway"

HISTORICAL: Final[tuple[str, ...]] = (
    "docs/decisions/",
    "docs/plans/",
    "docs/specs/",
    "docs/status.md",
    "CHANGELOG.md",
    "docs/product/",
)

# A word character or a hyphen before the name means it is not the engine folder, which keeps
# litellm-dashboard, token-iq-migrations and litellm-rust out: the UI, the migrations package and the
# crate, each renamed by a different phase.
#
# A slash before it is allowed on purpose. /app/litellm/proxy in the Dockerfile and
# $REPO_ROOT/litellm/proxy in the entrypoint are the two that matter most, and excluding a leading
# slash to keep tests/litellm/fixture out would have excluded both. What separates them is whether the
# path is really there under the new tree, which is the question asked below.
PATH: Final = re.compile(rf"(?<![\w\-]){OLD}/([A-Za-z_*][\w./*-]*)")


class Options(BaseModel):
    apply: bool = False
    dry_run: bool = False


def tracked() -> tuple[pathlib.Path, ...]:
    out: Final = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True).stdout
    return tuple(
        REPO / line
        for line in out.splitlines()
        if line
        and not line.endswith(".py")
        and not any(line.startswith(prefix) for prefix in HISTORICAL)
        and line != "scripts/rename/repoint_build_paths.py"
    )


def there(relative: str, root: pathlib.Path | None = None) -> bool:
    """Whether the path exists under the new tree. `root` is a parameter so a test can build one."""
    return ((REPO / NEW if root is None else root) / relative).exists()


Exists = Callable[[str], bool]


def _without_glob(relative: str) -> str:
    """The part of a path before any glob, which is the part that can be asked about.

    Everything from the first star onwards goes, not just trailing stars: the wheel names
    `router_strategy/complexity_router/artifacts/*.json`, and asking whether that exists always says no,
    so the entry would have been left behind pointing at a tree that has moved.
    """
    return relative.split("*", 1)[0].rstrip("/")


def rewrite(text: str, *, exists: Exists = there) -> tuple[str, int]:
    """Rewrite each path that points at something really there, and leave the rest."""
    counted = 0  # rebind-ok: a tally of substitutions made during one pass

    def swap(match: re.Match[str]) -> str:
        nonlocal counted
        relative: Final = match.group(1)
        if not exists(_without_glob(relative)):
            return match.group(0)
        counted += 1
        return f"{NEW}/{relative}"

    return PATH.sub(swap, text), counted


def named(path: pathlib.Path) -> str:
    return path.relative_to(REPO).as_posix() if path.is_relative_to(REPO) else path.as_posix()


Rewriter = Callable[[str], tuple[str, int]]


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
        after, counted = rewriter(before)
        if after == before:
            continue
        totals[named(path)] = counted
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
    counts: Final[Mapping[str, int]] = MappingProxyType(dict(totals))
    report: Final = (
        f"{sum(counts.values())} path(s) in {files} file(s)",
        *(f"{count:>5}  {name}" for name, count in sorted(counts.items(), key=lambda item: -item[1])[:12]),
    )
    sys.stdout.write("\n".join(report) + "\n")
    if skipped:
        sys.stdout.write(f"{len(skipped)} file(s) are not text and were not read\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
