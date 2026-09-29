from decimal import Decimal
from typing import Final

from litellm.recommendations.inputs import RuleInput
from litellm.recommendations.rules.provider_concentration import provider_concentration


def _input(**by_provider: str) -> RuleInput:
    return RuleInput(spend_by_provider={k: Decimal(v) for k, v in by_provider.items()})


def test_it_says_nothing_when_spend_is_spread() -> None:
    assert provider_concentration(_input(openai="50", anthropic="50")) is None


def test_it_says_nothing_when_no_provider_has_spent_anything() -> None:
    assert provider_concentration(_input()) is None
    assert provider_concentration(_input(openai="0")) is None


def test_a_token_second_provider_does_not_count_as_diversification() -> None:
    card: Final = provider_concentration(_input(openrouter="99", openai="1"))
    assert card is not None
    assert "openrouter" in card.noticed


def test_it_names_the_provider_and_the_share() -> None:
    card: Final = provider_concentration(_input(openrouter="100"))
    assert card is not None
    assert "openrouter" in card.noticed
    assert any("100.0%" in e.value for e in card.evidence)


def test_it_carries_no_figure_because_it_is_a_risk_not_a_cost() -> None:
    card: Final = provider_concentration(_input(openrouter="100"))
    assert card is not None
    assert card.figure is None
    assert card.figure_kind == "none"
    assert card.currency is None


def test_it_never_promises_a_saving() -> None:
    card: Final = provider_concentration(_input(openrouter="100"))
    assert card is not None
    assert "saving" not in card.noticed.lower()
    assert "save" not in card.noticed.lower() or "nothing is saved" in card.noticed.lower()


def test_it_says_in_words_that_this_is_a_risk_rather_than_a_cost() -> None:
    card: Final = provider_concentration(_input(openrouter="100"))
    assert card is not None
    assert "risk rather than a cost" in card.noticed


def test_it_says_who_should_act() -> None:
    card: Final = provider_concentration(_input(openrouter="100"))
    assert card is not None
    assert card.who_should_act != ""
