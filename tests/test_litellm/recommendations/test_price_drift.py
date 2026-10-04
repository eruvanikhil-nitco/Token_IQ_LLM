"""The product checking its own prices against real bills.

Review catches the price changes somebody reads. This catches the ones they waved through,
and the ones upstream never published at all, by noticing that what the gateway calculated
and what the provider actually charged have disagreed for long enough to not be noise.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Final

from litellm.recommendations.inputs import ModelPriceVariance, RuleInput
from litellm.recommendations.rules.price_drift import RULE_ID, price_drift


def _input(*variances: ModelPriceVariance) -> RuleInput:
    return RuleInput(model_price_variances=variances)


def _variance(
    model: str = "gpt-4o",
    days: int = 7,
    priced: str = "100",
    billed: str = "105",
) -> ModelPriceVariance:
    return ModelPriceVariance(
        model=model,
        consecutive_days=days,
        gateway_priced=Decimal(priced),
        provider_billed=Decimal(billed),
    )


class TestWhenItFires:
    def test_a_sustained_variance_raises_a_card(self) -> None:
        card: Final = price_drift(_input(_variance()))
        assert card is not None and card.rule_id == RULE_ID

    def test_it_says_nothing_when_no_model_has_drifted(self) -> None:
        assert price_drift(_input()) is None

    def test_a_variance_under_two_percent_is_noise(self) -> None:
        """Rounding, partial days and settlement lag all produce small gaps every day."""
        assert price_drift(_input(_variance(priced="100", billed="101"))) is None

    def test_a_variance_just_over_two_percent_is_not(self) -> None:
        assert price_drift(_input(_variance(priced="100", billed="102.5"))) is not None

    def test_six_days_is_not_long_enough(self) -> None:
        """One bad day is a settlement artefact. A week is a wrong price."""
        assert price_drift(_input(_variance(days=6))) is None

    def test_seven_days_is(self) -> None:
        assert price_drift(_input(_variance(days=7))) is not None

    def test_it_fires_when_the_gateway_priced_higher_than_the_bill(self) -> None:
        """A price too high overcharges a team internally, which is just as wrong."""
        assert price_drift(_input(_variance(priced="105", billed="100"))) is not None

    def test_a_model_the_provider_never_billed_is_not_drift(self) -> None:
        """Nothing to compare against. Reporting infinite drift would be noise, not a finding."""
        assert price_drift(_input(_variance(priced="100", billed="0"))) is None


class TestWhatItSays:
    def test_it_names_the_model_so_the_price_can_be_found(self) -> None:
        card: Final = price_drift(_input(_variance(model="claude-opus-4-5")))
        assert card is not None
        assert "claude-opus-4-5" in card.title or any("claude-opus-4-5" in e.value for e in card.evidence)

    def test_it_carries_no_money_figure(self) -> None:
        """A wrong price is a measurement error, not a saving and not unwatched spend. A
        number in the money slot would be read as either."""
        card: Final = price_drift(_input(_variance()))
        assert card is not None
        assert card.figure is None and card.figure_kind == "none"

    def test_the_evidence_shows_both_sides_and_the_gap(self) -> None:
        card: Final = price_drift(_input(_variance(priced="100", billed="105")))
        assert card is not None
        labels: Final = {e.label for e in card.evidence}
        assert {"Model", "Gateway priced", "Provider billed", "Variance", "Days running"} <= labels

    def test_it_is_a_technical_card(self) -> None:
        card: Final = price_drift(_input(_variance()))
        assert card is not None and card.kind == "technical"


class TestSeveralModels:
    def test_the_worst_drift_is_reported_first(self) -> None:
        card: Final = price_drift(
            _input(
                _variance(model="small-drift", priced="100", billed="103"),
                _variance(model="big-drift", priced="100", billed="140"),
            )
        )
        assert card is not None
        assert "big-drift" in next(e.value for e in card.evidence if e.label == "Model")

    def test_models_below_the_threshold_are_left_out(self) -> None:
        card: Final = price_drift(
            _input(
                _variance(model="quiet", priced="100", billed="100.5"),
                _variance(model="drifting", priced="100", billed="110"),
            )
        )
        assert card is not None
        joined: Final = " ".join(e.value for e in card.evidence)
        assert "drifting" in joined and "quiet" not in joined


class TestItIsRegistered:
    def test_the_rule_runs_as_part_of_the_set(self) -> None:
        """A rule nobody calls protects nothing."""
        from litellm.recommendations.registry import evaluate

        cards: Final = evaluate(_input(_variance()))
        assert any(card.rule_id == RULE_ID for card in cards)
