"""Run the phase 0 baseline and write it to the committed artifact.

Resumable on purpose. The full unit suite and the image build take long enough that an
all-or-nothing run would be abandoned halfway and the baseline never captured, so each
section is captured independently and merged into the same file.

    python -m scripts.inventory.capture --section token_iq
    python -m scripts.inventory.capture --section lint
    python -m scripts.inventory.capture --all
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import pathlib
import sys
from collections.abc import Mapping, Sequence
from typing import Final

from scripts.inventory.baseline import (
    Baseline,
    CommandRun,
    SuiteRun,
    capture_command,
    capture_suite,
    describe_environment,
    from_json,
)

REPO: Final = pathlib.Path(__file__).resolve().parents[2]
ARTIFACT: Final = REPO / "docs" / "plans" / "2026-10-04-phase-0-baseline.json"
"""The phase 0 record. Kept as written: it says what was true on 4 Oct, and a later phase
that rewrites it loses the only thing it was for. `--artifact` captures somewhere else."""

TOKEN_IQ: Final[tuple[str, ...]] = ("tests/token_iq",)
"""One path since phase 4: the Token IQ tests mirror the package instead of being seven
directories scattered through the engine's tree."""
TOKEN_IQ_PROXY: Final[tuple[str, ...]] = tuple(
    f"tests/test_litellm/proxy/{name}"
    for name in ("management_endpoints", "auth", "pass_through_endpoints", "spend_tracking", "db")
)

# Token IQ paths that fall outside both groups above and so were in no captured suite at all,
# found by checking the phase 4 move map against what the suites cover.
TOKEN_IQ_EDGES: Final[tuple[str, ...]] = ("tests/test_litellm/proxy/credential_endpoints",)
"""What is left of that gap. `pricing` and `types/proxy` moved into `tests/token_iq` in phase 4
and are covered by the suite above; this directory keeps engine tests of its own."""

SUITES: Final[Mapping[str, tuple[str, ...]]] = {
    "token_iq": TOKEN_IQ,
    "token_iq_edges": TOKEN_IQ_EDGES,
    "token_iq_proxy": TOKEN_IQ_PROXY,
    "repositories": ("tests/test_litellm/repositories",),
    "deploy": ("tests/deploy",),
    "unit": ("tests/test_litellm",),
}

UI: Final = REPO / "ui" / "litellm-dashboard"

COMMANDS: Final[Mapping[str, tuple[str, ...]]] = {
    "ci_coverage": (sys.executable, ".github/scripts/assert_ci_coverage.py"),
    # `make lint` needs make and the gate slot lock, which imports fcntl, so neither runs on
    # Windows. Recorded anyway: a baseline that silently omits a check is worse than one that
    # says where it came up short. CI supplies the real figure.
    "lint": ("make", "lint"),
    # The portable substitute, named differently so the two are never confused.
    "ruff": (sys.executable, "-m", "ruff", "check", "litellm", "scripts", "--output-format=concise"),
    "ui_build": ("npm", "run", "build"),
    # Deliberately not the whole vitest suite. `npx vitest run` with no path is 380 files and
    # the dashboard's own CLAUDE.md forbids it: it saturates the machine and CI runs it anyway.
    # Run bare here it died on an IPC channel closure, which is a resource failure dressed up
    # as a test failure. These are the paths phases 3 and 9 actually move.
    "ui_tests": (
        "npx",
        "vitest",
        "run",
        "src/lib/money.test.ts",
        "src/app/(dashboard)/overview",
        "src/app/(dashboard)/usage/_components/combined",
        "src/app/(dashboard)/ledger",
        "src/app/(dashboard)/recommendations",
        "src/app/(dashboard)/provider-apis",
        "src/app/(dashboard)/user-tools",
    ),
    "docker": ("docker", "build", "-t", "token-iq-baseline", "."),
}

IN_UI: Final[frozenset[str]] = frozenset({"ui_build", "ui_tests"})


def _load(artifact: pathlib.Path) -> Baseline:
    if artifact.exists():
        return from_json(artifact.read_text(encoding="utf-8"))
    env: Final = describe_environment(REPO, parallel=False)
    return Baseline(
        commit=str(env["commit"]),
        python=str(env["python"]),
        platform=str(env["platform"]),
        captured_at=str(env["captured_at"]),
        parallel=False,
        suites=(),
        commands=(),
    )


def _replacing(existing: Sequence[SuiteRun], fresh: SuiteRun) -> tuple[SuiteRun, ...]:
    kept: Final = tuple(s for s in existing if s.name != fresh.name)
    return tuple(sorted((*kept, fresh), key=lambda s: s.name))


def _replacing_command(existing: Sequence[CommandRun], fresh: CommandRun) -> tuple[CommandRun, ...]:
    kept: Final = tuple(c for c in existing if c.name != fresh.name)
    return tuple(sorted((*kept, fresh), key=lambda c: c.name))


def _write(baseline: Baseline, artifact: pathlib.Path) -> None:
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(dataclasses.asdict(baseline), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def capture(section: str, reports: pathlib.Path, workers: int = 0, artifact: pathlib.Path = ARTIFACT) -> None:
    current: Final = _load(artifact)
    if section in SUITES:
        run: Final = capture_suite(section, SUITES[section], REPO, reports, workers)
        failed: Final = sum(1 for o in run.outcomes if o.outcome in ("failed", "error"))
        print(f"{section}: {len(run.outcomes)} tests, {failed} failing")
        if run.collection_errors:
            # Said out loud, because the cases those files hold are absent from the report
            # rather than failing in it, and a quieter run would read as a smaller suite.
            print(f"{section}: {run.collection_errors} file(s) would not import")
        _write(dataclasses.replace(current, suites=_replacing(current.suites, run)), artifact)
        return

    where: Final = UI if section in IN_UI else REPO
    command: Final = capture_command(section, COMMANDS[section], where)
    print(f"{section}: exit {command.exit_code}")
    _write(dataclasses.replace(current, commands=_replacing_command(current.commands, command)), artifact)


def main(argv: Sequence[str] | None = None) -> int:
    known: Final = (*SUITES, *COMMANDS)
    parser: Final = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--section", action="append", choices=known, default=[])
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--reports", default=None, help="where junit xml is written")
    parser.add_argument("--workers", type=int, default=0, help="pytest-xdist workers; 0 runs serially")
    parser.add_argument("--artifact", default=None, help=f"where to write; default {ARTIFACT.name}")
    args: Final = parser.parse_args(argv)

    reports: Final = pathlib.Path(args.reports) if args.reports else REPO / ".git" / "phase0-reports"
    reports.mkdir(parents=True, exist_ok=True)

    artifact: Final = pathlib.Path(args.artifact) if args.artifact else ARTIFACT
    for section in known if args.all else args.section:
        capture(section, reports, args.workers, artifact)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
