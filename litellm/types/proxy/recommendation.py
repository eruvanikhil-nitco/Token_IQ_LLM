"""One thing worth doing, with the evidence behind it and an honest figure.

The figure rule is the whole point of this module. Most of what the rules find is not a saving:
spend that escaped the gateway is money already being spent, and concentration on one provider is
a risk rather than a cost. Putting a number labelled "saving" beside either would not survive a
finance lead asking one question, and it would discredit every other card on the screen.

So a card carries an amount and what kind of amount it is, and the type refuses the two obvious
ways to get that wrong: claiming a figure with no kind, and claiming a kind with no figure.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal, TypeAlias

RecommendationKind: TypeAlias = Literal["business", "technical"]

FigureKind: TypeAlias = Literal["could_stop_spending", "already_spent_unwatched", "none"]
"""could_stop_spending: acting on this reduces what the company pays.
already_spent_unwatched: the money is being spent either way; acting makes it visible and owned.
none: there is nothing honest to quantify, and the card says so rather than showing a zero."""


@dataclass(frozen=True, slots=True)
class Evidence:
    """One number a reader can check against another screen in the product."""

    label: str
    value: str


@dataclass(frozen=True, slots=True)
class Recommendation:
    rule_id: str
    kind: RecommendationKind
    title: str
    noticed: str
    evidence: tuple[Evidence, ...]
    figure: Decimal | None
    figure_kind: FigureKind
    currency: str | None
    who_should_act: str

    def __post_init__(self) -> None:
        """Refuse a card that misstates what its number is.

        This raises rather than returning a failure value, against the repo's usual convention,
        because a rule that builds a card wrongly is a mistake in our own code and not something
        a caller can handle. Failing at construction means it can never reach a screen.
        """
        if self.figure is None and self.figure_kind != "none":
            raise ValueError(f"{self.rule_id} claims a {self.figure_kind} figure but carries none")
        if self.figure is not None and self.figure_kind == "none":
            raise ValueError(f"{self.rule_id} carries a figure but will not say what kind it is")
        if self.figure is not None and not self.currency:
            raise ValueError(f"{self.rule_id} carries a figure with no currency")
