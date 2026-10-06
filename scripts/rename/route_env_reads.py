"""Route every read of a renamed environment variable through `compat.env`.

Phase 7 says the new name is read first and the old one still works, and the plan asks for one helper
rather than a fallback written out at each call site. This points the 101 reads at it and asks for the
new name: `os.getenv("LITELLM_SALT_KEY")` becomes `compat.env("TOKEN_IQ_SALT_KEY")`.

    python scripts/rename/route_env_reads.py --dry-run
    python scripts/rename/route_env_reads.py --apply

Only a read whose name is written out as a literal moves. A read through a variable cannot be rewritten
without knowing what the variable holds, and there are none of those for these names, so the audit says
so rather than the pass guessing.

`os.environ["X"]` is left for a person. It raises when the variable is absent and the helper returns a
default, so swapping one for the other changes what happens on a missing variable, which is a decision
about that call site rather than a rename. There is one of them.
"""

from __future__ import annotations

import argparse
import ast
import io
import pathlib
import subprocess
import sys
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from pydantic import BaseModel

REPO: Final = pathlib.Path(__file__).resolve().parents[2]
OLD_PREFIX: Final = "LITELLM_"
NEW_PREFIX: Final = "TOKEN_IQ_"
IMPORT: Final = "from token_iq.gateway import compat"

READERS: Final[frozenset[str]] = frozenset({"os.getenv", "getenv", "os.environ.get", "environ.get"})
"""The ways the engine reads an environment variable by name."""

SECRET_READERS: Final[frozenset[str]] = frozenset({"get_secret", "get_secret_str", "get_secret_bool"})
"""Reads that go through the secret-manager layer, which falls back to the environment when none is
configured. Only the name they ask for changes here: the fallback belongs inside that layer, so one edit
there covers every caller, and these keep returning the type their caller expects."""

SKIP: Final[tuple[str, ...]] = (
    "tests/",
    "docs/",
    "cookbook/",
    "scripts/",
    "token_iq/gateway/compat.py",
    # Installed as its own distribution, so importing the engine from it would be a dependency
    # that does not hold where it runs. Phase 8 renames that package and its variables together.
    "litellm-proxy-extras/",
)
"""Tests set the environment themselves and say which spelling they mean. The compat module is the one
place the old name belongs."""


class Options(BaseModel):
    apply: bool = False
    dry_run: bool = False
    audit: bool = False


@dataclass(frozen=True, slots=True)
class Edit:
    """One read to repoint, addressed the way Python numbers its source."""

    line: int
    start: int
    end: int
    old: str
    new: str


def tracked() -> tuple[pathlib.Path, ...]:
    out: Final = subprocess.run(
        ["git", "ls-files", "*.py"], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout
    return tuple(REPO / line for line in out.splitlines() if line and not any(line.startswith(skip) for skip in SKIP))


def dotted(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{dotted(node.value)}.{node.attr}"
    return ""


def reads(tree: ast.Module) -> tuple[ast.Call, ...]:
    """Every call that reads one of the renamed variables by a name written out in full."""
    return tuple(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and dotted(node.func) in READERS | SECRET_READERS
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
        and node.args[0].value.startswith(OLD_PREFIX)
    )


def edits(tree: ast.Module, text: str) -> tuple[Edit, ...]:
    """Where to write `compat.env` and the new name, for one module.

    Two spans per read: the function being called, and the name it is called with. Both are found in the
    line rather than assumed, because `os.getenv` and `os.environ.get` are different lengths and a call
    can be written across lines.
    """
    lines: Final = text.split("\n")

    def span(node: ast.AST, needle: str, *, after: int) -> Edit | None:
        line: Final = getattr(node, "lineno", None)
        if not isinstance(line, int) or line - 1 >= len(lines):
            return None
        raw: Final = lines[line - 1].encode("utf-8")
        found: Final = raw.find(needle.encode("utf-8"), after)
        if found < 0:
            return None
        new: Final = (
            "compat.env"
            if needle in READERS
            else needle
            if needle in SECRET_READERS
            else f"{NEW_PREFIX}{needle[len(OLD_PREFIX) :]}"
        )
        return Edit(line=line, start=found, end=found + len(needle.encode("utf-8")), old=needle, new=new)

    found: list[Edit | None] = []  # rebind-ok: gathered while walking the calls
    for call in reads(tree):
        name = call.args[0]  # rebind-ok: one argument per call in the loop
        assert isinstance(name, ast.Constant) and isinstance(name.value, str)
        # A secret read keeps its own function: only the name it asks for changes.
        if dotted(call.func) in READERS:
            found.append(span(call.func, dotted(call.func), after=call.func.col_offset))
        found.append(span(name, name.value, after=getattr(name, "col_offset", 0)))
    return tuple(edit for edit in found if edit is not None)


def with_import(text: str, first_use: int) -> str:
    """Add the import, after the last top-level import that comes before the first use.

    Not after the last import in the file. `__init__.py` reads one of these variables on line 26 and
    goes on importing until line 1470, so putting it at the end left the name undefined where it was
    wanted and the package would not import at all.

    When nothing is imported before that point it goes above the first use, after any `__future__`
    import, which has to stay first.
    """
    if IMPORT in text:
        return text
    try:
        tree: Final = ast.parse(text)
    except SyntaxError:
        return text
    before: Final = [
        node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom)) and node.lineno < first_use
    ]
    future: Final = [node for node in tree.body if isinstance(node, ast.ImportFrom) and node.module == "__future__"]
    # Next to the module own first-party imports when it has any, so the block stays in the order
    # isort wants and nothing else has to move. Reordering an existing block is what must not happen
    # here: these modules import each other and more than one relies on the order it already has, so
    # sorting them produced a circular import and the package stopped importing at all.
    siblings: Final = [
        node for node in before if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("token_iq")
    ]
    after: Final = (
        min(node.lineno for node in siblings) - 1
        if siblings
        else max(node.end_lineno or node.lineno for node in before)
        if before
        else max((node.end_lineno or node.lineno for node in future), default=first_use - 1)
    )
    lines = text.split(chr(10))  # rebind-ok: the accumulator of the insert
    return chr(10).join(lines[:after] + [IMPORT] + lines[after:])


def rewrite(text: str) -> tuple[str, Mapping[str, int]]:
    """Repoint every literal read in one module, and add the import if anything changed."""
    try:
        tree: Final = ast.parse(text)
    except SyntaxError:
        return text, MappingProxyType({})

    found: Final = sorted(edits(tree, text), key=lambda edit: (edit.line, edit.start), reverse=True)
    if not found:
        return text, MappingProxyType({})

    lines = text.split("\n")  # rebind-ok: edited back to front, so offsets hold
    counts: Counter[str] = Counter()  # rebind-ok: a tally of what was written
    for edit in found:
        raw = lines[edit.line - 1].encode("utf-8")
        if raw[edit.start : edit.end].decode("utf-8") != edit.old:
            continue
        lines[edit.line - 1] = raw[: edit.start].decode("utf-8") + edit.new + raw[edit.end :].decode("utf-8")
        counts["name" if edit.old.startswith(OLD_PREFIX) else "reader"] += 1
    first_use: Final = min(edit.line for edit in found)
    return with_import(chr(10).join(lines), first_use), MappingProxyType(dict(counts))


def unreachable(paths: Iterable[pathlib.Path]) -> tuple[str, ...]:
    """Reads this pass cannot repoint, with where each one is.

    A subscript raises on a missing variable where the helper returns a default, so swapping one for the
    other is a decision about that call site. A read through a variable cannot be rewritten at all.
    """
    found: list[str] = []  # rebind-ok: gathered while walking
    for path in paths:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, OSError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Subscript) and dotted(node.value) in ("os.environ", "environ"):
                index = node.slice
                if (
                    isinstance(index, ast.Constant)
                    and isinstance(index.value, str)
                    and index.value.startswith(OLD_PREFIX)
                ):
                    found.append(f"{named(path)}:{node.lineno}  os.environ[{index.value!r}]")
            if (
                isinstance(node, ast.Call)
                and dotted(node.func) in READERS
                and node.args
                and not isinstance(node.args[0], ast.Constant)
            ):
                found.append(f"{named(path)}:{node.lineno}  read through a variable")
    return tuple(found)


def named(path: pathlib.Path) -> str:
    return path.relative_to(REPO).as_posix() if path.is_relative_to(REPO) else path.as_posix()


def parses(text: str) -> bool:
    try:
        _ = ast.parse(text)
    except SyntaxError:
        return False
    return True


Rewriter = Callable[[str], tuple[str, Mapping[str, int]]]


def run(
    paths: Iterable[pathlib.Path], *, write: bool, rewriter: Rewriter = rewrite
) -> tuple[Counter[str], tuple[str, ...]]:
    totals: Counter[str] = Counter()  # rebind-ok: a tally across files
    broken: list[str] = []  # rebind-ok: files a rewrite would leave unparseable
    for path in paths:
        before = path.read_text(encoding="utf-8")
        after, counts = rewriter(before)
        if after == before:
            continue
        if parses(before) and not parses(after):
            broken.append(named(path))
            continue
        totals.update(counts)
        totals["files changed"] += 1
        if write:
            _ = path.write_text(after, encoding="utf-8", newline="")
    return totals, tuple(broken)


def _print_utf8() -> None:
    stream: Final = sys.stdout
    if isinstance(stream, io.TextIOWrapper):
        stream.reconfigure(encoding="utf-8", errors="replace")


def main(argv: Sequence[str] | None = None) -> int:
    parser: Final = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--apply", action="store_true", help="write the rewrites")
    _ = parser.add_argument("--dry-run", action="store_true", help="report and change nothing")
    _ = parser.add_argument("--audit", action="store_true", help="list reads this pass cannot repoint")
    options: Final = Options.model_validate(vars(parser.parse_args(argv)))
    _print_utf8()
    if sum((options.apply, options.dry_run, options.audit)) != 1:
        sys.stderr.write("pass exactly one of --apply, --dry-run and --audit\n")
        return 2

    paths: Final = tracked()
    if options.audit:
        remaining: Final = unreachable(paths)
        sys.stdout.write(f"{len(remaining)} read(s) this pass leaves for a person\n")
        sys.stdout.write("".join(f"  {line}\n" for line in remaining))
        return 0

    totals, broken = run(paths, write=options.apply)
    files: Final = totals.pop("files changed", 0)
    report: Final = (
        f"{totals['name']} read(s) repointed in {files} file(s)",
        *(f"{count:>7}  {kind}" for kind, count in totals.most_common()),
    )
    sys.stdout.write("\n".join(report) + "\n")
    if broken:
        sys.stderr.write(f"\n{len(broken)} file(s) would not parse after rewriting, left alone:\n")
        sys.stderr.write("\n".join(f"  {name}" for name in broken) + "\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
