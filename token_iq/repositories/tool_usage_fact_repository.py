"""Persistence for what a person spent inside a user tool.

Raw parameterised SQL, like every other new table here, and for the same reason: the generated
client only knows a table after `prisma generate`, which is blocked on some machines.

The key is derived here rather than in a connector. It is a storage concern: what makes two
rows the same row is a question about the table, and a connector that had to know the answer
could get it wrong in a way that silently doubles a customer's figures on the next run.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from types import MappingProxyType
from typing import Any, Final

from litellm.types.proxy.tool_usage import ToolUsageFact

_UPSERT_SQL: Final = """
INSERT INTO "LiteLLM_ToolUsageFact"
    (id, fact_key, tool, credential_name, person, usage_day, cost, currency, basis,
     model, input_tokens, output_tokens, sessions, fetched_at)
VALUES (gen_random_uuid()::text, $1, $2, $3, $4, $5::timestamp, $6, $7, $8, $9, $10, $11, $12, NOW())
ON CONFLICT (fact_key)
DO UPDATE SET cost = EXCLUDED.cost,
              currency = EXCLUDED.currency,
              basis = EXCLUDED.basis,
              input_tokens = EXCLUDED.input_tokens,
              output_tokens = EXCLUDED.output_tokens,
              sessions = EXCLUDED.sessions,
              fetched_at = NOW()
RETURNING fact_key
"""

_COUNTS_SQL: Final = """
SELECT f.credential_name AS credential_name, COUNT(*)::int AS stored
  FROM "LiteLLM_ToolUsageFact" f
 WHERE f.tool = $1
 GROUP BY 1
"""

_TOTALS_SQL: Final = """
SELECT f.person                          AS person,
       SUM(f.cost::numeric)::text        AS spent,
       MIN(f.currency)                   AS currency
  FROM "LiteLLM_ToolUsageFact" f
 WHERE f.tool = $1
   AND f.usage_day >= $2::timestamp
   AND f.usage_day <= $3::timestamp
   AND f.basis = 'new_money'
 GROUP BY 1
 ORDER BY SUM(f.cost::numeric) DESC
"""
"""Only `new_money` is summed. A row whose cost is already on a provider bill says who spent
it and must never reach a total that already counts the bill."""


def fact_key_for(fact: ToolUsageFact) -> str:
    """What makes two rows the same row: one tool, one person, one day, one model."""
    return f"{fact.tool}|{fact.person}|{fact.day.date().isoformat()}|{fact.model or '-'}"


def _read(row: object, key: str) -> object:
    return row.get(key) if isinstance(row, Mapping) else getattr(row, key, None)


class ToolUsageFactRepository:
    def __init__(self, prisma_client: object) -> None:
        self._prisma_client = prisma_client

    @property
    def _db(self) -> Any:  # any-ok: PrismaClient is an untyped runtime wrapper
        return self._prisma_client.db  # pyright: ignore[reportAttributeAccessIssue]  # object has no .db attr

    async def upsert_many(self, facts: Sequence[ToolUsageFact], *, credential_name: str) -> int:
        """Write facts, overwriting any already stored for the same tool, person, day and model.

        Overwriting rather than adding is the whole point: a window is refetched on every tick,
        so inserting would multiply a customer's tool spend by the number of times we looked.
        """
        written: Final[list[str]] = []  # mutable-ok: counts what the database accepted
        for fact in facts:
            rows: Sequence[Mapping[str, object]] = await self._db.query_raw(
                _UPSERT_SQL,
                fact_key_for(fact),
                fact.tool,
                credential_name,
                fact.person,
                fact.day.isoformat(),
                format(fact.cost, "f"),
                fact.currency,
                fact.basis,
                fact.model,
                fact.input_tokens,
                fact.output_tokens,
                fact.sessions,
            )
            written.extend(str(key) for row in rows if (key := _read(row, "fact_key")) is not None)
        return len(written)

    async def counts_by_credential(self, tool: str) -> Mapping[str, int]:
        """How many rows each account has produced, for deciding whether it has ever worked."""
        rows: Final[Sequence[Mapping[str, object]]] = await self._db.query_raw(_COUNTS_SQL, tool)
        return MappingProxyType(
            {
                name: stored
                for row in rows
                if isinstance(name := _read(row, "credential_name"), str)
                and isinstance(stored := _read(row, "stored"), int)
            }
        )

    async def spend_per_person(
        self, *, tool: str, period_start: datetime, period_end: datetime
    ) -> Mapping[str, str]:
        """What each person spent in this tool over the period, as exact digits.

        Summed in SQL and cast to text: this table grows on every tick, and a float would lose
        digits on the way out of the database, before anything could make a `Decimal` of it.
        """
        rows: Final[Sequence[Mapping[str, object]]] = await self._db.query_raw(
            _TOTALS_SQL, tool, period_start.isoformat(), period_end.isoformat()
        )
        return MappingProxyType(
            {
                person: spent
                for row in rows
                if isinstance(person := _read(row, "person"), str)
                and isinstance(spent := _read(row, "spent"), str)
            }
        )
