"""Who our customers are, as one file both provisioning and upgrades read.

A single list means the two cannot disagree. An upgrade that walked a directory of Terraform
state, or a provisioning step that took a name on the command line, would let an installation
exist that the other does not know about, and the one thing worse than an un-upgraded customer
is an un-upgraded customer nobody can name.

Every name is validated when the file is read rather than when Terraform runs, because a
customer key becomes a Postgres database and role name, and the failure mode for a bad one is
a half-created installation rather than a clear error.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal, TypeAlias

import yaml

Size: TypeAlias = Literal["small", "medium", "large"]

SIZES: Final[Mapping[Size, tuple[int, int]]] = {
    "small": (512, 1024),
    "medium": (1024, 2048),
    "large": (2048, 4096),
}
"""CPU units and memory in MiB. Fargate accepts only certain pairs, so a size is a name rather
than two free numbers a manifest could get wrong."""

SAFE_KEY: Final = re.compile(r"^[a-z][a-z0-9_]{2,30}$")
"""A customer key becomes a database name and a role name. Lower case and underscores only, so
it never needs quoting in SQL, and never starts with a digit."""

SAFE_HOST: Final = re.compile(r"^[a-z0-9][a-z0-9.-]{2,252}[a-z0-9]$")

VERSION: Final = re.compile(r"^[0-9a-f]{7,40}$|^v\d+\.\d+\.\d+$")
"""A commit hash or a semantic version. Never a moving tag such as `latest`: an installation
whose version cannot be named cannot be rolled back to a known one."""


class ManifestError(ValueError):
    """The manifest cannot be used as written. Raised at read time, before anything is created."""


@dataclass(frozen=True, slots=True)
class Installation:
    key: str
    hostname: str
    version: str
    size: Size = "small"

    @property
    def database(self) -> str:
        return f"tokeniq_{self.key}"

    @property
    def role(self) -> str:
        return f"tokeniq_{self.key}"

    @property
    def cpu(self) -> int:
        return SIZES[self.size][0]

    @property
    def memory(self) -> int:
        return SIZES[self.size][1]


def _installation_from(key: object, body: object) -> Installation:
    if not isinstance(key, str) or not SAFE_KEY.fullmatch(key):
        raise ManifestError(
            f"{key!r} is not a usable customer key. It becomes a database and role name, so it must be "
            "lower case letters, digits and underscores, start with a letter, and be 3 to 31 characters."
        )
    if not isinstance(body, Mapping):
        raise ManifestError(f"customer {key!r} has no settings")

    hostname: Final = body.get("hostname")
    if not isinstance(hostname, str) or not SAFE_HOST.fullmatch(hostname):
        raise ManifestError(f"customer {key!r} has no usable hostname: {hostname!r}")

    version: Final = body.get("version")
    if not isinstance(version, str) or not VERSION.fullmatch(version):
        raise ManifestError(
            f"customer {key!r} has no usable version: {version!r}. Use a commit hash or a semantic "
            "version, never a moving tag, so the installation can be rolled back to a known build."
        )

    size: Final = body.get("size", "small")
    if size not in SIZES:
        raise ManifestError(f"customer {key!r} has an unknown size {size!r}. Known sizes: {', '.join(SIZES)}.")

    return Installation(key=key, hostname=hostname, version=version, size=size)


def _refuse_duplicates(installations: Sequence[Installation]) -> None:
    for field, values in (
        ("hostname", tuple(entry.hostname for entry in installations)),
        ("database", tuple(entry.database for entry in installations)),
    ):
        seen: Final[set[str]] = set()  # mutable-ok: duplicate detection over one pass
        for value in values:
            if value in seen:
                raise ManifestError(f"two customers share the same {field}: {value!r}")
            seen.add(value)


def read_manifest(path: Path) -> tuple[Installation, ...]:
    """Every installation, validated. Raises rather than returning a partial list.

    This raises against the repository's usual preference for failure values because a caller
    cannot do anything useful with half a fleet: both callers either create infrastructure or
    upgrade it, and acting on a manifest we could not fully read is how a customer gets missed.
    """
    try:
        loaded: Final = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ManifestError(f"cannot read the manifest at {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ManifestError(f"the manifest at {path} is not valid YAML: {exc}") from exc

    if not isinstance(loaded, Mapping):
        raise ManifestError(f"the manifest at {path} should be a mapping of customer key to settings")

    customers: Final = loaded.get("installations")
    if not isinstance(customers, Mapping) or not customers:
        raise ManifestError(f"the manifest at {path} lists no installations")

    installations: Final = tuple(_installation_from(key, body) for key, body in customers.items())
    _refuse_duplicates(installations)
    return installations
