"""Gateway traffic priced at the customer's rates, and the one window where that is money.

The blueprint's words: "Confirmed cost appears on the provider's invoice data; estimated cost has
been observed by the gateway but not yet billed." So a priced figure is money for exactly the days
the provider has not billed yet, and for every earlier day it is the same dollars the provider
already reported, said a second way.

Getting that boundary wrong is the counting rule failing quietly. Priced spend added to a day the
provider has billed doubles that day. Priced spend withheld from a day the provider has not billed
leaves the current month reading as though nobody spent anything until the bill arrives, which is
the complaint this product exists to answer.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Final

from token_iq.truth.cost_line import Owner, Spend, WhoSpent, total_of
from token_iq.truth.priced import GatewayDay, priced_lines

BILLED_THROUGH: Final = datetime(2026, 9, 10, tzinfo=timezone.utc)
BEFORE: Final = datetime(2026, 9, 5, tzinfo=timezone.utc)
AFTER: Final = datetime(2026, 9, 15, tzinfo=timezone.utc)

PLATFORM: Final = Owner(owner_type="team", owner_id="platform-team")


def _day(
    amount: str = "4.00",
    *,
    day: datetime = AFTER,
    provider: str = "anthropic",
    model: str | None = "claude-sonnet",
    meter: str | None = "input_cost_per_token",
    currency: str = "USD",
) -> GatewayDay:
    return GatewayDay(
        day=day,
        provider=provider,
        model=model,
        meter=meter,
        currency=currency,
        amount=Decimal(amount),
        owner=PLATFORM,
    )


class TestAfterTheProviderHasBilled:
    def test_a_day_the_provider_has_not_billed_is_money(self) -> None:
        lines: Final = priced_lines((_day("4.00", day=AFTER),), billed_through={"anthropic": BILLED_THROUGH})

        assert isinstance(lines[0], Spend)
        assert total_of(lines) == {"USD": Decimal("4.00")}

    def test_it_carries_the_priced_grade_rather_than_the_provider_s(self) -> None:
        """The grade is the whole claim: this figure is ours, worked out from tokens and a rate,
        and the provider will replace it when it bills."""
        lines: Final = priced_lines((_day(),), billed_through={"anthropic": BILLED_THROUGH})

        assert lines[0].facts.evidence == "priced"

    def test_a_provider_that_has_never_billed_has_every_day_priced(self) -> None:
        # A provider connected to the gateway and not to billing has no invoice data at all, so the
        # priced figure is the only figure there is.
        lines: Final = priced_lines((_day(day=BEFORE), _day(day=AFTER)), billed_through={})

        assert all(isinstance(line, Spend) for line in lines)

    def test_it_keeps_the_owner_the_gateway_knew(self) -> None:
        # The gateway is the only source that can say who spent, which is the reason to price it at
        # all rather than waiting for a bill that names nobody.
        lines: Final = priced_lines((_day(),), billed_through={})

        assert lines[0].facts.owner == PLATFORM

    def test_it_keeps_the_day_the_model_and_the_meter(self) -> None:
        lines: Final = priced_lines((_day(model="claude-opus", meter="output_cost_per_token"),), billed_through={})

        facts: Final = lines[0].facts
        assert (facts.day, facts.model, facts.meter) == (AFTER, "claude-opus", "output_cost_per_token")


class TestOnOrBeforeTheDayTheProviderBilled:
    def test_a_day_the_provider_has_billed_is_not_money_again(self) -> None:
        """The counting rule at the only boundary where it is a date rather than a source."""
        lines: Final = priced_lines((_day("4.00", day=BEFORE),), billed_through={"anthropic": BILLED_THROUGH})

        assert isinstance(lines[0], WhoSpent)
        assert total_of(lines) == {}

    def test_the_day_the_provider_billed_through_is_itself_already_billed(self) -> None:
        # The watermark is the last day the provider reported, and it reported all of it.
        lines: Final = priced_lines((_day(day=BILLED_THROUGH),), billed_through={"anthropic": BILLED_THROUGH})

        assert isinstance(lines[0], WhoSpent)

    def test_it_says_why_it_is_not_money(self) -> None:
        lines: Final = priced_lines((_day(day=BEFORE),), billed_through={"anthropic": BILLED_THROUGH})

        assert isinstance(lines[0], WhoSpent)
        assert "billed" in lines[0].why

    def test_it_is_still_a_line_so_the_gateway_can_say_who_spent_it(self) -> None:
        # Dropped, the product loses the only record of which team spent the money on a day the
        # provider's own bill attributes to nobody.
        lines: Final = priced_lines((_day(day=BEFORE),), billed_through={"anthropic": BILLED_THROUGH})

        assert lines[0].facts.owner == PLATFORM
        assert lines[0].facts.amount == Decimal("4.00")


class TestOneWatermarkPerProvider:
    def test_each_provider_is_judged_against_its_own_bill(self) -> None:
        """Providers bill on their own schedules: OpenRouter prices each request as it happens and
        Bedrock settles two days late. One watermark across all of them would either double count
        the fast one or hide the slow one."""
        lines: Final = priced_lines(
            (
                _day("1.00", provider="anthropic", day=AFTER),
                _day("2.00", provider="bedrock", day=AFTER),
            ),
            billed_through={"anthropic": BILLED_THROUGH, "bedrock": datetime(2026, 9, 30, tzinfo=timezone.utc)},
        )

        assert total_of(lines) == {"USD": Decimal("1.00")}

    def test_a_provider_with_no_traffic_needs_no_watermark(self) -> None:
        assert priced_lines((), billed_through={"anthropic": BILLED_THROUGH}) == ()


class TestWhatItLeavesAlone:
    def test_two_currencies_stay_two_currencies(self) -> None:
        lines: Final = priced_lines(
            (_day("1.00", currency="USD"), _day("2.00", currency="EUR")),
            billed_through={},
        )

        assert total_of(lines) == {"USD": Decimal("1.00"), "EUR": Decimal("2.00")}

    def test_every_digit_survives(self) -> None:
        lines: Final = priced_lines((_day("0.00000315"),), billed_through={})

        assert total_of(lines)["USD"] == Decimal("0.00000315")
