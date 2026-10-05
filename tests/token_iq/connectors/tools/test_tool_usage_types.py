from datetime import datetime, timezone
from decimal import Decimal
from typing import Final

import pytest

from token_iq.types.tool_usage import ToolUsageFact

DAY: Final = datetime(2026, 9, 1, tzinfo=timezone.utc)


def _fact(**over: object) -> ToolUsageFact:
    base: Final[dict[str, object]] = {
        "tool": "claude_code",
        "person": "someone@example.test",
        "day": DAY,
        "cost": Decimal("1.86"),
        "currency": "USD",
        "basis": "new_money",
    }
    return ToolUsageFact(**{**base, **over})  # pyright: ignore[reportArgumentType]  # test builder spreads a dict


def test_spend_on_a_subscription_plan_counts_toward_the_total() -> None:
    assert _fact(basis="new_money").counts_toward_total is True


def test_spend_already_on_a_provider_bill_never_counts_toward_the_total() -> None:
    """Claude Code run against an API organisation bills that organisation, so the Anthropic
    connector already reports the same dollars. Counting both would overstate a customer's
    Anthropic spend by exactly what their developers ran through Claude Code."""
    assert _fact(basis="already_on_a_provider_bill").counts_toward_total is False


def test_a_row_that_does_not_count_is_still_kept() -> None:
    """Storing it is the point: it is the only thing that says who spent the money. What must
    never happen is adding it to a total that already contains the bill."""
    fact: Final = _fact(basis="already_on_a_provider_bill")

    assert fact.cost == Decimal("1.86")
    assert fact.person == "someone@example.test"


def test_a_cost_with_no_currency_is_refused_at_construction() -> None:
    with pytest.raises(ValueError, match="currency"):
        _fact(currency="")


def test_a_negative_cost_is_refused_rather_than_quietly_reducing_a_total() -> None:
    with pytest.raises(ValueError, match="negative"):
        _fact(cost=Decimal("-1"))


def test_usage_with_nobody_to_attribute_it_to_is_refused() -> None:
    with pytest.raises(ValueError, match="person"):
        _fact(person="")


def test_a_cost_keeps_every_digit_the_tool_reported() -> None:
    assert _fact(cost=Decimal("0.00000186")).cost == Decimal("0.00000186")
