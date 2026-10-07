"""Point the engine at the renamed Prisma models.

The schema pass renamed the 85 models and mapped each back to the table it already had. The generated
client's class names and accessors follow the model name, so every reference to one has to move with it:
`prisma_models.LiteLLM_TeamTable` becomes `prisma_models.TeamTable`, and `prisma_client.db.litellm_teamtable`
becomes `prisma_client.db.teamtable`.

    python scripts/rename/rename_prisma_references.py --audit
    python scripts/rename/rename_prisma_references.py --dry-run
    python scripts/rename/rename_prisma_references.py --apply

The hard part is telling a generated name from one that merely looks like it. `token_iq/gateway/models/`
declares its own Pydantic classes called `LiteLLM_BudgetTable` and so on, which mirror the rows but are not
them, and renaming those would change keys the API returns. So a name only moves when this file can see it
come from the `prisma` package: imported from a `prisma.*` module, or read off an alias bound to one. Six
such aliases exist, and they are collected per file rather than assumed.

Accessors are recognised by shape instead, an attribute starting with `litellm_` read off something called
`db`, because the accessor is the model name lowercased and nothing else in the engine is written that way.

The accessor rule is the generator's, not a guess: every one of the 80 models in the installed client
exposes itself as its own name lowercased, with no exceptions. The client cannot be regenerated on this
machine, so that is the evidence the rule rests on.

Positions are addressed as UTF-8 bytes on lines split only at "\\n", and edits are applied back to front,
for the reasons the earlier passes in this programme found the hard way.
"""

from __future__ import annotations

import argparse
import ast
import functools
import io
import pathlib
import re
import subprocess
import sys
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Final, Protocol

from pydantic import BaseModel

REPO: Final = pathlib.Path(__file__).resolve().parents[2]
PREFIX: Final = "LiteLLM_"
ACCESSOR_PREFIX: Final = "litellm_"
SCHEMA: Final = "schema.prisma"
MAPPED_TABLE: Final = re.compile(r'@@map\("LiteLLM_(\w+)"\)')


@functools.cache
def accessor_names() -> frozenset[str]:
    """Every accessor the generated client exposes, under the name it had before the schema pass.

    Read from the schema's `@@map` lines, so this is the set of models and nothing else. That matters
    because an accessor name is not a reserved shape: `litellm_params` is a config key and
    `litellm_provider` a field in the price file, and neither is `litellm_` plus a model name.

    Needed because some accessors are reached by name rather than by attribute, through
    `getattr(prisma_client.db, table_name)`, and a string that feeds one of those has to move too.
    """
    text: Final = (REPO / SCHEMA).read_text(encoding="utf-8")
    tables: Final[list[str]] = MAPPED_TABLE.findall(text)
    return frozenset(f"{ACCESSOR_PREFIX}{table.lower()}" for table in tables)


PRISMA_SUBMODULES: Final[frozenset[str]] = frozenset({"models", "types", "actions", "fields", "enums"})

SKIP: Final[tuple[str, ...]] = (
    "scripts/rename/rename_prisma_references.py",
    "tests/gateway/test_rename_prisma_references.py",
)
"""Both name the generated classes on purpose."""


@dataclass(frozen=True, slots=True)
class Edit:
    """One replacement, addressed as a line and a pair of byte offsets into that line's UTF-8."""

    line: int
    start: int
    end: int
    text: str
    kind: str


class Positioned(Protocol):
    """A syntax node that knows where it is. Every node this pass edits has these; `ast.AST` does not
    declare them, so without this the offsets are all unknown types."""

    lineno: int
    col_offset: int
    end_lineno: int | None
    end_col_offset: int | None


class Options(BaseModel):
    """The command line, typed. `parse_args` hands back `Any` for every flag."""

    apply: bool = False
    dry_run: bool = False
    audit: bool = False


def tracked() -> tuple[pathlib.Path, ...]:
    listed: Final = subprocess.run(
        ("git", "ls-files", "token_iq/*.py", "tests/*.py", "enterprise/*.py"),
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    return tuple(REPO / name for name in listed if name and name not in SKIP)


def named(path: pathlib.Path) -> str:
    try:
        return path.relative_to(REPO).as_posix()
    except ValueError:
        return path.name


def module_aliases(tree: ast.Module) -> frozenset[str]:
    """Names this module binds to a `prisma` submodule, so `<alias>.LiteLLM_X` is a generated class."""
    return frozenset(
        alias.asname
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] == "prisma"
        for alias in node.names
        if alias.asname and alias.name in PRISMA_SUBMODULES
    )


def imported_plainly(tree: ast.Module) -> frozenset[str]:
    """Generated classes this module imports under their own name, so a bare use of one is that class."""
    return frozenset(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] == "prisma"
        for alias in node.names
        if alias.name.startswith(PREFIX) and not alias.asname
    )


def scan(text: str) -> tuple[Edit, ...]:
    """Every reference in this file that has to move with the model it names."""
    try:
        tree: Final = ast.parse(text)
    except SyntaxError:
        return ()

    aliases: Final = module_aliases(tree)
    plain: Final = imported_plainly(tree)
    accessors: Final = accessor_names()
    lines: Final = text.split("\n")

    def at(node: Positioned, old: str, new: str, kind: str) -> Edit | None:
        """The edit that replaces `old` with `new` inside this node's own source text."""
        if node.lineno != node.end_lineno or node.end_col_offset is None:
            return None
        raw: Final = lines[node.lineno - 1].encode("utf-8")
        source: Final = raw[node.col_offset : node.end_col_offset].decode("utf-8")
        if old not in source:
            return None
        return Edit(node.lineno, node.col_offset, node.end_col_offset, source.replace(old, new), kind)

    def at_all(node: Positioned, mentions: Sequence[tuple[str, str]], kind: str) -> Edit | None:
        """One edit that applies every replacement to this node's source text.

        Pairs rather than one rule, because the prefix sits at the end of `prisma_models.LiteLLM_` and at
        the start of a bare `LiteLLM_Config`.
        """
        first: Final = at(node, *mentions[0], kind)
        if first is None:
            return None
        rewritten = first.text  # rebind-ok: one replacement per mention
        for old, new in mentions[1:]:
            rewritten = rewritten.replace(old, new)
        return Edit(first.line, first.start, first.end, rewritten, kind)

    def on_the_line(number: int, old: str, new: str, kind: str) -> Edit | None:
        """The edit that replaces the first `old` on one line, for a node whose span is its whole body."""
        raw: Final = lines[number - 1].encode("utf-8")
        start: Final = raw.find(old.encode("utf-8"))
        if start == -1:
            return None
        return Edit(number, start, start + len(old.encode("utf-8")), new, kind)

    found: list[Edit] = []  # rebind-ok: the accumulator of a scan over one file

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] == "prisma":
            # The alias node, not the whole statement: an import of four names over five lines is common
            # here, and editing the statement would skip it while its uses were renamed without it.
            for alias in node.names:
                if alias.name.startswith(PREFIX):
                    edit = at(alias, alias.name, alias.name.removeprefix(PREFIX), "import renamed")
                    if edit is not None:
                        found.append(edit)

        if isinstance(node, ast.Attribute) and node.attr.startswith(PREFIX):
            if isinstance(node.value, ast.Name) and node.value.id in aliases:
                edit = at(node, node.attr, node.attr.removeprefix(PREFIX), "generated class")
                if edit is not None:
                    found.append(edit)

        if isinstance(node, ast.Name) and node.id in plain:
            edit = at(node, node.id, node.id.removeprefix(PREFIX), "imported class")
            if edit is not None:
                found.append(edit)

        # By name rather than by what it is read off. The receiver is `prisma_client.db` in the engine, a
        # transaction in the MCP tables, and a `SimpleNamespace` or a hand-rolled `MockDB` in the tests, and
        # the first version of this rule only knew about `db` and would have shipped `tx.litellm_…` broken.
        # Safe because the set is the 85 models and nothing else: `litellm_params` is not in it.
        if isinstance(node, ast.Attribute) and node.attr in accessors:
            edit = at(node, node.attr, node.attr.removeprefix(ACCESSOR_PREFIX), "accessor")
            if edit is not None:
                found.append(edit)

        # A mock exposes its tables as properties, and the `def` line is the only place that name appears.
        # The node spans the whole body, so the edit is built from the name's own place on that line.
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in accessors:
            edit = on_the_line(node.lineno, node.name, node.name.removeprefix(ACCESSOR_PREFIX), "accessor")
            if edit is not None:
                found.append(edit)

        if isinstance(node, ast.Name) and node.id in accessors:
            edit = at(node, node.id, node.id.removeprefix(ACCESSOR_PREFIX), "accessor")
            if edit is not None:
                found.append(edit)

        if isinstance(node, ast.keyword) and node.arg in accessors:
            edit = at(node, node.arg, node.arg.removeprefix(ACCESSOR_PREFIX), "accessor")
            if edit is not None:
                found.append(edit)

        if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in accessors:
            edit = at(node, node.value, node.value.removeprefix(ACCESSOR_PREFIX), "accessor named in a string")
            if edit is not None:
                found.append(edit)

        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            # Every mention in one edit, because a string annotation can name two of them. A quoted type
            # hint is a string rather than a `Name`, so a plainly imported class only moves here, and
            # leaving one behind is an undefined name once the import beside it has been renamed.
            mentions = tuple(
                (old, new)
                for old, new in (
                    *((f"{alias}.{PREFIX}", f"{alias}.") for alias in sorted(aliases)),
                    *((name, name.removeprefix(PREFIX)) for name in sorted(plain, key=len, reverse=True)),
                )
                if old in node.value
            )
            if mentions:
                edit = at_all(node, mentions, "class named in a string")
                if edit is not None:
                    found.append(edit)

    return _one_per_span(found)


def _one_per_span(found: Sequence[Edit]) -> tuple[Edit, ...]:
    """One edit per span, keeping the first.

    Nested nodes can cover the same text, and splicing two rewrites over one span would put the second
    one on top of the unedited original rather than on top of the first.
    """
    merged: dict[tuple[int, int, int], Edit] = {}  # rebind-ok: keyed by the span it replaces
    for edit in found:
        _ = merged.setdefault((edit.line, edit.start, edit.end), edit)
    return tuple(merged.values())


def applied(text: str, edits: Sequence[Edit]) -> str:
    """The text with every edit made, back to front so no edit moves another one's offsets."""
    rebuilt: Final = text.split("\n")  # mutable-ok: the accumulator of a back-to-front splice
    for edit in sorted(edits, key=lambda e: (e.line, e.start), reverse=True):
        raw = rebuilt[edit.line - 1].encode("utf-8")  # rebind-ok: one line per pass
        rebuilt[edit.line - 1] = raw[: edit.start].decode("utf-8") + edit.text + raw[edit.end :].decode("utf-8")
    return "\n".join(rebuilt)


def rewrite(text: str) -> tuple[str, Counter[str]]:
    """The file as it should be, and what changed in it."""
    edits: Final = scan(text)
    if not edits:
        return text, Counter()
    return applied(text, edits), Counter(edit.kind for edit in edits)


def leftovers(paths: Iterable[pathlib.Path]) -> tuple[str, ...]:
    """Generated names a rule would not reach, for a person to read."""
    remaining: list[str] = []  # rebind-ok: the accumulator of a scan
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
            tree = ast.parse(text)
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        aliases = module_aliases(tree)
        if not aliases:
            continue
        lines = text.split("\n")
        remaining.extend(
            f"{named(path)}:{node.lineno}  {lines[node.lineno - 1].strip()[:90]}"
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)
            and node.attr.startswith(PREFIX)
            and isinstance(node.value, ast.Name)
            and node.value.id in aliases
            and node.lineno != getattr(node, "end_lineno", node.lineno)
        )
    return tuple(remaining)


def run(paths: Iterable[pathlib.Path], *, write: bool) -> tuple[Counter[str], tuple[str, ...]]:
    """Every file rewritten, with what changed and any file a rewrite would leave unparseable."""
    totals: Counter[str] = Counter()  # rebind-ok: a tally across files
    broken: list[str] = []  # rebind-ok: the files that refused the rewrite

    for path in paths:
        try:
            before = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        after, counts = rewrite(before)
        if after == before:
            continue
        try:
            _ = ast.parse(after)
        except SyntaxError:
            broken.append(named(path))
            continue
        totals.update(counts)
        totals["files changed"] += 1
        if write:
            _ = path.write_text(after, encoding="utf-8")

    return totals, tuple(broken)


def main(argv: Sequence[str] | None = None, out: io.TextIOBase | None = None) -> int:
    parser: Final = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--apply", action="store_true", help="write the changes")
    _ = parser.add_argument("--dry-run", action="store_true", help="say what would change")
    _ = parser.add_argument("--audit", action="store_true", help="list what no rule reaches")
    options: Final = Options.model_validate(vars(parser.parse_args(argv)))
    say: Final = out or sys.stdout

    if sum((options.apply, options.dry_run, options.audit)) != 1:
        print("pass exactly one of --apply, --dry-run and --audit", file=say)
        return 2

    paths: Final = tracked()

    if options.audit:
        remaining: Final = leftovers(paths)
        for line in remaining:
            print(line, file=say)
        print(f"\ngenerated names spread over more than one line: {len(remaining)}", file=say)
        return 0

    totals, broken = run(paths, write=options.apply)
    for kind, count in sorted(totals.items()):
        print(f"{count:>5}  {kind}", file=say)
    for name in broken:
        print(f"would not parse afterwards, left alone: {name}", file=say)
    return 1 if broken else 0


if __name__ == "__main__":
    raise SystemExit(main())
