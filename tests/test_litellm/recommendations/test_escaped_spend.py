from decimal import Decimal
from typing import Final

from token_iq.recommendations.inputs import RuleInput
from token_iq.recommendations.rules.escaped_spend import escaped_spend


def _input(unallocated: str = "0", accounts: tuple[str, ...] = ()) -> RuleInput:
    return RuleInput(unallocated=Decimal(unallocated), unallocated_accounts=accounts)


def test_it_says_nothing_when_every_difference_is_claimed_or_settled() -> None:
    assert escaped_spend(_input("0")) is None


def test_it_says_nothing_when_the_gateway_recorded_more_than_the_provider_billed() -> None:
    assert escaped_spend(_input("-5")) is None


def test_it_reports_what_bypassed_the_gateway_with_the_accounts_it_came_from() -> None:
    card: Final = escaped_spend(_input("0.00774700", ("openrouter-billing",)))
    assert card is not None
    assert card.figure == Decimal("0.00774700")
    assert any("openrouter-billing" in e.value for e in card.evidence)


def test_it_never_calls_this_a_saving() -> None:
    card: Final = escaped_spend(_input("0.00774700"))
    assert card is not None
    assert card.figure_kind == "already_spent_unwatched"
    assert "saving" not in card.noticed.lower()
    assert "save" not in card.noticed.lower()
    assert "saving" not in card.title.lower()


def test_it_says_in_words_that_the_money_is_already_being_spent() -> None:
    card: Final = escaped_spend(_input("1"))
    assert card is not None
    assert "already being spent" in card.noticed.lower()


def test_it_keeps_every_digit_rather_than_rounding_the_evidence() -> None:
    card: Final = escaped_spend(_input("0.00774700"))
    assert card is not None
    assert any("0.00774700" in e.value for e in card.evidence)


def test_it_says_who_should_act() -> None:
    card: Final = escaped_spend(_input("1"))
    assert card is not None
    assert card.who_should_act != ""


def test_it_names_the_account_even_when_none_was_recorded() -> None:
    card: Final = escaped_spend(_input("1", ()))
    assert card is not None
    assert any(e.value for e in card.evidence if e.label == "Accounts it came from")


def test_it_is_a_business_card_not_a_technical_one() -> None:
    card: Final = escaped_spend(_input("1"))
    assert card is not None
    assert card.kind == "business"
