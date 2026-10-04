"""Which modules are provably reached, and which the parser simply cannot speak for.

**Reachability proves "keep". It never proves "delete".**

Python resists static analysis. A module can be loaded by `importlib` with a name built at
runtime, by `getattr` on a package, by a plugin registry, or by a config string. None of
those are visible to `ast`. So this module emits two verdicts, `used` and `unproven`, and
there is deliberately no third. Turning `unproven` into a deletion is a person's job, done
with the folder open.

Every dynamic import it could not follow is collected and reported rather than dropped. Those
are the holes in the evidence, and an inventory built on this has to say how many there were
before claiming confidence.
"""

from __future__ import annotations

import ast
import dataclasses
import pathlib
import re
from collections.abc import Iterable, Mapping, Sequence
from typing import Final, Literal

Verdict = Literal["used", "used-type-only", "unproven"]

DYNAMIC_CALLS: Final[frozenset[str]] = frozenset({"import_module", "__import__"})

# A dotted name that could be a module path. Used only inside files that already perform an
# unresolvable dynamic import, because outside those a dotted string is far more likely to be
# prose or a log message than an import.
MODULE_SHAPED: Final = re.compile(r"^\.?[A-Za-z_][\w.]*$")


@dataclasses.dataclass(frozen=True, slots=True)
class Unresolved:
    """A dynamic import whose target could not be read, with where to go and look."""

    module: str
    line: int
    source: str


@dataclasses.dataclass(frozen=True, slots=True)
class Imports:
    runtime: tuple[str, ...]
    type_only: tuple[str, ...]
    unresolved: tuple[Unresolved, ...]
    unparsed: bool
    literal_candidates: tuple[str, ...] = ()
    """Dotted strings in a file that imports by name, which are therefore import candidates."""


@dataclasses.dataclass(frozen=True, slots=True)
class ModuleVerdict:
    module: str
    verdict: Verdict
    reached_from: tuple[str, ...]


@dataclasses.dataclass(frozen=True, slots=True)
class Graph:
    verdicts: Mapping[str, ModuleVerdict]
    unresolved: tuple[Unresolved, ...]
    entry_points: tuple[str, ...]
    unparsed: tuple[str, ...]


def module_name_for(path: pathlib.Path, root: pathlib.Path) -> str:
    relative: Final = path.relative_to(root).with_suffix("")
    parts: Final = tuple(relative.parts)
    trimmed: Final = parts[:-1] if parts and parts[-1] == "__init__" else parts
    return ".".join(trimmed)


def _absolute(node: ast.ImportFrom, module: str) -> str:
    if node.level == 0:
        return node.module or ""
    # A relative import counts levels up from the importing module's package, so the first
    # level is the package itself rather than its parent.
    owning: Final = module.split(".")[:-1]
    base: Final = owning[: len(owning) - (node.level - 1)] if node.level > 1 else owning
    return ".".join((*base, node.module)) if node.module else ".".join(base)


class _Collector(ast.NodeVisitor):
    def __init__(self, module: str) -> None:
        self.module: Final = module
        self.runtime: Final[set[str]] = set()  # mutable-ok: accumulated during a single AST walk
        self.type_only: Final[set[str]] = set()  # mutable-ok: accumulated during a single AST walk
        self.unresolved: Final[list[Unresolved]] = []  # mutable-ok: accumulated during a single AST walk
        self.literals: Final[set[str]] = set()  # mutable-ok: accumulated during a single AST walk
        self._in_type_block = False  # rebind-ok: tracks nesting during the walk

    def _record(self, name: str) -> None:
        if not name:
            return
        (self.type_only if self._in_type_block else self.runtime).add(name)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self._record(alias.name)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        base: Final = _absolute(node, self.module)
        self._record(base)
        # `from pkg import thing` cannot be told apart from `from pkg import submodule`
        # without importing, so both candidates are recorded and the resolver keeps whichever
        # is a real module. Missing an edge is the failure that makes live code look dead.
        for alias in node.names:
            if alias.name != "*":
                self._record(f"{base}.{alias.name}" if base else alias.name)

    def visit_If(self, node: ast.If) -> None:
        if _is_type_checking(node.test):
            was: Final = self._in_type_block
            self._in_type_block = True
            for child in node.body:
                self.visit(child)
            self._in_type_block = was
            for child in node.orelse:
                self.visit(child)
            return
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, str) and "." in node.value and MODULE_SHAPED.match(node.value):
            self.literals.add(node.value)

    def visit_Call(self, node: ast.Call) -> None:
        if _called_name(node.func) in DYNAMIC_CALLS:
            first: Final = node.args[0] if node.args else None
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                self._record(first.value)
            else:
                # The whole point of this branch: say so loudly rather than let the target
                # look unreferenced.
                self.unresolved.append(
                    Unresolved(module=self.module, line=node.lineno, source=ast.unparse(node)[:160])
                )
        self.generic_visit(node)


def _called_name(func: ast.expr) -> str:
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return ""


def _is_type_checking(test: ast.expr) -> bool:
    if isinstance(test, ast.Name):
        return test.id == "TYPE_CHECKING"
    if isinstance(test, ast.Attribute):
        return test.attr == "TYPE_CHECKING"
    return False


def imports_of(source: str, module: str) -> Imports:
    try:
        tree: Final = ast.parse(source)
    except SyntaxError:
        return Imports(runtime=(), type_only=(), unresolved=(), unparsed=True)

    collector: Final = _Collector(module)
    collector.visit(tree)
    return Imports(
        runtime=tuple(sorted(collector.runtime)),
        type_only=tuple(sorted(collector.type_only - collector.runtime)),
        unresolved=tuple(collector.unresolved),
        unparsed=False,
        # Collected for every file; `analyse` decides which files are allowed to use them,
        # so prose in an ordinary module cannot invent an edge.
        literal_candidates=tuple(sorted(collector.literals)),
    )


def _resolved_literals(module: str, found: Imports) -> tuple[str, ...]:
    """Absolute forms of this file's module-shaped literals, relative ones anchored to it."""
    package: Final = ".".join(module.split(".")[:-1])
    return tuple(
        f"{package}{candidate}" if candidate.startswith(".") else candidate
        for candidate in found.literal_candidates
    )


def _known_target(name: str, known: frozenset[str]) -> str | None:
    """An import names a module or something inside one; walk up until it names a module."""
    parts: Final = name.split(".")
    for stop in range(len(parts), 0, -1):
        candidate = ".".join(parts[:stop])
        if candidate in known:
            return candidate
    return None


def analyse(
    root: pathlib.Path,
    entry_points: Sequence[str],
    skip: Iterable[str] = (),
    literal_sources: Iterable[str] = (),
) -> Graph:
    skipped: Final = tuple(skip)
    named_sources: Final = frozenset(literal_sources)
    files: Final = {
        module_name_for(path, root): path
        for path in sorted(root.rglob("*.py"))
        if not any(part in {"node_modules", ".venv", "__pycache__", ".git"} for part in path.parts)
        and not any(path.relative_to(root).as_posix().startswith(prefix) for prefix in skipped)
    }
    known: Final = frozenset(files)

    edges: Final[dict[str, Imports]] = {}  # mutable-ok: built once over the file list
    for name, path in files.items():
        edges[name] = imports_of(path.read_text(encoding="utf-8", errors="ignore"), name)

    runtime_reached: Final[dict[str, str]] = {}  # mutable-ok: breadth-first frontier
    type_reached: Final[dict[str, str]] = {}  # mutable-ok: breadth-first frontier
    frontier: list[tuple[str, str]] = [(e, e) for e in entry_points if e in known]  # rebind-ok: the walk's queue

    while frontier:
        current, origin = frontier.pop()
        if current in runtime_reached:
            continue
        runtime_reached[current] = origin
        contributes: Final = bool(edges[current].unresolved) or current in named_sources
        literals: Final = _resolved_literals(current, edges[current]) if contributes else ()
        for target in (*edges[current].runtime, *literals):
            resolved = _known_target(target, known)
            if resolved is not None and resolved not in runtime_reached:
                frontier.append((resolved, origin))
        for target in edges[current].type_only:
            resolved = _known_target(target, known)
            if resolved is not None:
                type_reached.setdefault(resolved, origin)

    verdicts: Final = {
        name: ModuleVerdict(
            module=name,
            verdict=(
                "used" if name in runtime_reached else "used-type-only" if name in type_reached else "unproven"
            ),
            reached_from=(
                (runtime_reached[name],) if name in runtime_reached
                else (type_reached[name],) if name in type_reached
                else ()
            ),
        )
        for name in sorted(known)
    }

    return Graph(
        verdicts=verdicts,
        unresolved=tuple(u for name in sorted(known) for u in edges[name].unresolved),
        entry_points=tuple(e for e in entry_points if e in known),
        unparsed=tuple(name for name in sorted(known) if edges[name].unparsed),
    )
