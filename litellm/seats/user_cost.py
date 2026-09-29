"""Add a person's gateway traffic to the subscriptions assigned to them.

A pure function: no database, no clock. The caller reads both sides and passes them in.

Two things this module refuses to do, both because the result would look right and be wrong.
It never adds a subscription priced in one currency to spend in another, and it never presents
a total as complete: `tool_usage_known` is False on every result here, because no user tool
connector exists, and the screen says so rather than letting a reader assume the figure covers
everything a person spent.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Final

from litellm.types.proxy.seat import Seat


@dataclass(frozen=True, slots=True)
class SeatLine:
    tool: str
    currency: str
    amount: Decimal


@dataclass(frozen=True, slots=True)
class UserCost:
    user_id: str
    currency: str
    gateway: Decimal
    seats: Decimal
    total: Decimal
    seat_lines: tuple[SeatLine, ...]
    tool_usage_known: bool


def user_costs(*, gateway_by_user: Mapping[str, Decimal], seats: Sequence[Seat], currency: str) -> tuple[UserCost, ...]:
    """One entry per person who either drove gateway traffic or holds a subscription.

    Sorted by user id so a screen does not reorder itself between reads.

    A seat in another currency is left out of the total rather than converted. Adding thirty
    euros to ten dollars produces forty of nothing, and it would look like an answer.
    """
    in_currency: Final = tuple(s for s in seats if s.currency == currency)
    people: Final = sorted(frozenset(gateway_by_user) | frozenset(s.user_id for s in in_currency))

    return tuple(
        _cost_for(user_id, gateway_by_user.get(user_id, Decimal(0)), in_currency, currency) for user_id in people
    )


def _cost_for(user_id: str, gateway: Decimal, seats: Sequence[Seat], currency: str) -> UserCost:
    lines: Final = tuple(
        SeatLine(tool=s.tool, currency=s.currency, amount=s.amount) for s in seats if s.user_id == user_id
    )
    seat_total: Final = sum((line.amount for line in lines), Decimal(0))
    return UserCost(
        user_id=user_id,
        currency=currency,
        gateway=gateway,
        seats=seat_total,
        total=gateway + seat_total,
        seat_lines=lines,
        tool_usage_known=False,
    )
