"""The one composition every analysis screen reads, and the rule it exists to make unbreakable.

**A provider figure says how much was spent. A gateway figure says who spent it. They are never
added together.** Four modules compose that answer today and each respects the rule separately,
which means it only has to be forgotten once. Here it is a type: a line is either money or a
statement about who spent money, and the total matches on which.

What these assert is every way a figure could reach a total it does not belong in, and that an
amount still carries its exact digits after passing through the composition.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Final

from token_iq.truth.cost_line import (
    GatewayObservation,
    Owner,
    ProviderCostFact,
    Spend,
    WhoSpent,
    combine,
    total_of,
)
from token_iq.types.seat import Seat
from token_iq.types.tool_usage import ToolUsageFact

DAY: Final = datetime(2026, 9, 15, tzinfo=timezone.utc)
MONTH_START: Final = datetime(2026, 9, 1, tzinfo=timezone.utc)
MONTH_END: Final = datetime(2026, 9, 30, 23, 59, 59, tzinfo=timezone.utc)

PLATFORM: Final = Owner(owner_type="team", owner_id="platform-team")


def _fact(
    cost: str = "10.00",
    *,
    provider: str = "openrouter",
    credential_name: str = "openrouter-main",
    currency: str = "USD",
    model: str | None = "openai/gpt-4o",
    meter: str | None = "input",
) -> ProviderCostFact:
    return ProviderCostFact(
        day=DAY,
        provider=provider,
        credential_name=credential_name,
        model=model,
        meter=meter,
        evidence="reconciled",
        currency=currency,
        amount=Decimal(cost),
    )


def _tool(cost: str = "4.00", *, basis: str = "new_money", person: str = "dev@example.com") -> ToolUsageFact:
    return ToolUsageFact(
        tool="claude_code",
        person=person,
        day=DAY,
        cost=Decimal(cost),
        currency="USD",
        basis=basis,  # pyright: ignore[reportArgumentType]  # the literal is the point of one test below
    )


def _seat(amount: str = "20.00", *, user_id: str = "dev@example.com") -> Seat:
    return Seat(
        seat_id="s1",
        tool="copilot",
        user_id=user_id,
        cadence="monthly",
        currency="USD",
        amount=Decimal(amount),
        period_start=MONTH_START,
        period_end=MONTH_END,
    )


def _owner_for(provider: str, credential_name: str) -> Owner | None:
    return PLATFORM if (provider, credential_name) == ("openrouter", "openrouter-main") else None


class TestTheCountingRule:
    def test_what_the_gateway_observed_is_never_money(self) -> None:
        """The whole rule. The gateway's figure and the provider's describe the same spend, so a
        total holding both is roughly double what the customer actually paid."""
        truth: Final = combine(
            provider_facts=(_fact("10.00"),),
            tool_rows=(),
            seats=(),
            gateway=(GatewayObservation(day=DAY, currency="USD", amount=Decimal("9.80"), owner=PLATFORM),),
            owner_for=_owner_for,
        )

        assert total_of(truth.lines) == {"USD": Decimal("10.00")}

    def test_the_gateway_figure_is_still_reported_beside_it(self) -> None:
        # Dropped, the page loses the only thing that can say who spent the provider's money.
        truth: Final = combine(
            provider_facts=(_fact("10.00"),),
            tool_rows=(),
            seats=(),
            gateway=(GatewayObservation(day=DAY, currency="USD", amount=Decimal("9.80"), owner=PLATFORM),),
            owner_for=_owner_for,
        )

        observations: Final = [line for line in truth.lines if isinstance(line, WhoSpent)]
        assert len(observations) == 1
        assert observations[0].facts.amount == Decimal("9.80")

    def test_a_gateway_observation_says_why_it_is_not_money(self) -> None:
        truth: Final = combine(
            provider_facts=(),
            tool_rows=(),
            seats=(),
            gateway=(GatewayObservation(day=DAY, currency="USD", amount=Decimal("1"), owner=None),),
            owner_for=_owner_for,
        )

        assert isinstance(truth.lines[0], WhoSpent)
        assert truth.lines[0].why != ""

    def test_the_total_of_nothing_is_nothing_rather_than_zero(self) -> None:
        """A zero reads as a period in which nobody spent. Nothing reads as a period nobody has
        data for, and the two are different answers to "what did we spend"."""
        truth: Final = combine(provider_facts=(), tool_rows=(), seats=(), gateway=(), owner_for=_owner_for)

        assert truth.lines == ()
        assert total_of(truth.lines) == {}


class TestToolSpend:
    def test_money_on_no_provider_bill_is_money(self) -> None:
        truth: Final = combine(
            provider_facts=(),
            tool_rows=(_tool("4.00", basis="new_money"),),
            seats=(),
            gateway=(),
            owner_for=_owner_for,
        )

        assert total_of(truth.lines) == {"USD": Decimal("4.00")}

    def test_money_already_on_a_provider_bill_is_only_who_spent_it(self) -> None:
        """Claude Code run against an API organisation bills that organisation, so the same
        dollars arrive through the Anthropic connector. Adding both overstates the customer's
        Anthropic spend by exactly what their developers ran through Claude Code."""
        truth: Final = combine(
            provider_facts=(_fact("10.00"),),
            tool_rows=(_tool("4.00", basis="already_on_a_provider_bill"),),
            seats=(),
            gateway=(),
            owner_for=_owner_for,
        )

        assert total_of(truth.lines) == {"USD": Decimal("10.00")}
        assert any(isinstance(line, WhoSpent) for line in truth.lines)

    def test_a_tool_line_names_the_person_who_spent_it(self) -> None:
        # The only source that can say what a named human spent rather than what a key spent,
        # which is the whole reason it exists.
        truth: Final = combine(
            provider_facts=(),
            tool_rows=(_tool(person="asha@example.com"),),
            seats=(),
            gateway=(),
            owner_for=_owner_for,
        )

        assert truth.lines[0].facts.owner == Owner(owner_type="user", owner_id="asha@example.com")


class TestSeats:
    def test_a_seat_is_money(self) -> None:
        truth: Final = combine(
            provider_facts=(),
            tool_rows=(),
            seats=(_seat("20.00"),),
            gateway=(),
            owner_for=_owner_for,
        )

        assert total_of(truth.lines) == {"USD": Decimal("20.00")}

    def test_a_seat_carries_no_evidence_grade_because_nobody_asserted_anything(self) -> None:
        """The grades describe what a provider asserted. A seat is a figure a person read off a
        contract, so claiming one of them would be a claim about evidence that does not exist."""
        truth: Final = combine(
            provider_facts=(), tool_rows=(), seats=(_seat(),), gateway=(), owner_for=_owner_for
        )

        assert truth.lines[0].facts.evidence is None

    def test_a_seat_covers_its_period_rather_than_being_spread_over_days(self) -> None:
        # Spreading a monthly fee across days would invent a daily figure the company was never
        # charged.
        truth: Final = combine(
            provider_facts=(), tool_rows=(), seats=(_seat(),), gateway=(), owner_for=_owner_for
        )

        assert truth.lines[0].facts.day == MONTH_START


class TestWhatALineCarries:
    def test_a_provider_line_keeps_its_day_model_and_meter(self) -> None:
        # One cost line per day, owner and meter is the shape the blueprint asks for, so a screen
        # grouping by meter must not have to go back to the facts.
        truth: Final = combine(
            provider_facts=(_fact(model="openai/gpt-4o", meter="output"),),
            tool_rows=(),
            seats=(),
            gateway=(),
            owner_for=_owner_for,
        )

        facts: Final = truth.lines[0].facts
        assert (facts.day, facts.model, facts.meter) == (DAY, "openai/gpt-4o", "output")

    def test_a_provider_line_takes_its_owner_from_the_rules(self) -> None:
        truth: Final = combine(
            provider_facts=(_fact(),), tool_rows=(), seats=(), gateway=(), owner_for=_owner_for
        )

        assert truth.lines[0].facts.owner == PLATFORM

    def test_a_line_no_rule_claims_is_owned_by_nobody_rather_than_guessed(self) -> None:
        """Unallocated is a figure the product reports on purpose. Guessing an owner would make it
        disappear into somebody else's budget."""
        truth: Final = combine(
            provider_facts=(_fact(credential_name="not-in-any-rule"),),
            tool_rows=(),
            seats=(),
            gateway=(),
            owner_for=_owner_for,
        )

        assert truth.lines[0].facts.owner is None

    def test_a_provider_line_keeps_the_grade_the_connector_asserted(self) -> None:
        truth: Final = combine(
            provider_facts=(_fact(),), tool_rows=(), seats=(), gateway=(), owner_for=_owner_for
        )

        assert truth.lines[0].facts.evidence == "reconciled"

    def test_every_line_names_the_source_it_came_from(self) -> None:
        truth: Final = combine(
            provider_facts=(_fact(),),
            tool_rows=(_tool(),),
            seats=(_seat(),),
            gateway=(GatewayObservation(day=DAY, currency="USD", amount=Decimal("1"), owner=None),),
            owner_for=_owner_for,
        )

        assert {line.facts.source for line in truth.lines} == {"provider", "tool", "seat", "gateway"}


class TestCurrency:
    def test_two_currencies_are_two_totals(self) -> None:
        """Adding them produces a figure in no currency at all. Nothing here converts: a rate
        nobody chose looks authoritative and is not."""
        truth: Final = combine(
            provider_facts=(_fact("10.00", currency="USD"), _fact("8.00", currency="EUR")),
            tool_rows=(),
            seats=(),
            gateway=(),
            owner_for=_owner_for,
        )

        assert total_of(truth.lines) == {"USD": Decimal("10.00"), "EUR": Decimal("8.00")}

    def test_amounts_in_one_currency_add_up(self) -> None:
        truth: Final = combine(
            provider_facts=(_fact("10.00"), _fact("0.00005815")),
            tool_rows=(),
            seats=(),
            gateway=(),
            owner_for=_owner_for,
        )

        assert total_of(truth.lines) == {"USD": Decimal("10.00005815")}

    def test_every_digit_survives_the_composition(self) -> None:
        # The figures this product reads are fractions of a cent per request. Rounding anywhere in
        # here manufactures a discrepancy against the provider's own bill.
        truth: Final = combine(
            provider_facts=(_fact("0.00774700"),),
            tool_rows=(),
            seats=(),
            gateway=(),
            owner_for=_owner_for,
        )

        assert total_of(truth.lines)["USD"] == Decimal("0.00774700")
        assert isinstance(truth.lines[0].facts.amount, Decimal)
