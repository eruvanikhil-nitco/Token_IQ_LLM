"""Every `mock.patch` target naming a Token IQ module points at something that exists.

This is the one failure in a module move that does not announce itself. An import that moves
and is not updated raises `ModuleNotFoundError` on the first run. A patch target is a string
that `mock.patch` resolves lazily, so when a module moves underneath it the test does not
fail: it goes green having patched nothing, exercising the real collaborator or nothing at
all, and the thing it claimed to prove is no longer proved by anything.

Phase 3 moved 16 routers and 7 type modules with 11 such strings pointing into them. Nothing
in the suite would have caught a missed one.
"""

from __future__ import annotations

import ast
import importlib
import pathlib
import re
import warnings
from typing import Final

import pytest

REPO: Final = pathlib.Path(__file__).resolve().parents[2]
TESTS: Final = REPO / "tests"

# Only the paths this repository owns. A patch into a third-party package is that package's
# business and may legitimately name something created at runtime.
OURS: Final[tuple[str, ...]] = ("token_iq.", "litellm.")

TARGET: Final = re.compile(r"^[A-Za-z_][\w.]*$")


def _patch_targets() -> tuple[tuple[str, str, int], ...]:
    """Every string literal passed first to a `patch`-ish call, with where it came from."""
    return tuple(
        (path.relative_to(REPO).as_posix(), node.args[0].value, node.lineno)
        for path in TESTS.rglob("test_*.py")
        if "node_modules" not in path.parts
        for node in _calls(path)
        if node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
        and node.args[0].value.startswith(OURS)
        and TARGET.match(node.args[0].value)
    )


def _calls(path: pathlib.Path) -> tuple[ast.Call, ...]:
    try:
        with warnings.catch_warnings():
            # Reading other files' syntax, not compiling it: their bad escapes are not this
            # test's finding and drown out anything that is.
            warnings.simplefilter("ignore", SyntaxWarning)
            tree: Final = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return ()
    return tuple(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and _name_of(node.func) in {"patch", "patch.object", "mock.patch"}
    )


def _name_of(func: ast.expr) -> str:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return f"{_name_of(func.value)}.{func.attr}"
    return ""


def _resolves(target: str) -> bool:
    """Walk `a.b.c` as far as it imports, then as attributes, the way mock.patch does."""
    parts: Final = target.split(".")
    for split in range(len(parts) - 1, 0, -1):
        try:
            module = importlib.import_module(".".join(parts[:split]))
        except ImportError:
            continue
        obj: object = module
        for attr in parts[split:]:
            if not hasattr(obj, attr):
                return False
            obj = getattr(obj, attr)
        return True
    return False


TOKEN_IQ_TARGETS: Final = tuple(t for t in _patch_targets() if t[1].startswith("token_iq."))


class TestTokenIqPatchTargets:
    def test_there_are_some_to_check(self) -> None:
        """Guards the test below, which passes trivially if the scan finds nothing."""
        assert TOKEN_IQ_TARGETS, "no patch targets into token_iq were found; the scan is broken"

    @pytest.mark.parametrize(("where", "target", "line"), TOKEN_IQ_TARGETS)
    def test_the_target_exists(self, where: str, target: str, line: int) -> None:
        assert _resolves(target), f"{where}:{line} patches {target}, which resolves to nothing"
