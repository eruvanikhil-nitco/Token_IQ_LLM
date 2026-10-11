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

# The reconciliation outcome that means nobody has entered a bill for a period. The others,
# `unexplained_difference` and `currency_mismatch`, are real problems that belong to Invoice
# Reconciliation: they are about a bill that disagrees, not about data that never arrived.
MISSING_INVOICE_OUTCOME: Final = "no_invoice"


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
    "unmatched_people",
    "keys_without_project",
)
"""Fixed order, so the list does not reshuffle as counts change under it."""


def data_quality_issues(
    *,
    connection_states: Sequence[str],
    reconciliation_outcomes: Sequence[str],
    keys_without_project: int,
) -> tuple[DataQualityIssue, ...]:
    """The four issues, each either counted or declared unmeasurable.

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
            state=Measured(sum(1 for outcome in reconciliation_outcomes if outcome == MISSING_INVOICE_OUTCOME)),
            fix_on="ledger",
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


def issues_to_fix(issues: Sequence[DataQualityIssue]) -> int:
    """How many issues have something to act on.

    An unmeasurable issue is not counted here, and is not counted as fine either: it is simply not
    part of this number, and the list still shows it so nobody mistakes the number for the whole
    picture.
    """
    return sum(1 for issue in issues if isinstance(issue.state, Measured) and issue.state.count > 0)
