"""Money spent on requests that failed.

Unlike escaped spend, this genuinely is money that could stop being spent, so its figure is a
saving when the data carries one.

The discipline here is not inventing that figure. The spend rollup holds a request count and a
total spend, not spend per failed request. Dividing one by the other assumes every request costs
the same, which is false: a call that failed after filling its context window costs far more than
one rejected at the door. So the card reports the count and the rate as evidence, and gives a
figure only when the caller actually gathered cost attributable to failures. When it did not, the
card still earns its place by naming the rate.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Final

from litellm.types.proxy.recommendation import Evidence, Recommendation
from token_iq.recommendations.inputs import RuleInput

RULE_ID: Final = "failed_requests"

MIN_FAILURES: Final = 20
MIN_RATE: Final = Decimal("0.05")
"""Both thresholds must be crossed before this is worth a card.

A handful of failures in a large month is normal operation, and a high rate across five requests
is noise. A screen that shows the same card every month teaches people to stop reading it, which
costs more than the card is worth."""


def failed_requests(rule_input: RuleInput) -> Recommendation | None:
    """A card when enough requests failed, and often enough, to be worth acting on."""
    if rule_input.total_requests <= 0 or rule_input.failed_requests < MIN_FAILURES:
        return None

    rate: Final = Decimal(rule_input.failed_requests) / Decimal(rule_input.total_requests)
    if rate < MIN_RATE:
        return None

    spend: Final = rule_input.spend_on_failures
    percent: Final = (rate * 100).quantize(Decimal("0.1"))

    return Recommendation(
        rule_id=RULE_ID,
        kind="technical",
        title="A large share of requests are failing",
        noticed=(
            f"{rule_input.failed_requests} of {rule_input.total_requests} requests failed, which is "
            f"{percent}%. A request that fails can still cost money, and fixing the cause stops that "
            "spend rather than moving it."
            if spend is not None
            else (
                f"{rule_input.failed_requests} of {rule_input.total_requests} requests failed, which is "
                f"{percent}%. What those failures cost is not recorded separately, so no figure is shown: "
                "the spend rollup holds a request count and a total, and dividing one by the other would "
                "assume every request costs the same."
            )
        ),
        evidence=(
            Evidence(label="Failed requests", value=str(rule_input.failed_requests)),
            Evidence(label="Total requests", value=str(rule_input.total_requests)),
            Evidence(label="Failure rate", value=f"{percent}%"),
        ),
        figure=spend,
        figure_kind="could_stop_spending" if spend is not None else "none",
        currency=rule_input.currency if spend is not None else None,
        who_should_act="The team owning the failing integration, with a platform engineer on retry behaviour",
    )
