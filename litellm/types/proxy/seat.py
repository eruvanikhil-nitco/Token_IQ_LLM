"""A flat per-person subscription, as an admin read it off a contract.

Seat pricing lives on a contract rather than behind an API, so this is typed information a
person entered. `amount` is exact digits: it is added to a person's gateway spend, and a rounded
subscription would make that total wrong by a fraction of a cent every month.

A seat covers a period, never a day. Spreading a monthly fee across days to make it line up with
daily gateway spend would invent a daily figure the company was never charged.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal

SeatCadence = Literal["monthly", "annual"]
"""How often the subscription is billed. The period on the seat says which one it covers, so the
cadence is what the contract says rather than something the arithmetic depends on."""


@dataclass(frozen=True, slots=True)
class Seat:
    seat_id: str
    tool: str
    user_id: str
    cadence: SeatCadence
    currency: str
    amount: Decimal
    period_start: datetime
    period_end: datetime
    note: str | None = None
