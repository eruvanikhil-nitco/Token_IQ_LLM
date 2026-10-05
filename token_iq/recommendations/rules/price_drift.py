"""A model whose list price and real bill have disagreed for long enough to not be noise.

The third defence on prices, and the only one that does not depend on somebody looking.
The bundled list is kept current by a daily job and a reviewer, which catches the changes
upstream published and somebody read. It cannot catch a price upstream never published, a
price upstream got wrong, or a change a reviewer waved through.

A real bill catches all three. If what the gateway calculated and what the provider actually
charged have differed by more than a rounding margin every day for a week, the list price is
wrong, and the product says so rather than continuing to report a confident figure.

The card carries no money figure on purpose. A wrong price is a measurement error, not a
saving and not unwatched spend, and a number in the money slot would be read as one of those.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Final

from token_iq.recommendations.inputs import ModelPriceVariance, RuleInput
from token_iq.types.recommendation import Evidence, Recommendation

RULE_ID: Final = "price_drift"

# Below this, a daily gap is rounding, a partial day, or settlement lag.
NOISE_THRESHOLD: Final = Decimal("0.02")

# One bad day is a settlement artefact. A week running is a wrong price.
SUSTAINED_DAYS: Final = 7


def _variance_ratio(reading: ModelPriceVariance) -> Decimal | None:
    """How far apart the two sides are, as a share of what was actually billed.

    None when the provider billed nothing for the model: there is nothing to be wrong
    against, and reporting an infinite gap would be noise rather than a finding.
    """
    if reading.provider_billed == 0:
        return None
    return abs(reading.provider_billed - reading.gateway_priced) / abs(reading.provider_billed)


def _drifting(reading: ModelPriceVariance) -> bool:
    ratio: Final = _variance_ratio(reading)
    return ratio is not None and ratio > NOISE_THRESHOLD and reading.consecutive_days >= SUSTAINED_DAYS


def price_drift(rule_input: RuleInput) -> Recommendation | None:
    """A card when a model's list price no longer matches what the provider charges."""
    drifting: Final = tuple(r for r in rule_input.model_price_variances if _drifting(r))
    if not drifting:
        return None

    worst: Final = max(drifting, key=lambda r: _variance_ratio(r) or Decimal(0))
    ratio: Final = _variance_ratio(worst) or Decimal(0)
    others: Final = len(drifting) - 1

    return Recommendation(
        rule_id=RULE_ID,
        kind="technical",
        title="A model's list price no longer matches what the provider charges",
        noticed=(
            f"For {worst.consecutive_days} days running, what the gateway calculated for "
            f"{worst.model} and what the provider billed have differed by "
            f"{ratio * 100:.1f}%. A gap that persists is a wrong price in the list rather "
            "than a settlement delay, and every figure the product reports for this model "
            "carries the same error."
            + (f" {others} other model(s) are drifting too." if others else "")
        ),
        evidence=(
            Evidence(label="Model", value=worst.model),
            Evidence(label="Gateway priced", value=format(worst.gateway_priced, "f")),
            Evidence(label="Provider billed", value=format(worst.provider_billed, "f")),
            Evidence(label="Variance", value=f"{ratio * 100:.1f}%"),
            Evidence(label="Days running", value=str(worst.consecutive_days)),
        ),
        figure=None,
        figure_kind="none",
        currency=None,
        who_should_act="Whoever owns prices, by correcting the entry in the price list",
    )
