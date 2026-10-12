"""Where this product stops counting the same money twice, rule by rule.

Four rules, and they are not variations of one. Naming them together is the point of this module,
because three are enforced elsewhere and the fourth was enforced nowhere.

1. **A re-fetched fact.** A connector asked for a window it has already read. Stopped by the
   database: `fact_key` is unique on `LiteLLM_ProviderUsageFact` and on `LiteLLM_ToolUsageFact`, and
   each connector computes it from the thing being charged for, so a second read writes nothing new.
   Nothing to do here.

2. **Tool spend already on a provider bill.** Claude Code run against an API organisation bills that
   organisation, so the same dollars arrive through the Anthropic connector too. Stopped by the cost
   line's own type in `cost_line.py`: the row becomes `WhoSpent`, which no total can add.

3. **Two connections covering one provider account.** A customer connects a management account and a
   member account, or re-connects after rotating a key without removing the old connection. Nothing
   stopped this, and this module is it.

4. **A provider figure against the gateway's own.** The counting rule. Stopped by the same type as
   rule 2: a gateway observation is never `Spend`.

Rule 3 cannot be settled from what a provider tells us. No connector learns the provider's own
account identifier, so two credentials reading one AWS account look exactly like two credentials
reading two separate AWS accounts. Dropping one on a guess halves a customer's bill, which is as
wrong as doubling it and far harder to notice, since every screen still adds up.

What is distinguishable is the figure itself. Two accounts reporting the same amount, to every
digit, for the same day and the same meter is one account read twice. Two real accounts billing an
identical fraction of a cent on the same model and day is not something that happens. So that is
what this reports, and it reports it: nothing here drops a fact, because the cost of a wrong
suspicion is one look at a provider console, and the cost of a wrong deletion is a bill that reads
half what the customer paid with nothing to show it was halved.
"""

from __future__ import annotations

import dataclasses
import itertools
from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from typing import Final, TypeAlias

from token_iq.truth.cost_line import ProviderCostFact

_Group: TypeAlias = tuple[str, datetime, str | None, str | None, str, Decimal]


@dataclasses.dataclass(frozen=True, slots=True)
class DoubleCountRisk:
    """One figure two or more connections both reported.

    Everything a reader needs to check it against the provider's own console, because the answer is
    theirs to give: the same spend read twice, or two accounts that genuinely both billed this.
    """

    provider: str
    day: datetime
    model: str | None
    meter: str | None
    currency: str
    amount: Decimal
    accounts: tuple[str, ...]


def _group_of(fact: ProviderCostFact) -> _Group:
    return (fact.provider, fact.day, fact.model, fact.meter, fact.currency, fact.amount)


def double_count_risks(facts: Sequence[ProviderCostFact]) -> tuple[DoubleCountRisk, ...]:
    """Figures that two or more connections on one provider both reported.

    Zero is excluded. Two accounts reporting nothing against a model is the commonest figure a
    provider publishes, and pairing those would put a risk on the list for every unused model in a
    customer's estate, which teaches a reader to ignore the list.
    """
    sortable: Final = sorted(
        (fact for fact in facts if fact.amount != 0),
        key=lambda fact: (fact.provider, fact.day, fact.model or "", fact.meter or "", fact.currency, fact.amount),
    )
    grouped: Final = (
        (group, tuple(sorted(frozenset(fact.credential_name for fact in members))))
        for group, members in itertools.groupby(sortable, key=_group_of)
    )
    return tuple(
        DoubleCountRisk(
            provider=provider,
            day=day,
            model=model,
            meter=meter,
            currency=currency,
            amount=amount,
            accounts=accounts,
        )
        for (provider, day, model, meter, currency, amount), accounts in grouped
        if len(accounts) > 1
    )
