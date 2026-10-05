"""Everything the rules read, gathered once.

A module of its own so a rule can import it without importing the registry that lists the
rules, which would be a cycle. Each field is added by the task whose rule needs it, so no
rule can quietly start reading something nobody gathered.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType
from typing import Final

_NO_SPEND: Final[Mapping[str, Decimal]] = MappingProxyType({})
"""A frozen default, so the dataclass never builds a mutable one per instance."""


@dataclass(frozen=True, slots=True)
class ModelPriceVariance:
    """What one model cost according to each side, and for how long they have disagreed.

    The gateway figure is calculated from the price list; the provider figure is what the
    bill said. A sustained gap means the list price is wrong, which no amount of reviewing
    upstream's changes can catch on its own.
    """

    model: str
    consecutive_days: int
    gateway_priced: Decimal
    provider_billed: Decimal


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
    model_price_variances: tuple[ModelPriceVariance, ...] = ()
