"""The issues list on Data Sources > Overview: what is wrong with the incoming data.

The tab's question is "Can the data be trusted?", and blueprint section 12 names the four things it
answers with: failing connections, missing invoices, unmatched people, keys without projects.

Three of the four can be answered from what this repository already stores. The fourth cannot, and
that is the reason an issue's state is a tagged union rather than an integer. A zero means "I looked
and found none". An issue nobody can measure yet must not borrow that number, because on a page
asking whether the data can be trusted a zero reads as reassurance, and the one thing worse than a
known problem is an unknown one presented as a clean bill of health.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from typing import Final, TypeAlias

# The connection state that means somebody has to do something. `not_connected` is the normal state
# of a provider a customer does not use, and `waiting_for_first_data` is a connection that is fine
# and simply new; counting either would put every unused provider on the list on day one.
FAILING_CONNECTION_STATE: Final = "needs_attention"


@dataclasses.dataclass(frozen=True, slots=True)
class Measured:
    """How many of this issue there are. Zero means looked at and none found."""

    count: int


@dataclasses.dataclass(frozen=True, slots=True)
class Unmeasurable:
    """Nobody can answer this yet, and why.

    The reason is the useful part: it is the thing somebody has to go and build or configure before
    the question can be answered at all.
    """

    reason: str


IssueState: TypeAlias = Measured | Unmeasurable


@dataclasses.dataclass(frozen=True, slots=True)
class DataQualityIssue:
    key: str
    title: str
    state: IssueState
    fix_on: str
    """The page id that fixes it. A count with nowhere to go is a complaint rather than an issue."""


ISSUE_KEYS: Final[tuple[str, ...]] = (
    "failing_connections",
    "missing_invoices",
    "accounts_double_counted",
    "unmatched_people",
    "keys_without_project",
)
"""Fixed order, so the list does not reshuffle as counts change under it."""


def data_quality_issues(
    *,
    connection_states: Sequence[str],
    missing_invoices: int,
    accounts_double_counted: int,
    keys_without_project: int,
) -> tuple[DataQualityIssue, ...]:
    """The issues, each either counted or declared unmeasurable.

    Takes the facts rather than fetching them, so the rule about what counts as a problem is
    testable without a database and lives in one place instead of in each screen that asks.
    """
    return (
        DataQualityIssue(
            key="failing_connections",
            title="Connections needing attention",
            state=Measured(sum(1 for state in connection_states if state == FAILING_CONNECTION_STATE)),
            fix_on="data-sources",
        ),
        DataQualityIssue(
            key="missing_invoices",
            title="Periods with no invoice",
            # Counted by the repository, which asks for providers that billed in the period and
            # have no invoice covering it. That is the ledger's `no_invoice` outcome and only
            # that one: `unexplained_difference` and `currency_mismatch` are real problems about
            # a bill that disagrees rather than data that never arrived, and they belong to
            # Invoice Reconciliation, so sending somebody here to fix one would be the wrong page.
            state=Measured(missing_invoices),
            fix_on="ledger",
        ),
        DataQualityIssue(
            key="accounts_double_counted",
            title="Figures two accounts both reported",
            # The fourth de-duplication rule, and the only one nothing else enforces. No provider
            # tells us which of its accounts a credential reads, so two connections covering one
            # account cannot be told from two covering two. What can be told is the figure: the
            # same amount, to every digit, for one day and one meter under two accounts. Reported
            # rather than dropped, because the answer belongs to the customer and a wrong deletion
            # halves a bill with nothing to show it was halved.
            state=Measured(accounts_double_counted),
            fix_on="data-sources",
        ),
        DataQualityIssue(
            key="unmatched_people",
            title="People not matched across accounts",
            # Matching one person across gateway keys, ChatGPT, Claude Code and Copilot needs
            # directory sync, which section 12 lists as its own "Must" and which nothing here
            # implements. There is no directory to match against, so there is no number.
            state=Unmeasurable(reason="Needs directory sync, which is not built yet"),
            fix_on="access-control",
        ),
        DataQualityIssue(
            key="keys_without_project",
            title="Virtual keys with no project",
            state=Measured(keys_without_project),
            fix_on="api-keys",
        ),
    )


@dataclasses.dataclass(frozen=True, slots=True)
class InvoicesCovered:
    """How many of the providers that billed in the period have an invoice covering it."""

    providers_billed: int
    providers_invoiced: int


@dataclasses.dataclass(frozen=True, slots=True)
class NothingBilled:
    """No provider billed anything in the period, so there is nothing an invoice could cover.

    Its own state rather than a zero over zero, for the same reason `Unmeasurable` exists. "0 of 0
    invoiced" is read either as perfect coverage or as total failure depending on how a screen
    renders it, and neither is what happened.
    """


InvoiceCoverage: TypeAlias = InvoicesCovered | NothingBilled


def invoice_coverage(*, providers_billed: int, providers_missing_invoice: int) -> InvoiceCoverage:
    """Invoice coverage for the period, as the blueprint's headline figure reads it.

    The missing count is a subset of the billed count by construction: both come from the providers
    with usage facts inside the period, and the missing one additionally requires no invoice
    spanning the day. So the covered figure is the difference, with nothing to clamp.
    """
    if providers_billed == 0:
        return NothingBilled()
    return InvoicesCovered(
        providers_billed=providers_billed,
        providers_invoiced=providers_billed - providers_missing_invoice,
    )


def issues_to_fix(issues: Sequence[DataQualityIssue]) -> int:
    """How many issues have something to act on.

    An unmeasurable issue is not counted here, and is not counted as fine either: it is simply not
    part of this number, and the list still shows it so nobody mistakes the number for the whole
    picture.
    """
    return sum(1 for issue in issues if isinstance(issue.state, Measured) and issue.state.count > 0)
