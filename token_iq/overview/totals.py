"""The headline figures for the Overview page.

Pure, so the one rule this product cannot get wrong can be tested without a database.

**A provider figure says how much was spent. A gateway figure says who spent it. They are
never added together.** This is where breaking that would do the most damage, because the
headline total is the number a customer repeats to their finance team without checking, and
adding the gateway's figure to the provider's would roughly double it.

So the total is what the providers billed, plus tool spend that appears on no provider bill,
plus seat fees. The gateway's figure never enters it. It appears on this page only as
attribution: how much of the provider total we can say who spent.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Final


@dataclass(frozen=True, slots=True)
class Sources:
    """What each source reported for one period, already summed.

    `gateway` is deliberately here and deliberately not added. Leaving it out of the type
    would make the rule invisible; a reader would have to know it was omitted on purpose
    rather than forgotten.
    """

    provider_billed: Decimal
    tool_new_money: Decimal
    seats: Decimal
    gateway_recorded: Decimal
    unallocated: Decimal
    has_any_data: bool


@dataclass(frozen=True, slots=True)
class Totals:
    total: Decimal | None
    previous_total: Decimal | None
    change: Decimal | None
    """The signed difference. None when there is nothing to compare against, rather than a
    rise from zero, which would read as a new customer tripling their spend in their first
    month."""

    attributed: Decimal | None
    unallocated: Decimal | None
    unallocated_share: Decimal | None

    @property
    def has_figures(self) -> bool:
        return self.total is not None


def _share(part: Decimal, whole: Decimal) -> Decimal | None:
    """A percentage, or nothing when the denominator cannot support one."""
    if whole <= 0:
        return None
    return (part / whole * 100).quantize(Decimal("0.1"))


def totals_for(current: Sources, previous: Sources | None = None) -> Totals:
    """The headline figures, or nothing when the period holds nothing.

    A period with no data reports nothing rather than zero. Zero asserts the company spent
    nothing, which is a different and more dangerous claim than not knowing yet, and on a
    landing page it is the difference between "you are not connected" and "you are free".
    """
    if not current.has_any_data:
        return Totals(
            total=None,
            previous_total=None,
            change=None,
            attributed=None,
            unallocated=None,
            unallocated_share=None,
        )

    # The gateway figure is absent from this sum on purpose. See the module docstring.
    total: Final = current.provider_billed + current.tool_new_money + current.seats

    previous_total: Final = (
        previous.provider_billed + previous.tool_new_money + previous.seats
        if previous is not None and previous.has_any_data
        else None
    )

    return Totals(
        total=total,
        previous_total=previous_total,
        change=None if previous_total is None else total - previous_total,
        attributed=current.gateway_recorded,
        unallocated=current.unallocated,
        unallocated_share=_share(current.unallocated, current.provider_billed),
    )
