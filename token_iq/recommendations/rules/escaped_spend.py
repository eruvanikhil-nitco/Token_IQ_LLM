"""Spend that reached a provider without passing through the gateway.

The strongest rule in the set, because the engine behind it is already proven against real data:
`token_iq/attribution/gap_owner.py` decides it and the Combined screen shows it.

Its figure is deliberately not a saving. The money is already being spent. Routing it through the
gateway makes it visible and gives it an owner; it does not give any of it back. A card that said
"save this" would put a number in front of a finance team that does not survive one question.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Final

from litellm.types.proxy.recommendation import Evidence, Recommendation
from token_iq.recommendations.inputs import RuleInput

RULE_ID: Final = "escaped_spend"


def escaped_spend(rule_input: RuleInput) -> Recommendation | None:
    """A card when some spend bypassed the gateway and no rule claims it."""
    if rule_input.unallocated <= Decimal(0):
        return None

    accounts: Final = ", ".join(rule_input.unallocated_accounts) or "an account with no name recorded"
    return Recommendation(
        rule_id=RULE_ID,
        kind="business",
        title="Spend is reaching a provider without passing through the gateway",
        noticed=(
            "Providers billed more than the gateway recorded, and no attribution rule claims the "
            "difference. This money is already being spent: routing it through the gateway, or "
            "assigning the account to a team, makes it visible and owned rather than reducing it."
        ),
        evidence=(
            Evidence(label="Unclaimed difference", value=format(rule_input.unallocated, "f")),
            Evidence(label="Accounts it came from", value=accounts),
        ),
        figure=rule_input.unallocated,
        figure_kind="already_spent_unwatched",
        currency=rule_input.currency,
        who_should_act="Whoever owns the provider accounts, with a platform admin to add the attribution rule",
    )
