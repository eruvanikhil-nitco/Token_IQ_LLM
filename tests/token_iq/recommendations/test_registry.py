from decimal import Decimal
from typing import Final

import pytest

from token_iq.recommendations.inputs import RuleInput
from token_iq.recommendations.registry import evaluate
from token_iq.types.recommendation import Evidence, Recommendation

EMPTY_INPUT: Final = RuleInput()


def _card(**overrides: object) -> Recommendation:
    base: Final[dict[str, object]] = {
        "rule_id": "r",
        "kind": "business",
        "title": "t",
        "noticed": "n",
        "evidence": (),
        "figure": None,
        "figure_kind": "none",
        "currency": None,
        "who_should_act": "an admin",
    }
    return Recommendation(**{**base, **overrides})  # pyright: ignore[reportArgumentType]  # fixture spread


def test_a_card_with_no_honest_figure_carries_no_number() -> None:
    assert _card().figure is None


def test_a_figure_must_say_what_kind_of_figure_it_is() -> None:
    with pytest.raises(ValueError, match="will not say what kind it is"):
        _card(figure=Decimal("10"), figure_kind="none", currency="USD")


def test_a_card_claiming_a_kind_may_not_leave_the_figure_out() -> None:
    with pytest.raises(ValueError, match="claims a could_stop_spending figure but carries none"):
        _card(figure=None, figure_kind="could_stop_spending", currency="USD")


def test_a_figure_always_names_its_currency() -> None:
    with pytest.raises(ValueError, match="carries a figure with no currency"):
        _card(figure=Decimal("10"), figure_kind="could_stop_spending", currency=None)


def test_a_well_formed_card_is_accepted() -> None:
    card: Final = _card(figure=Decimal("10"), figure_kind="could_stop_spending", currency="USD")
    assert card.figure == Decimal("10")
    assert card.figure_kind == "could_stop_spending"


def test_evidence_travels_with_the_card() -> None:
    card: Final = _card(evidence=(Evidence(label="failed", value="94 of 156"),))
    assert card.evidence[0].value == "94 of 156"


def test_a_rule_with_nothing_to_say_produces_no_card_rather_than_an_empty_one() -> None:
    assert evaluate(EMPTY_INPUT) == ()


def test_every_card_that_comes_back_is_a_recommendation() -> None:
    assert all(isinstance(c, Recommendation) for c in evaluate(EMPTY_INPUT))
