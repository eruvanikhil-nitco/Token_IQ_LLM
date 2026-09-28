"""Persistence for attribution rules."""

from __future__ import annotations

from typing import Any, Final, get_args

from litellm.types.proxy.attribution import AttributionRule, MatchType, OwnerType

_MATCH_TYPES: Final[frozenset[str]] = frozenset(get_args(MatchType))
_OWNER_TYPES: Final[frozenset[str]] = frozenset(get_args(OwnerType))


def _rule_or_none(row: object) -> AttributionRule | None:
    """A row we cannot read is dropped rather than guessed at.

    A rule whose match_type or owner_type nobody can interpret must not silently assign
    someone's spend to the wrong owner.
    """
    match_type: Final = getattr(row, "match_type", None)
    if match_type not in _MATCH_TYPES:
        return None
    owner_type: Final = getattr(row, "owner_type", None)
    if owner_type not in _OWNER_TYPES:
        return None
    rule_id: Final = getattr(row, "rule_id", None)
    provider: Final = getattr(row, "provider", None)
    match_value: Final = getattr(row, "match_value", None)
    owner_id: Final = getattr(row, "owner_id", None)
    if not (
        isinstance(rule_id, str)
        and isinstance(provider, str)
        and isinstance(match_value, str)
        and isinstance(owner_id, str)
    ):
        return None
    note: Final = getattr(row, "note", None)
    return AttributionRule(
        rule_id=rule_id,
        provider=provider,
        match_type=match_type,
        match_value=match_value,
        owner_type=owner_type,
        owner_id=owner_id,
        note=note if isinstance(note, str) else None,
    )


def _row(rule: AttributionRule) -> dict[str, object]:
    return {
        "provider": rule.provider,
        "match_type": rule.match_type,
        "match_value": rule.match_value,
        "owner_type": rule.owner_type,
        "owner_id": rule.owner_id,
        "note": rule.note,
    }


class AttributionRuleRepository:
    def __init__(self, prisma_client: object) -> None:
        self._prisma_client = prisma_client

    @property
    def _table(self) -> Any:  # any-ok: PrismaClient is an untyped runtime wrapper
        db: Final = self._prisma_client.db  # pyright: ignore[reportAttributeAccessIssue]  # object has no .db attr
        return db.litellm_attributionrule

    async def all(self) -> tuple[AttributionRule, ...]:
        rows: Final = await self._table.find_many()
        return tuple(rule for row in rows if (rule := _rule_or_none(row)) is not None)

    async def upsert(self, rule: AttributionRule) -> AttributionRule | None:
        """Keyed on the account, not `rule_id`: writing a rule for an account that already
        has one updates its owner in place instead of colliding with the unique index on
        (provider, match_type, match_value). `rule_id` is set only on the create branch, so
        a reassigned account keeps the rule_id it already had.

        An empty `rule_id` is left out of the create entirely so the database assigns one.
        Writing it through would put an empty string in the primary key, and the second rule
        created that way would collide with the first.
        """
        row: Final[dict[str, object]] = _row(rule)
        created: Final[dict[str, object]] = {"rule_id": rule.rule_id, **row} if rule.rule_id else row
        stored: Final = await self._table.upsert(
            where={
                "provider_match_type_match_value": {
                    "provider": rule.provider,
                    "match_type": rule.match_type,
                    "match_value": rule.match_value,
                }
            },
            data={"create": created, "update": row},
        )
        return _rule_or_none(stored)

    async def delete(self, rule_id: str) -> bool:
        from prisma.errors import RecordNotFoundError

        try:
            await self._table.delete(where={"rule_id": rule_id})
        except RecordNotFoundError:
            return False
        return True
