from datetime import datetime, timezone
from decimal import Decimal
from typing import Final

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from token_iq.gateway.proxy._types import GatewayUserRoles, UserAPIKeyAuth
from token_iq.api.seats import user_cost_response
from token_iq.seats.user_cost import SeatLine, UserCost
from token_iq.api.types.seats import SeatBody

START: Final = datetime(2026, 9, 1, tzinfo=timezone.utc)
END: Final = datetime(2026, 9, 30, tzinfo=timezone.utc)

COST_40: Final = UserCost(
    user_id="u-1",
    currency="USD",
    gateway=Decimal("10"),
    seats=Decimal("30"),
    total=Decimal("40"),
    seat_lines=(SeatLine(tool="claude-code", currency="USD", amount=Decimal("30")),),
    tool_usage_known=False,
)

ADMIN: Final = UserAPIKeyAuth(user_role=GatewayUserRoles.PROXY_ADMIN, api_key="sk-test")


def _member(user_id: str) -> UserAPIKeyAuth:
    return UserAPIKeyAuth(user_role=GatewayUserRoles.INTERNAL_USER, api_key="sk-test", user_id=user_id)


def test_every_amount_crosses_as_a_string_and_the_parts_stay_separate() -> None:
    body: Final = user_cost_response(cost=COST_40, period_start=START, period_end=END)
    assert body.gateway == "10"
    assert body.seats == "30"
    assert body.total == "40"
    assert isinstance(body.total, str)


def test_the_response_says_tool_usage_is_not_included() -> None:
    body: Final = user_cost_response(cost=COST_40, period_start=START, period_end=END)
    assert body.tool_usage_known is False
    assert "tool" in body.note.lower()


def test_each_subscription_is_named_rather_than_summed_away() -> None:
    body: Final = user_cost_response(cost=COST_40, period_start=START, period_end=END)
    assert body.seat_lines[0].tool == "claude-code"
    assert body.seat_lines[0].amount == "30"


def test_a_tiny_amount_is_readable_rather_than_scientific() -> None:
    tiny: Final = UserCost("u-1", "USD", Decimal("0.0000072"), Decimal(0), Decimal("0.0000072"), (), False)
    body: Final = user_cost_response(cost=tiny, period_start=START, period_end=END)
    assert body.gateway == "0.0000072"
    assert "E" not in body.gateway


def test_the_period_is_reported_back_so_a_reader_knows_what_was_counted() -> None:
    body: Final = user_cost_response(cost=COST_40, period_start=START, period_end=END)
    assert body.period_start == "2026-09-01"
    assert body.period_end == "2026-09-30"


@pytest.mark.asyncio
async def test_a_person_may_not_read_someone_else_s_cost() -> None:
    from token_iq.api.seats import user_cost

    with pytest.raises(HTTPException) as caught:
        await user_cost(
            user_id="u-2",
            period_start="2026-09-01",
            period_end="2026-09-30",
            currency="USD",
            user_api_key_dict=_member("u-1"),
        )
    assert caught.value.status_code == 403


@pytest.mark.asyncio
async def test_a_person_reading_their_own_cost_gets_past_the_privacy_check() -> None:
    from token_iq.api.seats import user_cost

    with pytest.raises(HTTPException) as caught:
        await user_cost(
            user_id="u-1",
            period_start="2026-09-01",
            period_end="2026-09-30",
            currency="USD",
            user_api_key_dict=_member("u-1"),
        )
    assert caught.value.status_code == 500
    assert "database" in str(caught.value.detail).lower()


@pytest.mark.asyncio
async def test_a_non_admin_cannot_list_everyone_s_cost() -> None:
    from token_iq.api.seats import all_user_costs

    with pytest.raises(HTTPException) as caught:
        await all_user_costs(
            period_start="2026-09-01",
            period_end="2026-09-30",
            currency="USD",
            user_api_key_dict=_member("u-1"),
        )
    assert caught.value.status_code == 403


@pytest.mark.asyncio
async def test_a_non_admin_cannot_assign_a_seat() -> None:
    from token_iq.api.seats import upsert_seat

    body: Final = SeatBody(
        tool="claude-code",
        user_id="u-1",
        cadence="monthly",
        amount="30",
        period_start="2026-09-01",
        period_end="2026-09-30",
    )
    with pytest.raises(HTTPException) as caught:
        await upsert_seat(body=body, user_api_key_dict=_member("u-1"))
    assert caught.value.status_code == 403


@pytest.mark.asyncio
async def test_a_period_that_is_not_a_date_is_refused_rather_than_defaulted() -> None:
    from token_iq.api.seats import all_user_costs

    with pytest.raises(HTTPException) as caught:
        await all_user_costs(
            period_start="the first of September",
            period_end="2026-09-30",
            currency="USD",
            user_api_key_dict=ADMIN,
        )
    assert caught.value.status_code == 400


def test_a_seat_with_an_unknown_cadence_is_refused_by_validation() -> None:
    with pytest.raises(ValidationError):
        SeatBody(
            tool="claude-code",
            user_id="u-1",
            cadence="fortnightly",  # pyright: ignore[reportArgumentType]  # the point of the test
            amount="30",
            period_start="2026-09-01",
            period_end="2026-09-30",
        )


def test_a_period_end_given_as_a_date_covers_that_whole_day() -> None:
    from token_iq.api.seats import _period_end_or_400

    end: Final = _period_end_or_400("2026-09-30", "period_end")
    assert end.hour == 23
    assert end.minute == 59


def test_the_last_instant_survives_a_millisecond_column_without_rolling_over() -> None:
    """These columns are TIMESTAMP(3). A microsecond value rounds up on insert, so a period
    ending 23:59:59.999999 is stored as midnight the next day and falls outside its own period.
    Proven live: a seat saved that way could never be found again."""
    from token_iq.api.seats import _period_end_or_400

    end: Final = _period_end_or_400("2026-09-30", "period_end")
    assert end.microsecond == 999000
    assert end.day == 30
