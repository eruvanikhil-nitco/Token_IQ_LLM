"""Serve the seats an admin entered and what each person costs.

The arithmetic lives in `token_iq/seats/user_cost.py` and the reads in the two repositories, all
tested there. This module shapes the answer into strings a JSON client cannot round, and
enforces who is allowed to see whose cost.

Privacy is a requirement of this module, not of the screen in front of it. The product design
says a person sees only their own cost and an admin sees everyone's. A UI that merely hid the
other rows would still be handing them over to anyone who called the endpoint directly.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Final

import fastapi
from fastapi import APIRouter, Depends, HTTPException, status

from litellm.proxy._types import CommonProxyErrors, LitellmUserRoles, UserAPIKeyAuth
from litellm.proxy.auth.user_api_key_auth import user_api_key_auth
from litellm.types.proxy.seat import Seat
from token_iq.api.types.seats import (
    SeatBody,
    SeatDeletedResponse,
    SeatLineResponse,
    SeatListResponse,
    SeatResponse,
    UserCostListResponse,
    UserCostResponse,
)
from token_iq.repositories.gateway_spend_repository import GatewaySpendRepository
from token_iq.repositories.seat_repository import SeatRepository
from token_iq.seats.user_cost import UserCost, user_costs

router: Final = APIRouter(
    tags=["seats"],  # mutable-ok: fixed single-element tag list, never grown after this line
    dependencies=(Depends(user_api_key_auth),),
)

INCOMPLETE_NOTE: Final = (
    "This covers gateway traffic and subscriptions. It does not include what this person spent "
    "inside Claude Code, Copilot, Cursor or Codex, because no user tool is connected."
)
"""Said on every response, not only when it looks wrong.

A total that quietly omitted a third of someone's cost would be read as their whole cost."""


def _plain(value: Decimal) -> str:
    """Fixed-point, never scientific notation: Decimal renders small results as 5E-7."""
    return format(value, "f")


def _proxy_error(status_code: int, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"error": message},  # mutable-ok: fixed one-key error envelope, matches every other proxy endpoint
    )


def _admin_or_403(user_api_key_dict: UserAPIKeyAuth) -> None:
    if user_api_key_dict.user_role != LitellmUserRoles.PROXY_ADMIN:
        raise _proxy_error(status.HTTP_403_FORBIDDEN, "Only a proxy admin may read or change seats.")


def _self_or_admin_or_403(user_api_key_dict: UserAPIKeyAuth, user_id: str) -> None:
    """A person may read their own cost. Anyone else's needs an admin.

    What one person costs is personal, so this is checked here rather than left to the screen.
    """
    if user_api_key_dict.user_role == LitellmUserRoles.PROXY_ADMIN:
        return
    if user_api_key_dict.user_id == user_id:
        return
    raise _proxy_error(status.HTTP_403_FORBIDDEN, "You may only read your own cost.")


def _day_or_400(value: str, field: str) -> datetime:
    try:
        parsed: Final = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise _proxy_error(status.HTTP_400_BAD_REQUEST, f"{field} is not a date: {value!r}.") from None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def _period_end_or_400(value: str, field: str) -> datetime:
    """The last instant of the period, not its first.

    A reader who types the thirtieth means the whole of it. Parsing that to midnight drops
    almost the entire final day, which the ledger endpoints already had to learn.

    The last instant is `.999` and not `.999999` because these columns are `TIMESTAMP(3)`:
    Postgres rounds a microsecond value up on insert, so `23:59:59.999999` becomes midnight on
    the next day and lands outside the very period it belongs to. A seat stored that way could
    never be found again, which a live run proved before any test did.
    """
    parsed: Final = _day_or_400(value, field)
    names_a_time: Final = "T" in value or " " in value.strip()
    return parsed if names_a_time else parsed.replace(hour=23, minute=59, second=59, microsecond=999000)


def _amount_or_400(value: str, field: str) -> Decimal:
    try:
        return Decimal(value)
    except InvalidOperation:
        raise _proxy_error(status.HTTP_400_BAD_REQUEST, f"{field} is not an amount: {value!r}.") from None


def _seat_response(seat: Seat) -> SeatResponse:
    return SeatResponse(
        seat_id=seat.seat_id,
        tool=seat.tool,
        user_id=seat.user_id,
        cadence=seat.cadence,
        currency=seat.currency,
        amount=_plain(seat.amount),
        period_start=seat.period_start.date().isoformat(),
        period_end=seat.period_end.date().isoformat(),
        note=seat.note,
    )


def user_cost_response(*, cost: UserCost, period_start: datetime, period_end: datetime) -> UserCostResponse:
    """Shape one person's cost into the response a screen reads.

    Split out of the route so the shaping, in particular that the parts stay separate and the
    missing part stays named, can be tested without a database.
    """
    return UserCostResponse(
        user_id=cost.user_id,
        period_start=period_start.date().isoformat(),
        period_end=period_end.date().isoformat(),
        currency=cost.currency,
        gateway=_plain(cost.gateway),
        seats=_plain(cost.seats),
        total=_plain(cost.total),
        seat_lines=tuple(
            SeatLineResponse(tool=line.tool, currency=line.currency, amount=_plain(line.amount))
            for line in cost.seat_lines
        ),
        tool_usage_known=cost.tool_usage_known,
        note=INCOMPLETE_NOTE,
    )


async def _costs_for(prisma_client: object, *, start: datetime, end: datetime, currency: str) -> tuple[UserCost, ...]:
    gateway: Final = await GatewaySpendRepository(prisma_client).by_user_for_period(period_start=start, period_end=end)
    seats: Final = await SeatRepository(prisma_client).for_period(period_start=start, period_end=end)
    return user_costs(gateway_by_user=gateway, seats=seats, currency=currency)


@router.get("/seats", response_model=SeatListResponse)
async def list_seats(user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth)) -> SeatListResponse:
    """Every subscription an admin has entered."""
    from litellm.proxy.proxy_server import prisma_client

    _admin_or_403(user_api_key_dict)
    if prisma_client is None:
        raise _proxy_error(status.HTTP_500_INTERNAL_SERVER_ERROR, CommonProxyErrors.db_not_connected_error.value)

    seats: Final = await SeatRepository(prisma_client).all()
    return SeatListResponse(seats=tuple(_seat_response(s) for s in seats))


@router.post("/seats", response_model=SeatResponse)
async def upsert_seat(
    body: SeatBody,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
) -> SeatResponse:
    """Assign a subscription to a person for a period, or correct the one already there."""
    from litellm.proxy.proxy_server import prisma_client

    _admin_or_403(user_api_key_dict)
    start: Final = _day_or_400(body.period_start, "period_start")
    end: Final = _period_end_or_400(body.period_end, "period_end")
    amount: Final = _amount_or_400(body.amount, "amount")
    if prisma_client is None:
        raise _proxy_error(status.HTTP_500_INTERNAL_SERVER_ERROR, CommonProxyErrors.db_not_connected_error.value)

    stored: Final = await SeatRepository(prisma_client).upsert(
        Seat(
            seat_id="",
            tool=body.tool,
            user_id=body.user_id,
            cadence=body.cadence,
            currency=body.currency,
            amount=amount,
            period_start=start,
            period_end=end,
            note=body.note,
        )
    )
    if stored is None:
        raise _proxy_error(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "The seat was written but could not be read back in a shape this server understands.",
        )
    return _seat_response(stored)


@router.delete("/seats/{seat_id}", response_model=SeatDeletedResponse)
async def delete_seat(
    seat_id: str,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
) -> SeatDeletedResponse:
    """Remove a subscription, after which it stops counting toward that person's cost."""
    from litellm.proxy.proxy_server import prisma_client

    _admin_or_403(user_api_key_dict)
    if prisma_client is None:
        raise _proxy_error(status.HTTP_500_INTERNAL_SERVER_ERROR, CommonProxyErrors.db_not_connected_error.value)

    deleted: Final = await SeatRepository(prisma_client).delete(seat_id)
    if not deleted:
        raise _proxy_error(status.HTTP_404_NOT_FOUND, f"No seat with id {seat_id!r}.")
    return SeatDeletedResponse(deleted=True)


@router.get("/users/cost", response_model=UserCostListResponse)
async def all_user_costs(
    period_start: str = fastapi.Query(description="First day of the period, as YYYY-MM-DD"),
    period_end: str = fastapi.Query(description="Last day of the period, as YYYY-MM-DD"),
    currency: str = fastapi.Query(default="USD"),
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
) -> UserCostListResponse:
    """What every person cost over the period. Admin only, because it is everyone's cost."""
    from litellm.proxy.proxy_server import prisma_client

    _admin_or_403(user_api_key_dict)
    start: Final = _day_or_400(period_start, "period_start")
    end: Final = _period_end_or_400(period_end, "period_end")
    if prisma_client is None:
        raise _proxy_error(status.HTTP_500_INTERNAL_SERVER_ERROR, CommonProxyErrors.db_not_connected_error.value)

    costs: Final = await _costs_for(prisma_client, start=start, end=end, currency=currency)
    return UserCostListResponse(
        period_start=start.date().isoformat(),
        period_end=end.date().isoformat(),
        currency=currency,
        costs=tuple(user_cost_response(cost=c, period_start=start, period_end=end) for c in costs),
    )


@router.get("/users/{user_id}/cost", response_model=UserCostResponse)
async def user_cost(
    user_id: str,
    period_start: str = fastapi.Query(description="First day of the period, as YYYY-MM-DD"),
    period_end: str = fastapi.Query(description="Last day of the period, as YYYY-MM-DD"),
    currency: str = fastapi.Query(default="USD"),
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
) -> UserCostResponse:
    """What one person cost over the period.

    A person with no gateway traffic and no subscription still gets an answer, with zeroes,
    rather than a 404: "you cost nothing this month" is a fact, and a missing page is not.
    """
    from litellm.proxy.proxy_server import prisma_client

    _self_or_admin_or_403(user_api_key_dict, user_id)
    start: Final = _day_or_400(period_start, "period_start")
    end: Final = _period_end_or_400(period_end, "period_end")
    if prisma_client is None:
        raise _proxy_error(status.HTTP_500_INTERNAL_SERVER_ERROR, CommonProxyErrors.db_not_connected_error.value)

    costs: Final = await _costs_for(prisma_client, start=start, end=end, currency=currency)
    found: Final = next((c for c in costs if c.user_id == user_id), None)
    if found is not None:
        return user_cost_response(cost=found, period_start=start, period_end=end)

    return UserCostResponse(
        user_id=user_id,
        period_start=start.date().isoformat(),
        period_end=end.date().isoformat(),
        currency=currency,
        gateway="0",
        seats="0",
        total="0",
        seat_lines=(),
        tool_usage_known=False,
        note=INCOMPLETE_NOTE,
    )
