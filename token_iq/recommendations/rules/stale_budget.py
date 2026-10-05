"""A budget that no longer matches what is actually spent.

No figure either. Changing a budget changes a limit, not spend: raising one saves nothing and
lowering one saves nothing by itself. What it changes is whether the limit still means anything,
which is worth knowing in both directions.

A budget being exceeded and a budget set far too high are different problems for different
people, so they are reported as different cards rather than one card with a signed number.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Final

from token_iq.recommendations.inputs import BudgetSnapshot, RuleInput
from token_iq.types.recommendation import Evidence, Recommendation

RULE_ID: Final = "stale_budget"

UNUSED_BELOW: Final = Decimal("0.25")
"""A budget used less than this is not doing any work, and the number in it is not a decision."""


def _worst(budgets: tuple[BudgetSnapshot, ...]) -> tuple[BudgetSnapshot, Decimal] | None:
    """The budget furthest from its spend, over or under, or nothing when all are sensible."""
    scored: Final = tuple((b, b.spent / b.limit) for b in budgets if b.limit > Decimal(0))
    interesting: Final = tuple((b, used) for b, used in scored if used > Decimal(1) or used < UNUSED_BELOW)
    if not interesting:
        return None
    return max(interesting, key=lambda pair: abs(pair[1] - Decimal(1)))


def stale_budget(rule_input: RuleInput) -> Recommendation | None:
    """A card when a budget is being exceeded, or is set so high it constrains nothing."""
    found: Final = _worst(rule_input.budgets)
    if found is None:
        return None

    budget, used = found
    percent: Final = (used * 100).quantize(Decimal("0.1"))
    exceeded: Final = used > Decimal(1)

    return Recommendation(
        rule_id=RULE_ID,
        kind="business",
        title="A budget is being exceeded" if exceeded else "A budget no longer constrains anything",
        noticed=(
            f"{budget.owner} spent {percent}% of its budget. The limit is being passed, so it is "
            "either the wrong limit or the spend needs attention."
            if exceeded
            else (
                f"{budget.owner} spent {percent}% of its budget. A limit this far above actual spend "
                "stops no overspend, so the number in it is not really a decision any more."
            )
        ),
        evidence=(
            Evidence(label="Budget owner", value=budget.owner),
            Evidence(label="Limit", value=format(budget.limit, "f")),
            Evidence(label="Spent", value=format(budget.spent, "f")),
        ),
        figure=None,
        figure_kind="none",
        currency=None,
        who_should_act="Whoever set the budget",
    )
