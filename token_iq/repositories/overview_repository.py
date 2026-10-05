"""The figures the Overview page needs, each summed over one explicit period.

Its own reads rather than the existing repositories, because most of those take a window in
days counted back from now, and every tile on a landing page must cover the same period the
reader chose. Bending five day-based signatures would have been a larger change than five
focused queries.

Every money column is summed in SQL and cast to text. This table grows on every scheduler
tick, so pulling rows into Python to add them up would make drawing the landing page cost more
every month, and a float on the way out would lose digits before anything could make a
`Decimal` of it.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from types import MappingProxyType
from typing import Any, Final

_PROVIDER_BILLED_SQL: Final = """
SELECT COALESCE(SUM(f.billed_cost::numeric), 0)::text AS billed
  FROM "LiteLLM_ProviderUsageFact" f
 WHERE f.bucket_start >= $1::timestamp AND f.bucket_start <= $2::timestamp
"""

_TOOL_NEW_MONEY_SQL: Final = """
SELECT COALESCE(SUM(t.cost::numeric), 0)::text AS spent
  FROM "LiteLLM_ToolUsageFact" t
 WHERE t.usage_day >= $1::timestamp AND t.usage_day <= $2::timestamp
   AND t.basis = 'new_money'
"""
"""Only `new_money`. A Claude Code row billed to an API organisation is already inside the
provider total, so adding it here would count the same dollars twice."""

_SEATS_SQL: Final = """
SELECT COALESCE(SUM(s.amount::numeric), 0)::text AS spent
  FROM "LiteLLM_UserSeat" s
 WHERE s.period_start >= $1::timestamp AND s.period_end <= $2::timestamp
"""
"""A seat counts only when its whole period fits inside the window, the same rule the Users
screen already follows: a month's fee cannot be attributed to one day inside it."""

_GATEWAY_SQL: Final = """
SELECT COALESCE(SUM(s.spend), 0)::numeric::text AS spent
  FROM "LiteLLM_SpendLogs" s
 WHERE s."startTime" >= $1::timestamp AND s."startTime" <= $2::timestamp
"""

_BY_PROVIDER_SQL: Final = """
WITH theirs AS (
    SELECT f.provider                        AS provider,
           SUM(f.billed_cost::numeric)::text AS billed
      FROM "LiteLLM_ProviderUsageFact" f
     WHERE f.bucket_start >= $1::timestamp AND f.bucket_start <= $2::timestamp
     GROUP BY 1
), ours AS (
    SELECT s.custom_llm_provider        AS provider,
           SUM(s.spend)::numeric::text  AS recorded
      FROM "LiteLLM_SpendLogs" s
     WHERE s.custom_llm_provider <> ''
       AND s."startTime" >= $1::timestamp AND s."startTime" <= $2::timestamp
     GROUP BY 1
)
SELECT theirs.provider AS provider, theirs.billed AS billed, ours.recorded AS recorded
  FROM theirs LEFT JOIN ours ON theirs.provider = ours.provider
 ORDER BY theirs.billed::numeric DESC
"""

_FRESHNESS_SQL: Final = """
SELECT r.provider AS source, MAX(r.finished_at) AS last_sync
  FROM "LiteLLM_ProviderSyncRun" r
 WHERE r.outcome = 'fetched'
 GROUP BY 1
 ORDER BY 1
"""


@dataclass(frozen=True, slots=True)
class ProviderStanding:
    provider: str
    billed: Decimal
    recorded: Decimal | None
    """None when the gateway saw nothing for this provider, which is different from zero: a
    provider read only through its bill has no gateway figure to compare against at all."""


def _decimal_or_zero(value: object) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return Decimal(0)
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return Decimal(0)


def _decimal_or_none(value: object) -> Decimal | None:
    if value is None:
        return None
    return _decimal_or_zero(value)


def _read(row: object, key: str) -> object:
    return row.get(key) if isinstance(row, Mapping) else getattr(row, key, None)


class OverviewRepository:
    def __init__(self, prisma_client: object) -> None:
        self._prisma_client = prisma_client

    @property
    def _db(self) -> Any:  # any-ok: PrismaClient is an untyped runtime wrapper
        return self._prisma_client.db  # pyright: ignore[reportAttributeAccessIssue]  # object has no .db attr

    async def _one_amount(self, query: str, key: str, start: datetime, end: datetime) -> Decimal:
        rows: Final[Sequence[Mapping[str, object]]] = await self._db.query_raw(
            query, start.isoformat(), end.isoformat()
        )
        return _decimal_or_zero(_read(rows[0], key)) if rows else Decimal(0)

    async def provider_billed(self, start: datetime, end: datetime) -> Decimal:
        return await self._one_amount(_PROVIDER_BILLED_SQL, "billed", start, end)

    async def tool_new_money(self, start: datetime, end: datetime) -> Decimal:
        return await self._one_amount(_TOOL_NEW_MONEY_SQL, "spent", start, end)

    async def seats(self, start: datetime, end: datetime) -> Decimal:
        return await self._one_amount(_SEATS_SQL, "spent", start, end)

    async def gateway_recorded(self, start: datetime, end: datetime) -> Decimal:
        return await self._one_amount(_GATEWAY_SQL, "spent", start, end)

    async def by_provider(self, start: datetime, end: datetime) -> tuple[ProviderStanding, ...]:
        """What each provider billed, beside what the gateway recorded for it."""
        rows: Final[Sequence[Mapping[str, object]]] = await self._db.query_raw(
            _BY_PROVIDER_SQL, start.isoformat(), end.isoformat()
        )
        return tuple(
            ProviderStanding(
                provider=str(provider),
                billed=_decimal_or_zero(_read(row, "billed")),
                recorded=_decimal_or_none(_read(row, "recorded")),
            )
            for row in rows
            if isinstance(provider := _read(row, "provider"), str) and provider
        )

    async def freshness(self) -> Mapping[str, str]:
        """When each source last returned data, as an ISO string, for sources that ever have.

        A source absent from this map has never had a successful sync, which the screen says
        as "never" rather than leaving blank.
        """
        rows: Final[Sequence[Mapping[str, object]]] = await self._db.query_raw(_FRESHNESS_SQL)
        return MappingProxyType(
            {
                str(source): last.isoformat() if isinstance(last, datetime) else str(last)
                for row in rows
                if isinstance(source := _read(row, "source"), str) and (last := _read(row, "last_sync")) is not None
            }
        )
