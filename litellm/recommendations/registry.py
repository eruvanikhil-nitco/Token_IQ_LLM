"""Run every rule over one snapshot of the data and keep the cards with something to say.

A rule is a pure function from `RuleInput` to a card or nothing. It never touches a database:
the caller gathers the slices once and hands them over, which is what lets every rule be tested
against fixed numbers and keeps the clock and the connection at the edge of the system.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final, Protocol

from litellm.recommendations.inputs import RuleInput
from litellm.recommendations.rules.escaped_spend import escaped_spend
from litellm.recommendations.rules.failed_requests import failed_requests
from litellm.recommendations.rules.provider_concentration import provider_concentration
from litellm.recommendations.rules.stale_budget import stale_budget
from litellm.types.proxy.recommendation import Recommendation


class Rule(Protocol):
    """A pure decision over one snapshot: a card, or nothing to say.

    A Protocol rather than a Callable alias, because `Callable[[RuleInput], ...]` needs a list
    literal for its parameters and the discipline checker counts that as a mutable construction.
    A Protocol says the same thing with no suppression.
    """

    def __call__(self, rule_input: RuleInput) -> Recommendation | None: ...


_RULES: Final[tuple[Rule, ...]] = (escaped_spend, failed_requests, provider_concentration, stale_budget)
"""Every rule, in the order their cards are offered to a reader.

A rule is registered here and nowhere else, so the set a screen shows is readable in one place."""


def evaluate(rule_input: RuleInput) -> tuple[Recommendation, ...]:
    """Every card that has something to say about this data.

    A rule with nothing to report returns None and contributes no card, rather than an empty one:
    a screen of cards saying "nothing to see here" teaches people to stop reading the screen.
    """
    rules: Final[Sequence[Rule]] = _RULES
    return tuple(card for rule in rules if (card := rule(rule_input)) is not None)
