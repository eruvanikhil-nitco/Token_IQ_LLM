from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

import pytest

REPO: Final = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from deploy.images.build import (  # noqa: E402
    ALL_IN_ONE,
    BuildRefused,
    ImageSpec,
    build_all,
    build_command,
    push_command,
    reference_for,
    version_of,
)

REGISTRY: Final = "123456789012.dkr.ecr.eu-west-2.amazonaws.com"


def _repo(tmp_path: Path, *, dirty: bool = False) -> Path:
    subprocess.run(("git", "init", "-q"), cwd=tmp_path, check=True)
    subprocess.run(("git", "config", "user.email", "t@example.com"), cwd=tmp_path, check=True)
    subprocess.run(("git", "config", "user.name", "t"), cwd=tmp_path, check=True)
    (tmp_path / "a.txt").write_text("one", encoding="utf-8")
    subprocess.run(("git", "add", "-A"), cwd=tmp_path, check=True)
    subprocess.run(("git", "commit", "-qm", "first"), cwd=tmp_path, check=True)
    if dirty:
        (tmp_path / "a.txt").write_text("two", encoding="utf-8")
    return tmp_path


def test_an_image_is_named_under_our_own_registry(tmp_path: Path) -> None:
    reference: Final = reference_for(ALL_IN_ONE, registry=REGISTRY, version="abc123def456")

    assert reference.startswith(REGISTRY)
    assert "/token-iq/" in reference
    assert "berriai" not in reference


def test_an_image_is_tagged_with_the_commit_it_came_from(tmp_path: Path) -> None:
    repo: Final = _repo(tmp_path)
    version: Final = version_of(repo)

    assert reference_for(ALL_IN_ONE, registry=REGISTRY, version=version).endswith(f":{version}")


def test_a_moving_tag_is_refused(tmp_path: Path) -> None:
    """The manifest refuses such a version anyway, so producing one would only create an image
    nobody is allowed to deploy."""
    for moving in ("latest", "main", "stable", "edge"):
        with pytest.raises(BuildRefused, match="moving tag"):
            reference_for(ALL_IN_ONE, registry=REGISTRY, version=moving)


def test_an_empty_version_is_refused(tmp_path: Path) -> None:
    with pytest.raises(BuildRefused):
        reference_for(ALL_IN_ONE, registry=REGISTRY, version="")


def test_a_dirty_working_tree_stops_the_build(tmp_path: Path) -> None:
    """The tag says which commit an image came from. Building from uncommitted changes makes
    that a lie, and it is discovered when a rollback puts the wrong code back."""
    repo: Final = _repo(tmp_path, dirty=True)

    with pytest.raises(BuildRefused, match="uncommitted"):
        version_of(repo)


def test_a_developer_can_still_build_a_throwaway_from_a_dirty_tree(tmp_path: Path) -> None:
    repo: Final = _repo(tmp_path, dirty=True)

    assert version_of(repo, allow_dirty=True)


def test_the_build_command_passes_no_shell_string(tmp_path: Path) -> None:
    """A command built as one string would put a path through a shell, which is both a
    quoting bug waiting on a space and the shape the CI rules forbid."""
    command: Final = build_command(ALL_IN_ONE, registry=REGISTRY, version="abc123", repo=tmp_path)

    assert isinstance(command, tuple)
    assert command[0] == "docker"
    assert all(isinstance(part, str) for part in command)


def test_the_push_command_names_exactly_what_was_built(tmp_path: Path) -> None:
    built: Final = reference_for(ALL_IN_ONE, registry=REGISTRY, version="abc123")

    assert push_command(ALL_IN_ONE, registry=REGISTRY, version="abc123") == ("docker", "push", built)


@dataclass
class FakeRunner:
    fails_on: str | None = None
    commands: list[tuple[str, ...]] = field(default_factory=list)  # mutable-ok: a spy the test reads

    def run(self, command: tuple[str, ...], check: bool = False) -> object:
        self.commands.append(command)
        failed: Final = self.fails_on is not None and any(self.fails_on in part for part in command)
        return subprocess.CompletedProcess(args=command, returncode=1 if failed else 0)


def test_every_image_is_built_at_one_version(tmp_path: Path) -> None:
    """A gateway from one commit beside a UI from another is a combination nobody tested."""
    repo: Final = _repo(tmp_path)
    runner: Final = FakeRunner()
    specs: Final = (ImageSpec(name="one", dockerfile="Dockerfile"), ImageSpec(name="two", dockerfile="Dockerfile"))

    built: Final = build_all(specs, registry=REGISTRY, repo=repo, runner=runner)

    versions = {reference.rsplit(":", 1)[1] for reference in built}
    assert len(versions) == 1
    assert len(runner.commands) == 2


def test_a_failed_build_stops_and_says_which_image(tmp_path: Path) -> None:
    repo: Final = _repo(tmp_path)
    specs: Final = (ImageSpec(name="one", dockerfile="Dockerfile"), ImageSpec(name="two", dockerfile="Dockerfile"))

    with pytest.raises(BuildRefused, match="one"):
        build_all(specs, registry=REGISTRY, repo=repo, runner=FakeRunner(fails_on="/one:"))


def test_the_all_in_one_image_builds_from_the_repository_dockerfile() -> None:
    """The spec has to name a Dockerfile that is actually there, or the first real build fails
    on something a test could have caught."""
    assert (REPO / ALL_IN_ONE.dockerfile).is_file()
