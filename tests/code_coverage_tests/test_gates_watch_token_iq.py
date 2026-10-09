"""Every quality gate watches the whole of `token_iq/`.

Phase 3 moved Token IQ's code into a package of its own and phase 6 moved the engine inside it.
Three gates name their target as a literal string, so a path can leave type checking and both
lint budgets the moment it moves. Nothing fails. The budgets even appear to improve, because the
violations they were counting moved somewhere nothing is looking.

Two tests here used to demand the gates and the type checker also name `litellm`, which was the
right property while the engine was a sibling package. It is `token_iq/gateway/` now, so one
target covers both, and the pair had become a demand for the old name. What replaced them checks
the thing that still matters: that the engine subtree is really reached.

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

    def test_the_engine_subtree_is_reached(self) -> None:
        """Naming the package is only coverage if the engine inside it is reached. `include` also
        listed `litellm`, a directory phase 6 deleted, so the entry read as coverage and resolved
        to nothing."""
        config: Final = json.loads((REPO / "pyrightconfig.json").read_text(encoding="utf-8"))
        roots: Final = tuple(entry for entry in config["include"] if (REPO / entry).exists())

        assert roots == tuple(config["include"]), "an include entry names nothing"
        assert any((REPO / entry / "gateway").is_dir() for entry in roots), "the engine is unwatched"


class TestLintGates:
    @pytest.mark.parametrize("gate", GATES)
    def test_the_gate_scans_token_iq(self, gate: str) -> None:
        targets: Final = _targets_of((REPO / gate).read_text(encoding="utf-8"))
        assert targets, f"{gate} declares no target this test can read"
        assert "token_iq" in targets, f"{gate} scans {targets}, so token_iq is unwatched"

    @pytest.mark.parametrize("gate", GATES)
    def test_every_target_the_gate_names_is_really_there(self, gate: str) -> None:
        """A gate pointed at a path that does not exist scans nothing and says so to nobody,
        which is how the engine would leave both budgets without a single test going red."""
        targets: Final = _targets_of((REPO / gate).read_text(encoding="utf-8"))
        missing: Final = tuple(target for target in targets if not (REPO / target).exists())

        assert not missing, f"{gate} scans {missing}, which is not on disk"


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

EXCLUDED_ON_PURPOSE: Final[dict[str, str]] = {
    "token_iq/gateway/types/utils.py": (
        "1,470 diagnostics across this file and the one below, almost all missing parameter and "
        "argument types on inherited shapes. The exclusion arrived with an upstream feature commit "
        "and no reason; keeping it is a budget decision, so it waits on the basedpyright ratchet "
        "rather than on this test"
    ),
    "token_iq/gateway/proxy/_types.py": "the other half of the same measurement",
}
"""Files inside the package that type checking skips on purpose, each with its reason.

Measured by lifting both exclusions and running basedpyright over the two files. Reading them in
would add 1,470 diagnostics to a budget the ratchet exists to drive down, which is a decision to
take deliberately rather than as a side effect of a test going green.
"""


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
        unexplained: Final = tuple(path for path in excluded if path not in EXCLUDED_ON_PURPOSE)

        assert not unexplained, (
            f"these are inside token_iq but excluded from type checking: {unexplained}. "
            "Remove the exclusion, or add it to EXCLUDED_ON_PURPOSE with a reason."
        )

    def test_every_deliberate_exclusion_is_still_excluded(self) -> None:
        """An entry nobody needs any more keeps a file out of type checking by habit."""
        config: Final = json.loads((REPO / "pyrightconfig.json").read_text(encoding="utf-8"))
        stale: Final = tuple(
            path
            for path in EXCLUDED_ON_PURPOSE
            if not self._excluded(path, config["exclude"]) or not (REPO / path).is_file()
        )

        assert not stale, f"these are listed as deliberate but are not excluded any more: {stale}"

    def test_the_package_is_not_empty(self) -> None:
        """Guards the test above, which passes trivially if token_iq holds nothing."""
        assert len(tuple((REPO / "token_iq").rglob("*.py"))) > 40
