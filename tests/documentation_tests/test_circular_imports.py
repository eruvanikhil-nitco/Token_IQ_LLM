"""No annotation inside the engine names the engine's own package.

`x: token_iq.gateway.ModelResponse` resolves the package at import time, so a module annotated that way
has to import the package that is importing it. The engine holds none today, and this is what keeps it
that way.

Until phase 9 this ran as `cd litellm && python ../tests/documentation_tests/test_circular_imports.py`,
against a folder phase 6 had deleted, looking for a prefix phase 6 had renamed, and printing what it
found without ever failing. Three ways of reading zero, none of them the invariant. Hence the guard test
below: a detector that cannot detect reads exactly the same as a tree that is clean.
"""

from __future__ import annotations

import ast
import pathlib
import sys
from collections.abc import Iterator
from typing import Final

from pydantic import BaseModel

REPO: Final = pathlib.Path(__file__).resolve().parents[2]
ENGINE: Final = REPO / "token_iq" / "gateway"
PACKAGE: Final = "token_iq.gateway."

SKIP: Final[tuple[str, ...]] = ("__pycache__", ".venv", "venv", "myenv", "_experimental/out")


class Annotated(BaseModel, frozen=True):
    """One annotation that names the engine package, and where to find it."""

    file: str
    line: int
    hint: str


def _annotations(tree: ast.AST) -> Iterator[ast.expr]:
    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign):
            yield node.annotation
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            yield from (
                argument.annotation
                for argument in (
                    *node.args.posonlyargs,
                    *node.args.args,
                    *node.args.kwonlyargs,
                    node.args.vararg,
                    node.args.kwarg,
                )
                if argument is not None and argument.annotation is not None
            )
            if node.returns is not None:
                yield node.returns


def _named(path: pathlib.Path) -> str:
    return path.relative_to(REPO).as_posix()


def _scanned(root: pathlib.Path) -> tuple[pathlib.Path, ...]:
    return tuple(path for path in sorted(root.rglob("*.py")) if not any(part in _named(path) for part in SKIP))


def found_in(source: str, name: str = "<string>") -> tuple[Annotated, ...]:
    """Every annotation in one module that names the engine package."""
    try:
        tree: Final = ast.parse(source)
    except SyntaxError:
        return ()
    return tuple(
        Annotated(file=name, line=node.lineno, hint=hint)
        for node in _annotations(tree)
        if PACKAGE in (hint := ast.unparse(node))
    )


def found_under(root: pathlib.Path) -> tuple[Annotated, ...]:
    return tuple(
        one
        for path in _scanned(root)
        for one in found_in(path.read_text(encoding="utf-8-sig", errors="replace"), _named(path))
    )


def test_no_annotation_names_the_engine_package() -> None:
    offenders: Final = found_under(ENGINE)
    assert not offenders, "these annotations risk a circular import: " + ", ".join(
        f"{one.file}:{one.line} {one.hint}" for one in offenders
    )


def test_the_detector_can_detect() -> None:
    """Said against annotations it must catch, because an empty result is also what a dead scan returns."""
    caught: Final = found_in(
        "\n".join(
            (
                f"total: {PACKAGE}Usage = x",
                f"def one(response: {PACKAGE}ModelResponse) -> None: ...",
                f"async def two(*args: {PACKAGE}Thing, **kw: {PACKAGE}Other) -> {PACKAGE}Result: ...",
                f"def three(a, /, b: {PACKAGE}Four, *, c: {PACKAGE}Five) -> None: ...",
            )
        )
    )

    assert len(caught) == 7, caught


def test_an_ordinary_annotation_is_left_alone() -> None:
    assert found_in("def one(x: int) -> ModelResponse: ...") == ()


def test_the_engine_is_really_being_scanned() -> None:
    """Guards the invariant above, which passes trivially if the walk reaches nothing."""
    assert len(_scanned(ENGINE)) > 1000


if __name__ == "__main__":
    offending: Final = found_under(ENGINE)
    for found in offending:
        sys.stdout.write(f"{found.file}:{found.line} - {found.hint}\n")
    sys.stdout.write(f"{len(offending)} annotation(s) naming {PACKAGE.rstrip('.')}\n")
    sys.exit(1 if offending else 0)
