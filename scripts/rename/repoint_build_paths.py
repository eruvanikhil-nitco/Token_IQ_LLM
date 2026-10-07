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

`--audit` lists the paths this pass declines. That mode exists because declining is silent, and three
stale entries hid behind it: `litellm_core_utils` became `core_utils` inside the engine, so
`litellm/litellm_core_utils/litellm_logging.py` does not exist under the new tree either, and the rule
above reads that as "leave it alone" rather than "this is broken". Each one was a config entry pointing
at nothing: a ruff suppression, a codecov component and a CI step. Run the audit after any pass that
renames inside the engine.
"""

from __future__ import annotations

import argparse
import functools
import io
import pathlib
import re
import subprocess
import sys
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from types import MappingProxyType
from typing import Final, Protocol

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
    audit: bool = False


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


IGNORE_FILES: Final[frozenset[str]] = frozenset({".gitignore", ".dockerignore"})
"""Where the rule below is inverted, because an ignore pattern names a file that is deliberately not
in the tree. Asking `there` about `litellm/proxy/application.log` always says no, so 32 entries stayed
pointing at the old tree and runtime junk under the new one stopped being ignored."""


def _holds(relative: str, *, exists: Exists = there) -> bool:
    """Whether the folder an ignore pattern sits in is there, which is as much as can be asked of it.

    `litellm/proxy/application.log` moves because `proxy` is there; `litellm/tests/langfuse.log` does not,
    because the fork has no such folder and the entry is upstream cruft for a human to delete.
    """
    folder: Final = _without_glob(relative).rsplit("/", 1)
    return len(folder) == 2 and exists(folder[0])


def question_for(name: str, exists: Exists = there) -> Exists:
    """Which question to ask of the paths in one file.

    An ignore file gets the folder question and everything else gets `exists`. One function because the
    rewrite and the audit have to agree: a path a run moves must not also be reported as declined.
    """
    return (lambda relative: _holds(relative, exists=exists)) if name in IGNORE_FILES else exists


def rewrite(text: str, *, exists: Exists = there) -> tuple[str, int]:
    """Rewrite each path that `exists` says points at something really there, and leave the rest."""
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


class Declined(BaseModel, frozen=True):
    """One old-name path the rewrite left alone, and where its file went if it went anywhere."""

    file: str
    line: int
    path: str
    moved_to: str


@functools.cache
def _by_basename() -> Mapping[str, tuple[str, ...]]:
    """Every file under the new tree grouped by basename, so a declined path can say where its file went."""
    found: Final = tuple(
        line
        for line in subprocess.run(
            ["git", "ls-files", f"{NEW}/"], cwd=REPO, capture_output=True, text=True, check=True
        ).stdout.splitlines()
        if line
    )
    return MappingProxyType(
        {
            base: tuple(name for name in found if name.rsplit("/", 1)[-1] == base)
            for base in {name.rsplit("/", 1)[-1] for name in found}
        }
    )


def _moved_to(relative: str) -> str:
    """Where the file this path names now lives, or why there is nothing to point at."""
    bare: Final = _without_glob(relative)
    if not bare:
        return "the engine root"
    candidates: Final = _by_basename().get(bare.rsplit("/", 1)[-1], ())
    if not candidates:
        return "nowhere: no file of that name is under the engine"
    return " or ".join(candidates[:3])


def _lines(path: pathlib.Path) -> tuple[str, ...]:
    try:
        return tuple(path.read_text(encoding="utf-8").splitlines())
    except (OSError, UnicodeDecodeError):
        return ()


def declined(paths: Iterable[pathlib.Path], *, exists: Exists = there) -> tuple[Declined, ...]:
    """Every old-name path the rewrite declines, with the file and line that holds it.

    Declining is right when the path names something the fork deleted and wrong when the file simply moved
    again, and the two look identical from inside `rewrite`. This is how a human tells them apart.
    """
    return tuple(
        Declined(file=named(path), line=number, path=match.group(0), moved_to=_moved_to(match.group(1)))
        for path in paths
        for number, line in enumerate(_lines(path), start=1)
        for match in PATH.finditer(line)
        if not question_for(named(path), exists)(_without_glob(match.group(1)))
    )


class Rewriter(Protocol):
    """What `run` calls per file. Spelled out rather than `Callable[..., ...]`, which accepted an injected
    rewriter of the wrong arity and turned a signature change into a runtime error in one test."""

    def __call__(self, text: str, *, exists: Exists) -> tuple[str, int]: ...


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
        after, counted = rewriter(before, exists=question_for(named(path)))
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
    _ = parser.add_argument("--audit", action="store_true", help="list the paths this pass declines")
    options: Final = Options.model_validate(vars(parser.parse_args(argv)))
    _print_utf8()
    if sum((options.apply, options.dry_run, options.audit)) != 1:
        sys.stderr.write("pass exactly one of --apply, --dry-run and --audit\n")
        return 2

    if options.audit:
        left: Final = declined(tracked())
        for one in left:
            sys.stdout.write(f"{one.file}:{one.line}  {one.path}\n        now at: {one.moved_to}\n")
        sys.stdout.write(f"\n{len(left)} declined path(s)\n")
        return 0

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
