"""Phase 0 baseline: telling "this already failed" apart from "I broke this"."""

from __future__ import annotations

import dataclasses
import json
import pathlib
from typing import Final

import pytest

from scripts.inventory.baseline import Baseline, SuiteRun, CaseOutcome, as_json, capture_suite, compare, count_collection_errors, from_json, parse_junit

REPO: Final = pathlib.Path(__file__).resolve().parents[2]


def _baseline(*outcomes: tuple[str, str]) -> Baseline:
    return Baseline(
        commit="deadbeef",
        python="3.12.0",
        platform="win32",
        captured_at="2026-10-04T00:00:00Z",
        parallel=False,
        suites=(SuiteRun(name="unit", outcomes=tuple(CaseOutcome(nodeid=n, outcome=o) for n, o in outcomes)),),
        commands=(),
    )


class TestCompare:
    def test_reports_a_test_that_newly_fails(self) -> None:
        before: Final = _baseline(("a::test_one", "passed"))
        after: Final = _baseline(("a::test_one", "failed"))
        assert compare(before, after).newly_failing == ("unit/a::test_one",)

    def test_stays_silent_about_a_test_that_failed_in_both(self) -> None:
        """The whole point of a baseline: an inherited failure is not a regression."""
        before: Final = _baseline(("a::test_one", "failed"))
        after: Final = _baseline(("a::test_one", "failed"))
        drift: Final = compare(before, after)
        assert drift.newly_failing == ()
        assert drift.still_failing == ("unit/a::test_one",)

    def test_reports_a_test_that_disappeared(self) -> None:
        """A move that loses a file makes the suite greener, which must not read as success."""
        before: Final = _baseline(("a::test_one", "passed"), ("a::test_two", "passed"))
        after: Final = _baseline(("a::test_one", "passed"))
        assert compare(before, after).disappeared == ("unit/a::test_two",)

    def test_reports_a_test_that_appeared(self) -> None:
        before: Final = _baseline(("a::test_one", "passed"))
        after: Final = _baseline(("a::test_one", "passed"), ("a::test_new", "passed"))
        assert compare(before, after).appeared == ("unit/a::test_new",)

    def test_reports_a_recovered_test_separately_from_a_broken_one(self) -> None:
        before: Final = _baseline(("a::test_one", "failed"), ("a::test_two", "passed"))
        after: Final = _baseline(("a::test_one", "passed"), ("a::test_two", "failed"))
        drift: Final = compare(before, after)
        assert drift.newly_passing == ("unit/a::test_one",)
        assert drift.newly_failing == ("unit/a::test_two",)

    def test_counts_an_error_as_a_failure(self) -> None:
        """A collection error is a broken test, not a passing one."""
        before: Final = _baseline(("a::test_one", "passed"))
        after: Final = _baseline(("a::test_one", "error"))
        assert compare(before, after).newly_failing == ("unit/a::test_one",)

    def test_does_not_treat_a_skip_as_a_failure(self) -> None:
        before: Final = _baseline(("a::test_one", "passed"))
        after: Final = _baseline(("a::test_one", "skipped"))
        drift: Final = compare(before, after)
        assert drift.newly_failing == ()

    def test_compares_each_suite_separately_so_a_nodeid_collision_cannot_hide_a_break(self) -> None:
        """The same nodeid can exist in two suites; they are different tests."""
        before: Final = Baseline(
            commit="x",
            python="3.12.0",
            platform="win32",
            captured_at="t",
            parallel=False,
            suites=(
                SuiteRun(name="unit", outcomes=(CaseOutcome(nodeid="a::t", outcome="passed"),)),
                SuiteRun(name="deploy", outcomes=(CaseOutcome(nodeid="a::t", outcome="passed"),)),
            ),
            commands=(),
        )
        after: Final = Baseline(
            commit="y",
            python="3.12.0",
            platform="win32",
            captured_at="t",
            parallel=False,
            suites=(
                SuiteRun(name="unit", outcomes=(CaseOutcome(nodeid="a::t", outcome="passed"),)),
                SuiteRun(name="deploy", outcomes=(CaseOutcome(nodeid="a::t", outcome="failed"),)),
            ),
            commands=(),
        )
        assert compare(before, after).newly_failing == ("deploy/a::t",)

    def test_reports_a_whole_suite_that_vanished(self) -> None:
        before: Final = Baseline(
            commit="x",
            python="3.12.0",
            platform="win32",
            captured_at="t",
            parallel=False,
            suites=(
                SuiteRun(name="unit", outcomes=(CaseOutcome(nodeid="a::t", outcome="passed"),)),
                SuiteRun(name="deploy", outcomes=(CaseOutcome(nodeid="b::t", outcome="passed"),)),
            ),
            commands=(),
        )
        after: Final = _baseline(("a::t", "passed"))
        assert compare(before, after).disappeared == ("deploy/b::t",)


class TestParseJunit:
    def test_reads_a_passing_case(self) -> None:
        xml: Final = """<testsuites><testsuite name="pytest">
            <testcase classname="tests.test_a" name="test_one" />
        </testsuite></testsuites>"""
        assert parse_junit(xml) == (CaseOutcome(nodeid="tests/test_a.py::test_one", outcome="passed"),)

    def test_reads_a_failure_an_error_and_a_skip(self) -> None:
        xml: Final = """<testsuites><testsuite name="pytest">
            <testcase classname="tests.test_a" name="test_f"><failure message="boom" /></testcase>
            <testcase classname="tests.test_a" name="test_e"><error message="collect" /></testcase>
            <testcase classname="tests.test_a" name="test_s"><skipped message="why" /></testcase>
        </testsuite></testsuites>"""
        assert tuple(o.outcome for o in parse_junit(xml)) == ("failed", "error", "skipped")

    def test_keeps_the_class_when_a_test_lives_in_one(self) -> None:
        """Two tests of the same name in different classes are different tests."""
        xml: Final = """<testsuites><testsuite name="pytest">
            <testcase classname="tests.test_a.TestOne" name="test_x" />
            <testcase classname="tests.test_a.TestTwo" name="test_x" />
        </testsuite></testsuites>"""
        assert tuple(o.nodeid for o in parse_junit(xml)) == (
            "tests/test_a.py::TestOne::test_x",
            "tests/test_a.py::TestTwo::test_x",
        )

    def test_rejects_xml_it_cannot_read_rather_than_reporting_an_empty_run(self) -> None:
        """An empty parse would look like a suite where every test vanished."""
        with pytest.raises(ValueError, match="not a junit report"):
            parse_junit("not xml at all")


class TestWorkersAreRecordedPerSuite:
    """How a suite was run belongs on the suite, not on the whole baseline.

    Suites are captured one at a time and resumed across sessions, so some can be serial and
    others parallel in the same artifact. One global flag then misstates most of them, and a
    baseline that cannot say how it was produced cannot be reproduced, which is its only job.
    """

    def test_a_suite_carries_its_own_worker_count(self) -> None:
        serial: Final = SuiteRun(name="a", outcomes=(), workers=0)
        parallel: Final = SuiteRun(name="b", outcomes=(), workers=4)
        assert (serial.workers, parallel.workers) == (0, 4)

    def test_a_baseline_can_hold_suites_run_differently(self) -> None:
        baseline: Final = Baseline(
            commit="x",
            python="3.12.0",
            platform="win32",
            captured_at="t",
            parallel=False,
            suites=(SuiteRun(name="a", outcomes=(), workers=0), SuiteRun(name="b", outcomes=(), workers=4)),
            commands=(),
        )
        assert {s.name: s.workers for s in baseline.suites} == {"a": 0, "b": 4}

    def test_a_round_trip_through_json_keeps_the_worker_count(self) -> None:
        baseline: Final = Baseline(
            commit="x",
            python="3.12.0",
            platform="win32",
            captured_at="t",
            parallel=False,
            suites=(SuiteRun(name="b", outcomes=(), workers=4),),
            commands=(),
        )
        assert from_json(as_json(baseline)).suites[0].workers == 4


class TestCollectionErrorsAreRecorded:
    """A suite whose collection was interrupted writes a smaller report, not no report.

    This is what went wrong in phase 0. `capture_suite` guards against collection dying
    outright, because then pytest writes nothing at all. It did not guard against pytest
    stopping partway: an unimportable file interrupts collection, the report is written with
    the cases gathered so far, and the rest are simply absent. The phase 0 baseline recorded
    372 cases under the Token IQ directories where a direct run collects 468, and nothing
    said so. Later that reads as 96 tests having vanished in whatever phase next compares.
    """

    def test_the_capture_tolerates_a_file_it_cannot_import(self) -> None:
        """Otherwise one bad file silently truncates everything collected after it."""
        # The quoted form, not the bare word: the comment explaining the flag also contains it,
        # so searching for the text passes whether or not the argument is actually passed.
        source: Final = (REPO / "scripts" / "inventory" / "baseline.py").read_text(encoding="utf-8")
        assert '"--continue-on-collection-errors"' in source, (
            "capture_suite stops at the first collection error, so every case after it is "
            "recorded as absent rather than as a problem with that file"
        )

    def test_a_suite_records_how_many_files_failed_to_collect(self) -> None:
        run: Final = SuiteRun(name="s", outcomes=(), collection_errors=3)
        assert run.collection_errors == 3

    def test_collection_errors_default_to_zero_so_old_artifacts_still_load(self) -> None:
        """The committed phase 0 baseline predates the field."""
        restored: Final = from_json(
            json.dumps(
                {
                    "commit": "c",
                    "python": "3.12",
                    "platform": "p",
                    "captured_at": "t",
                    "parallel": False,
                    "suites": [{"name": "s", "outcomes": []}],
                    "commands": [],
                }
            )
        )
        assert restored.suites[0].collection_errors == 0

    def test_more_files_failing_to_collect_is_reported_as_drift(self) -> None:
        """Without this a suite can lose a whole file and read as unchanged, because the
        cases it held are absent from both sides of the comparison rather than failing."""
        before: Final = Baseline(
            commit="a", python="3.12", platform="p", captured_at="t", parallel=False,
            suites=(SuiteRun(name="s", outcomes=(CaseOutcome("t.py::one", "passed"),), collection_errors=0),),
            commands=(),
        )
        after: Final = dataclasses.replace(
            before,
            suites=(SuiteRun(name="s", outcomes=(CaseOutcome("t.py::one", "passed"),), collection_errors=2),),
        )
        assert compare(before, after).newly_uncollectable == ("s: 0 to 2",)

    def test_the_same_number_failing_to_collect_is_not_drift(self) -> None:
        before: Final = Baseline(
            commit="a", python="3.12", platform="p", captured_at="t", parallel=False,
            suites=(SuiteRun(name="s", outcomes=(), collection_errors=2),),
            commands=(),
        )
        assert compare(before, before).newly_uncollectable == ()


class TestCountingCollectionErrors:
    """Taken from a real junit report, not from how junit is assumed to look."""

    COLLECTION_ERROR: Final = """<?xml version="1.0" encoding="utf-8"?>
    <testsuites><testsuite name="pytest" errors="1" failures="0" skipped="0" tests="11">
      <testcase classname="" name="tests.test_litellm.test_broken" time="0.0">
        <error message="collection failure">FileNotFoundError</error>
      </testcase>
      <testcase classname="tests.token_iq.ledger.test_reconciliation" name="test_one" time="0.0"/>
    </testsuite></testsuites>"""

    FIXTURE_ERROR: Final = """<?xml version="1.0" encoding="utf-8"?>
    <testsuites><testsuite name="pytest" errors="1" failures="0" skipped="0" tests="1">
      <testcase classname="tests.test_litellm.test_a" name="test_one" time="0.0">
        <error message="fixture blew up">RuntimeError</error>
      </testcase>
    </testsuite></testsuites>"""

    def test_a_file_that_would_not_import_is_counted(self) -> None:
        assert count_collection_errors(self.COLLECTION_ERROR) == 1

    def test_a_test_erroring_in_a_fixture_is_not_counted(self) -> None:
        """It is a failing test, not a lost file, and the comparison already reports it."""
        assert count_collection_errors(self.FIXTURE_ERROR) == 0

    def test_a_report_it_cannot_parse_counts_nothing_rather_than_raising(self) -> None:
        assert count_collection_errors("not xml") == 0

    def test_the_collectable_cases_are_still_parsed_alongside_the_error(self) -> None:
        """The point of tolerating the error is keeping everything collected after it."""
        assert parse_junit(self.COLLECTION_ERROR) == (
            CaseOutcome("tests/test_litellm/test_broken.py", "error"),
            CaseOutcome("tests/token_iq/ledger/test_reconciliation.py::test_one", "passed"),
        )

    def test_a_collection_error_is_named_after_the_file_not_turned_into_a_py_nodeid(self) -> None:
        """The committed phase 0 baseline holds 31 cases whose nodeid is `.py::<module>`, which
        names no file and matches nothing on either side of a comparison."""
        nodeids: Final = tuple(case.nodeid for case in parse_junit(self.COLLECTION_ERROR))
        assert not any(n.startswith(".py") for n in nodeids), nodeids


class TestATruncatedRunIsNotMistakenForACompleteOne:
    """pytest collected 46,571 cases and the report held 44,743, and nothing said so.

    `capture_suite` writes whatever junit holds when pytest exits. That is right when the run
    finished and wrong when it did not: a worker that dies under `-n 4` takes its unreported
    tests with it, pytest still exits and still writes a report, and the missing cases read
    later as tests that were deleted on purpose. Recording how many were collected alongside
    how many were reported is the only thing that tells those two apart.
    """

    def test_a_suite_records_how_many_cases_were_collected(self) -> None:
        run: Final = SuiteRun(name="s", outcomes=(), collected=12)
        assert run.collected == 12

    def test_collected_defaults_to_zero_so_older_artifacts_still_load(self) -> None:
        restored: Final = from_json(
            json.dumps(
                {
                    "commit": "c", "python": "3.12", "platform": "p", "captured_at": "t",
                    "parallel": False,
                    "suites": [{"name": "s", "outcomes": []}],
                    "commands": [],
                }
            )
        )
        assert restored.suites[0].collected == 0

    def test_a_run_reporting_fewer_cases_than_it_collected_is_incomplete(self) -> None:
        run: Final = SuiteRun(name="s", outcomes=(CaseOutcome("t.py::one", "passed"),), collected=3)
        assert run.unreported == 2
        assert not run.complete

    def test_a_run_reporting_everything_it_collected_is_complete(self) -> None:
        run: Final = SuiteRun(name="s", outcomes=(CaseOutcome("t.py::one", "passed"),), collected=1)
        assert run.unreported == 0
        assert run.complete

    def test_a_suite_that_never_recorded_a_collected_count_is_not_called_incomplete(self) -> None:
        """The phase 0 artifact predates the field; absent is unknown, not zero cases run."""
        run: Final = SuiteRun(name="s", outcomes=(CaseOutcome("t.py::one", "passed"),))
        assert run.complete

    def test_an_incomplete_run_is_reported_as_drift(self) -> None:
        before: Final = Baseline(
            commit="a", python="3.12", platform="p", captured_at="t", parallel=False,
            suites=(SuiteRun(name="s", outcomes=(CaseOutcome("t.py::one", "passed"),), collected=1),),
            commands=(),
        )
        after: Final = dataclasses.replace(
            before,
            suites=(SuiteRun(name="s", outcomes=(CaseOutcome("t.py::one", "passed"),), collected=9),),
        )
        assert compare(before, after).incomplete == ("s: reported 1 of 9 collected",)


class TestCaptureSuiteEndToEnd:
    """One real capture, on one real directory, through the whole path.

    Everything above tests the pieces. This runs pytest, writes junit, parses it back, and
    compares the reported count against the collected one, which is the only way to find out
    that an `Iterable` consumed twice leaves the second use with nothing.
    """

    @pytest.fixture(scope="class")
    def run(self, tmp_path_factory: pytest.TempPathFactory) -> SuiteRun:
        reports: Final = tmp_path_factory.mktemp("reports")
        # A generator, not a tuple: a second use of an exhausted one means pytest with no paths,
        # which collects the entire repository rather than this one directory.
        paths = (p for p in ("tests/token_iq/ledger",))
        return capture_suite("one_directory", paths, REPO, reports, workers=0)

    def test_it_collected_and_reported_the_same_number(self, run: SuiteRun) -> None:
        assert run.collected > 0, "nothing was collected; the paths did not reach pytest"
        assert run.unreported == 0, f"reported {len(run.outcomes)} of {run.collected} collected"
        assert run.complete

    def test_it_stayed_inside_the_directory_it_was_given(self, run: SuiteRun) -> None:
        """An exhausted generator would run the whole repository and still look like a pass."""
        outside: Final = tuple(
            case.nodeid for case in run.outcomes if not case.nodeid.startswith("tests/token_iq/ledger/")
        )
        assert not outside, f"ran {len(outside)} cases outside the given path, e.g. {outside[:2]}"

    def test_nothing_failed_to_collect(self, run: SuiteRun) -> None:
        assert run.collection_errors == 0
