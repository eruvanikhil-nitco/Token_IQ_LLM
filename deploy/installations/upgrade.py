"""Roll every customer installation to one version.

Stops at the first failure rather than carrying on. A half-upgraded fleet is survivable; a
half-upgraded fleet where nobody can say which half is not, and continuing past a failure is
how that happens. The report names who moved, who failed and who was never touched, so the
person reading it can act without guessing.

An installation already on the target version is left alone, so running this twice is safe and
a retry after a failure does not redo the work that succeeded.

The thing that actually applies a change is injected. That keeps this testable without an AWS
account, and it keeps the decision about how to apply, Terraform today, separate from the
decision about what order to apply it in.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Protocol

from deploy.installations.manifest import Installation


class Applier(Protocol):
    """Moves one installation to one version, or raises describing why it could not."""

    def apply(self, installation: Installation, version: str) -> None: ...


@dataclass(frozen=True, slots=True)
class Upgraded:
    installation: Installation
    from_version: str
    to_version: str


@dataclass(frozen=True, slots=True)
class Failed:
    installation: Installation
    to_version: str
    reason: str


@dataclass(frozen=True, slots=True)
class UpgradeReport:
    """What happened, in enough detail to act on without rerunning anything."""

    target: str
    upgraded: tuple[Upgraded, ...]
    already_current: tuple[Installation, ...]
    failed: Failed | None
    untouched: tuple[Installation, ...]

    @property
    def stopped_early(self) -> bool:
        return self.failed is not None

    def summary(self) -> str:
        lines: Final = [
            f"target {self.target}",
            f"  upgraded       {len(self.upgraded)}",
            f"  already there  {len(self.already_current)}",
        ]
        if self.failed is not None:
            lines.append(f"  FAILED         {self.failed.installation.key}: {self.failed.reason}")
            lines.append(f"  not attempted  {len(self.untouched)}")
        return "\n".join(lines)


def plan_upgrade(installations: Sequence[Installation], target: str) -> UpgradeReport:
    """What an upgrade would do, without doing any of it."""
    return UpgradeReport(
        target=target,
        upgraded=tuple(
            Upgraded(installation=entry, from_version=entry.version, to_version=target)
            for entry in installations
            if entry.version != target
        ),
        already_current=tuple(entry for entry in installations if entry.version == target),
        failed=None,
        untouched=(),
    )


def upgrade(installations: Sequence[Installation], target: str, applier: Applier) -> UpgradeReport:
    """Move every installation to the target version, stopping at the first failure."""
    upgraded: Final[list[Upgraded]] = []  # mutable-ok: accumulated in order across the fleet
    already: Final[list[Installation]] = []  # mutable-ok: same

    for index, entry in enumerate(installations):
        if entry.version == target:
            already.append(entry)
            continue
        try:
            applier.apply(entry, target)
        except Exception as exc:  # noqa: BLE001  # any failure stops the roll; the reason is reported verbatim
            return UpgradeReport(
                target=target,
                upgraded=tuple(upgraded),
                already_current=tuple(already),
                failed=Failed(installation=entry, to_version=target, reason=f"{type(exc).__name__}: {exc}"),
                untouched=tuple(installations[index + 1 :]),
            )
        upgraded.append(Upgraded(installation=entry, from_version=entry.version, to_version=target))

    return UpgradeReport(
        target=target,
        upgraded=tuple(upgraded),
        already_current=tuple(already),
        failed=None,
        untouched=(),
    )
