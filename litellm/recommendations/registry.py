"""Run every rule over one snapshot of the data and keep the cards with something to say.

A rule is a pure function from `RuleInput` to a card or nothing. It never touches a database:
the caller gathers the slices once and hands them over, which is what lets every rule be tested
against fixed numbers and keeps the clock and the connection at the edge of the system.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType
from typing import Final, Protocol

from litellm.types.proxy.recommendation import Recommendation

_NO_SPEND: Final[Mapping[str, Decimal]] = MappingProxyType({})
"""A frozen default, so the dataclass never builds a mutable one per instance."""


@dataclass(frozen=True, slots=True)
class BudgetSnapshot:
    """One budget and what was actually spent against it."""

    budget_id: str
    owner: str
    limit: Decimal
    spent: Decimal


@dataclass(frozen=True, slots=True)
class RuleInput:
    """Everything the rules read, gathered once.

    Each field is added by the task that needs it, so a rule can never quietly start reading
    something nobody gathered.
    """

    currency: str = "USD"
    unallocated: Decimal = Decimal(0)
    unallocated_accounts: tuple[str, ...] = ()
    failed_requests: int = 0
    total_requests: int = 0
    spend_on_failures: Decimal | None = None
    spend_by_provider: Mapping[str, Decimal] = _NO_SPEND
    budgets: tuple[BudgetSnapshot, ...] = ()


class Rule(Protocol):
    """A pure decision over one snapshot: a card, or nothing to say.

    A Protocol rather than a Callable alias, because `Callable[[RuleInput], ...]` needs a list
    literal for its parameters and the discipline checker counts that as a mutable construction.
    A Protocol says the same thing with no suppression.
    """

    def __call__(self, rule_input: RuleInput) -> Recommendation | None: ...


_RULES: Final[tuple[Rule, ...]] = ()
"""Every rule, in the order their cards are offered to a reader.

Empty until Task 2. A rule is registered here and nowhere else, so the set a screen shows is
readable in one place."""


def evaluate(rule_input: RuleInput) -> tuple[Recommendation, ...]:
    """Every card that has something to say about this data.

    A rule with nothing to report returns None and contributes no card, rather than an empty one:
    a screen of cards saying "nothing to see here" teaches people to stop reading the screen.
    """
    rules: Final[Sequence[Rule]] = _RULES
    return tuple(card for rule in rules if (card := rule(rule_input)) is not None)
