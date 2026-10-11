"""The issues list on Data Sources > Overview.

Blueprint section 12 names four: failing connections, missing invoices, unmatched people, keys
without projects. The tab's own question is "Can the data be trusted?", so the list has to be
honest about what it has not looked at, which is the whole reason this is a tagged union rather
than four integers.

A count of zero means "I looked and found none". An issue nobody can measure yet must not borrow
that number, because on a page answering "can this be trusted?" a zero reads as reassurance.
"""

from __future__ import annotations

import pytest

from token_iq.overview.data_quality import (
    ISSUE_KEYS,
    Measured,
    Unmeasurable,
    data_quality_issues,
)


def _issue(issues, key: str):
    found = [issue for issue in issues if issue.key == key]
    assert len(found) == 1, f"{key} appears {len(found)} times"
    return found[0]


class TestFailingConnections:
    def test_counts_a_connection_needing_attention(self) -> None:
        issues = data_quality_issues(
            connection_states=("healthy", "needs_attention", "healthy"),
            missing_invoices=0,
            keys_without_project=0,
        )

        assert _issue(issues, "failing_connections").state == Measured(1)

    def test_a_source_nobody_has_connected_is_not_a_failure(self) -> None:
        """`not_connected` is the normal state of a provider a customer does not use. Counting it as
        a failure would put every unused provider on the issues list on day one."""
        issues = data_quality_issues(
            connection_states=("not_connected", "not_connected"),
            missing_invoices=0,
            keys_without_project=0,
        )

        assert _issue(issues, "failing_connections").state == Measured(0)

    def test_waiting_for_first_data_is_not_a_failure_either(self) -> None:
        issues = data_quality_issues(
            connection_states=("waiting_for_first_data",),
            missing_invoices=0,
            keys_without_project=0,
        )

        assert _issue(issues, "failing_connections").state == Measured(0)


class TestMissingInvoices:
    def test_counts_a_period_with_no_invoice(self) -> None:
        issues = data_quality_issues(
            connection_states=(),
            missing_invoices=2,
            keys_without_project=0,
        )

        assert _issue(issues, "missing_invoices").state == Measured(2)

class TestKeysWithoutProjects:
    def test_counts_them(self) -> None:
        issues = data_quality_issues(connection_states=(), missing_invoices=0, keys_without_project=4)

        assert _issue(issues, "keys_without_project").state == Measured(4)

    def test_none_is_a_measured_zero(self) -> None:
        issues = data_quality_issues(connection_states=(), missing_invoices=0, keys_without_project=0)

        assert _issue(issues, "keys_without_project").state == Measured(0)


class TestUnmatchedPeople:
    """The one the blueprint names that cannot be answered yet.

    Matching a person across gateway keys, ChatGPT, Claude Code and Copilot needs directory sync,
    which section 12 lists as its own "Must" and which nothing in this repository implements. There
    is no directory to match against, so there is no number.
    """

    def test_it_is_reported_as_unmeasurable_rather_than_zero(self) -> None:
        issues = data_quality_issues(connection_states=(), missing_invoices=0, keys_without_project=0)
        state = _issue(issues, "unmatched_people").state

        assert isinstance(state, Unmeasurable)
        assert state != Measured(0)

    def test_it_says_what_is_missing_rather_than_just_declining(self) -> None:
        """"Unknown" on a page asking whether the data can be trusted is only useful with the
        reason attached, because the reason is the thing somebody has to go and fix."""
        issues = data_quality_issues(connection_states=(), missing_invoices=0, keys_without_project=0)
        state = _issue(issues, "unmatched_people").state

        assert isinstance(state, Unmeasurable)
        assert "directory" in state.reason.lower()


class TestTheListItself:
    def test_every_issue_the_blueprint_names_appears(self) -> None:
        issues = data_quality_issues(connection_states=(), missing_invoices=0, keys_without_project=0)

        assert tuple(issue.key for issue in issues) == ISSUE_KEYS

    def test_each_one_says_where_it_is_fixed(self) -> None:
        """A count with nowhere to go is a complaint. The blueprint's issues list links to the page
        that fixes each one."""
        issues = data_quality_issues(connection_states=(), missing_invoices=0, keys_without_project=0)

        for issue in issues:
            assert issue.fix_on, issue.key
            assert issue.title, issue.key

    def test_the_order_is_fixed_so_the_list_does_not_reshuffle(self) -> None:
        busy = data_quality_issues(
            connection_states=("needs_attention",),
            missing_invoices=1,
            keys_without_project=9,
        )
        quiet = data_quality_issues(connection_states=(), missing_invoices=0, keys_without_project=0)

        assert tuple(i.key for i in busy) == tuple(i.key for i in quiet)

    @pytest.mark.parametrize("key", ISSUE_KEYS)
    def test_no_issue_is_silently_dropped(self, key: str) -> None:
        issues = data_quality_issues(connection_states=(), missing_invoices=0, keys_without_project=0)

        assert key in {issue.key for issue in issues}


class TestWhatNeedsAttentionOverall:
    def test_says_how_many_issues_actually_have_something_to_fix(self) -> None:
        from token_iq.overview.data_quality import issues_to_fix

        issues = data_quality_issues(
            connection_states=("needs_attention",),
            missing_invoices=1,
            keys_without_project=0,
        )

        assert issues_to_fix(issues) == 2

    def test_an_unmeasurable_issue_is_not_counted_as_something_to_fix(self) -> None:
        """Nor as something that is fine. It is simply not part of this number, and the list still
        shows it so nobody mistakes the number for the whole picture."""
        from token_iq.overview.data_quality import issues_to_fix

        issues = data_quality_issues(connection_states=(), missing_invoices=0, keys_without_project=0)

        assert issues_to_fix(issues) == 0
