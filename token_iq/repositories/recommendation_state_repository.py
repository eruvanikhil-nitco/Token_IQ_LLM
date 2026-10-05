"""An admin's decision about one recommendation.

Only the decision is stored, never the card. Every card is recomputed from current data, so a
problem that goes away and comes back produces a fresh card rather than staying hidden behind a
decision someone made last quarter.

Raw parameterised SQL, like every other new table here, and for the same reason: the generated
client only knows a table after `prisma generate`, which is blocked on some machines.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import Any, Final, Literal, TypeAlias

from pydantic import TypeAdapter, ValidationError

DecisionState: TypeAlias = Literal["done", "dismissed"]
"""done: the thing was acted on. dismissed: it was read and judged not worth acting on."""

_DECISION: Final[TypeAdapter[DecisionState]] = TypeAdapter(DecisionState)

_SELECT_SQL: Final = 'SELECT rule_id, state FROM "LiteLLM_RecommendationState"'

_UPSERT_SQL: Final = """
INSERT INTO "LiteLLM_RecommendationState" (rule_id, state, decided_by, note, decided_at)
VALUES ($1, $2, $3, $4, NOW())
ON CONFLICT (rule_id)
DO UPDATE SET state = EXCLUDED.state, decided_by = EXCLUDED.decided_by,
              note = EXCLUDED.note, decided_at = NOW()
RETURNING rule_id
"""

_DELETE_SQL: Final = 'DELETE FROM "LiteLLM_RecommendationState" WHERE rule_id = $1 RETURNING rule_id'


def _read(row: object, key: str) -> object:
    return row.get(key) if isinstance(row, Mapping) else getattr(row, key, None)


def _decision_or_none(value: object) -> DecisionState | None:
    try:
        return _DECISION.validate_python(value)
    except ValidationError:
        return None


class RecommendationStateRepository:
    def __init__(self, prisma_client: object) -> None:
        self._prisma_client = prisma_client

    @property
    def _db(self) -> Any:  # any-ok: PrismaClient is an untyped runtime wrapper
        return self._prisma_client.db  # pyright: ignore[reportAttributeAccessIssue]  # object has no .db attr

    async def all(self) -> Mapping[str, DecisionState]:
        """Every decision, keyed by rule.

        A row whose state is not one we know is left out rather than guessed at: a decision
        nobody can name would otherwise hide a card for a reason the screen cannot state.
        """
        rows: Final[Sequence[Mapping[str, object]]] = await self._db.query_raw(_SELECT_SQL)
        return MappingProxyType(
            {
                rule_id: state
                for row in rows
                if isinstance(rule_id := _read(row, "rule_id"), str)
                and (state := _decision_or_none(_read(row, "state"))) is not None
            }
        )

    async def decide(self, *, rule_id: str, state: DecisionState, decided_by: str | None, note: str | None) -> bool:
        """Record a decision, or change one already made."""
        rows: Final[Sequence[Mapping[str, object]]] = await self._db.query_raw(
            _UPSERT_SQL, rule_id, state, decided_by, note
        )
        return bool(rows)

    async def clear(self, rule_id: str) -> bool:
        """Bring a card back. False when there was no decision to undo."""
        rows: Final[Sequence[Mapping[str, object]]] = await self._db.query_raw(_DELETE_SQL, rule_id)
        return bool(rows)
