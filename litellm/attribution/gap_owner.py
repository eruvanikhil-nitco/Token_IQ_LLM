"""Deciding who owns a gap between what a provider billed and what the gateway recorded."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Final, Literal

from litellm.types.proxy.attribution import AttributionRule, OwnerType

GapState = Literal["owned", "unallocated", "matched", "not_settled"]


@dataclass(frozen=True, slots=True)
class GapRow:
    provider: str
    credential_name: str
    day: datetime
    provider_cost: Decimal
    gateway_cost: Decimal


@dataclass(frozen=True, slots=True)
class AttributedGap:
    row: GapRow
    gap: Decimal
    owner_type: OwnerType | None
    owner_id: str | None
    rule_id: str | None
    state: GapState


def _match(row: GapRow, rules: Sequence[AttributionRule]) -> AttributionRule | None:
    """The account a fact was fetched with is the only thing a fact says about who spent the
    money, so it is the only thing a rule can key on today."""
    return next(
        (
            rule
            for rule in rules
            if rule.provider == row.provider
            and rule.match_type == "cloud_account"
            and rule.match_value == row.credential_name
        ),
        None,
    )


def _attribute_one(row: GapRow, rules: Sequence[AttributionRule], settled_before: datetime) -> AttributedGap:
    if row.day >= settled_before:
        return AttributedGap(
            row=row, gap=Decimal(0), owner_type=None, owner_id=None, rule_id=None, state="not_settled"
        )

    gap: Final[Decimal] = row.provider_cost - row.gateway_cost
    if gap <= Decimal(0):
        return AttributedGap(row=row, gap=Decimal(0), owner_type=None, owner_id=None, rule_id=None, state="matched")

    rule: Final = _match(row, rules)
    if rule is None:
        return AttributedGap(row=row, gap=gap, owner_type=None, owner_id=None, rule_id=None, state="unallocated")

    return AttributedGap(
        row=row, gap=gap, owner_type=rule.owner_type, owner_id=rule.owner_id, rule_id=rule.rule_id, state="owned"
    )


def attribute(
    rows: Sequence[GapRow], rules: Sequence[AttributionRule], *, settled_before: datetime
) -> tuple[AttributedGap, ...]:
    return tuple(_attribute_one(row, rules, settled_before) for row in rows)
