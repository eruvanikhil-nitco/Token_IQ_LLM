from decimal import Decimal
from typing import Final

from token_iq.recommendations.inputs import BudgetSnapshot, RuleInput
from token_iq.recommendations.rules.stale_budget import stale_budget


def _budget(owner: str, limit: str, spent: str) -> BudgetSnapshot:
    return BudgetSnapshot(budget_id=f"b-{owner}", owner=owner, limit=Decimal(limit), spent=Decimal(spent))


def _input(*budgets: BudgetSnapshot) -> RuleInput:
    return RuleInput(budgets=budgets)


def test_a_budget_matching_its_spend_needs_no_card() -> None:
    assert stale_budget(_input(_budget("platform", "100", "90"))) is None


def test_a_budget_comfortably_used_needs_no_card() -> None:
    assert stale_budget(_input(_budget("platform", "100", "40"))) is None


def test_no_budgets_at_all_produces_nothing() -> None:
    assert stale_budget(_input()) is None


def test_a_budget_of_zero_is_ignored_rather_than_dividing_by_it() -> None:
    assert stale_budget(_input(_budget("platform", "0", "50"))) is None


def test_a_budget_far_above_what_is_spent_is_worth_saying() -> None:
    card: Final = stale_budget(_input(_budget("platform", "100", "2")))
    assert card is not None
    assert any("100" in e.value for e in card.evidence)
    assert "not really a decision" in card.noticed


def test_a_budget_being_exceeded_is_reported_differently_from_one_set_too_high() -> None:
    over: Final = stale_budget(_input(_budget("platform", "100", "150")))
    under: Final = stale_budget(_input(_budget("platform", "100", "2")))
    assert over is not None and under is not None
    assert over.noticed != under.noticed
    assert over.title != under.title


def test_the_budget_furthest_from_its_spend_is_the_one_reported() -> None:
    card: Final = stale_budget(_input(_budget("mild", "100", "10"), _budget("worst", "100", "1")))
    assert card is not None
    assert card.evidence[0].value == "worst"


def test_it_carries_no_figure_because_changing_a_limit_changes_no_spend() -> None:
    card: Final = stale_budget(_input(_budget("platform", "100", "2")))
    assert card is not None
    assert card.figure is None
    assert card.figure_kind == "none"


def test_it_keeps_every_digit_of_the_limit_and_the_spend() -> None:
    card: Final = stale_budget(_input(_budget("platform", "100.00000001", "2")))
    assert card is not None
    assert any("100.00000001" in e.value for e in card.evidence)


def test_it_never_promises_a_saving_in_either_direction() -> None:
    """Changing a limit changes what is allowed, not what is spent. Neither the exceeded card nor
    the unused one may read as money the company gets back."""
    exceeded: Final = stale_budget(_input(_budget("platform", "100", "120")))
    unused: Final = stale_budget(_input(_budget("platform", "100", "2")))
    for card in (exceeded, unused):
        assert card is not None
        assert "saving" not in card.noticed.lower()
        assert "save" not in card.noticed.lower()
        assert "saving" not in card.title.lower()
        assert card.figure is None
        assert card.figure_kind == "none"
