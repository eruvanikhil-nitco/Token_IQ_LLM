"""The dependency updater is configured, and configured for things that exist.

Dependabot fails silently. A wrong ecosystem name, a directory that was renamed, or a
manifest that moved produces no pull requests and no error: the updates simply stop, and
the first anyone knows is a dependency years out of date. Upstream used to do this work,
so there is nothing to notice its absence except this.
"""

from __future__ import annotations

import pathlib
from typing import Final

import pytest
import yaml

REPO: Final = pathlib.Path(__file__).resolve().parents[2]
CONFIG: Final = REPO / ".github" / "dependabot.yml"

# What each ecosystem must find in the directory it is pointed at. An entry watching a
# directory with no manifest is the silent-failure case.
MANIFESTS: Final[dict[str, tuple[str, ...]]] = {
    "uv": ("uv.lock", "pyproject.toml"),
    "npm": ("package.json",),
    "docker": ("Dockerfile",),
    "github-actions": (".github/workflows",),
}


@pytest.fixture(scope="module")
def config() -> dict[str, object]:
    assert CONFIG.is_file(), f"{CONFIG} is missing; nothing updates dependencies"
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


class TestItIsValid:
    def test_the_file_parses_and_declares_version_two(self, config: dict[str, object]) -> None:
        assert config["version"] == 2

    def test_every_entry_names_a_known_ecosystem(self, config: dict[str, object]) -> None:
        for entry in config["updates"]:
            assert entry["package-ecosystem"] in MANIFESTS, entry["package-ecosystem"]

    def test_every_entry_has_a_schedule(self, config: dict[str, object]) -> None:
        for entry in config["updates"]:
            assert entry["schedule"]["interval"], entry


class TestItPointsAtThingsThatExist:
    def test_every_watched_directory_is_real(self, config: dict[str, object]) -> None:
        """A renamed directory is how the updates stop without anybody noticing."""
        for entry in config["updates"]:
            target = REPO / str(entry["directory"]).lstrip("/")
            assert target.is_dir(), f"{entry['package-ecosystem']} watches {entry['directory']}, which does not exist"

    def test_every_watched_directory_holds_a_manifest_that_ecosystem_reads(
        self, config: dict[str, object]
    ) -> None:
        for entry in config["updates"]:
            target = REPO / str(entry["directory"]).lstrip("/")
            wanted = MANIFESTS[str(entry["package-ecosystem"])]
            found = [name for name in wanted if (target / name).exists()]
            assert found, (
                f"{entry['package-ecosystem']} watches {entry['directory']} "
                f"but none of {wanted} is there, so it will find nothing"
            )


class TestEverythingWithDependenciesIsWatched:
    def test_both_node_projects_are_covered(self, config: dict[str, object]) -> None:
        """The dashboard and the e2e harness have separate lockfiles. Watching one and
        forgetting the other leaves half the dependencies frozen."""
        watched = {str(e["directory"]) for e in config["updates"] if e["package-ecosystem"] == "npm"}
        # relative_to gives "." for the repository root, which Dependabot spells "/".
        on_disk = {
            "/" + p.parent.relative_to(REPO).as_posix().removeprefix(".").lstrip("/")
            for p in REPO.rglob("package-lock.json")
            if "node_modules" not in p.parts
        }
        assert on_disk <= watched, f"unwatched node projects: {sorted(on_disk - watched)}"

    def test_python_and_actions_are_covered(self, config: dict[str, object]) -> None:
        ecosystems = {str(e["package-ecosystem"]) for e in config["updates"]}
        assert {"uv", "github-actions"} <= ecosystems
