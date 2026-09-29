from decimal import Decimal
from typing import Final

from litellm.recommendations.inputs import RuleInput
from litellm.recommendations.rules.failed_requests import failed_requests


def _input(failed: int, total: int, spend: str | None = None) -> RuleInput:
    return RuleInput(
        failed_requests=failed,
        total_requests=total,
        spend_on_failures=None if spend is None else Decimal(spend),
    )


def test_it_says_nothing_when_nothing_failed() -> None:
    assert failed_requests(_input(0, 100)) is None


def test_it_says_nothing_when_there_were_no_requests_at_all() -> None:
    assert failed_requests(_input(0, 0)) is None


def test_a_handful_of_failures_in_a_large_month_is_not_worth_a_card() -> None:
    assert failed_requests(_input(1, 100000)) is None


def test_a_high_rate_across_a_tiny_sample_is_noise_not_a_finding() -> None:
    assert failed_requests(_input(3, 4)) is None


def test_it_reports_the_rate_as_evidence_a_reader_can_check() -> None:
    card: Final = failed_requests(_input(94, 156))
    assert card is not None
    assert any("94" in e.value for e in card.evidence)
    assert any("156" in e.value for e in card.evidence)
    assert any("60.3%" in e.value for e in card.evidence)


def test_it_does_not_invent_a_cost_per_failed_request() -> None:
    card: Final = failed_requests(_input(94, 156, spend=None))
    assert card is not None
    assert card.figure is None
    assert card.figure_kind == "none"
    assert card.currency is None


def test_it_says_why_no_figure_is_shown_rather_than_leaving_a_blank() -> None:
    card: Final = failed_requests(_input(94, 156, spend=None))
    assert card is not None
    assert "not recorded separately" in card.noticed


def test_when_the_data_does_carry_the_cost_it_is_money_that_could_stop() -> None:
    card: Final = failed_requests(_input(94, 156, spend="1.50"))
    assert card is not None
    assert card.figure == Decimal("1.50")
    assert card.figure_kind == "could_stop_spending"
    assert card.currency == "USD"


def test_a_cost_that_is_carried_keeps_every_digit() -> None:
    card: Final = failed_requests(_input(94, 156, spend="1.50000000004"))
    assert card is not None
    assert card.figure == Decimal("1.50000000004")


def test_it_is_a_technical_card_not_a_business_one() -> None:
    card: Final = failed_requests(_input(94, 156))
    assert card is not None
    assert card.kind == "technical"


def test_it_says_who_should_act() -> None:
    card: Final = failed_requests(_input(94, 156))
    assert card is not None
    assert card.who_should_act != ""


def test_many_failures_that_are_still_a_small_share_are_not_worth_a_card() -> None:
    """Exercises the rate threshold specifically. The earlier small-sample tests are stopped by
    the minimum count first, so neither of them proves the rate check does anything: 25 failures
    is above the count floor, and 2.5% is below the rate floor."""
    assert failed_requests(_input(25, 1000)) is None


def test_the_same_count_at_a_high_enough_share_does_earn_a_card() -> None:
    card = failed_requests(_input(25, 200))
    assert card is not None
    assert any("12.5%" in e.value for e in card.evidence)


def test_it_never_promises_a_saving_when_it_has_no_figure_to_back_one() -> None:
    """The type stops a figure without a kind. It cannot stop a sentence, and a card that reads
    like a saving while carrying no number is the exact mistake this feature exists to avoid."""
    card: Final = failed_requests(_input(94, 156, spend=None))
    assert card is not None
    assert "saving" not in card.noticed.lower()
    assert "save" not in card.noticed.lower()
    assert "saving" not in card.title.lower()
