"""Capture what this repository does today, so a later phase can prove it changed nothing.

The artifact exists to answer one question six weeks from now: did I break this, or was it
already broken? A baseline that cannot answer that is a paragraph, not a baseline, which is
why the comparison here is tested as carefully as any product code.

It reports a test that vanished as loudly as one that failed. A refactor that loses a file
makes the suite greener, and green is exactly how that mistake disguises itself.
"""

from __future__ import annotations

import dataclasses
import json
import pathlib
import platform
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ElementTree
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from typing import Final, Literal

Outcome = Literal["passed", "failed", "error", "skipped"]

FAILING: Final[frozenset[str]] = frozenset({"failed", "error"})


@dataclasses.dataclass(frozen=True, slots=True)
class CaseOutcome:
    nodeid: str
    outcome: Outcome


@dataclasses.dataclass(frozen=True, slots=True)
class SuiteRun:
    name: str
    outcomes: tuple[CaseOutcome, ...]
    workers: int = 0
    """xdist workers used, 0 for serial. Per suite, because suites are captured one at a
    time and resumed across sessions, so one artifact can legitimately hold both."""


@dataclasses.dataclass(frozen=True, slots=True)
class CommandRun:
    """A check that either passes or does not, with no per-test detail: lint, build, image."""

    name: str
    command: str
    exit_code: int
    summary: str


@dataclasses.dataclass(frozen=True, slots=True)
class Baseline:
    commit: str
    python: str
    platform: str
    captured_at: str
    parallel: bool
    suites: tuple[SuiteRun, ...]
    commands: tuple[CommandRun, ...]


@dataclasses.dataclass(frozen=True, slots=True)
class Drift:
    newly_failing: tuple[str, ...]
    newly_passing: tuple[str, ...]
    still_failing: tuple[str, ...]
    disappeared: tuple[str, ...]
    appeared: tuple[str, ...]


def _keyed(baseline: Baseline) -> Mapping[str, Outcome]:
    """Qualify every nodeid by its suite, because the same id can exist in two of them."""
    return {f"{suite.name}/{o.nodeid}": o.outcome for suite in baseline.suites for o in suite.outcomes}


def compare(before: Baseline, after: Baseline) -> Drift:
    old: Final = _keyed(before)
    new: Final = _keyed(after)
    shared: Final = frozenset(old) & frozenset(new)
    return Drift(
        newly_failing=tuple(sorted(k for k in shared if new[k] in FAILING and old[k] not in FAILING)),
        newly_passing=tuple(sorted(k for k in shared if old[k] in FAILING and new[k] not in FAILING)),
        still_failing=tuple(sorted(k for k in shared if old[k] in FAILING and new[k] in FAILING)),
        disappeared=tuple(sorted(frozenset(old) - frozenset(new))),
        appeared=tuple(sorted(frozenset(new) - frozenset(old))),
    )


def _nodeid(classname: str, name: str) -> str:
    """junit's dotted classname back into a pytest nodeid.

    `tests.test_a.TestOne` is a module and a class; `tests.test_a` is only a module. The last
    segment is a class when it starts with an upper-case letter, which is the convention
    pytest collection already relies on.
    """
    parts: Final = classname.split(".")
    has_class: Final = len(parts) > 1 and parts[-1][:1].isupper()
    module: Final = "/".join(parts[:-1] if has_class else parts)
    suffix: Final = f"::{parts[-1]}::{name}" if has_class else f"::{name}"
    return f"{module}.py{suffix}"


def parse_junit(xml_text: str) -> tuple[CaseOutcome, ...]:
    try:
        root: Final = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError as error:
        # Returning () here would read as "every test vanished" on the next comparison.
        raise ValueError(f"not a junit report: {error}") from error

    return tuple(
        CaseOutcome(nodeid=_nodeid(case.get("classname", ""), case.get("name", "")), outcome=_outcome_of(case))
        for case in root.iter("testcase")
    )


def _outcome_of(case: ElementTree.Element) -> Outcome:
    for tag, outcome in (("failure", "failed"), ("error", "error"), ("skipped", "skipped")):
        if case.find(tag) is not None:
            return outcome  # pyright: ignore[reportReturnType]  # tag/outcome pairs are exhaustive over Outcome
    return "passed"


def as_json(baseline: Baseline) -> str:
    return json.dumps(dataclasses.asdict(baseline), indent=2, sort_keys=True)


def from_json(text: str) -> Baseline:
    raw: Final = json.loads(text)
    return Baseline(
        commit=raw["commit"],
        python=raw["python"],
        platform=raw["platform"],
        captured_at=raw["captured_at"],
        parallel=raw["parallel"],
        suites=tuple(
            SuiteRun(
                name=s["name"],
                outcomes=tuple(CaseOutcome(**o) for o in s["outcomes"]),
                workers=s.get("workers", 0),
            )
            for s in raw["suites"]
        ),
        commands=tuple(CommandRun(**c) for c in raw["commands"]),
    )


def _resolve(program: str) -> str:
    """Find the real executable.

    On Windows `npm`, `npx` and `make` are `.cmd` shims that `subprocess` cannot find from a
    bare name, and the alternative, `shell=True`, is banned for good reason.
    """
    return shutil.which(program) or program


def _run(command: tuple[str, ...], cwd: pathlib.Path) -> tuple[int, str]:
    resolved: Final = (_resolve(command[0]), *command[1:])
    finished: Final = subprocess.run(  # noqa: S603  # fixed argument vectors, never a shell string
        resolved, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False
    )
    tail: Final = (finished.stdout + finished.stderr).strip().splitlines()
    return finished.returncode, "\n".join(tail[-12:])


def capture_suite(
    name: str, paths: Iterable[str], repo: pathlib.Path, reports: pathlib.Path, workers: int = 0
) -> SuiteRun:
    report: Final = reports / f"{name}.xml"
    # Workers cut the proxy suite from an hour to minutes and produced identical outcomes when
    # checked against a serial run, so the recorded result is the same either way. `parallel`
    # on the artifact says which was used, since a baseline that does not say how it was
    # produced cannot be reproduced.
    parallel: Final = ("-n", str(workers)) if workers > 0 else ()
    _run((sys.executable, "-m", "pytest", *paths, "-q", f"--junitxml={report}", "-p", "no:randomly", *parallel), repo)
    if not report.exists():
        # Collection died before pytest could write anything. An empty suite would later read
        # as every test in it having vanished, so say so instead.
        raise RuntimeError(f"suite {name!r} produced no junit report; its collection failed")
    return SuiteRun(name=name, outcomes=parse_junit(report.read_text(encoding="utf-8")), workers=workers)


def capture_command(name: str, command: tuple[str, ...], repo: pathlib.Path) -> CommandRun:
    if shutil.which(command[0]) is None:
        # Recording "exit 1, tool missing" would read later as a real failure of that check.
        return CommandRun(name=name, command=" ".join(command), exit_code=-1, summary=f"{command[0]} not installed")
    exit_code, summary = _run(command, repo)
    return CommandRun(name=name, command=" ".join(command), exit_code=exit_code, summary=summary)


def head_commit(repo: pathlib.Path) -> str:
    _, out = _run(("git", "rev-parse", "HEAD"), repo)
    return out.strip() or "unknown"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def describe_environment(repo: pathlib.Path, *, parallel: bool) -> Mapping[str, str | bool]:
    return {
        "commit": head_commit(repo),
        "python": platform.python_version(),
        "platform": sys.platform,
        "captured_at": now(),
        "parallel": parallel,
    }
