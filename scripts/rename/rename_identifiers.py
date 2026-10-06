"""Rename the 1,316 identifiers phase 6 owns, from the committed scope artifact.

Phase 6, third part. `docs/plans/phase-6-identifier-scope.csv` already decided which of the rename
map's identifiers are Python's own and which are a calling convention, a payload field, a price-file key
or a module; this pass reads that file and renames only the rows it marks `phase 6`. The decision is not
made here, so changing what gets renamed means changing an artifact a reviewer can read.

    python scripts/rename/rename_identifiers.py --dry-run
    python scripts/rename/rename_identifiers.py --apply
    python scripts/rename/rename_identifiers.py --audit    # names it could not reach

Renaming happens through the syntax tree, in every position a Python name can occupy: a reference, an
attribute, a class or function definition, a parameter, a keyword argument at a call site, an import
alias. A text pass would also hit the comments and strings that phases 7 to 9 own, and those outnumber
the identifiers: of the rows this pass does not touch, 383 appear in a `.py` file only inside a string.

A class is also renamed where it is written as a string, because a forward reference is resolved against
module globals and `"LiteLLMLoggingObj"` appears 172 times that way. A snake_case name is not, and the
scope artifact has already deferred every snake_case name that is written as a string at all, so there
is nothing left for that to get wrong.

Positions are addressed as UTF-8 bytes on lines split only at a newline, which is what Python's own line
and column numbers mean. `str.splitlines` invents breaks at U+2028, U+2029, a form feed and four more,
and `col_offset` is a byte offset; the first pass of phase 6 lost edits silently to both.
"""

from __future__ import annotations

import argparse
import ast
import csv
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
SCOPE: Final = REPO / "docs" / "plans" / "phase-6-identifier-scope.csv"

ITS_OWN_FILES: Final[frozenset[str]] = frozenset(
    {
        # A pass that rewrites its own source, or the files that say what it should do, turns the
        # question into the answer and then reports a clean run having matched nothing.
        "scripts/rename/rename_identifiers.py",
        "tests/gateway/test_rename_identifiers.py",
        "scripts/rename/scope_identifiers.py",
        "tests/gateway/test_scope_identifiers.py",
        "scripts/rename/build_rename_map.py",
        "tests/gateway/test_build_rename_map.py",
        "scripts/rename/move_engine_package.py",
        "tests/gateway/test_move_engine_package.py",
        "scripts/rename/rename_bound_name.py",
        "tests/gateway/test_rename_bound_name.py",
    }
)


class Options(BaseModel):
    apply: bool = False
    dry_run: bool = False
    audit: bool = False


@dataclass(frozen=True, slots=True)
class Span:
    """One name to replace, addressed the way Python numbers its source."""

    line: int
    start: int
    end: int
    old: str
    new: str


def renames() -> Mapping[str, str]:
    """What this phase renames, read from the artifact a reviewer signs off rather than decided here."""
    with SCOPE.open(encoding="utf-8") as handle:
        return MappingProxyType(
            {row["old"]: row["new"] for row in csv.DictReader(handle) if row["verdict"] == "phase 6"}
        )


def tracked() -> tuple[pathlib.Path, ...]:
    out: Final = subprocess.run(
        ["git", "ls-files", "*.py"], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout
    return tuple(REPO / line for line in out.splitlines() if line and line not in ITS_OWN_FILES)


def capwords(name: str) -> bool:
    stripped: Final = name.lstrip("_")
    return bool(stripped) and stripped[0].isupper()


def _span(node: ast.AST, old: str, new: str, *, start: int | None = None, end: int | None = None) -> Span | None:
    """A span only when the thing sits on one line, which is all this pass needs to edit."""
    line: Final = getattr(node, "lineno", None)
    end_line: Final = getattr(node, "end_lineno", None)
    first: Final = getattr(node, "col_offset", None) if start is None else start
    last: Final = getattr(node, "end_col_offset", None) if end is None else end
    if not all(isinstance(value, int) for value in (line, end_line, first, last)):
        return None
    assert isinstance(line, int) and isinstance(end_line, int) and isinstance(first, int) and isinstance(last, int)
    return Span(line=line, start=first, end=last, old=old, new=new) if line == end_line else None


def spans(tree: ast.Module, wanted: Mapping[str, str], text: str) -> tuple[Span, ...]:
    """Every place in one module where a renamed name is written.

    An attribute, a definition, a parameter, a keyword argument and an import alias each sit at a
    different offset from the node that holds them, and none of them is the node's own start, so each
    one is found in the line rather than assumed. A reference is the node itself.
    """
    lines: Final = text.split("\n")

    def at(node: ast.AST, name: str) -> Span | None:
        """The name's own offsets, found on the node's first line.

        Built from `lineno` and the position the name is found at, never from `end_lineno`. A class or a
        function ends where its body ends, so asking whether the node is on one line rejects every
        definition in the repository while its references are renamed anyway. The audit caught that: 756
        of 1,316 names looked unreachable, and applying it would have left a tree that does not import.
        """
        line: Final = getattr(node, "lineno", None)
        start: Final = getattr(node, "col_offset", None)
        if not (isinstance(line, int) and isinstance(start, int) and line - 1 < len(lines)):
            return None
        raw: Final = lines[line - 1].encode("utf-8")
        found: Final = raw.find(name.encode("utf-8"), start)
        if found < 0:
            return None
        return Span(line=line, start=found, end=found + len(name.encode("utf-8")), old=name, new=wanted[name])

    collected: list[Span | None] = []  # rebind-ok: gathered while walking the tree
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in wanted:
            collected.append(_span(node, node.id, wanted[node.id]))
        elif isinstance(node, ast.Attribute) and node.attr in wanted:
            collected.append(at(node, node.attr))
        elif isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in wanted:
            collected.append(at(node, node.name))
        elif isinstance(node, ast.arg) and node.arg in wanted:
            collected.append(_span(node, node.arg, wanted[node.arg], end=node.col_offset + len(node.arg)))
        elif isinstance(node, ast.keyword) and node.arg is not None and node.arg in wanted:
            collected.append(at(node, node.arg))
        elif isinstance(node, ast.alias):
            for part in (node.name, node.asname):
                if part is not None and part in wanted:
                    collected.append(at(node, part))
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            # These hold their names as plain strings rather than as `Name` nodes. Missing one leaves a
            # function declaring `global _LiteLLMLogging` while assigning `_GatewayLogging`, which makes
            # the assignment local and the read an UnboundLocalError on the first call.
            collected.extend(at(node, name) for name in node.names if name in wanted)
        elif (
            isinstance(node, (ast.ExceptHandler, ast.MatchAs, ast.MatchStar))
            and node.name is not None
            and node.name in wanted
        ):
            collected.append(at(node, node.name))
        elif isinstance(node, ast.MatchMapping) and node.rest is not None and node.rest in wanted:
            collected.append(at(node, node.rest))
        elif isinstance(node, ast.Call) and _dotted(node.func).endswith("parametrize"):
            # pytest reads its parameter names out of a comma-separated string, so renaming the
            # function's parameter without this one leaves pytest saying the function uses no argument
            # by that name, and the whole file stops collecting.
            collected.extend(_in_argnames(node, wanted, at))
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            collected.extend(_in_string(node, node.value, wanted, at))
    return tuple(found for found in collected if found is not None)


Finder = Callable[[ast.Module, Mapping[str, str], str], tuple[Span, ...]]


def _dotted(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_dotted(node.value)}.{node.attr}"
    return ""


def _in_argnames(
    node: ast.Call, wanted: Mapping[str, str], at: Callable[[ast.AST, str], Span | None]
) -> tuple[Span | None, ...]:
    """The renamed parameter names inside a `parametrize` call's first argument.

    pytest takes either one comma-separated string or a sequence of strings, and both are handled: the
    names are Python parameters that happen to be spelled in a string, so they move with the parameters.
    """
    if not node.args:
        return ()
    first: Final = node.args[0]
    pieces: Final = (
        (first,)
        if isinstance(first, ast.Constant)
        else tuple(element for element in first.elts if isinstance(element, ast.Constant))
        if isinstance(first, (ast.List, ast.Tuple))
        else ()
    )
    return tuple(
        at(piece, name)
        for piece in pieces
        if isinstance(piece.value, str)
        for name in (part.strip() for part in piece.value.split(","))
        if name in wanted
    )


def _in_string(
    node: ast.Constant, value: str, wanted: Mapping[str, str], at: Callable[[ast.AST, str], Span | None]
) -> tuple[Span | None, ...]:
    """The renamed names written inside one string literal.

    Two shapes, and nothing else:

    - the whole literal is a class name. A forward reference is resolved against module globals when
      something asks for it, and `"LiteLLMLoggingObj"` appears 172 times that way. Only a class, because
      the scope artifact deferred every snake_case name written as a whole literal: that is how a caller
      passes an argument by name
    - a segment of a path that already names the engine's new home, as in
      `patch("token_iq.gateway.proxy.x.transform_litellm_user_to_scim_user")`. Inside such a path a
      segment is a module, a class or a function, never a field, so a snake_case one moves here too. 47
      patch targets needed it, and the gate named every one
    """
    if value in wanted and capwords(value):
        return (at(node, value),)
    if not value.startswith("token_iq.gateway."):
        return ()
    return tuple(at(node, segment) for segment in value.split(".") if segment in wanted)


def rewrite(text: str, wanted: Mapping[str, str], *, finder: Finder = spans) -> tuple[str, Mapping[str, int]]:
    """Every renamed name in one file's text, with how many were written.

    `finder` is injected so the guard below can be tested with one that hands over a span pointing at the
    wrong place. Without that the guard is unexercised, which is the same as not having it.
    """
    try:
        tree: Final = ast.parse(text)
    except SyntaxError:
        return text, MappingProxyType({})

    found: Final = sorted(finder(tree, wanted, text), key=lambda span: (span.line, span.start), reverse=True)
    if not found:
        return text, MappingProxyType({})

    # Edited back to front, so every span's offsets still describe the text when its turn comes.
    lines = text.split("\n")  # rebind-ok: the accumulator of the edit
    counts: Counter[str] = Counter()  # rebind-ok: a tally of names actually written
    for span in found:
        raw = lines[span.line - 1].encode("utf-8")
        written = raw[span.start : span.end].decode("utf-8")
        if written != span.old:
            # The offsets did not land on the name. Nothing is written rather than a guess, because the
            # alternative is cutting an arbitrary span out of a line and splicing a name into the gap.
            continue
        lines[span.line - 1] = raw[: span.start].decode("utf-8") + span.new + raw[span.end :].decode("utf-8")
        counts[span.old] += 1
    return "\n".join(lines), MappingProxyType(dict(counts))


def named(path: pathlib.Path) -> str:
    return path.relative_to(REPO).as_posix() if path.is_relative_to(REPO) else path.as_posix()


def parses(text: str) -> bool:
    try:
        _ = ast.parse(text)
    except SyntaxError:
        return False
    return True


Rewriter = Callable[[str, Mapping[str, str]], tuple[str, Mapping[str, int]]]


def run(
    paths: Iterable[pathlib.Path], wanted: Mapping[str, str], *, write: bool, rewriter: Rewriter = rewrite
) -> tuple[Counter[str], tuple[str, ...]]:
    """`rewriter` is injected so the guard below can be tested with one that breaks a file on purpose."""
    totals: Counter[str] = Counter()  # rebind-ok: a tally across files
    broken: list[str] = []  # rebind-ok: files a rewrite would leave unparseable
    for path in paths:
        before = path.read_text(encoding="utf-8")
        after, counts = rewriter(before, wanted)
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


def unreachable(paths: Iterable[pathlib.Path], wanted: Mapping[str, str]) -> tuple[str, ...]:
    """Names this phase owns that no file writes as a Python identifier, so the pass renames nothing.

    A row here is not a failure; it says the scope artifact and the tree disagree, which is worth seeing
    rather than reading a count that is lower than the artifact's and not knowing why.
    """
    written: Final[Counter[str]] = Counter()
    for path in paths:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, OSError):
            continue
        written.update(span.old for span in spans(tree, wanted, path.read_text(encoding="utf-8")))
    return tuple(sorted(set(wanted) - set(written)))


def _print_utf8() -> None:
    """Let the report hold any character a name or a source line holds."""
    stream: Final = sys.stdout
    if isinstance(stream, io.TextIOWrapper):
        stream.reconfigure(encoding="utf-8", errors="replace")


def main(argv: Sequence[str] | None = None) -> int:
    parser: Final = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--apply", action="store_true", help="write the renames")
    _ = parser.add_argument("--dry-run", action="store_true", help="report and change nothing")
    _ = parser.add_argument("--audit", action="store_true", help="list names no file writes")
    options: Final = Options.model_validate(vars(parser.parse_args(argv)))
    _print_utf8()
    if sum((options.apply, options.dry_run, options.audit)) != 1:
        sys.stderr.write("pass exactly one of --apply, --dry-run and --audit\n")
        return 2

    wanted: Final = renames()
    paths: Final = tracked()

    if options.audit:
        missing: Final = unreachable(paths, wanted)
        sys.stdout.write(f"{len(missing)} of {len(wanted)} name(s) this phase owns are written nowhere\n")
        sys.stdout.write("".join(f"  {name}\n" for name in missing))
        return 0

    totals, broken = run(paths, wanted, write=options.apply)
    files: Final = totals.pop("files changed", 0)
    report: Final = (
        f"{sum(totals.values())} name(s) rewritten in {files} file(s), from {len(wanted)} this phase owns",
        *(f"{count:>7}  {name}" for name, count in totals.most_common(15)),
    )
    sys.stdout.write("\n".join(report) + "\n")
    if broken:
        sys.stderr.write(f"\n{len(broken)} file(s) would not parse after rewriting, left alone:\n")
        sys.stderr.write("\n".join(f"  {name}" for name in broken) + "\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
