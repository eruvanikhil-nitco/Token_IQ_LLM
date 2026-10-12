"""One reporting currency, using a rate a customer recorded and never one we invented.

Every figure in this product carries the currency it was billed in, and totals are reported per
currency because adding two of them produces a number in no currency at all. A customer with
invoices in two currencies still wants one figure, and the only honest way to give them one is with
a rate they entered, dated, with where it came from.

Three refusals hold the line. A pair nobody recorded cannot be converted, and the total says which
pair is missing rather than quietly leaving that money out. A rate recorded in the other direction
is not inverted, because 1 divided by 1.08 is a figure nobody entered. And two rates for one pair on
one day are a conflict, for the same reason two prices for one model are.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Final

from token_iq.pricing.currency import (
    AppliedConversion,
    CurrencyRate,
    MissingRates,
    NoConversionRate,
    OneTotal,
    RateConflict,
    SameCurrency,
    UseRate,
    conversion,
    convert_total,
)

SEPTEMBER: Final = date(2026, 9, 15)
AUGUST: Final = date(2026, 8, 15)


def _rate(
    value: str = "1.08",
    *,
    source_currency: str = "EUR",
    target: str = "USD",
    start: date = date(2026, 1, 1),
    end: date | None = None,
    rate_id: str = "c1",
) -> CurrencyRate:
    return CurrencyRate(
        rate_id=rate_id,
        source_currency=source_currency,
        target_currency=target,
        rate=Decimal(value),
        effective_from=start,
        effective_to=end,
        source="the rate our finance team booked the month at",
    )


class TestWhichRateConverts:
    def test_the_recorded_rate_for_that_pair_and_day(self) -> None:
        answer: Final = conversion((_rate("1.08"),), source="EUR", target="USD", when=SEPTEMBER)

        assert answer == UseRate(rate=_rate("1.08"))

    def test_the_same_currency_needs_no_rate_at_all(self) -> None:
        # Its own answer, so a screen does not say "converted at 1.0" about money that never moved.
        answer: Final = conversion((), source="USD", target="USD", when=SEPTEMBER)

        assert answer == SameCurrency()

    def test_a_pair_nobody_recorded_cannot_be_converted(self) -> None:
        answer: Final = conversion((_rate(source_currency="EUR"),), source="INR", target="USD", when=SEPTEMBER)

        assert answer == NoConversionRate(source="INR", target="USD")

    def test_a_rate_recorded_the_other_way_round_is_not_inverted(self) -> None:
        """One divided by 1.08 is a figure nobody entered. The fix is to record the direction being
        reported in, which the refusal names."""
        answer: Final = conversion(
            (_rate(source_currency="EUR", target="USD"),), source="USD", target="EUR", when=SEPTEMBER
        )

        assert answer == NoConversionRate(source="USD", target="EUR")

    def test_a_rate_outside_its_period_does_not_apply(self) -> None:
        # The reason a rate carries a period: a closed month converts at the rate booked then.
        answer: Final = conversion(
            (_rate(start=date(2026, 10, 1)),), source="EUR", target="USD", when=SEPTEMBER
        )

        assert answer == NoConversionRate(source="EUR", target="USD")

    def test_a_rate_that_has_ended_still_converts_the_month_it_covered(self) -> None:
        rule: Final = _rate(end=date(2026, 8, 31))

        answer: Final = conversion((rule,), source="EUR", target="USD", when=AUGUST)

        assert answer == UseRate(rate=rule)

    def test_the_newer_of_two_rates_for_one_pair_wins(self) -> None:
        # A month-by-month booked rate is recorded as a new row, never by editing the old one.
        september_rate: Final = _rate("1.10", start=date(2026, 9, 1), rate_id="c2")

        answer: Final = conversion(
            (_rate("1.08", start=date(2026, 1, 1), rate_id="c1"), september_rate),
            source="EUR",
            target="USD",
            when=SEPTEMBER,
        )

        assert answer == UseRate(rate=september_rate)

    def test_two_rates_as_recent_as_each_other_are_a_conflict(self) -> None:
        one: Final = _rate("1.08", rate_id="c1")
        two: Final = _rate("1.10", rate_id="c2")

        answer: Final = conversion((one, two), source="EUR", target="USD", when=SEPTEMBER)

        assert answer == RateConflict(rates=(one, two))


class TestOneTotalFromSeveralCurrencies:
    def test_one_currency_needs_no_conversion_and_says_so(self) -> None:
        outcome: Final = convert_total(
            {"USD": Decimal("100.00")}, into="USD", rates=(), when=SEPTEMBER
        )

        assert outcome == OneTotal(currency="USD", amount=Decimal("100.00"), applied=())

    def test_two_currencies_become_one_figure_at_the_recorded_rate(self) -> None:
        outcome: Final = convert_total(
            {"USD": Decimal("100.00"), "EUR": Decimal("50.00")},
            into="USD",
            rates=(_rate("1.08"),),
            when=SEPTEMBER,
        )

        assert isinstance(outcome, OneTotal)
        assert outcome.amount == Decimal("154.00")

    def test_the_conversion_is_stated_beside_the_figure(self) -> None:
        """A converted total that does not say what was converted, at which rate and from where, is
        a number a finance team cannot check, which means a number they will not use."""
        outcome: Final = convert_total(
            {"EUR": Decimal("50.00")}, into="USD", rates=(_rate("1.08"),), when=SEPTEMBER
        )

        assert isinstance(outcome, OneTotal)
        assert outcome.applied == (
            AppliedConversion(
                source="EUR",
                target="USD",
                amount=Decimal("50.00"),
                rate=Decimal("1.08"),
                converted=Decimal("54.00"),
                rate_source="the rate our finance team booked the month at",
            ),
        )

    def test_a_currency_with_no_rate_refuses_the_whole_total(self) -> None:
        """Leaving it out silently is the worst of the three options: the figure looks complete and
        is short by exactly the money nobody could convert."""
        outcome: Final = convert_total(
            {"USD": Decimal("100.00"), "INR": Decimal("8000.00")},
            into="USD",
            rates=(_rate("1.08"),),
            when=SEPTEMBER,
        )

        assert isinstance(outcome, MissingRates)
        assert outcome.pairs == (("INR", "USD"),)

    def test_the_refusal_still_carries_the_per_currency_totals(self) -> None:
        # So a screen can show what it does know rather than nothing at all.
        outcome: Final = convert_total(
            {"USD": Decimal("100.00"), "INR": Decimal("8000.00")},
            into="USD",
            rates=(),
            when=SEPTEMBER,
        )

        assert isinstance(outcome, MissingRates)
        assert outcome.by_currency == {"USD": Decimal("100.00"), "INR": Decimal("8000.00")}

    def test_a_conflicting_rate_refuses_the_total_too(self) -> None:
        outcome: Final = convert_total(
            {"EUR": Decimal("50.00")},
            into="USD",
            rates=(_rate("1.08", rate_id="c1"), _rate("1.10", rate_id="c2")),
            when=SEPTEMBER,
        )

        assert isinstance(outcome, MissingRates)
        assert outcome.pairs == (("EUR", "USD"),)

    def test_nothing_at_all_totals_nothing_in_the_reporting_currency(self) -> None:
        outcome: Final = convert_total({}, into="USD", rates=(), when=SEPTEMBER)

        assert outcome == OneTotal(currency="USD", amount=Decimal(0), applied=())

    def test_every_digit_survives_the_conversion(self) -> None:
        outcome: Final = convert_total(
            {"EUR": Decimal("0.00774700")}, into="USD", rates=(_rate("1.0823"),), when=SEPTEMBER
        )

        assert isinstance(outcome, OneTotal)
        assert outcome.amount == Decimal("0.00774700") * Decimal("1.0823")
