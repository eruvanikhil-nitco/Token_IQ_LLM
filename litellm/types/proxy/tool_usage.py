"""What one person spent inside one user tool on one day.

This is the third data source, beside the gateway and the provider APIs, and it is the only one
that can say what a named person spent inside Claude Code or Cursor rather than what an API key
spent. That is the whole reason it exists.

It also carries the one flag that stops the product double counting. Claude Code run against an
API organisation bills that organisation, so the same dollars already arrive through the
Anthropic billing connector. Adding both would overstate a customer's Anthropic spend by exactly
what their developers ran through Claude Code, which for a heavy user is the largest number on
the screen. The row is still worth storing, because knowing who spent it is the point, but it
must never be added to a total that already contains the provider bill.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal, TypeAlias

ToolName: TypeAlias = Literal["claude_code", "cursor", "copilot"]

CostBasis: TypeAlias = Literal["new_money", "already_on_a_provider_bill"]
"""new_money: this amount appears on no provider bill we read, so it adds to the total.
already_on_a_provider_bill: the same dollars arrive through a provider connector, so this row
says who spent them and must never be added to a total that already counts the bill."""


@dataclass(frozen=True, slots=True)
class ToolUsageFact:
    """One person, one tool, one day.

    `person` is whatever the tool calls the human, which is an email address for Claude Code and
    Cursor. It is deliberately not a Token IQ user id: matching the two is a separate decision
    that can fail, and a fact that silently attributed itself to the wrong person would be worse
    than one that says plainly it matches nobody.
    """

    tool: ToolName
    person: str
    day: datetime
    cost: Decimal
    currency: str
    basis: CostBasis
    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    sessions: int | None = None

    def __post_init__(self) -> None:
        """Refuse a fact that cannot be added up or attributed.

        This raises rather than returning a failure value, against the repo's usual convention,
        because each of these is a mistake in our own code rather than something a caller can
        handle, and failing at construction means it can never reach a total.
        """
        if not self.currency:
            raise ValueError(f"{self.tool} usage for {self.person!r} carries a cost with no currency")
        if self.cost < 0:
            raise ValueError(f"{self.tool} usage for {self.person!r} carries a negative cost: {self.cost}")
        if not self.person:
            raise ValueError(f"{self.tool} usage carries no person to attribute it to")

    @property
    def counts_toward_total(self) -> bool:
        """Whether this amount may be added to what the company spent.

        A property rather than a bare comparison at each call site, so that adding a third basis
        later cannot quietly start counting.
        """
        return self.basis == "new_money"


@dataclass(frozen=True, slots=True)
class ToolFetched:
    facts: tuple[ToolUsageFact, ...]
    watermark: datetime


@dataclass(frozen=True, slots=True)
class ToolFetchFailed:
    reason: str
    retryable: bool


@dataclass(frozen=True, slots=True)
class ToolNotConfigured:
    reason: str


ToolFetchResult: TypeAlias = ToolFetched | ToolFetchFailed | ToolNotConfigured
