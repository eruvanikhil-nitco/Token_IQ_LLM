"""A deployment artefact must not name another company's container registry.

The inherited Terraform defaulted its four image variables to another company's published
images. Overriding them was possible and documented, which is not the same as safe: a
deployment that forgot would have run someone else's build inside a customer's installation,
with their branding, their release cadence and their supply chain.

The fix is a variable with no default, so a missing value fails at plan time. This check
exists so the defaults cannot quietly come back.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from types import MappingProxyType
from typing import Final

REPO: Final = Path(__file__).resolve().parents[2]

SEARCHED: Final[tuple[str, ...]] = ("terraform", "deploy", "docker", ".github/workflows")

SEARCHED_SUFFIXES: Final[frozenset[str]] = frozenset({".tf", ".tfvars", ".yml", ".yaml", ".json", ".sh", ".py"})

FOREIGN_REGISTRY: Final = re.compile(
    r"""(?xi)
    (?:^|["'\s=:/])                 # not mid-word
    (?P<ref>
        (?:ghcr\.io|docker\.io|quay\.io)/
        (?!tokeniq/)                # our own namespace is fine wherever it is published
        [\w.-]+/[\w.-]+
        (?::[\w.-]+)?
    )
    """
)

ALLOWED: Final[Mapping[str, str]] = MappingProxyType(
    {
        # Base images we build FROM are a different thing from images we ship as the product:
        # every image is built on someone else's base, and naming one is not shipping theirs.
        "docker/Dockerfile.database": "FROM line, a base image we build on",
        "docker/Dockerfile.non_root": "FROM line, a base image we build on",
        # Inherited release automation that publishes the upstream project and writes release
        # notes telling a reader to verify it with the upstream signing key. It deploys
        # nothing, so it is outside what this check polices, but it does not belong in a
        # Token IQ release either and is recorded as an open item in the deployment plan.
    }
)

FROM_LINE: Final = re.compile(r"^\s*FROM\s", re.IGNORECASE)


def _candidates() -> Iterator[Path]:
    for root in SEARCHED:
        base: Final = REPO / root
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file() and path.suffix in SEARCHED_SUFFIXES:
                yield path


def offenders(paths: Sequence[Path]) -> tuple[tuple[str, int, str], ...]:
    found: list[tuple[str, int, str]] = []  # mutable-ok: accumulated while walking files
    for path in paths:
        relative = path.relative_to(REPO).as_posix()
        if relative in ALLOWED:
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, OSError):
            continue
        for number, line in enumerate(lines, start=1):
            if FROM_LINE.match(line):
                continue
            match = FOREIGN_REGISTRY.search(line)
            if match is not None:
                found.append((relative, number, match.group("ref")))
    return tuple(found)


def main() -> int:
    found: Final = offenders(tuple(_candidates()))
    if not found:
        print("No deployment artefact ships another company's container image.")
        return 0

    print(f"{len(found)} deployment reference(s) name another company's container image:\n")
    for relative, number, ref in found:
        print(f"  {relative}:{number}\n    {ref}")
    print(
        "\nShip an image we build. A variable with no default is better than a default that "
        "points somewhere else, because a missing value then fails at plan time."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
