"""The Token IQ tests keep the isolation they had before they moved.

pytest finds fixtures and hook implementations by name in the conftest files along a test's own
directory path. A test moved out from under a conftest loses every autouse fixture and every hook
in it, with no error and nothing absent from the run. The moved test passes.

What breaks is the next test in the same xdist worker. `tests/test_litellm/proxy/conftest.py`
states the mechanism: a leaked `master_key` flips the auth short-circuit in `user_api_key_auth`
so unrelated tests return 401 instead of 200, and a leaked `llm_router` makes the PTU rollup
count another test's deployments as the proxy's own. That arrives days later, in a file nobody
touched, and looks like flakiness.

So this reads the conftests and compares the names, because the failure being guarded is a name
going missing rather than a fixture misbehaving. It is deliberately not a test that runs the
suite: a suite that passes is exactly what the broken case looks like.
"""

from __future__ import annotations

import ast
import pathlib
from typing import Final

import pytest

REPO: Final = pathlib.Path(__file__).resolve().parents[2]

# Each Token IQ conftest, and the conftest whose isolation it has to carry over.
INHERITS: Final[tuple[tuple[str, str], ...]] = (
    ("tests/token_iq/conftest.py", "tests/test_litellm/conftest.py"),
    ("tests/token_iq/api/conftest.py", "tests/test_litellm/proxy/conftest.py"),
    ("tests/token_iq/policy/conftest.py", "tests/test_litellm/proxy/conftest.py"),
)


def _tree(path: str) -> ast.Module:
    return ast.parse((REPO / path).read_text(encoding="utf-8"))


def _must_carry_over(path: str) -> frozenset[str]:
    """Autouse fixtures and hooks: the names pytest applies without a test asking for them.

    A named fixture a test requests explicitly fails loudly when it is missing, so it needs no
    guard. These do not: nothing requests them, so nothing notices their absence.
    """
    return frozenset(
        node.name
        for node in _tree(path).body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and (
            node.name.startswith("pytest_")
            or any("autouse" in ast.unparse(d) for d in node.decorator_list)
        )
    )


def _imported_by(path: str) -> frozenset[str]:
    return frozenset(
        alias.name
        for node in _tree(path).body
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    )


class TestIsolationCarriesOver:
    @pytest.mark.parametrize(("mirror", "source"), INHERITS)
    def test_every_autouse_fixture_and_hook_is_re_exported(self, mirror: str, source: str) -> None:
        missing: Final = _must_carry_over(source) - _imported_by(mirror)
        assert not missing, (
            f"{mirror} does not re-export {sorted(missing)} from {source}, so tests under it run "
            f"without that isolation and leak into whatever shares their xdist worker"
        )

    @pytest.mark.parametrize(("mirror", "source"), INHERITS)
    def test_the_source_still_has_something_to_carry_over(self, mirror: str, source: str) -> None:
        """Guards the test above, which passes trivially if the source conftest is emptied."""
        assert _must_carry_over(source), f"{source} defines no autouse fixture or hook"

    @pytest.mark.parametrize(("mirror", "_source"), INHERITS)
    def test_the_mirror_exists(self, mirror: str, _source: str) -> None:
        assert (REPO / mirror).is_file()


class TestTheHookPairStaysAHookPair:
    """`pytest_runtest_setup` and `pytest_runtest_teardown` cannot become an autouse fixture.

    The original conftest explains why: such a fixture requests `monkeypatch`, so `monkeypatch`'s
    undo stack unwinds after every other finalizer, and a test that patches a global while a
    fixture holds it patched records the fixture's mock as the original. `monkeypatch.undo` then
    re-plants that mock after all the restores have run, poisoning the global for the rest of the
    worker. Anyone tidying this into a fixture should fail here first.
    """

    SOURCE: Final = "tests/test_litellm/proxy/conftest.py"

    def test_both_halves_of_the_pair_are_defined(self) -> None:
        defined: Final = _must_carry_over(self.SOURCE)
        assert {"pytest_runtest_setup", "pytest_runtest_teardown"} <= defined, sorted(defined)

    @pytest.mark.parametrize("mirror", [m for m, s in INHERITS if s.endswith("proxy/conftest.py")])
    def test_both_halves_are_re_exported_together(self, mirror: str) -> None:
        """One half without the other snapshots and never restores, or restores nothing."""
        imported: Final = _imported_by(mirror)
        assert ("pytest_runtest_setup" in imported) == ("pytest_runtest_teardown" in imported), (
            f"{mirror} re-exports one half of the hook pair without the other"
        )
