"""Persistence for the rules that map a provider account to an owner.

Raw SQL rather than the generated Prisma model, for two reasons. The generated client only
knows a table after `prisma generate` has been re-run, which is a build step this table would
otherwise need on every machine, and the conflict behaviour here is load-bearing: writing a
rule for an account that already has one must change its owner and keep its `rule_id`, which
`ON CONFLICT ... DO UPDATE` states in one place the database enforces. Every other read of the
new billing tables in this codebase is raw SQL for the same reason.

Nothing is interpolated into these statements. The account name and owner id come from an admin
over HTTP, so they are bound as parameters and never formatted into the text.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Final, get_args
from uuid import uuid4

from token_iq.types.attribution import AttributionRule, MatchType, OwnerType

_MATCH_TYPES: Final[frozenset[str]] = frozenset(get_args(MatchType))
_OWNER_TYPES: Final[frozenset[str]] = frozenset(get_args(OwnerType))

_COLUMNS: Final = "rule_id, provider, match_type, match_value, owner_type, owner_id, note"

_SELECT_SQL: Final = f'SELECT {_COLUMNS} FROM "LiteLLM_AttributionRule" ORDER BY provider, match_value'

_UPSERT_SQL: Final = f"""
INSERT INTO "LiteLLM_AttributionRule"
       (rule_id, provider, match_type, match_value, owner_type, owner_id, note, updated_at)
VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
ON CONFLICT (provider, match_type, match_value)
DO UPDATE SET owner_type = EXCLUDED.owner_type,
              owner_id   = EXCLUDED.owner_id,
              note       = EXCLUDED.note,
              updated_at = NOW()
RETURNING {_COLUMNS}
"""
"""The conflict target is the account, so a second rule for one account reassigns it.

`rule_id` is deliberately absent from the DO UPDATE list: a reassigned account keeps the id it
already had, so anything holding a reference to that rule still resolves."""

_DELETE_SQL: Final = 'DELETE FROM "LiteLLM_AttributionRule" WHERE rule_id = $1 RETURNING rule_id'


def _read(row: object, key: str) -> object:
    return row.get(key) if isinstance(row, Mapping) else getattr(row, key, None)


def _rule_or_none(row: object) -> AttributionRule | None:
    """A row we cannot read is dropped rather than guessed at.

    A rule whose match or owner kind is not one we know would otherwise be handed to the
    matcher, which would silently assign a customer's spend to an owner nobody can name.
    """
    match_type: Final = _read(row, "match_type")
    owner_type: Final = _read(row, "owner_type")
    if match_type not in _MATCH_TYPES or owner_type not in _OWNER_TYPES:
        return None
    rule_id: Final = _read(row, "rule_id")
    provider: Final = _read(row, "provider")
    match_value: Final = _read(row, "match_value")
    owner_id: Final = _read(row, "owner_id")
    if not all(isinstance(value, str) and value for value in (rule_id, provider, match_value, owner_id)):
        return None
    note: Final = _read(row, "note")
    return AttributionRule(
        rule_id=str(rule_id),
        provider=str(provider),
        match_type=match_type,
        match_value=str(match_value),
        owner_type=owner_type,
        owner_id=str(owner_id),
        note=note if isinstance(note, str) else None,
    )


class AttributionRuleRepository:
    def __init__(self, prisma_client: object) -> None:
        self._prisma_client = prisma_client

    @property
    def _db(self) -> Any:  # any-ok: PrismaClient is an untyped runtime wrapper
        return self._prisma_client.db  # pyright: ignore[reportAttributeAccessIssue]  # object has no .db attr

    async def all(self) -> tuple[AttributionRule, ...]:
        rows: Final[Sequence[Mapping[str, object]]] = await self._db.query_raw(_SELECT_SQL)
        return tuple(rule for row in rows if (rule := _rule_or_none(row)) is not None)

    async def upsert(self, rule: AttributionRule) -> AttributionRule | None:
        """Write a rule, or reassign the account that already has one.

        `None` means the write landed but the stored row could not be read back in a shape
        this code understands, which the endpoint turns into an error rather than reporting a
        rule it cannot describe.
        """
        rows: Final[Sequence[Mapping[str, object]]] = await self._db.query_raw(
            _UPSERT_SQL,
            rule.rule_id or str(uuid4()),
            rule.provider,
            rule.match_type,
            rule.match_value,
            rule.owner_type,
            rule.owner_id,
            rule.note,
        )
        return _rule_or_none(rows[0]) if rows else None

    async def delete(self, rule_id: str) -> bool:
        """False when no rule had that id, so the endpoint can answer 404 rather than pretend."""
        rows: Final[Sequence[Mapping[str, object]]] = await self._db.query_raw(_DELETE_SQL, rule_id)
        return bool(rows)
