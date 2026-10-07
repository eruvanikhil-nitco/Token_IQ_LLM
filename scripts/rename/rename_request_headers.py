"""Rename the engine's own request and response headers, and route every read through `compat.header`.

Phase 7 says a response carries `x-token-iq-*` only, while a caller still sending `x-litellm-*` is
understood. Those are two different jobs, and this does both:

    `headers["x-litellm-model-group"] = g`   ->  `headers["x-token-iq-model-group"] = g`
    `request.headers.get("x-litellm-tags")`  ->  `compat.header(request.headers, "x-token-iq-tags")`

    python scripts/rename/rename_request_headers.py --audit
    python scripts/rename/rename_request_headers.py --dry-run
    python scripts/rename/rename_request_headers.py --apply

Every read goes through the helper, including reads of a dict the engine filled in itself. Sorting them
into "could be a caller's" and "could only be ours" would be a judgement at 44 call sites, and getting it
wrong in the first direction rejects a request from a client that has not been updated. Getting it wrong
the other way costs a dictionary lookup that misses.

The name is edited inside the source text of the literal rather than re-rendered from its value, so
quotes, string prefixes, escapes and the segments of an f-string all survive untouched. Only a literal
whose value *starts* with the old prefix is renamed; one that merely mentions the prefix part-way through
is prose, and `--audit` lists those for a person instead of guessing at the sentence around them.

Writes are the half that fails loudly: a renamed emit site that was missed leaves a test asserting a
header that is no longer sent. A missed read still works, because the old name is what it already asks
for, which is why the audit exists to say what was left behind.
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
OLD_PREFIX: Final = "x-litellm-"
NEW_PREFIX: Final = "x-token-iq-"
IMPORT: Final = "from token_iq.gateway import compat"

OLD_IN_SOURCE: Final = re.compile(re.escape(OLD_PREFIX), re.IGNORECASE)
HEADER_SHAPED: Final = re.compile(r"[A-Za-z0-9-]*")

READ_SCOPE: Final = "token_iq/"
"""Where reads are routed through the helper. A test says which spelling it means, so rewriting one there
would change what it is testing; the names it asserts on still move, because a response carries the new
one."""

SKIP: Final[tuple[str, ...]] = (
    "docs/",
    "cookbook/",
    "token_iq/gateway/compat.py",
    # The tools that measure how much of the old name is left. Their patterns are the old name, so
    # renaming one leaves it reporting zero of whatever it was counting.
    "scripts/inventory/",
    # Installed as its own distribution, so importing the engine from it would be a dependency that does
    # not hold where it runs.
    "litellm-proxy-extras/",
)

ITS_OWN_FILES: Final[frozenset[str]] = frozenset(
    {
        "scripts/rename/rename_request_headers.py",
        "tests/gateway/test_rename_request_headers.py",
        # The two that prove a caller sending the old name is still understood. Renaming the names in them
        # left every case green while testing nothing, because both sides of each assertion moved together.
        "tests/gateway/test_compat.py",
        "tests/gateway/proxy/test_upgrade_keeps_working.py",
    }
)
"""Files that name both spellings on purpose. Letting the pass rewrite one turns every literal it looks
for into the thing it replaces them with, after which it matches nothing and reports a clean run."""


@dataclass(frozen=True, slots=True)
class Edit:
    """One replacement, addressed as a line and a pair of byte offsets into that line's UTF-8."""

    line: int
    start: int
    end: int
    text: str
    kind: str


class Options(BaseModel):
    """The command line, typed. `parse_args` hands back `Any` for every flag."""

    apply: bool = False
    dry_run: bool = False
    audit: bool = False


class Mention(BaseModel):
    """A literal that names the old prefix part-way through, for a person to read."""

    where: str
    line: int
    value: str


def tracked(scope: str = "") -> tuple[pathlib.Path, ...]:
    listed: Final = subprocess.run(
        ("git", "ls-files", f"{scope}*.py"), cwd=REPO, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    return tuple(REPO / name for name in listed if name and not name.startswith(SKIP) and name not in ITS_OWN_FILES)


def named(path: pathlib.Path) -> str:
    """The path as the repository spells it, or just its name when it is outside (a test's own file)."""
    try:
        return path.relative_to(REPO).as_posix()
    except ValueError:
        return path.name


def renamed(source: str) -> str:
    """The source text of a header literal with the prefix moved on and the rest put in lower case.

    Lower case because that is the form HTTP/2 puts on the wire and the form every call site asks for.
    Only a run that is shaped like the rest of a header name is touched, so a literal that carries a
    sentence after the name keeps the sentence as it was written.
    """
    match: Final = OLD_IN_SOURCE.search(source)
    if match is None:
        return source
    rest: Final = HEADER_SHAPED.match(source, match.end())
    cut: Final = rest.end() if rest is not None else match.end()
    return f"{source[: match.start()]}{NEW_PREFIX}{source[match.end() : cut].lower()}{source[cut:]}"


def receiver_of(call: ast.Call) -> ast.expr | None:
    """The mapping a `.get(…)` is being read from, or None when this is not that shape."""
    if not isinstance(call.func, ast.Attribute) or call.func.attr != "get":
        return None
    if not call.args or len(call.args) > 2 or call.keywords:
        return None
    first: Final = call.args[0]
    if not (isinstance(first, ast.Constant) and isinstance(first.value, str)):
        return None
    return call.func.value if first.value.lower().startswith((OLD_PREFIX, NEW_PREFIX)) else None


def is_ours(value: object) -> bool:
    return isinstance(value, str) and value.lower().startswith(OLD_PREFIX)


def scan(text: str, path: str, *, route_reads: bool) -> tuple[tuple[Edit, ...], tuple[Mention, ...]]:
    """Every edit this file needs, and every literal left for a person."""
    try:
        tree: Final = ast.parse(text)
    except SyntaxError:
        return (), ()

    lines: Final = text.split("\n")

    def source_of(node: ast.expr) -> str | None:
        if node.lineno != node.end_lineno or node.end_col_offset is None:
            return None
        raw: Final = lines[node.lineno - 1].encode("utf-8")
        return raw[node.col_offset : node.end_col_offset].decode("utf-8")

    renames: Final = tuple(
        Edit(node.lineno, node.col_offset, node.end_col_offset, renamed(found), "header renamed")
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and is_ours(node.value)
        and node.lineno == node.end_lineno
        and node.end_col_offset is not None
        for found in (source_of(node),)
        if found is not None and renamed(found) != found
    )

    mentions: Final = tuple(
        Mention(where=path, line=node.lineno, value=node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and OLD_PREFIX in node.value.lower()
        and not is_ours(node.value)
    )

    if not route_reads:
        return renames, mentions

    reads: Final = tuple(
        Edit(
            call.func.lineno,
            call.func.col_offset,
            call.args[0].col_offset,
            f"compat.header({source}, ",
            "read routed",
        )
        for call in ast.walk(tree)
        if isinstance(call, ast.Call)
        for receiver in (receiver_of(call),)
        if receiver is not None
        # One line, so the splice is a slice of it. Every one of them is.
        if call.func.lineno == call.args[0].lineno and isinstance(call.func, ast.Attribute)
        for source in (source_of(receiver),)
        if source is not None
    )
    return renames + reads, mentions


def applied(text: str, edits: Sequence[Edit]) -> str:
    """The text with every edit made, back to front so no edit moves another one's offsets.

    Lines are split on "\\n" alone: `str.splitlines()` also breaks on U+2028, U+2029 and form feed, which
    invents line numbers the parser never used. Offsets are byte offsets into each line's UTF-8, because
    that is what `col_offset` means.
    """
    lines: Final = text.split("\n")
    rebuilt: Final = list(lines)  # mutable-ok: the accumulator of a back-to-front splice
    for edit in sorted(edits, key=lambda e: (e.line, e.start), reverse=True):
        raw = rebuilt[edit.line - 1].encode("utf-8")  # rebind-ok: one line per pass of the loop
        rebuilt[edit.line - 1] = raw[: edit.start].decode("utf-8") + edit.text + raw[edit.end :].decode("utf-8")
    return "\n".join(rebuilt)


def with_import(text: str, first_use: int) -> str:
    """Add the helper's import, after the last top-level import that comes before the first use of it."""
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
    after: Final = (
        max(node.end_lineno or node.lineno for node in before)
        if before
        else max((node.end_lineno or node.lineno for node in future), default=first_use - 1)
    )
    lines: Final = text.split("\n")
    return "\n".join(lines[:after] + [IMPORT] + lines[after:])


def rewrite(
    text: str, path: str = "", *, route_reads: bool = True
) -> tuple[str, Mapping[str, int], tuple[Mention, ...]]:
    """The file as it should be, what changed in it, and what was left for a person."""
    edits, mentions = scan(text, path, route_reads=route_reads)
    if not edits:
        return text, MappingProxyType({}), mentions

    counts: Final = Counter(edit.kind for edit in edits)
    done: Final = applied(text, edits)
    routed: Final = [edit for edit in edits if edit.kind == "read routed"]
    if not routed:
        return done, MappingProxyType(dict(counts)), mentions
    return (
        with_import(done, min(edit.line for edit in routed)),
        MappingProxyType(dict(counts)),
        mentions,
    )


def routes_reads(name: str) -> bool:
    """Whether reads in this file are pointed at the helper, as opposed to only its names moving."""
    return name.startswith(READ_SCOPE)


Rewriter = Callable[[str, str, bool], tuple[str, Mapping[str, int], tuple[Mention, ...]]]


def one_file(text: str, path: str, reads: bool) -> tuple[str, Mapping[str, int], tuple[Mention, ...]]:
    """The default rewriter, named rather than a lambda so its parameters carry their types."""
    return rewrite(text, path, route_reads=reads)


def run(
    paths: Iterable[pathlib.Path],
    *,
    write: bool,
    rewriter: Rewriter = one_file,
    reads_in: Callable[[str], bool] = routes_reads,
) -> tuple[Mapping[str, int], tuple[str, ...], tuple[Mention, ...]]:
    """Every file rewritten, with what changed, what would not parse afterwards, and what was left."""
    change: Final[Rewriter] = rewriter
    totals: Counter[str] = Counter()  # rebind-ok: a tally over files
    broken: list[str] = []  # rebind-ok: the files that refused the rewrite
    mentions: list[Mention] = []  # rebind-ok: what the audit reports

    for path in paths:
        name = named(path)
        before = path.read_text(encoding="utf-8")
        after, counts, found = change(before, name, reads_in(name))
        mentions.extend(found)
        if after == before:
            continue
        try:
            _ = ast.parse(after)
        except SyntaxError:
            broken.append(name)
            continue
        totals.update(counts)
        totals["files changed"] += 1
        if write:
            _ = path.write_text(after, encoding="utf-8")

    return MappingProxyType(dict(totals)), tuple(broken), tuple(mentions)


def main(argv: Sequence[str] | None = None, out: io.TextIOBase | None = None) -> int:
    parser: Final = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--apply", action="store_true", help="write the changes")
    _ = parser.add_argument("--dry-run", action="store_true", help="say what would change")
    _ = parser.add_argument("--audit", action="store_true", help="list what is left for a person")
    options: Final = Options.model_validate(vars(parser.parse_args(argv)))
    say: Final = out or sys.stdout

    if not (options.apply or options.dry_run or options.audit):
        parser.print_help(say)
        return 2

    totals, broken, mentions = run(tracked(), write=options.apply)

    if options.audit:
        for mention in mentions:
            print(f"{mention.where}:{mention.line}  {mention.value[:100]}", file=say)
        print(f"\nliterals naming the old prefix part-way through: {len(mentions)}", file=say)
        return 0

    for kind, count in sorted(totals.items()):
        print(f"{count:>6}  {kind}", file=say)
    for name in broken:
        print(f"would not parse afterwards, left alone: {name}", file=say)
    return 1 if broken else 0


if __name__ == "__main__":
    raise SystemExit(main())
