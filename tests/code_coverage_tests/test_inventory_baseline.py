"""Phase 0 baseline: telling "this already failed" apart from "I broke this"."""

from __future__ import annotations

from typing import Final

import pytest

from scripts.inventory.baseline import Baseline, SuiteRun, CaseOutcome, compare, parse_junit


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
        with pytest.raises(ValueError):
            parse_junit("not xml at all")
