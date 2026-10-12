"""The wiring Pricing & Rates depends on.

The rules are tested in `tests/token_iq/pricing/test_rates.py` without a database. What is asserted
here is the boundary: a figure a person typed off a contract surviving as exact digits, a rate that
could never price anything being refused before it is stored, and every answer about what prices a
model reaching the client as itself, including the two that are refusals.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Final

import pytest
from fastapi import HTTPException

from token_iq.api.pricing import effective_rate_to_wire, rate_from_body, rate_to_wire
from token_iq.api.types.pricing import RateBody
from token_iq.pricing.rates import (
    AppliedRate,
    ConflictingRates,
    Discount,
    NoCustomerRate,
    RateRule,
    UnitPrice,
)

LIST_PER_TOKEN: Final = Decimal("0.000003")


def _body(**overrides: object) -> RateBody:
    fields: Final = {
        "provider": "anthropic",
        "basis": "discount",
        "percent_off": "13.5",
        "effective_from": "2026-09-01",
        "source": "contract",
    }
    return RateBody(**{**fields, **overrides})  # pyright: ignore[reportArgumentType]  # overrides are the test's point


def _rule(basis: Discount | UnitPrice, *, rate_id: str = "r1", model: str | None = None, field: str | None = None) -> RateRule:
    return RateRule(
        rate_id=rate_id,
        provider="anthropic",
        model=model,
        field=field,
        basis=basis,
        effective_from=date(2026, 9, 1),
        effective_to=None,
        source="contract",
    )


class TestWhatAnAdministratorSends:
    def test_a_discount_keeps_its_digits(self) -> None:
        rule: Final = rate_from_body(_body(percent_off="13.5"))

        assert rule.basis == Discount(percent_off=Decimal("13.5"))

    def test_a_committed_price_keeps_its_digits(self) -> None:
        rule: Final = rate_from_body(
            _body(basis="unit_price", per_million="2.50", percent_off=None, model="claude-sonnet", field="input_cost_per_token")
        )

        assert rule.basis == UnitPrice(per_million=Decimal("2.50"))

    def test_the_period_is_read_as_days(self) -> None:
        rule: Final = rate_from_body(_body(effective_from="2026-09-01", effective_to="2026-12-31"))

        assert (rule.effective_from, rule.effective_to) == (date(2026, 9, 1), date(2026, 12, 31))

    def test_an_open_ended_rate_has_no_end(self) -> None:
        assert rate_from_body(_body(effective_to=None)).effective_to is None

    def test_a_date_nobody_can_read_is_refused_rather_than_defaulted(self) -> None:
        """Defaulted to today, a rate would silently fail to price the month it was entered for."""
        with pytest.raises(HTTPException) as refused:
            rate_from_body(_body(effective_from="last September"))

        assert refused.value.status_code == 400

    def test_a_discount_with_no_figure_is_refused(self) -> None:
        with pytest.raises(HTTPException) as refused:
            rate_from_body(_body(percent_off=None))

        assert refused.value.status_code == 400

    def test_a_committed_price_with_no_figure_is_refused(self) -> None:
        with pytest.raises(HTTPException):
            rate_from_body(_body(basis="unit_price", per_million=None, percent_off=None))


class TestWhatTheScreenReads:
    def test_a_discount_carries_its_percentage_and_no_unit_price(self) -> None:
        wire: Final = rate_to_wire(_rule(Discount(percent_off=Decimal("13.5"))))

        assert (wire.basis, wire.percent_off, wire.per_million) == ("discount", "13.5", None)

    def test_a_committed_price_carries_its_amount_and_no_percentage(self) -> None:
        wire: Final = rate_to_wire(
            _rule(UnitPrice(per_million=Decimal("2.50")), model="claude-sonnet", field="input_cost_per_token")
        )

        assert (wire.basis, wire.percent_off, wire.per_million) == ("unit_price", None, "2.50")

    def test_a_rate_covering_every_model_says_so_with_null_rather_than_a_word(self) -> None:
        # A screen can write "every model"; a backend writing it would put a model nobody can look
        # up into a field other code matches on.
        wire: Final = rate_to_wire(_rule(Discount(percent_off=Decimal("20"))))

        assert (wire.model, wire.field) == (None, None)


class TestWhatPricesAMillionTokens:
    def test_no_rate_prices_at_list(self) -> None:
        wire: Final = effective_rate_to_wire(NoCustomerRate(), LIST_PER_TOKEN)

        assert wire.kind == "list_price"
        # Compared as a figure rather than as a string: the scale is whatever the arithmetic left,
        # and the product keeps every digit rather than trimming to look tidy.
        assert Decimal(wire.cost_per_million) == Decimal("3")

    def test_a_discount_prices_below_list(self) -> None:
        wire: Final = effective_rate_to_wire(AppliedRate(rule=_rule(Discount(percent_off=Decimal("20")))), LIST_PER_TOKEN)

        assert wire.kind == "applied"
        assert Decimal(wire.cost_per_million) == Decimal("2.4")

    def test_a_committed_price_replaces_list(self) -> None:
        rule: Final = _rule(UnitPrice(per_million=Decimal("2.50")), model="claude-sonnet", field="input_cost_per_token")

        wire: Final = effective_rate_to_wire(AppliedRate(rule=rule), LIST_PER_TOKEN)

        assert Decimal(wire.cost_per_million) == Decimal("2.50")

    def test_a_committed_price_needs_no_list_price_at_all(self) -> None:
        """A model the bundled list has never heard of still prices, because the contract says what
        it costs. Refusing here would make a private model unpriceable."""
        rule: Final = _rule(UnitPrice(per_million=Decimal("2.50")), model="private-model", field="input_cost_per_token")

        wire: Final = effective_rate_to_wire(AppliedRate(rule=rule), None)

        assert wire.kind == "applied"
        assert Decimal(wire.cost_per_million) == Decimal("2.50")

    def test_a_discount_without_a_list_price_is_unknown_rather_than_free(self) -> None:
        # A percentage off nothing is nothing, and a zero here would report real spend as free.
        wire: Final = effective_rate_to_wire(AppliedRate(rule=_rule(Discount(percent_off=Decimal("20")))), None)

        assert wire.kind == "unknown"
        assert "list price" in wire.reason

    def test_an_unknown_model_is_unknown_rather_than_free(self) -> None:
        wire: Final = effective_rate_to_wire(NoCustomerRate(), None)

        assert wire.kind == "unknown"

    def test_a_conflict_reaches_the_client_naming_both_rates(self) -> None:
        """Resolved silently, the figure would depend on which row was written first, which nobody
        could work out from a screen. Named, somebody removes one."""
        one: Final = _rule(UnitPrice(per_million=Decimal("2.50")), rate_id="u1", model="m", field="input_cost_per_token")
        two: Final = _rule(UnitPrice(per_million=Decimal("2.00")), rate_id="u2", model="m", field="input_cost_per_token")

        wire: Final = effective_rate_to_wire(ConflictingRates(rules=(one, two)), LIST_PER_TOKEN)

        assert wire.kind == "conflict"
        assert {rate.rate_id for rate in wire.rates} == {"u1", "u2"}
        assert not hasattr(wire, "cost_per_million")
