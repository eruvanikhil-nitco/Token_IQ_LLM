from __future__ import annotations

from decimal import Decimal
from typing import Final

from litellm.overview.totals import Sources, totals_for


def _sources(**over: object) -> Sources:
    base: Final[dict[str, object]] = {
        "provider_billed": Decimal("100"),
        "tool_new_money": Decimal("20"),
        "seats": Decimal("30"),
        "gateway_recorded": Decimal("90"),
        "unallocated": Decimal("10"),
        "has_any_data": True,
    }
    return Sources(**{**base, **over})  # pyright: ignore[reportArgumentType]  # test builder spreads a dict


def test_the_total_is_what_the_providers_billed_plus_money_on_no_provider_bill() -> None:
    assert totals_for(_sources()).total == Decimal("150")


def test_the_gateway_figure_is_never_added_to_the_total() -> None:
    """The product's oldest rule, and this is the number a customer repeats to their finance
    team. Adding the gateway's figure would roughly double it."""
    quiet_gateway: Final = totals_for(_sources(gateway_recorded=Decimal("0"))).total
    busy_gateway: Final = totals_for(_sources(gateway_recorded=Decimal("9999"))).total

    assert quiet_gateway == busy_gateway == Decimal("150")


def test_the_gateway_figure_is_reported_as_attribution_rather_than_dropped() -> None:
    """It answers a real question, who spent it, just not how much was spent."""
    assert totals_for(_sources()).attributed == Decimal("90")


def test_a_period_with_nothing_in_it_reports_nothing_rather_than_zero() -> None:
    """Zero asserts the company spent nothing. On a landing page that is the difference
    between "you are not connected yet" and "you are free"."""
    result: Final = totals_for(_sources(has_any_data=False))

    assert result.total is None
    assert result.has_figures is False


def test_with_no_previous_period_there_is_no_change_rather_than_a_rise_from_zero() -> None:
    """A rise from zero would read as a new customer tripling their spend in month one."""
    result: Final = totals_for(_sources(), previous=None)

    assert result.previous_total is None
    assert result.change is None


def test_an_empty_previous_period_is_also_no_change() -> None:
    result: Final = totals_for(_sources(), previous=_sources(has_any_data=False))

    assert result.change is None


def test_a_rise_and_a_fall_are_signed_so_they_can_be_told_apart() -> None:
    rose: Final = totals_for(_sources(), previous=_sources(provider_billed=Decimal("50")))
    fell: Final = totals_for(_sources(), previous=_sources(provider_billed=Decimal("150")))

    assert rose.change == Decimal("50")
    assert fell.change == Decimal("-50")


def test_the_unallocated_share_is_a_share_of_what_the_providers_billed() -> None:
    """Not of the headline total: seats and tool spend were never going to be attributed by
    the gateway, so including them would make the gap look smaller than it is."""
    assert totals_for(_sources()).unallocated_share == Decimal("10.0")


def test_an_unallocated_share_of_nothing_is_absent_rather_than_zero() -> None:
    result: Final = totals_for(_sources(provider_billed=Decimal("0")))

    assert result.unallocated_share is None


def test_every_figure_keeps_its_exact_digits() -> None:
    result: Final = totals_for(
        _sources(
            provider_billed=Decimal("0.00000186"),
            tool_new_money=Decimal("0.00000001"),
            seats=Decimal("0"),
        )
    )

    assert result.total == Decimal("0.00000187")
