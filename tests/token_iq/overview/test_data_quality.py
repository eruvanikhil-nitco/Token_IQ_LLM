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
            accounts_double_counted=0,
            keys_without_project=0,
        )

        assert _issue(issues, "failing_connections").state == Measured(1)

    def test_a_source_nobody_has_connected_is_not_a_failure(self) -> None:
        """`not_connected` is the normal state of a provider a customer does not use. Counting it as
        a failure would put every unused provider on the issues list on day one."""
        issues = data_quality_issues(
            connection_states=("not_connected", "not_connected"),
            missing_invoices=0,
            accounts_double_counted=0,
            keys_without_project=0,
        )

        assert _issue(issues, "failing_connections").state == Measured(0)

    def test_waiting_for_first_data_is_not_a_failure_either(self) -> None:
        issues = data_quality_issues(
            connection_states=("waiting_for_first_data",),
            missing_invoices=0,
            accounts_double_counted=0,
            keys_without_project=0,
        )

        assert _issue(issues, "failing_connections").state == Measured(0)


class TestMissingInvoices:
    def test_counts_a_period_with_no_invoice(self) -> None:
        issues = data_quality_issues(
            connection_states=(),
            missing_invoices=2,
            accounts_double_counted=0,
            keys_without_project=0,
        )

        assert _issue(issues, "missing_invoices").state == Measured(2)

class TestKeysWithoutProjects:
    def test_counts_them(self) -> None:
        issues = data_quality_issues(connection_states=(), missing_invoices=0, accounts_double_counted=0, keys_without_project=4)

        assert _issue(issues, "keys_without_project").state == Measured(4)

    def test_none_is_a_measured_zero(self) -> None:
        issues = data_quality_issues(connection_states=(), missing_invoices=0, accounts_double_counted=0, keys_without_project=0)

        assert _issue(issues, "keys_without_project").state == Measured(0)


class TestUnmatchedPeople:
    """The one the blueprint names that cannot be answered yet.

    Matching a person across gateway keys, ChatGPT, Claude Code and Copilot needs directory sync,
    which section 12 lists as its own "Must" and which nothing in this repository implements. There
    is no directory to match against, so there is no number.
    """

    def test_it_is_reported_as_unmeasurable_rather_than_zero(self) -> None:
        issues = data_quality_issues(connection_states=(), missing_invoices=0, accounts_double_counted=0, keys_without_project=0)
        state = _issue(issues, "unmatched_people").state

        assert isinstance(state, Unmeasurable)
        assert state != Measured(0)

    def test_it_says_what_is_missing_rather_than_just_declining(self) -> None:
        """"Unknown" on a page asking whether the data can be trusted is only useful with the
        reason attached, because the reason is the thing somebody has to go and fix."""
        issues = data_quality_issues(connection_states=(), missing_invoices=0, accounts_double_counted=0, keys_without_project=0)
        state = _issue(issues, "unmatched_people").state

        assert isinstance(state, Unmeasurable)
        assert "directory" in state.reason.lower()


class TestTheListItself:
    def test_every_issue_the_blueprint_names_appears(self) -> None:
        issues = data_quality_issues(connection_states=(), missing_invoices=0, accounts_double_counted=0, keys_without_project=0)

        assert tuple(issue.key for issue in issues) == ISSUE_KEYS

    def test_each_one_says_where_it_is_fixed(self) -> None:
        """A count with nowhere to go is a complaint. The blueprint's issues list links to the page
        that fixes each one."""
        issues = data_quality_issues(connection_states=(), missing_invoices=0, accounts_double_counted=0, keys_without_project=0)

        for issue in issues:
            assert issue.fix_on, issue.key
            assert issue.title, issue.key

    def test_the_order_is_fixed_so_the_list_does_not_reshuffle(self) -> None:
        busy = data_quality_issues(
            connection_states=("needs_attention",),
            missing_invoices=1,
            accounts_double_counted=0,
            keys_without_project=9,
        )
        quiet = data_quality_issues(connection_states=(), missing_invoices=0, accounts_double_counted=0, keys_without_project=0)

        assert tuple(i.key for i in busy) == tuple(i.key for i in quiet)

    @pytest.mark.parametrize("key", ISSUE_KEYS)
    def test_no_issue_is_silently_dropped(self, key: str) -> None:
        issues = data_quality_issues(connection_states=(), missing_invoices=0, accounts_double_counted=0, keys_without_project=0)

        assert key in {issue.key for issue in issues}


class TestWhatNeedsAttentionOverall:
    def test_says_how_many_issues_actually_have_something_to_fix(self) -> None:
        from token_iq.overview.data_quality import issues_to_fix

        issues = data_quality_issues(
            connection_states=("needs_attention",),
            missing_invoices=1,
            accounts_double_counted=0,
            keys_without_project=0,
        )

        assert issues_to_fix(issues) == 2

    def test_an_unmeasurable_issue_is_not_counted_as_something_to_fix(self) -> None:
        """Nor as something that is fine. It is simply not part of this number, and the list still
        shows it so nobody mistakes the number for the whole picture."""
        from token_iq.overview.data_quality import issues_to_fix

        issues = data_quality_issues(connection_states=(), missing_invoices=0, accounts_double_counted=0, keys_without_project=0)

        assert issues_to_fix(issues) == 0


class TestInvoiceCoverage:
    """The blueprint's headline figure reads "September invoices: 5 of 6", so this is a fraction
    rather than a defect count. A bare "1 missing" does not say whether that is one of two or one
    of fifty."""

    def test_covered_is_the_billed_providers_that_have_an_invoice(self) -> None:
        from token_iq.overview.data_quality import InvoicesCovered, invoice_coverage

        coverage = invoice_coverage(providers_billed=6, providers_missing_invoice=1)

        assert coverage == InvoicesCovered(providers_billed=6, providers_invoiced=5)

    def test_every_billed_provider_invoiced_is_full_coverage(self) -> None:
        from token_iq.overview.data_quality import InvoicesCovered, invoice_coverage

        assert invoice_coverage(providers_billed=3, providers_missing_invoice=0) == InvoicesCovered(
            providers_billed=3, providers_invoiced=3
        )

    def test_none_of_them_invoiced_is_zero_of_the_billed_count(self) -> None:
        """The state this installation is actually in: one provider billing and no invoices at all.
        It has to read as nothing covered rather than as nothing to cover."""
        from token_iq.overview.data_quality import InvoicesCovered, invoice_coverage

        assert invoice_coverage(providers_billed=1, providers_missing_invoice=1) == InvoicesCovered(
            providers_billed=1, providers_invoiced=0
        )

    def test_nobody_billing_is_its_own_state_rather_than_zero_of_zero(self) -> None:
        """"0 of 0 invoiced" renders as perfect coverage or as total failure depending on the
        screen, and a period in which nobody billed is neither. Same reason `Unmeasurable` exists."""
        from token_iq.overview.data_quality import InvoicesCovered, NothingBilled, invoice_coverage

        coverage = invoice_coverage(providers_billed=0, providers_missing_invoice=0)

        assert coverage == NothingBilled()
        assert not isinstance(coverage, InvoicesCovered)


class TestFiguresTwoAccountsBothReported:
    """The fourth de-duplication rule, and the only one nothing else enforces.

    It reaches this list rather than dropping a fact, because no provider says which of its
    accounts a credential reads: two connections covering one account cannot be told from two
    covering two, and a wrong deletion halves a bill with nothing to show it was halved.
    """

    def test_it_is_counted_and_sends_the_reader_to_the_accounts(self) -> None:
        issues = data_quality_issues(
            connection_states=(),
            missing_invoices=0,
            accounts_double_counted=3,
            keys_without_project=0,
        )
        found = next(issue for issue in issues if issue.key == "accounts_double_counted")

        assert found.state == Measured(3)
        assert found.fix_on == "data-sources"

    def test_none_found_is_a_measured_zero_rather_than_unmeasurable(self) -> None:
        # Unlike matching people across accounts, this question can be answered from what is
        # stored, so a zero here means looked at and none found.
        issues = data_quality_issues(
            connection_states=(),
            missing_invoices=0,
            accounts_double_counted=0,
            keys_without_project=0,
        )
        found = next(issue for issue in issues if issue.key == "accounts_double_counted")

        assert found.state == Measured(0)

    def test_it_counts_towards_what_needs_fixing(self) -> None:
        from token_iq.overview.data_quality import issues_to_fix

        issues = data_quality_issues(
            connection_states=(),
            missing_invoices=0,
            accounts_double_counted=2,
            keys_without_project=0,
        )

        assert issues_to_fix(issues) == 1
