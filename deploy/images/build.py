"""Build the images a customer installation runs.

Every image is named under our own registry and tagged with the commit it was built from.
Nothing here ever produces a moving tag: an installation whose version cannot be named cannot
be rolled back to a known build, and the manifest refuses such a version anyway, so producing
one would only create an image nobody is allowed to deploy.

A dirty working tree stops the build. The tag says which commit an image came from, and an
image built from uncommitted changes makes that a lie, which is discovered at the worst
possible moment: when a rollback puts the wrong code back.
"""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

REGISTRY_SUFFIX: Final = "/tokeniq"
"""Every image lives under our own namespace. The registry host differs per environment, an
ECR account for production and something local for a rehearsal, but the namespace does not."""

MOVING_TAGS: Final[frozenset[str]] = frozenset({"latest", "main", "stable", "edge"})


@dataclass(frozen=True, slots=True)
class ImageSpec:
    """One image we build, and where its build lives."""

    name: str
    dockerfile: str
    context: str = "."


ALL_IN_ONE: Final = ImageSpec(name="tokeniq", dockerfile="Dockerfile")
"""One container per installation, which is the shape a customer installation runs. The
componentized gateway, backend and UI images stay available for a customer who outgrows it."""


class BuildRefused(RuntimeError):
    """The build must not happen. Raised before anything is built rather than returned, so a
    caller cannot accidentally carry on and publish an image whose tag is untrue."""


def _git(repo: Path, *args: str) -> str:
    result: Final = subprocess.run(("git", *args), cwd=repo, capture_output=True, text=True, check=False, timeout=60)
    if result.returncode != 0:
        raise BuildRefused(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def version_of(repo: Path, *, allow_dirty: bool = False) -> str:
    """The commit this build comes from, refusing a working tree that has uncommitted changes.

    `allow_dirty` exists for a developer building a throwaway image on their own machine. It
    is never used by the release path, because the tag would then name a commit whose contents
    are not what the image contains.
    """
    dirty: Final = _git(repo, "status", "--porcelain")
    if dirty and not allow_dirty:
        changed: Final = len(dirty.splitlines())
        raise BuildRefused(
            f"the working tree has {changed} uncommitted change(s), so an image tagged with this "
            "commit would not contain this commit. Commit first, or pass allow_dirty for a throwaway."
        )
    return _git(repo, "rev-parse", "--short=12", "HEAD")


def reference_for(spec: ImageSpec, *, registry: str, version: str) -> str:
    """The full name an image is published under."""
    if version in MOVING_TAGS:
        raise BuildRefused(
            f"{version!r} is a moving tag. Tag with the commit, so the image a customer runs can "
            "always be traced back to the code in it."
        )
    if not version:
        raise BuildRefused("an image needs a version")
    return f"{registry.rstrip('/')}{REGISTRY_SUFFIX}/{spec.name}:{version}"


def build_command(spec: ImageSpec, *, registry: str, version: str, repo: Path) -> tuple[str, ...]:
    """The command that builds one image, as a list so nothing is passed through a shell."""
    return (
        "docker",
        "build",
        "--tag",
        reference_for(spec, registry=registry, version=version),
        "--file",
        str(repo / spec.dockerfile),
        str(repo / spec.context),
    )


def push_command(spec: ImageSpec, *, registry: str, version: str) -> tuple[str, ...]:
    return ("docker", "push", reference_for(spec, registry=registry, version=version))


def build_all(
    specs: Sequence[ImageSpec],
    *,
    registry: str,
    repo: Path,
    allow_dirty: bool = False,
    runner: object = subprocess,
) -> tuple[str, ...]:
    """Build every image at one version, and return what was built.

    One version across all of them on purpose: an installation running a gateway from one
    commit and a UI from another is a combination nobody tested.
    """
    version: Final = version_of(repo, allow_dirty=allow_dirty)
    built: Final[list[str]] = []  # mutable-ok: accumulated in order for the caller's report
    for spec in specs:
        command = build_command(spec, registry=registry, version=version, repo=repo)
        result = runner.run(command, check=False)  # pyright: ignore[reportAttributeAccessIssue]  # injected runner
        if getattr(result, "returncode", 1) != 0:
            raise BuildRefused(f"building {spec.name} failed")
        built.append(reference_for(spec, registry=registry, version=version))
    return tuple(built)
