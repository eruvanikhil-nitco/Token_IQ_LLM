"""Deciding who owns a gap between what a provider billed and what the gateway recorded."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Final, Literal, TypeAlias

from token_iq.types.attribution import AttributionRule, OwnerType

GapState: TypeAlias = Literal["owned", "unallocated", "matched", "not_settled", "no_provider_data"]
"""owned: a rule maps this account to a team, project or user, and the gap is theirs.
unallocated: the gap is real and positive, but no rule maps this account to an owner.
matched: the gateway recorded no more than the provider billed, so there is no gap to assign.
not_settled: the provider has not finished billing this day yet, so no comparison is made.
no_provider_data: the provider reported nothing for this day, so no comparison is possible."""


@dataclass(frozen=True, slots=True)
class GapRow:
    provider: str
    credential_name: str
    day: datetime
    provider_cost: Decimal | None
    gateway_cost: Decimal


@dataclass(frozen=True, slots=True)
class AttributedGap:
    row: GapRow
    gap: Decimal
    owner_type: OwnerType | None
    owner_id: str | None
    rule_id: str | None
    state: GapState


def _to_utc(value: datetime) -> datetime:
    """A naive datetime is treated as UTC; an aware one is converted to it, so a day read
    from naive SQL and a cutoff built from an aware clock still compare correctly."""
    return value.astimezone(timezone.utc) if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


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
    if _to_utc(row.day) >= _to_utc(settled_before):
        return AttributedGap(row=row, gap=Decimal(0), owner_type=None, owner_id=None, rule_id=None, state="not_settled")

    if row.provider_cost is None:
        return AttributedGap(
            row=row, gap=Decimal(0), owner_type=None, owner_id=None, rule_id=None, state="no_provider_data"
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
    """Decide who owns each row's gap, in the same order the rows arrived in.

    One AttributedGap per row: the GapState it landed in, the gap itself (never negative),
    and the owner a matching rule assigned it, if any.

    `settled_before` is the first day the provider has NOT finished billing, so a day equal
    to it is reported as not settled rather than compared. A naive datetime on either side
    is read as UTC.
    """
    return tuple(_attribute_one(row, rules, settled_before) for row in rows)
