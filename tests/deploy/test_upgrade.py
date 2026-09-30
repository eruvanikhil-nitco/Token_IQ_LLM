from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

REPO: Final = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from deploy.installations.manifest import Installation  # noqa: E402
from deploy.installations.upgrade import plan_upgrade, upgrade  # noqa: E402


def _fleet(*versions: str) -> tuple[Installation, ...]:
    return tuple(
        Installation(key=f"customer_{index}", hostname=f"c{index}.tokeniq.test", version=version)
        for index, version in enumerate(versions)
    )


@dataclass
class RecordingApplier:
    fails_on: str | None = None
    applied: list[tuple[str, str]] = field(default_factory=list)  # mutable-ok: a spy the test reads

    def apply(self, installation: Installation, version: str) -> None:
        if self.fails_on == installation.key:
            raise RuntimeError("the task never became healthy")
        self.applied.append((installation.key, version))


def test_every_installation_moves_to_the_target() -> None:
    applier: Final = RecordingApplier()

    report: Final = upgrade(_fleet("v1.0.0", "v1.0.0"), "v2.0.0", applier)

    assert applier.applied == [("customer_0", "v2.0.0"), ("customer_1", "v2.0.0")]
    assert len(report.upgraded) == 2
    assert report.stopped_early is False


def test_an_installation_already_on_the_target_is_left_alone() -> None:
    """Re-running after a partial failure must not redo the work that succeeded."""
    applier: Final = RecordingApplier()

    report: Final = upgrade(_fleet("v2.0.0", "v1.0.0"), "v2.0.0", applier)

    assert applier.applied == [("customer_1", "v2.0.0")]
    assert tuple(entry.key for entry in report.already_current) == ("customer_0",)


def test_a_failure_stops_the_roll_rather_than_carrying_on() -> None:
    """A half-upgraded fleet is survivable. A half-upgraded fleet where nobody can say which
    half is not, and carrying on past a failure is how that happens."""
    applier: Final = RecordingApplier(fails_on="customer_1")

    report: Final = upgrade(_fleet("v1.0.0", "v1.0.0", "v1.0.0"), "v2.0.0", applier)

    assert applier.applied == [("customer_0", "v2.0.0")]
    assert report.failed is not None
    assert report.failed.installation.key == "customer_1"


def test_the_report_names_who_moved_who_failed_and_who_was_never_touched() -> None:
    """The person reading this has to act on it without rerunning anything to find out."""
    applier: Final = RecordingApplier(fails_on="customer_1")

    report: Final = upgrade(_fleet("v1.0.0", "v1.0.0", "v1.0.0"), "v2.0.0", applier)

    assert tuple(entry.installation.key for entry in report.upgraded) == ("customer_0",)
    assert report.failed is not None and report.failed.installation.key == "customer_1"
    assert tuple(entry.key for entry in report.untouched) == ("customer_2",)


def test_the_failure_carries_the_reason_the_applier_gave() -> None:
    """A generic failure would send someone to the logs of every installation in turn."""
    applier: Final = RecordingApplier(fails_on="customer_0")

    report: Final = upgrade(_fleet("v1.0.0"), "v2.0.0", applier)

    assert report.failed is not None
    assert "never became healthy" in report.failed.reason


def test_a_dry_run_changes_nothing_and_says_what_it_would_do() -> None:
    applier: Final = RecordingApplier()

    planned: Final = plan_upgrade(_fleet("v1.0.0", "v2.0.0"), "v2.0.0")

    assert applier.applied == []
    assert tuple(entry.installation.key for entry in planned.upgraded) == ("customer_0",)
    assert tuple(entry.key for entry in planned.already_current) == ("customer_1",)


def test_an_upgrade_of_a_fleet_already_current_does_nothing_and_says_so() -> None:
    applier: Final = RecordingApplier()

    report: Final = upgrade(_fleet("v2.0.0", "v2.0.0"), "v2.0.0", applier)

    assert applier.applied == []
    assert report.upgraded == ()
    assert len(report.already_current) == 2


def test_the_summary_names_the_failing_customer() -> None:
    """The summary is what a person actually reads, so the failing customer has to be in it."""
    report: Final = upgrade(_fleet("v1.0.0", "v1.0.0"), "v2.0.0", RecordingApplier(fails_on="customer_1"))

    assert "customer_1" in report.summary()
    assert "FAILED" in report.summary()
