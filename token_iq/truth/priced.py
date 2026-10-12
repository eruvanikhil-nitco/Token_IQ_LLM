"""Gateway traffic priced at the customer's rates, and the one window where that is money.

The blueprint: "Confirmed cost appears on the provider's invoice data; estimated cost has been
observed by the gateway but not yet billed." So a priced figure is money for exactly the days a
provider has not billed yet. For every earlier day it is the same dollars the provider already
reported, said a second way, and the cost line's type keeps it out of totals.

That boundary is the counting rule in its only form that is a date rather than a source. Priced
spend added to a day the provider has billed doubles that day. Priced spend withheld from a day the
provider has not billed leaves the current month reading as though nobody had spent anything until
the invoice arrives, which is the complaint this product exists to answer.

The watermark is per provider, because providers bill on their own schedules: OpenRouter prices
each request as it happens, Bedrock's Cost Explorer settles about two days late, and Azure reports
by day for a whole subscription. One watermark across all of them would either double count the
fast one or hide the slow one.

What this does not do is price anything. The amounts arrive already priced, because pricing needs
the rate rules, the price history and a day, and because a rate conflict has to be reported rather
than turned into a figure: see `token_iq/pricing/rates.py`.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from typing import Final

from token_iq.truth.cost_line import CostLine, LineFacts, Owner, Spend, WhoSpent

ALREADY_BILLED: Final = (
    "The provider has already billed this day, so this says who spent it rather than adding to "
    "what was spent."
)


@dataclasses.dataclass(frozen=True, slots=True)
class GatewayDay:
    """What the gateway observed of one provider, model and meter on one day, already priced."""

    day: datetime
    provider: str
    model: str | None
    meter: str | None
    currency: str
    amount: Decimal
    owner: Owner | None


def _line(observed: GatewayDay, billed_through: datetime | None) -> CostLine:
    facts: Final = LineFacts(
        day=observed.day,
        source="gateway",
        currency=observed.currency,
        amount=observed.amount,
        evidence="priced",
        owner=observed.owner,
        provider=observed.provider,
        model=observed.model,
        meter=observed.meter,
    )
    if billed_through is not None and observed.day <= billed_through:
        return WhoSpent(facts=facts, why=ALREADY_BILLED)
    return Spend(facts=facts)


def priced_lines(
    observed: Sequence[GatewayDay],
    *,
    billed_through: Mapping[str, datetime],
) -> tuple[CostLine, ...]:
    """Priced gateway days as cost lines, money only where the provider has not billed yet.

    `billed_through` is the last day each provider has reported, which is the newest `bucket_start`
    among its facts. A provider missing from it has never billed at all, so every day of its
    traffic is money: a provider connected to the gateway and not to billing has no invoice data
    for anything, and the priced figure is the only figure there is.
    """
    return tuple(_line(day, billed_through.get(day.provider)) for day in observed)
