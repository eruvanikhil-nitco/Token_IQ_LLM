"""Every provider dollar going through one provider.

This card carries no figure, and that is the point of it. Concentration is a risk, not a cost:
nothing is saved by spreading spend, and a number beside this card would have to be invented.
A finance lead still wants to know, because an outage, a price rise or a contract dispute at one
provider becomes the company's problem with no alternative already in place.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Final

from litellm.recommendations.inputs import RuleInput
from litellm.types.proxy.recommendation import Evidence, Recommendation

RULE_ID: Final = "provider_concentration"

CONCENTRATED_AT: Final = Decimal("0.90")
"""Above this share of provider spend, one provider is effectively the only one.

Ninety rather than a hundred: a company with a token second provider it has never scaled is in
the same position as one with none."""


def provider_concentration(rule_input: RuleInput) -> Recommendation | None:
    """A card when almost every provider dollar goes to a single provider."""
    total: Final = sum(rule_input.spend_by_provider.values(), Decimal(0))
    if total <= Decimal(0):
        return None

    leader: Final = max(rule_input.spend_by_provider.items(), key=lambda pair: pair[1])
    share: Final = leader[1] / total
    if share < CONCENTRATED_AT:
        return None

    percent: Final = (share * 100).quantize(Decimal("0.1"))
    return Recommendation(
        rule_id=RULE_ID,
        kind="business",
        title="Almost all provider spend goes through one provider",
        noticed=(
            f"{percent}% of provider spend went to {leader[0]}. This is a risk rather than a cost: "
            "nothing is saved by spreading it, but an outage, a price rise or a contract dispute "
            "there becomes the company's problem with no alternative already running."
        ),
        evidence=(
            Evidence(label="Largest provider", value=leader[0]),
            Evidence(label="Its share of provider spend", value=f"{percent}%"),
            Evidence(label="Providers with any spend", value=str(len(rule_input.spend_by_provider))),
        ),
        figure=None,
        figure_kind="none",
        currency=None,
        who_should_act="Whoever owns provider contracts, with engineering on what a second provider would take",
    )
