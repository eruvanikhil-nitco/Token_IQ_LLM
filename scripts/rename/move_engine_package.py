"""Rewrite every reference to the engine package so it can live at `token_iq/gateway/`.

Phase 6, first half. This pass changes where the package is imported FROM and leaves the name each
module binds alone: `import litellm` becomes `from token_iq import gateway as litellm`, so the 58,000
`litellm.<attr>` uses keep working untouched. Renaming the bound name to `gateway` is the second
half, and it is a pure local-name rename once this has landed and been verified.

Splitting it this way is the whole point. Each half is verifiable on its own: this one must not
change the route table, the registries or the package's public surface at all, and the dumps under
`docs/plans/phase-6-*-before.txt` say what those were. A single pass doing both would fail the same
diff with no way to tell which half caused it.

Run order matters. The string-literal rule asks the live interpreter whether a dotted string resolves
today, exactly as `mock.patch` does, so it has to run while the old layout is still importable:

    python scripts/rename/move_engine_package.py --dry-run     # report, change nothing
    python scripts/rename/move_engine_package.py --apply       # rewrite references
    git mv litellm token_iq/gateway
    git mv token_iq/gateway/litellm_core_utils token_iq/gateway/core_utils

Dotted string literals are rewritten by where they sit, never by how they look, and the default is to
leave them. `"litellm.proxy.proxy_server.prisma_client"` appears 1,246 times as a `mock.patch` target
and must move. `"litellm.trace_id"` is an OpenTelemetry attribute, `"litellm.completion"` is a
`call_type` value, `"litellm.RateLimitError"` is a sentinel a caller passes as `mock_response` to force
an error, and `tracer.trace("litellm.proxy.auth.budget_checks")` is a span name. Every one of those
resolves to something real, so a rule that rewrote whatever resolves would rename a public sentinel and
a customer's dashboards along with it.

Default-deny is chosen for the shape of its failures. A reference this pass misses raises
ModuleNotFoundError, fails the patch-target gate, or drops a route, and all three are loud. A string
rewritten that should not have been is silent: telemetry keeps flowing under a new name and the
sentinel stops matching. So a string moves only when it is an argument to a call that resolves module
paths, a `sys.modules` lookup, a `module_path` keyword, or inside a file that is nothing but a registry
of module paths.
"""

from __future__ import annotations

import argparse
import ast
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
OLD_PACKAGE: Final = "litellm"
NEW_PACKAGE: Final = "token_iq.gateway"
OLD_CORE_UTILS: Final = "litellm_core_utils"
NEW_CORE_UTILS: Final = "core_utils"


class Options(BaseModel):
    apply: bool = False
    dry_run: bool = False
    audit: bool = False


@dataclass(frozen=True, slots=True)
class Rule:
    """One rewrite, named so the dry run can be read a category at a time."""

    name: str
    pattern: re.Pattern[str]
    replacement: str


# Ordered. `litellm.litellm_core_utils` has to be rewritten before the general `litellm.` rule
# reaches it, or the inner package keeps its redundant prefix.
IMPORT_RULES: Final[tuple[Rule, ...]] = (
    Rule(
        "core_utils, absolute",
        re.compile(rf"\b{OLD_PACKAGE}\.{OLD_CORE_UTILS}\b"),
        f"{NEW_PACKAGE}.{NEW_CORE_UTILS}",
    ),
    Rule(
        "core_utils, relative",
        re.compile(rf"^([ \t]*from[ \t]+\.+){OLD_CORE_UTILS}\b", re.MULTILINE),
        rf"\g<1>{NEW_CORE_UTILS}",
    ),
    Rule(
        "from the package's submodule",
        re.compile(rf"^([ \t]*)from[ \t]+{OLD_PACKAGE}\.", re.MULTILINE),
        rf"\g<1>from {NEW_PACKAGE}.",
    ),
    Rule(
        "from the package itself",
        re.compile(rf"^([ \t]*)from[ \t]+{OLD_PACKAGE}[ \t]+import\b", re.MULTILINE),
        rf"\g<1>from {NEW_PACKAGE} import",
    ),
    # `import litellm.x as name` binds only `name`, so the submodule import on its own is right here
    # and no old binding is needed. Matched before the unaliased form, which would otherwise take it.
    Rule(
        "import a submodule under another name",
        re.compile(rf"^([ 	]*)import[ 	]+{OLD_PACKAGE}\.([\w.]+)[ 	]+as[ 	]+(\w+)", re.MULTILINE),
        rf"\g<1>import {NEW_PACKAGE}.\g<2> as \g<3>",
    ),
    # `import litellm.utils` binds the name `litellm`, and callers then write `litellm.utils.foo`.
    # Importing the submodule alone would bind `token_iq` instead and every such call would break,
    # so the submodule import is kept for its side effect and the old name is bound beside it.
    Rule(
        "import a submodule",
        re.compile(rf"^([ \t]*)import[ \t]+{OLD_PACKAGE}\.([\w.]+)([ \t]*(?:\#.*)?)$", re.MULTILINE),
        rf"\g<1>import {NEW_PACKAGE}.\g<2>\g<3>\n\g<1>from token_iq import gateway as {OLD_PACKAGE}",
    ),
    Rule(
        "import the package under another name",
        re.compile(rf"^([ \t]*)import[ \t]+{OLD_PACKAGE}[ \t]+as[ \t]+(\w+)", re.MULTILINE),
        r"\g<1>from token_iq import gateway as \g<2>",
    ),
    Rule(
        "import the package",
        re.compile(rf"^([ \t]*)import[ \t]+{OLD_PACKAGE}([ \t]*(?:\#.*)?)$", re.MULTILINE),
        rf"\g<1>from token_iq import gateway as {OLD_PACKAGE}\g<2>",
    ),
)

DOTTED: Final = re.compile(rf"^{OLD_PACKAGE}(?:\.[A-Za-z_]\w*)+$")
"""A dotted path written as a whole string literal, matched against a literal's value rather than
against a file's text, because where the literal sits is what decides whether it moves."""

RESOLVING_CALLS: Final[frozenset[str]] = frozenset(
    {
        # mock.patch and friends take a dotted path and resolve it lazily, which is why a missed one
        # does not fail: the test goes green having patched nothing.
        "patch",
        "patch.object",
        "patch.dict",
        "patch.multiple",
        "mock.patch",
        "mock.patch.object",
        "mock.patch.dict",
        "mock.patch.multiple",
        "unittest.mock.patch",
        # Imports and package data by name.
        "import_module",
        "importlib.import_module",
        "__import__",
        "files",
        "resources.files",
        "importlib.resources.files",
        "resources.open_text",
        "importlib.resources.open_text",
        "read_binary",
        "resources.read_binary",
    }
)
"""Calls whose string arguments name a module or something inside one."""

RESOLVING_KEYWORDS: Final[frozenset[str]] = frozenset({"module_path", "target"})
"""Keyword arguments whose string value is a module path. `module_path=` is how `_lazy_features`
registers a router, and a missed one drops every route that module serves."""

RESOLVING_SUBSCRIPTS: Final[frozenset[str]] = frozenset({"sys.modules"})
"""`sys.modules["litellm.utils"]` and `sys.modules.get(...)`, which read the import cache by name."""

MODULE_PATH_REGISTRIES: Final[frozenset[str]] = frozenset(
    {
        # These files are nothing but tables of module paths, held as plain tuples and dicts with no
        # call around them, so no context rule can see them. Named here instead, one file at a time.
        "litellm/_lazy_imports_registry.py",
        "litellm/_lazy_features.py",
        "litellm/integrations/otel/logger.py",
    }
)

CONCATENATED_PREFIXES: Final[Mapping[str, str]] = MappingProxyType(
    {
        # litellm/llms/__init__.py builds a module path from a filesystem walk. The literal is just
        # the package prefix, so no shape-based rule can tell it from a telemetry namespace.
        'module_path = "litellm." + rel_path.replace(os.sep, ".")': (
            'module_path = "token_iq.gateway." + rel_path.replace(os.sep, ".")'
        ),
        # guardrail_registry.py and prompt_registry.py each build theirs with an f-string.
        'f"litellm.proxy.guardrails.guardrail_hooks.{item}"': (
            'f"token_iq.gateway.proxy.guardrails.guardrail_hooks.{item}"'
        ),
        'f"litellm.integrations.{item}"': 'f"token_iq.gateway.integrations.{item}"',
    }
)
"""Prefixes that are completed at runtime. Each is written out in full so a reviewer sees the line
that changes rather than a pattern that might match it."""


def tracked(pattern: str) -> tuple[pathlib.Path, ...]:
    out: Final = subprocess.run(
        ["git", "ls-files", pattern], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout
    return tuple(REPO / line for line in out.splitlines() if line)


def dotted_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{dotted_name(node.value)}.{node.attr}"
    return ""


def moving_literals(tree: ast.Module, *, whole_file: bool) -> tuple[ast.Constant, ...]:
    """Every string literal in this module that names something being moved.

    `whole_file` is for the registry files, where the paths sit in bare tuples and dicts with no call
    to read the context from. Everywhere else a literal has to be somewhere that resolves a name, and
    the default is to leave it: a telemetry attribute, a `call_type` value and a `mock_response`
    sentinel all look exactly like a module path, and renaming one of those is silent.
    """
    chosen: dict[int, ast.Constant] = {}  # rebind-ok: gathering nodes while walking the tree

    def take(node: ast.expr) -> None:
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and DOTTED.match(node.value):
            chosen[id(node)] = node

    for node in ast.walk(tree):
        if whole_file:
            if isinstance(node, ast.expr):
                take(node)
            continue
        if isinstance(node, ast.Call):
            name = dotted_name(node.func)
            if name in RESOLVING_CALLS or name.endswith(".patch"):
                for argument in node.args:
                    take(argument)
            for keyword in node.keywords:
                if keyword.arg in RESOLVING_KEYWORDS:
                    take(keyword.value)
            if dotted_name(node.func).rsplit(".", 1)[0] in RESOLVING_SUBSCRIPTS:
                for argument in node.args:
                    take(argument)
        if isinstance(node, ast.Subscript) and dotted_name(node.value) in RESOLVING_SUBSCRIPTS:
            take(node.slice)
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else (node.target,)
            if any("module_path" in dotted_name(t) for t in targets) and node.value is not None:
                take(node.value)

    return tuple(chosen.values())


def rewrite_strings(text: str, *, whole_file: bool) -> tuple[str, int]:
    """Rewrite the chosen literals in place, by position, leaving every other one alone."""
    try:
        tree: Final = ast.parse(text)
    except SyntaxError:
        return text, 0
    found: Final = sorted(
        moving_literals(tree, whole_file=whole_file),
        key=lambda node: (node.lineno, node.col_offset),
        reverse=True,
    )
    if not found:
        return text, 0

    lines = text.splitlines(keepends=True)  # rebind-ok: edited back to front, so offsets hold
    for node in found:
        if node.end_lineno is None or node.end_col_offset is None or node.lineno != node.end_lineno:
            continue
        line = lines[node.lineno - 1]
        literal = line[node.col_offset : node.end_col_offset]
        lines[node.lineno - 1] = (
            line[: node.col_offset] + literal.replace(OLD_PACKAGE, NEW_PACKAGE, 1) + line[node.end_col_offset :]
        )
    return "".join(lines), len(found)


def rewrite(text: str, *, whole_file: bool = False) -> tuple[str, Mapping[str, int]]:
    """Every rule applied to one file's text, with how many times each one fired."""
    counts: dict[str, int] = {}  # rebind-ok: a tally built while folding the rules over the text
    current = text  # rebind-ok: the fold's accumulator
    for rule in IMPORT_RULES:
        current, fired = rule.pattern.subn(rule.replacement, current)
        if fired:
            counts[rule.name] = fired
    for old, new in CONCATENATED_PREFIXES.items():
        if old in current:
            counts["prefix completed at runtime"] = counts.get("prefix completed at runtime", 0) + current.count(old)
            current = current.replace(old, new)
    current, strings = rewrite_strings(current, whole_file=whole_file)
    if strings:
        counts["dotted string in a resolving position"] = strings
    return current, MappingProxyType(counts)


LEFTOVER: Final = re.compile(rf"^[ \t]*(?:from|import)[ \t]+{OLD_PACKAGE}\b.*$", re.MULTILINE)
"""An import statement still naming the old package. The plan says to apply the codemod and then
fix what remains by hand, and this is what produces the list of what remains, instead of leaving it
to be found by whatever runs next."""


def leftovers(paths: Iterable[pathlib.Path]) -> tuple[str, ...]:
    """Import statements the rules would not rewrite, with where each one is.

    Run against the rewritten text rather than the original, so a line only appears when no rule
    claimed it. Text, not parsed imports, so a line inside a docstring counts: the single hit today is
    `import litellm, asyncio` in an example in one, which is prose and not an import. A real
    multi-target import would show here too, and no sane rule splits one.
    """
    return tuple(
        f"{named(path)}:{text[: found.start()].count(chr(10)) + 1}  {found.group().strip()}"
        for path in paths
        for text in (rewrite(path.read_text(encoding="utf-8"), whole_file=named(path) in MODULE_PATH_REGISTRIES)[0],)
        for found in LEFTOVER.finditer(text)
    )


def named(path: pathlib.Path) -> str:
    """Repo-relative where that means something, the whole path where it does not. Reporting a
    failure must never itself fail, which `relative_to` does for anything outside the repository."""
    return path.relative_to(REPO).as_posix() if path.is_relative_to(REPO) else path.as_posix()


def parses(text: str) -> bool:
    try:
        _ = ast.parse(text)
    except SyntaxError:
        return False
    return True


Rewriter = Callable[..., tuple[str, Mapping[str, int]]]


def run(
    paths: Iterable[pathlib.Path], *, write: bool, rewriter: Rewriter = rewrite
) -> tuple[Counter[str], tuple[str, ...]]:
    """`rewriter` is injected so the guard below can be tested with one that deliberately breaks a
    file. Without that, the guard is unexercised, which is the same as not having it."""
    totals: Counter[str] = Counter()  # rebind-ok: a tally across files
    broken: list[str] = []  # rebind-ok: files a rewrite would leave unparseable
    for path in paths:
        before = path.read_text(encoding="utf-8")
        after, counts = rewriter(before, whole_file=named(path) in MODULE_PATH_REGISTRIES)
        if after == before:
            continue
        if path.suffix == ".py" and parses(before) and not parses(after):
            broken.append(named(path))
            continue
        totals.update(counts)
        totals["files changed"] += 1
        if write:
            _ = path.write_text(after, encoding="utf-8")
    return totals, tuple(broken)


def main(argv: Sequence[str] | None = None) -> int:
    parser: Final = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--apply", action="store_true", help="write the rewrites")
    _ = parser.add_argument("--dry-run", action="store_true", help="report and change nothing")
    _ = parser.add_argument("--audit", action="store_true", help="list imports no rule would rewrite")
    options: Final = Options.model_validate(vars(parser.parse_args(argv)))
    if sum((options.apply, options.dry_run, options.audit)) != 1:
        sys.stderr.write("pass exactly one of --apply, --dry-run and --audit\n")
        return 2

    if not (REPO / OLD_PACKAGE / "__init__.py").exists():
        sys.stderr.write(f"{OLD_PACKAGE}/ is already gone; this pass runs before the folder moves\n")
        return 2

    if options.audit:
        remaining: Final = leftovers(tracked("*.py"))
        sys.stdout.write(f"{len(remaining)} import statement(s) no rule would rewrite\n")
        sys.stdout.write("".join(f"  {line}\n" for line in remaining))
        return 0

    totals, broken = run(tracked("*.py"), write=options.apply)

    report: Final = tuple(f"{count:>7}  {name}" for name, count in totals.most_common())
    sys.stdout.write(("\n".join(report) or "nothing to do") + "\n")
    if broken:
        sys.stderr.write(f"\n{len(broken)} file(s) would not parse after rewriting, left alone:\n")
        sys.stderr.write("\n".join(f"  {name}" for name in broken) + "\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
