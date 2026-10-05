from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from typing import Final

from token_iq.seats.user_cost import user_costs
from litellm.types.proxy.seat import Seat

START: Final = datetime(2026, 9, 1, tzinfo=timezone.utc)
END: Final = datetime(2026, 9, 30, tzinfo=timezone.utc)

SEAT_30: Final = Seat("s1", "claude-code", "u-1", "monthly", "USD", Decimal("30"), START, END, None)


def test_a_persons_total_is_their_gateway_spend_plus_their_seats() -> None:
    result: Final = user_costs(gateway_by_user={"u-1": Decimal("10")}, seats=(SEAT_30,), currency="USD")
    assert result[0].gateway == Decimal("10")
    assert result[0].seats == Decimal("30")
    assert result[0].total == Decimal("40")


def test_the_parts_stay_visible_so_nobody_has_to_trust_one_blended_number() -> None:
    result: Final = user_costs(gateway_by_user={"u-1": Decimal("10")}, seats=(SEAT_30,), currency="USD")
    assert result[0].seat_lines[0].tool == "claude-code"
    assert result[0].seat_lines[0].amount == Decimal("30")


def test_a_person_with_a_seat_and_no_gateway_traffic_still_costs_money() -> None:
    result: Final = user_costs(gateway_by_user={}, seats=(SEAT_30,), currency="USD")
    assert result[0].gateway == Decimal(0)
    assert result[0].total == Decimal("30")


def test_a_person_with_traffic_and_no_seat_is_not_given_one() -> None:
    result: Final = user_costs(gateway_by_user={"u-2": Decimal("5")}, seats=(), currency="USD")
    assert result[0].seats == Decimal(0)
    assert result[0].seat_lines == ()


def test_a_seat_in_another_currency_is_left_out_rather_than_added_to_dollars() -> None:
    euro: Final = replace(SEAT_30, currency="EUR")
    result: Final = user_costs(gateway_by_user={"u-1": Decimal("10")}, seats=(euro,), currency="USD")
    assert result[0].seats == Decimal(0)
    assert result[0].total == Decimal("10")
    assert result[0].seat_lines == ()


def test_a_person_who_only_holds_a_foreign_currency_seat_does_not_appear_with_a_wrong_total() -> None:
    euro: Final = replace(SEAT_30, user_id="u-9", currency="EUR")
    result: Final = user_costs(gateway_by_user={}, seats=(euro,), currency="USD")
    assert result == ()


def test_every_total_says_tool_usage_is_not_counted_yet() -> None:
    result: Final = user_costs(gateway_by_user={"u-1": Decimal("10")}, seats=(), currency="USD")
    assert result[0].tool_usage_known is False


def test_two_seats_for_one_person_both_count() -> None:
    cursor: Final = replace(SEAT_30, seat_id="s2", tool="cursor", amount=Decimal("20"))
    result: Final = user_costs(gateway_by_user={"u-1": Decimal("10")}, seats=(SEAT_30, cursor), currency="USD")
    assert result[0].seats == Decimal("50")
    assert tuple(line.tool for line in result[0].seat_lines) == ("claude-code", "cursor")


def test_one_persons_seat_never_lands_on_another() -> None:
    result: Final = user_costs(
        gateway_by_user={"u-1": Decimal("10"), "u-2": Decimal("5")}, seats=(SEAT_30,), currency="USD"
    )
    by_user: Final = {c.user_id: c for c in result}
    assert by_user["u-1"].seats == Decimal("30")
    assert by_user["u-2"].seats == Decimal(0)


def test_money_never_passes_through_a_float() -> None:
    tiny: Final = replace(SEAT_30, amount=Decimal("0.1"))
    result: Final = user_costs(gateway_by_user={"u-1": Decimal("0.30000000000000004")}, seats=(tiny,), currency="USD")
    assert result[0].total == Decimal("0.40000000000000004")


def test_people_come_back_in_a_stable_order_so_a_screen_does_not_jump() -> None:
    result: Final = user_costs(gateway_by_user={"u-2": Decimal("5"), "u-1": Decimal("10")}, seats=(), currency="USD")
    assert tuple(c.user_id for c in result) == ("u-1", "u-2")
