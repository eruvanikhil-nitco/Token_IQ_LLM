"""A customer's own rate, which is what "priced at the client's real rates" means.

The bundled price list says what a model costs anybody. What a customer pays is that, less whatever
their contract says: a percentage off list, or a committed price per million tokens for one model.
Nothing in this product could record either, so every figure it worked out itself was list price,
which for a customer with a negotiated discount is wrong by exactly the discount they negotiated.

Two things here are deliberately refusals rather than answers. A period with no rate falls back to
list price and says so, because a missing rate is not a free month. And two rates claiming the same
model on the same day are reported as a conflict rather than resolved by picking one, because
picking one quietly means the figure depends on which row was written first.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Final

from token_iq.pricing.rates import (
    AppliedRate,
    ConflictingRates,
    Discount,
    NoCustomerRate,
    RateRule,
    UnitPrice,
    cost_of,
    effective_rate,
    rate_problem,
)

SEPTEMBER: Final = date(2026, 9, 15)
AUGUST: Final = date(2026, 8, 15)

LIST_PRICE_PER_TOKEN: Final = Decimal("0.000003")
"""Three dollars per million, which is what a mid-sized model costs at list."""


def _discount(
    percent: str = "20",
    *,
    provider: str = "anthropic",
    model: str | None = None,
    field: str | None = None,
    start: date = date(2026, 1, 1),
    end: date | None = None,
    rate_id: str = "r1",
) -> RateRule:
    return RateRule(
        rate_id=rate_id,
        provider=provider,
        model=model,
        field=field,
        basis=Discount(percent_off=Decimal(percent)),
        effective_from=start,
        effective_to=end,
        source="contract, entered by an administrator",
    )


def _unit(
    per_million: str = "2.50",
    *,
    provider: str = "anthropic",
    model: str | None = "claude-sonnet",
    field: str | None = "input_cost_per_token",
    start: date = date(2026, 1, 1),
    rate_id: str = "u1",
) -> RateRule:
    return RateRule(
        rate_id=rate_id,
        provider=provider,
        model=model,
        field=field,
        basis=UnitPrice(per_million=Decimal(per_million)),
        effective_from=start,
        effective_to=None,
        source="committed-use agreement",
    )


class TestWhichRateApplies:
    def test_a_provider_wide_discount_applies_to_every_model(self) -> None:
        answer: Final = effective_rate(
            (_discount(),), provider="anthropic", model="claude-sonnet", field="input_cost_per_token", when=SEPTEMBER
        )

        assert answer == AppliedRate(rule=_discount())

    def test_no_rate_at_all_means_list_price_rather_than_nothing(self) -> None:
        """A missing rate is not a free month. Every figure still has a price: the list one."""
        answer: Final = effective_rate(
            (), provider="anthropic", model="claude-sonnet", field="input_cost_per_token", when=SEPTEMBER
        )

        assert answer == NoCustomerRate()

    def test_a_rate_for_another_provider_does_not_apply(self) -> None:
        answer: Final = effective_rate(
            (_discount(provider="openai"),),
            provider="anthropic",
            model="claude-sonnet",
            field="input_cost_per_token",
            when=SEPTEMBER,
        )

        assert answer == NoCustomerRate()

    def test_a_rate_for_another_model_does_not_apply(self) -> None:
        answer: Final = effective_rate(
            (_discount(model="claude-opus"),),
            provider="anthropic",
            model="claude-sonnet",
            field="input_cost_per_token",
            when=SEPTEMBER,
        )

        assert answer == NoCustomerRate()

    def test_a_rate_that_has_not_started_does_not_apply(self) -> None:
        answer: Final = effective_rate(
            (_discount(start=date(2026, 10, 1)),),
            provider="anthropic",
            model="claude-sonnet",
            field="input_cost_per_token",
            when=SEPTEMBER,
        )

        assert answer == NoCustomerRate()

    def test_a_rate_that_has_ended_does_not_apply(self) -> None:
        # The reason a rate carries a period at all: a closed month is re-priced with the rate that
        # applied then, not with today's.
        answer: Final = effective_rate(
            (_discount(end=date(2026, 8, 31)),),
            provider="anthropic",
            model="claude-sonnet",
            field="input_cost_per_token",
            when=SEPTEMBER,
        )

        assert answer == NoCustomerRate()

    def test_a_rate_that_had_ended_still_applies_to_the_month_it_covered(self) -> None:
        rule: Final = _discount(end=date(2026, 8, 31))

        answer: Final = effective_rate(
            (rule,), provider="anthropic", model="claude-sonnet", field="input_cost_per_token", when=AUGUST
        )

        assert answer == AppliedRate(rule=rule)

    def test_a_rate_with_no_end_is_still_in_force(self) -> None:
        answer: Final = effective_rate(
            (_discount(end=None),),
            provider="anthropic",
            model="claude-sonnet",
            field="input_cost_per_token",
            when=SEPTEMBER,
        )

        assert isinstance(answer, AppliedRate)


class TestWhichRateWinsWhenSeveralCould:
    def test_a_rate_for_one_model_beats_one_for_the_whole_provider(self) -> None:
        # The specific thing a customer negotiated is the thing they negotiated. A provider-wide
        # discount is the floor, not the answer.
        specific: Final = _unit(model="claude-sonnet", rate_id="u1")

        answer: Final = effective_rate(
            (_discount(rate_id="r1"), specific),
            provider="anthropic",
            model="claude-sonnet",
            field="input_cost_per_token",
            when=SEPTEMBER,
        )

        assert answer == AppliedRate(rule=specific)

    def test_a_rate_for_one_field_beats_one_for_every_field(self) -> None:
        field_rate: Final = _discount(field="output_cost_per_token", rate_id="r-field")

        answer: Final = effective_rate(
            (_discount(rate_id="r-all"), field_rate),
            provider="anthropic",
            model="claude-sonnet",
            field="output_cost_per_token",
            when=SEPTEMBER,
        )

        assert answer == AppliedRate(rule=field_rate)

    def test_the_newer_of_two_equally_specific_rates_wins(self) -> None:
        # A renegotiation is recorded as a new rate rather than by editing the old one, because the
        # old one priced months that are already reported.
        renegotiated: Final = _unit(per_million="2.00", start=date(2026, 6, 1), rate_id="u2")

        answer: Final = effective_rate(
            (_unit(per_million="2.50", start=date(2026, 1, 1), rate_id="u1"), renegotiated),
            provider="anthropic",
            model="claude-sonnet",
            field="input_cost_per_token",
            when=SEPTEMBER,
        )

        assert answer == AppliedRate(rule=renegotiated)

    def test_two_rates_as_specific_and_as_recent_as_each_other_are_a_conflict(self) -> None:
        """Picking one silently makes the figure depend on which row was written first, which is
        not something anybody could debug from a screen."""
        one: Final = _unit(per_million="2.50", rate_id="u1")
        two: Final = _unit(per_million="2.00", rate_id="u2")

        answer: Final = effective_rate(
            (one, two), provider="anthropic", model="claude-sonnet", field="input_cost_per_token", when=SEPTEMBER
        )

        assert answer == ConflictingRates(rules=(one, two))

    def test_a_conflict_names_both_rates_so_somebody_can_remove_one(self) -> None:
        one: Final = _unit(rate_id="u1")
        two: Final = _unit(rate_id="u2")

        answer: Final = effective_rate(
            (two, one), provider="anthropic", model="claude-sonnet", field="input_cost_per_token", when=SEPTEMBER
        )

        assert isinstance(answer, ConflictingRates)
        assert {rule.rate_id for rule in answer.rules} == {"u1", "u2"}


class TestWhatThatCosts:
    def test_list_price_when_the_customer_has_no_rate(self) -> None:
        cost: Final = cost_of(tokens=1_000_000, list_price_per_token=LIST_PRICE_PER_TOKEN, rate=NoCustomerRate())

        assert cost == Decimal("3")

    def test_a_discount_comes_off_list(self) -> None:
        cost: Final = cost_of(
            tokens=1_000_000,
            list_price_per_token=LIST_PRICE_PER_TOKEN,
            rate=AppliedRate(rule=_discount("20")),
        )

        assert cost == Decimal("2.4")

    def test_a_committed_unit_price_replaces_list_rather_than_discounting_it(self) -> None:
        cost: Final = cost_of(
            tokens=1_000_000,
            list_price_per_token=LIST_PRICE_PER_TOKEN,
            rate=AppliedRate(rule=_unit("2.50")),
        )

        assert cost == Decimal("2.50")

    def test_a_conflict_prices_nothing(self) -> None:
        """Returning a figure from one of two conflicting rates would be a guess wearing the look
        of an answer. The caller reports the conflict instead."""
        cost: Final = cost_of(
            tokens=1_000_000,
            list_price_per_token=LIST_PRICE_PER_TOKEN,
            rate=ConflictingRates(rules=(_unit(rate_id="u1"), _unit(rate_id="u2"))),
        )

        assert cost is None

    def test_every_digit_survives(self) -> None:
        # The figures this product compares are fractions of a cent. A discount applied as a float
        # reconciles to the penny in a test and drifts on a real bill.
        cost: Final = cost_of(
            tokens=333_333,
            list_price_per_token=Decimal("0.0000031"),
            rate=AppliedRate(rule=_discount("13.5")),
        )

        assert cost == Decimal("0.0000031") * 333_333 * (Decimal("100") - Decimal("13.5")) / Decimal("100")

    def test_no_tokens_costs_nothing_at_any_rate(self) -> None:
        assert cost_of(tokens=0, list_price_per_token=LIST_PRICE_PER_TOKEN, rate=NoCustomerRate()) == 0


class TestARateNobodyShouldBeAbleToRecord:
    def test_a_discount_of_more_than_everything_is_refused(self) -> None:
        """Over a hundred per cent makes spend negative, and a negative cost line would reduce a
        total that other lines increased, which no screen could explain."""
        problem: Final = rate_problem(_discount("120"))

        assert problem is not None

    def test_a_negative_discount_is_refused(self) -> None:
        # A premium over list is a real thing for a reseller, and it is recorded as a unit price
        # rather than as a negative discount, so that the figure says what it is.
        assert rate_problem(_discount("-5")) is not None

    def test_a_negative_unit_price_is_refused(self) -> None:
        assert rate_problem(_unit("-1")) is not None

    def test_a_period_that_ends_before_it_starts_is_refused(self) -> None:
        assert rate_problem(_discount(start=date(2026, 9, 1), end=date(2026, 8, 1))) is not None

    def test_a_unit_price_for_every_field_at_once_is_refused(self) -> None:
        """A price per million means nothing without saying which meter it is for: input and output
        differ by a factor of three or more at list."""
        problem: Final = rate_problem(_unit(field=None))

        assert problem is not None

    def test_a_unit_price_for_every_model_at_once_is_refused(self) -> None:
        # One price across a provider's whole catalogue would price a small model like a large one.
        assert rate_problem(_unit(model=None)) is not None

    def test_an_ordinary_discount_is_accepted(self) -> None:
        assert rate_problem(_discount("20")) is None

    def test_a_free_month_is_accepted_because_credits_are_real(self) -> None:
        assert rate_problem(_discount("100")) is None

    def test_an_ordinary_unit_price_is_accepted(self) -> None:
        assert rate_problem(_unit("2.50")) is None
