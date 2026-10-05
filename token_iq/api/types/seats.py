"""Request and response shapes for seats and per-person cost.

Every amount crosses as a string, and a person's total always travels with its parts. A single
blended figure would give a reader no way to see how much is gateway traffic and how much is a
subscription, and no way to notice when one of them is missing.

`tool_usage_known` is on every response on purpose. No user tool connector exists, so a total
here covers gateway traffic and subscriptions only. A screen that did not say so would be read
as complete.
"""

from __future__ import annotations

from pydantic import BaseModel

from token_iq.types.seat import SeatCadence


class SeatBody(BaseModel):
    """What an admin sends after reading a subscription off a contract.

    `cadence` is the literal type, so a value nobody can name is refused by validation rather
    than stored and then silently skipped on read.
    """

    tool: str
    user_id: str
    cadence: SeatCadence
    currency: str = "USD"
    amount: str
    period_start: str
    period_end: str
    note: str | None = None


class SeatResponse(BaseModel):
    seat_id: str
    tool: str
    user_id: str
    cadence: SeatCadence
    currency: str
    amount: str
    period_start: str
    period_end: str
    note: str | None


class SeatListResponse(BaseModel):
    seats: tuple[SeatResponse, ...]


class SeatDeletedResponse(BaseModel):
    deleted: bool


class SeatLineResponse(BaseModel):
    tool: str
    currency: str
    amount: str


class UserCostResponse(BaseModel):
    user_id: str
    period_start: str
    period_end: str
    currency: str
    gateway: str
    seats: str
    total: str
    seat_lines: tuple[SeatLineResponse, ...]
    tool_usage_known: bool
    note: str


class UserCostListResponse(BaseModel):
    period_start: str
    period_end: str
    currency: str
    costs: tuple[UserCostResponse, ...]
