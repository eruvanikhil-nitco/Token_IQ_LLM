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
import builtins
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


def _creates(node: ast.Call) -> bool:
    """Whether the call passes `create=True`, which says outright that the attribute is not there yet.

    `mock.patch` then makes it, so asking whether it resolves is asking the wrong question.
    """
    return any(
        keyword.arg == "create" and isinstance(keyword.value, ast.Constant) and keyword.value.value is True
        for keyword in node.keywords
    )


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
        and not _creates(node)
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
    """Walk `a.b.c` as far as it imports, then as attributes, the way mock.patch does.

    Two things mock.patch accepts that a plain `hasattr` walk does not, and both are about what is true
    at import time rather than about whether the path is right:

    - An attribute that exists and holds `None`. `proxy_server.llm_router` is declared
      `Router | None = None` and is built when the proxy starts, so `llm_router.acompletion` is a
      correct target that cannot be walked before then. The module path is what this gate is for
    - A builtin named as the last step. `patch("...some_module.isinstance")` patches the builtin the
      module calls, and a module does not carry builtins as attributes, so mock reaches for `builtins`
    """
    parts: Final = target.split(".")
    for split in range(len(parts) - 1, 0, -1):
        try:
            module = importlib.import_module(".".join(parts[:split]))
        except ImportError:
            continue
        obj: object = module
        rest = parts[split:]  # rebind-ok: one slice per candidate split of the dotted path
        for position, attr in enumerate(rest):
            if obj is None:
                return True
            if not hasattr(obj, attr):
                return position == len(rest) - 1 and hasattr(builtins, attr)
            obj = getattr(obj, attr)  # pyright: ignore[reportAny]  # walking an unannotated module tree
        return True
    return False


TOKEN_IQ_TARGETS: Final = tuple(t for t in _patch_targets() if t[1].startswith("token_iq."))

STALE_TARGETS: Final = tuple(t for t in _patch_targets() if t[1].startswith("litellm."))
"""Targets still naming the package by the name it had before phase 6 moved it.

Every one of these is now wrong, so they are a failure rather than something to skip. Filtering them
out is how 32 of them survived the move: each is a module path written as two adjacent string literals,
which Python folds into one value spanning two lines, and the pass that rewrote the rest skipped any
literal that was not on a single line."""


class TestTokenIqPatchTargets:
    def test_there_are_some_to_check(self) -> None:
        """Guards the test below, which passes trivially if the scan finds nothing."""
        assert TOKEN_IQ_TARGETS, "no patch targets into token_iq were found; the scan is broken"

    @pytest.mark.parametrize(("where", "target", "line"), TOKEN_IQ_TARGETS)
    def test_the_target_exists(self, where: str, target: str, line: int) -> None:
        assert _resolves(target), f"{where}:{line} patches {target}, which resolves to nothing"


class TestNoTargetNamesTheOldPackage:
    def test_no_patch_target_still_names_the_package_by_its_old_name(self) -> None:
        """A target naming `litellm.` resolves to nothing now, and `mock.patch` only finds out when the
        test enters the patch, so this says it at collection time instead."""
        assert not STALE_TARGETS, chr(10).join(
            f"{where}:{line} patches {target}, which moved to token_iq.gateway in phase 6"
            for where, target, line in STALE_TARGETS
        )


ENGINE_PATH: Final = re.compile(r"^token_iq(\.[A-Za-z_][A-Za-z0-9_]*)+$")
"""A dotted path into the engine and nothing else. `TARGET` above is loose enough to match a hostname, and
`litellm.example.com` appears in a test as one."""

DELIBERATELY_ABSENT: Final[frozenset[str]] = frozenset(
    {
        # A fixture in the mutation report's own test, standing in for a mutated function.
        "token_iq.gateway.proxy.management_endpoints.key_management_endpoints.x_2",
        # The snapshot test asserts what happens when a lazy import names nothing.
        "token_iq.gateway.proxy.this_module_does_not_exist",
    }
)
"""Paths a test names on purpose because nothing is there. Each needs a reason beside it."""


def _dotted_paths_outside_patches() -> tuple[tuple[str, str, int], ...]:
    """Every dotted path into the engine written as a string somewhere other than a `patch` call.

    The gate above sees only the first argument of a `patch`-ish call, and a target held in a
    `parametrize` list is not that. Three tests patched `litellm.afile_delete` from one of those lists and
    had been failing since phase 6 moved the package, with nothing saying why: `mock.patch` reports a
    missing module only once a test enters the patch, and these were failing inside a suite that already
    could not import the enterprise package.
    """
    return tuple(
        (path.relative_to(REPO).as_posix(), node.value, node.lineno)
        for path in TESTS.rglob("test_*.py")
        if "node_modules" not in path.parts
        for tree in (_parsed(path),)
        if tree is not None
        for patched in (
            {
                id(call.args[0])
                for call in ast.walk(tree)
                if isinstance(call, ast.Call) and call.args and isinstance(call.args[0], ast.Constant)
            },
        )
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and ENGINE_PATH.match(node.value)
        and id(node) not in patched
        and node.value not in DELIBERATELY_ABSENT
    )


def _parsed(path: pathlib.Path) -> ast.Module | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return None


DOTTED_PATHS: Final = _dotted_paths_outside_patches()


def _names_something(target: str) -> bool:
    """Whether this path names a module or an attribute.

    `_resolves` above deliberately starts one segment in, because that is what `mock.patch` does: it imports
    the parent and reaches for the last part as an attribute. A path in a `parametrize` list is often a whole
    module path instead, and `token_iq.gateway.proxy.proxy_server` is not an attribute of
    `token_iq.gateway.proxy` until something has imported it.
    """
    try:
        _ = importlib.import_module(target)
    except ImportError:
        return _resolves(target)
    return True


class TestDottedPathsOutsidePatchCalls:
    def test_there_are_some_to_check(self) -> None:
        assert DOTTED_PATHS, "no dotted paths into token_iq were found outside patch calls; the scan is broken"

    @pytest.mark.parametrize(("where", "target", "line"), DOTTED_PATHS)
    def test_the_path_exists(self, where: str, target: str, line: int) -> None:
        """Most of these are patch targets held in a `parametrize` list. A few name a module for some other
        reason, and those should resolve too, so one rule covers both."""
        assert _names_something(target), f"{where}:{line} names {target}, which resolves to nothing"
