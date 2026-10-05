"""Every quality gate watches `token_iq/`, not only `litellm/`.

Phase 3 moves Token IQ's code into a package of its own. Three gates name their target as a
literal string, so the moment that package exists its modules leave type checking and both
lint budgets. Nothing fails. The budgets even appear to improve, because the violations they
were counting moved somewhere nothing is looking.

This reads configuration rather than running the gates: the failure being guarded is a path
going unwatched, not a rule misbehaving.
"""

from __future__ import annotations

import fnmatch
import json
import pathlib
import re
from collections.abc import Sequence
from typing import Final

import pytest

REPO: Final = pathlib.Path(__file__).resolve().parents[2]

GATES: Final[tuple[str, ...]] = (
    "scripts/ruff_strict_gate.py",
    "scripts/type_discipline_gate.py",
)


def _targets_of(source: str) -> tuple[str, ...]:
    """The paths a gate scans, however it spells them."""
    single: Final = re.search(r'^TARGET\s*=\s*"([^"]+)"', source, re.MULTILINE)
    if single:
        return (single.group(1),)
    plural: Final = re.search(r"^TARGETS[^=]*=\s*\(([^)]*)\)", source, re.MULTILINE | re.DOTALL)
    if plural:
        return tuple(re.findall(r'"([^"]+)"', plural.group(1)))
    return ()


class TestTypeChecking:
    def test_pyright_includes_token_iq(self) -> None:
        config: Final = json.loads((REPO / "pyrightconfig.json").read_text(encoding="utf-8"))
        assert "token_iq" in config["include"], (
            f"basedpyright would not see token_iq; include = {config['include']}"
        )

    def test_pyright_still_includes_the_engine(self) -> None:
        """Adding one must not replace the other."""
        config: Final = json.loads((REPO / "pyrightconfig.json").read_text(encoding="utf-8"))
        assert "litellm" in config["include"]


class TestLintGates:
    @pytest.mark.parametrize("gate", GATES)
    def test_the_gate_scans_token_iq(self, gate: str) -> None:
        targets: Final = _targets_of((REPO / gate).read_text(encoding="utf-8"))
        assert targets, f"{gate} declares no target this test can read"
        assert "token_iq" in targets, f"{gate} scans {targets}, so token_iq is unwatched"

    @pytest.mark.parametrize("gate", GATES)
    def test_the_gate_still_scans_the_engine(self, gate: str) -> None:
        assert "litellm" in _targets_of((REPO / gate).read_text(encoding="utf-8"))


class TestTheMakefile:
    def test_ruff_covers_token_iq(self) -> None:
        """`lint-ruff` cds into litellm and runs `ruff check .`, which cannot see a sibling."""
        makefile: Final = (REPO / "Makefile").read_text(encoding="utf-8")
        target: Final = re.search(r"^lint-ruff:.*?\n(?=\w|\n\w)", makefile, re.MULTILINE | re.DOTALL)
        assert target, "lint-ruff target not found"
        assert "token_iq" in target.group(0), f"lint-ruff does not lint token_iq:\n{target.group(0)}"

    def test_format_check_covers_token_iq(self) -> None:
        makefile: Final = (REPO / "Makefile").read_text(encoding="utf-8")
        target: Final = re.search(r"^format-check:.*?\n(?=\w|\n\w)", makefile, re.MULTILINE | re.DOTALL)
        assert target, "format-check target not found"
        assert "token_iq" in target.group(0), f"format-check does not check token_iq:\n{target.group(0)}"

class TestEveryTokenIqFileIsReallyChecked:
    """`include` naming the package is not the same as every file in it being checked.

    An `exclude` pattern can quietly swallow a subtree, and the count of files the checker sees
    is the only thing that says so. Phase 3 moved 59 modules between two watched trees; this is
    what proves none of them fell down the gap.
    """

    @staticmethod
    def _excluded(path: str, patterns: Sequence[str]) -> bool:
        return any(
            fnmatch.fnmatch(path, pattern) or path == pattern or path.startswith(pattern.rstrip("*") + "/")
            for pattern in patterns
        )

    def test_no_token_iq_module_is_excluded(self) -> None:
        config: Final = json.loads((REPO / "pyrightconfig.json").read_text(encoding="utf-8"))
        excluded: Final = tuple(
            path.relative_to(REPO).as_posix()
            for path in (REPO / "token_iq").rglob("*.py")
            if self._excluded(path.relative_to(REPO).as_posix(), config["exclude"])
        )
        assert not excluded, f"these are inside token_iq but excluded from type checking: {excluded}"

    def test_the_package_is_not_empty(self) -> None:
        """Guards the test above, which passes trivially if token_iq holds nothing."""
        assert len(tuple((REPO / "token_iq").rglob("*.py"))) > 40
