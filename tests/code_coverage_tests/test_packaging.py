"""What the wheel is told to ship, and that a job checks what it really shipped.

maturin builds the one Python package `module-name` points at. Data files inside that package
ship with it; anything outside needs `tool.maturin.include`, and naming it there turned out not
to be enough. The price list sat at the repository root under `data/pricing/`, was named in the
include list with a comment saying that is what made it ship, and the built wheel held one
top-level tree anyway, so the published image could not import its own engine. It is package
data now, under `token_iq/pricing/data/`.

A checkout notices none of this, because every directory is right there on `sys.path`.

These are the cheap half. They read configuration, so they run anywhere and say nothing about
what a real build produces. `.github/scripts/verify_wheel_contents.py` is the other half: it
opens the built wheel, installs it, and imports from outside the checkout. The last test here
exists so that script cannot quietly stop being called.
"""

from __future__ import annotations

import pathlib
import tomllib
from typing import Final

import pytest
import yaml

REPO: Final = pathlib.Path(__file__).resolve().parents[2]
VERIFIER: Final = ".github/scripts/verify_wheel_contents.py"

# Every directory of non-Python data an installed copy needs. Each is inside the package, which
# is what makes a wheel carry it; the include list names them as well, and the names are what
# these check. A path that moves out of `token_iq/` is the failure that killed the image, so
# `test_the_tree_is_inside_the_package` is the one to read first.
MUST_SHIP: Final[tuple[str, ...]] = (
    "token_iq/pricing/data",
    "token_iq/gateway/proxy/_experimental/out",
    "token_iq/gateway/router_strategy/complexity_router/artifacts",
)


@pytest.fixture(scope="module")
def maturin() -> dict[str, object]:
    config: Final = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    return config["tool"]["maturin"]


class TestTheIncludeList:
    @pytest.mark.parametrize("tree", MUST_SHIP)
    def test_the_tree_is_named(self, tree: str, maturin: dict[str, object]) -> None:
        include: Final = tuple(str(entry) for entry in maturin.get("include", ()))
        assert any(entry.startswith(f"{tree}/") for entry in include), (
            f"{tree}/ is not packaged, so an installed copy would not have it. include = {include}"
        )

    @pytest.mark.parametrize("tree", MUST_SHIP)
    def test_the_tree_is_inside_the_package(self, tree: str) -> None:
        """The one that would have caught it. Naming a tree in `include` did not make a wheel
        carry it when the tree sat outside the package; being inside does."""
        assert pathlib.Path(tree).parts[0] == "token_iq"
        assert (REPO / tree).is_relative_to(REPO / "token_iq")

    def test_the_package_maturin_builds_is_still_the_engine(self, maturin: dict[str, object]) -> None:
        """If this ever changes, which trees need naming in `include` changes with it."""
        assert str(maturin["module-name"]).startswith("token_iq.gateway.")

    @pytest.mark.parametrize("tree", MUST_SHIP)
    def test_the_tree_exists_on_disk(self, tree: str) -> None:
        """An include entry pointing at nothing packages nothing, and says so to no one."""
        assert (REPO / tree).is_dir()


class TestSomethingChecksTheRealWheel:
    def test_the_verifier_exists(self) -> None:
        assert (REPO / VERIFIER).is_file(), f"{VERIFIER} is gone; nothing opens the built wheel"

    def test_a_workflow_runs_it_against_a_built_wheel(self) -> None:
        """A verifier no job invokes is the same as no verifier."""
        callers: Final = tuple(
            path.name
            for path in (REPO / ".github" / "workflows").rglob("*.yml")
            if VERIFIER in path.read_text(encoding="utf-8")
        )
        assert callers, f"no workflow runs {VERIFIER}"

    def test_the_job_that_runs_it_also_builds_a_wheel(self) -> None:
        """Checking a wheel in a job that never builds one would pass on nothing."""
        for path in (REPO / ".github" / "workflows").rglob("*.yml"):
            text = path.read_text(encoding="utf-8")
            if VERIFIER not in text:
                continue
            for name, job in yaml.safe_load(text)["jobs"].items():
                steps = tuple(str(step.get("run", "")) for step in job.get("steps", ()))
                if not any(VERIFIER in step for step in steps):
                    continue
                assert any("build --wheel" in step or "build_wheel" in step for step in steps), (
                    f"{path.name}:{name} runs the verifier but builds no wheel"
                )
                return
        pytest.fail(f"no job runs {VERIFIER}")
