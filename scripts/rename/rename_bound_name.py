"""Rename the name every module binds the engine to, from `litellm` to `gateway`.

Phase 6, second half. The first half moved the package and deliberately kept the old bound name, so
`import litellm` became `from token_iq import gateway as litellm` and the 16,000 `litellm.<attr>` uses
went untouched. This pass finishes it: the alias goes, and every use reads `gateway.<attr>`.

It is a local-name rename, which is why it comes second. Nothing crosses a module boundary, so the
route table, the registries and the package's public surface must all come out identical, and the
dumps under `docs/plans/phase-6-*-before.txt` say what they were.

    python scripts/rename/rename_bound_name.py --dry-run
    python scripts/rename/rename_bound_name.py --apply
    python scripts/rename/rename_bound_name.py --audit     # what no rule would rewrite

The name is renamed through the syntax tree rather than by matching text, because `litellm` is a
substring of names that are not it and must not move in this phase: `litellm_params` is a config key,
`LITELLM_MASTER_KEY` an environment variable, `LiteLLM_TeamTable` a database model, and
`"litellm.trace_id"` an OpenTelemetry attribute. A `Name` node is unambiguously the bound name; a
comment, a telemetry string and a longer identifier are not `Name` nodes at all.

Positions are addressed as UTF-8 bytes on lines split only at "\\n", for the two reasons the first half
found the hard way: `col_offset` is a byte offset, and `str.splitlines` invents line breaks at U+2028,
U+2029, a form feed and four more that Python's tokenizer does not.
"""

from __future__ import annotations

import argparse
import ast
import io
import pathlib
import re
import subprocess
import sys
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from pydantic import BaseModel

REPO: Final = pathlib.Path(__file__).resolve().parents[2]
OLD_NAME: Final = "litellm"
NEW_NAME: Final = "gateway"


def bound_names(tree: ast.Module) -> Mapping[str, str]:
    """What this module calls the engine, and what each of those becomes.

    Read from the module rather than listed, because modules spell the alias more ways than a list
    keeps up with: `litellm`, `_litellm`, `litellm_module` and `litellm_mod` are all in the tree today,
    and the first list of spellings missed two of them. Any alias holding the old name is renamed by
    substituting the new one, so `litellm_module` becomes `gateway_module` and the private spelling
    stays private.
    """
    return MappingProxyType(
        {
            alias.asname: alias.asname.replace(OLD_NAME, NEW_NAME)
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module == "token_iq"
            for alias in node.names
            if alias.name == "gateway" and alias.asname is not None and OLD_NAME in alias.asname
        }
    )


class Options(BaseModel):
    apply: bool = False
    dry_run: bool = False
    audit: bool = False


@dataclass(frozen=True, slots=True)
class Rule:
    name: str
    pattern: re.Pattern[str]
    replacement: str


IMPORT_RULES: Final[tuple[Rule, ...]] = (
    Rule(
        "the alias goes",
        re.compile(rf"^([ \t]*)from token_iq import gateway as {OLD_NAME}([ \t]*(?:\#.*)?)$", re.MULTILINE),
        r"\g<1>from token_iq import gateway\g<2>",
    ),
    Rule(
        "an alias holding the old name is renamed",
        re.compile(rf"^([ \t]*from token_iq import gateway as [\w]*){OLD_NAME}", re.MULTILINE),
        rf"\g<1>{NEW_NAME}",
    ),
)

ITS_OWN_FILES: Final[frozenset[str]] = frozenset(
    {
        # A pass that rewrites its own source turns every literal it looks for into the thing it
        # replaces them with, after which it matches nothing and reports a clean run.
        "scripts/rename/rename_bound_name.py",
        "tests/gateway/test_rename_bound_name.py",
        # The other half's tests, whose expectations are what that pass produces: the alias this
        # one removes is the right answer there.
        "scripts/rename/move_engine_package.py",
        "tests/gateway/test_move_engine_package.py",
    }
)

NAMED_CHANGES: Final[Mapping[str, str]] = MappingProxyType(
    {
        # A multi-target import. No rule splits one, and there is exactly one.
        "import pytest, litellm": "import pytest\nfrom token_iq import gateway",
        # Python source held as data and run in a subprocess, so no syntax tree reaches inside it.
        "            import json, litellm\n": "            import json\n            from token_iq import gateway\n",
        "            print(json.dumps([litellm.enable_anthropic_prompt_caching, "
        "litellm.anthropic_prompt_caching_ttl]))\n": (
            "            print(json.dumps([gateway.enable_anthropic_prompt_caching, "
            "gateway.anthropic_prompt_caching_ttl]))\n"
        ),
    }
)
"""Changes no syntax tree can make, written out in full so a reviewer reads the line that changes."""

INSIDE_A_MODULE_PATH: Final = re.compile(rf"(?<=\.){OLD_NAME}(?=\.|$)")
"""The bound name as one segment of a path that already names the engine's new home.

`patch("token_iq.gateway.llms.azure.common_utils.litellm.module_level_client")` reaches through one
module's own binding of the engine, so renaming the binding renames the target with it. 55 patch targets
are written that way.

Only applied to a literal that already starts with `token_iq.gateway.`, which is what makes the segment
unambiguous: inside such a path a bare `litellm` segment is this binding and nothing else. The lookarounds
require it to be a whole segment, so `core_utils.litellm_logging`, a real module, is untouched."""


LEFTOVER: Final = re.compile(rf"(?<![\w.]){OLD_NAME}\.[A-Za-z_]", re.MULTILINE)
"""A use of the old bound name that survived. Text, not a syntax tree, so it also reports comments and
telemetry strings; the audit says which of those are expected."""


def tracked() -> tuple[pathlib.Path, ...]:
    out: Final = subprocess.run(
        ["git", "ls-files", "*.py"], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout
    return tuple(REPO / line for line in out.splitlines() if line and line not in ITS_OWN_FILES)


def annotation_strings(tree: ast.Module) -> frozenset[int]:
    """The ids of string literals that sit in an annotation.

    A forward reference is resolved against the module's globals when something asks for it, so it
    names the bound name and has to be renamed with it. There are nine. Every other string holding the
    old name belongs to a later phase.
    """
    found: set[int] = set()  # rebind-ok: gathering ids while walking the tree

    def mark(node: ast.expr | None) -> None:
        if node is None:
            return
        for inner in ast.walk(node):
            if isinstance(inner, ast.Constant) and isinstance(inner.value, str):
                found.add(id(inner))

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            mark(node.returns)
            arguments = (
                list(node.args.posonlyargs)
                + list(node.args.args)
                + list(node.args.kwonlyargs)
                + ([node.args.vararg] if node.args.vararg else [])
                + ([node.args.kwarg] if node.args.kwarg else [])
            )
            for argument in arguments:
                mark(argument.annotation)
        if isinstance(node, ast.AnnAssign):
            mark(node.annotation)
    return frozenset(found)


@dataclass(frozen=True, slots=True)
class Span:
    """One piece of text to replace, addressed the way Python numbers its source."""

    line: int
    start: int
    end: int
    old: str
    new: str


def spans(tree: ast.Module, renamed: Mapping[str, str]) -> tuple[Span, ...]:
    """Every place in one module where the bound name is written, and what it becomes.

    Four kinds, and each is a different syntactic thing rather than a different-looking string:
    a `Name` node, an `ImportFrom` alias that re-exports the name, an `__all__` entry naming it, and a
    forward reference in an annotation.
    """
    annotations: Final = annotation_strings(tree)
    reexports: Final = frozenset(
        id(alias)
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
        if alias.name in renamed and alias.asname is None
    )
    in_all: Final = frozenset(
        id(entry)
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets)
        for entry in ast.walk(node.value)
        if isinstance(entry, ast.Constant) and entry.value in renamed
    )

    return tuple(
        found
        for node in ast.walk(tree)
        for found in (_span_for(node, annotations=annotations, reexports=reexports, in_all=in_all, renamed=renamed),)
        if found is not None
    )


def _span_for(
    node: ast.AST,
    *,
    annotations: frozenset[int],
    reexports: frozenset[int],
    in_all: frozenset[int],
    renamed: Mapping[str, str],
) -> Span | None:
    if isinstance(node, ast.Name) and node.id in renamed:
        return _one_line(node, node.id, renamed[node.id])
    if isinstance(node, ast.alias) and id(node) in reexports:
        return _one_line(node, node.name, renamed[node.name])
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        if id(node) in in_all:
            return _one_line(node, node.value, renamed[node.value])
        if id(node) in annotations and node.value.startswith(f"{OLD_NAME}."):
            return _one_line(node, OLD_NAME, NEW_NAME)
        if node.value.startswith("token_iq.gateway.") and INSIDE_A_MODULE_PATH.search(node.value):
            return _one_line(node, f".{OLD_NAME}", f".{NEW_NAME}")
    return None


def _one_line(node: ast.AST, old: str, new: str) -> Span | None:
    """A span only when the thing is on one line, because that is all this pass needs to edit."""
    line: Final = getattr(node, "lineno", None)
    end_line: Final = getattr(node, "end_lineno", None)
    start: Final = getattr(node, "col_offset", None)
    end: Final = getattr(node, "end_col_offset", None)
    if not (isinstance(line, int) and isinstance(end_line, int) and isinstance(start, int) and isinstance(end, int)):
        return None
    return Span(line=line, start=start, end=end, old=old, new=new) if line == end_line else None


def rewrite(text: str) -> tuple[str, Mapping[str, int]]:
    """Every rule applied to one file's text, with how many times each one fired."""
    counts: dict[str, int] = {}  # rebind-ok: a tally built while folding the rules over the text
    # Read before anything changes. The import rules below rewrite the alias on its import line, after
    # which the module no longer says what it used to call the engine, while every use of it still does.
    try:
        aliases: Mapping[str, str] = bound_names(ast.parse(text))
    except SyntaxError:
        aliases = {}
    current = text  # rebind-ok: the fold's accumulator
    for rule in IMPORT_RULES:
        current, fired = rule.pattern.subn(rule.replacement, current)
        if fired:
            counts[rule.name] = fired
    for old, new in NAMED_CHANGES.items():
        if old in current:
            counts["a change no syntax tree can make"] = counts.get("a change no syntax tree can make", 0) + 1
            current = current.replace(old, new)

    try:
        tree: Final = ast.parse(current)
    except SyntaxError:
        return current, MappingProxyType(counts)

    # Edited back to front, so every span's offsets still describe the text when its turn comes.
    lines = current.split("\n")  # rebind-ok: the accumulator of the edit
    edited = 0  # rebind-ok: a tally of spans actually rewritten
    # The aliases this module used, read before the import rules touched them, plus the plain name,
    # whose import line those rules have already turned into a bare `from token_iq import gateway`.
    renamed: Final = MappingProxyType({OLD_NAME: NEW_NAME, **aliases})
    for span in sorted(spans(tree, renamed), key=lambda found: (found.line, found.start), reverse=True):
        raw = lines[span.line - 1].encode("utf-8")
        written = raw[span.start : span.end].decode("utf-8")
        if span.old not in written:
            continue
        lines[span.line - 1] = (
            raw[: span.start].decode("utf-8") + written.replace(span.old, span.new, 1) + raw[span.end :].decode("utf-8")
        )
        edited += 1
    if edited:
        counts["the bound name where it is written"] = edited
    return "\n".join(lines), MappingProxyType(counts)


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
    """`rewriter` is injected so the guard below can be tested with one that breaks a file on purpose."""
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


def leftovers(paths: Iterable[pathlib.Path]) -> tuple[str, ...]:
    """Uses of the old bound name that no rule would rewrite, with where each one is."""
    return tuple(
        f"{named(path)}:{text[: found.start()].count(chr(10)) + 1}  {text.splitlines()[text[: found.start()].count(chr(10))].strip()[:90]}"
        for path in paths
        for text in (rewrite(path.read_text(encoding="utf-8"))[0],)
        for found in LEFTOVER.finditer(text)
    )


def _print_utf8() -> None:
    """Let the report hold any character a source line holds.

    This console is cp1252, and one arrow in one file otherwise turns the whole report into a
    UnicodeEncodeError, after which only the count is printed and that reads as nothing to report.
    """
    stream: Final = sys.stdout
    if isinstance(stream, io.TextIOWrapper):
        stream.reconfigure(encoding="utf-8", errors="replace")


def main(argv: Sequence[str] | None = None) -> int:
    parser: Final = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--apply", action="store_true", help="write the rewrites")
    _ = parser.add_argument("--dry-run", action="store_true", help="report and change nothing")
    _ = parser.add_argument("--audit", action="store_true", help="list uses no rule would rewrite")
    options: Final = Options.model_validate(vars(parser.parse_args(argv)))
    _print_utf8()
    if sum((options.apply, options.dry_run, options.audit)) != 1:
        sys.stderr.write("pass exactly one of --apply, --dry-run and --audit\n")
        return 2

    if options.audit:
        remaining: Final = leftovers(tracked())
        sys.stdout.write(f"{len(remaining)} use(s) of the old bound name no rule would rewrite\n")
        sys.stdout.write("".join(f"  {line}\n" for line in remaining))
        return 0

    totals, broken = run(tracked(), write=options.apply)
    report: Final = tuple(f"{count:>7}  {name}" for name, count in totals.most_common())
    sys.stdout.write(("\n".join(report) or "nothing to do") + "\n")
    if broken:
        sys.stderr.write(f"\n{len(broken)} file(s) would not parse after rewriting, left alone:\n")
        sys.stderr.write("\n".join(f"  {name}" for name in broken) + "\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
