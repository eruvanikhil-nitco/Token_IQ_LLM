"""The truth layer: one cost line per day, owner and meter, composed in one place.

The blueprint's middle layer. Data Sources answers whether the input can be trusted, analysis
answers what the money means, and this sits between them: the combined, de-duplicated data every
screen above reads, so that none of them composes its own version of the answer.

**A provider figure says how much was spent. A gateway figure says who spent it. They are never
added together.** Here that is a type rather than a convention. Every line is either `Spend`, which
a total may add, or `WhoSpent`, which says who spent money counted somewhere else and can never
reach a total. Four modules compose this answer today and each respects the rule separately, which
means it only has to be forgotten once.

Composed from the facts rather than stored. The blueprint says "table", and a stored table is a
second source of truth that drifts: facts arrive late, a connector re-fetches, a rate is corrected,
an attribution rule changes, and each of those makes a stored line wrong in a way that still looks
like a figure. What would change this is a measured read that is too slow on a real customer's
volume, at which point materialising happens behind this function and its callers do not move.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from types import MappingProxyType
from typing import Final, Literal, TypeAlias

from token_iq.types.attribution import OwnerType
from token_iq.types.provider_billing import EvidenceLevel
from token_iq.types.seat import Seat
from token_iq.types.tool_usage import ToolUsageFact

Source: TypeAlias = Literal["provider", "tool", "seat", "gateway"]
"""Which kind of source a line came from, not which account: the account is on the line."""

NEW_MONEY: Final = "new_money"

ALREADY_BILLED: Final = (
    "The same dollars arrive on a provider bill, so this line says who spent them rather than "
    "adding to what was spent."
)

GATEWAY_IS_ATTRIBUTION: Final = (
    "What the gateway observed. The provider's own figure says how much was spent, so this says "
    "who spent it and is never added to a total."
)


@dataclasses.dataclass(frozen=True, slots=True)
class ProviderCostFact:
    """One provider-billed cost line as a read of the facts yields it.

    Narrower than the `ProviderUsageFact` a connector writes, which also carries tokens, request
    ids and the raw payload. Those belong to the write and to the raw-records view; what the money
    needs is this, and building the write shape here would mean filling fields this read never
    looked at with None.
    """

    day: datetime
    provider: str
    credential_name: str
    model: str | None
    meter: str | None
    evidence: EvidenceLevel
    currency: str
    amount: Decimal


@dataclasses.dataclass(frozen=True, slots=True)
class Owner:
    owner_type: OwnerType
    owner_id: str


@dataclasses.dataclass(frozen=True, slots=True)
class LineFacts:
    """What every line carries, whether or not it is money.

    `evidence` is None for a line nobody asserted: the grades describe what a provider said, and a
    seat is a figure a person read off a contract, so claiming one would be a claim about evidence
    that does not exist.
    """

    day: datetime
    source: Source
    currency: str
    amount: Decimal
    evidence: EvidenceLevel | None
    owner: Owner | None
    provider: str | None = None
    credential_name: str | None = None
    """The stored credential the money was read with, or the tool it came from.

    The same name the fact table, the attribution rules and the connect flow use, rather than a
    second word for it: two names for one thing is how a join eventually goes wrong.
    """

    model: str | None = None
    meter: str | None = None


@dataclasses.dataclass(frozen=True, slots=True)
class Spend:
    """Money. A total may add this."""

    facts: LineFacts


@dataclasses.dataclass(frozen=True, slots=True)
class WhoSpent:
    """A statement about money counted somewhere else. No total may add this.

    `why` is carried so a screen showing the line can say what it is, rather than leaving a reader
    to wonder why a figure they can see is missing from the total above it.
    """

    facts: LineFacts
    why: str


CostLine: TypeAlias = Spend | WhoSpent


@dataclasses.dataclass(frozen=True, slots=True)
class GatewayObservation:
    """One gateway figure, already summed to whatever grain the caller read it at."""

    day: datetime
    currency: str
    amount: Decimal
    owner: Owner | None


@dataclasses.dataclass(frozen=True, slots=True)
class Truth:
    lines: tuple[CostLine, ...]


OwnerLookup: TypeAlias = Callable[[str, str], Owner | None]
"""Provider and account to the owner the attribution rules give it, or None.

None is a real answer and the product reports it: unallocated cost is a figure on the Overview
page. Guessing an owner would make it disappear into somebody else's budget.
"""


def _provider_line(fact: ProviderCostFact, owner_for: OwnerLookup) -> CostLine:
    return Spend(
        facts=LineFacts(
            day=fact.day,
            source="provider",
            currency=fact.currency,
            amount=fact.amount,
            evidence=fact.evidence,
            owner=owner_for(fact.provider, fact.credential_name),
            provider=fact.provider,
            credential_name=fact.credential_name,
            model=fact.model,
            meter=fact.meter,
        )
    )


def _tool_line(row: ToolUsageFact) -> CostLine:
    facts: Final = LineFacts(
        day=row.day,
        source="tool",
        currency=row.currency,
        amount=row.cost,
        evidence=None,
        owner=Owner(owner_type="user", owner_id=row.person),
        credential_name=row.tool,
        model=row.model,
    )
    return Spend(facts=facts) if row.basis == NEW_MONEY else WhoSpent(facts=facts, why=ALREADY_BILLED)


def _seat_line(seat: Seat) -> CostLine:
    """A seat covers its period and sits on the day that period starts.

    Spreading a monthly fee across days to line it up with daily spend would invent a daily figure
    the company was never charged.
    """
    return Spend(
        facts=LineFacts(
            day=seat.period_start,
            source="seat",
            currency=seat.currency,
            amount=seat.amount,
            evidence=None,
            owner=Owner(owner_type="user", owner_id=seat.user_id),
            credential_name=seat.tool,
        )
    )


def _gateway_line(observation: GatewayObservation) -> CostLine:
    return WhoSpent(
        facts=LineFacts(
            day=observation.day,
            source="gateway",
            currency=observation.currency,
            amount=observation.amount,
            evidence="allocated",
            owner=observation.owner,
        ),
        why=GATEWAY_IS_ATTRIBUTION,
    )


def combine(
    *,
    provider_facts: Sequence[ProviderCostFact],
    tool_rows: Sequence[ToolUsageFact],
    seats: Sequence[Seat],
    gateway: Sequence[GatewayObservation],
    owner_for: OwnerLookup,
) -> Truth:
    """Every cost line the product holds for whatever window the caller read.

    Takes the facts rather than fetching them, so the rule above can be tested without a database,
    the way the reconciliation arithmetic and the data-quality rules are.
    """
    return Truth(
        lines=(
            *(_provider_line(fact, owner_for) for fact in provider_facts),
            *(_tool_line(row) for row in tool_rows),
            *(_seat_line(seat) for seat in seats),
            *(_gateway_line(observation) for observation in gateway),
        )
    )


def money_of(line: CostLine) -> LineFacts | None:
    """The figure a total may add, or None for a line that only says who spent it.

    Exhaustive over the two kinds on purpose. A third kind added later is a type error here rather
    than a line quietly left out of, or quietly added to, every total in the product.
    """
    match line:
        case Spend(facts=facts):
            return facts
        case WhoSpent():
            return None


def total_of(lines: Sequence[CostLine]) -> Mapping[str, Decimal]:
    """What was spent, per currency, from the lines that are money.

    Keyed by currency rather than one figure: a customer billed in two currencies has two totals,
    and adding them produces a number in no currency at all. Nothing here converts, because a rate
    nobody chose would look authoritative and not be.

    An empty mapping for a period with no lines, never a zero: a zero says nobody spent anything,
    and the two are different answers.
    """
    money: Final = tuple(facts for line in lines if (facts := money_of(line)) is not None)
    return MappingProxyType(
        {
            currency: sum((facts.amount for facts in money if facts.currency == currency), Decimal(0))
            for currency in {facts.currency for facts in money}
        }
    )
