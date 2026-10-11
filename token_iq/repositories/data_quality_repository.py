"""The two data-quality counts that need the database.

The rules about what counts as a problem live in `token_iq/overview/data_quality.py` and are tested
without a database. This only fetches the two numbers that rule cannot work out for itself.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any, Final

_KEYS_WITHOUT_PROJECT_SQL: Final = """
    SELECT COUNT(*)::int AS count
      FROM "LiteLLM_VerificationToken"
     WHERE project_id IS NULL
"""

_PROVIDERS_MISSING_INVOICE_SQL: Final = """
    SELECT COUNT(*)::int AS count
      FROM (
            SELECT DISTINCT f.provider
              FROM "LiteLLM_ProviderUsageFact" f
             WHERE f.bucket_start >= $1::timestamp
               AND f.bucket_start < $2::timestamp
               AND NOT EXISTS (
                     SELECT 1
                       FROM "LiteLLM_ProviderInvoice" i
                      WHERE i.provider = f.provider
                        AND i.period_start <= f.bucket_start
                        AND i.period_end > f.bucket_start
                   )
           ) AS uninvoiced
"""
"""Providers that billed something in the period and have no invoice covering it.

Only providers that actually billed: one nobody uses has no invoice and needs none, and counting it
would put every unused provider on the issues list, which is the same trap `not_connected` is on the
connections side.
"""


def _read(row: object, key: str) -> object:
    return row.get(key) if isinstance(row, Mapping) else getattr(row, key, None)


def _count(rows: Sequence[object]) -> int:
    """The first row's count, or zero when the query matched nothing.

    `query_raw` hands back mappings in some paths and attribute-bearing rows in others, so this
    reads both rather than assuming one and returning a silent zero for the other.
    """
    if not rows:
        return 0
    value: Final = _read(rows[0], "count")
    return int(value) if isinstance(value, (int, float)) else 0


class DataQualityRepository:
    def __init__(self, prisma_client: object) -> None:
        self._prisma_client = prisma_client

    @property
    def _db(self) -> Any:  # any-ok: PrismaClient is an untyped runtime wrapper
        return self._prisma_client.db  # pyright: ignore[reportAttributeAccessIssue]  # object has no .db attr

    async def keys_without_project(self) -> int:
        rows: Final[Sequence[object]] = await self._db.query_raw(_KEYS_WITHOUT_PROJECT_SQL)
        return _count(rows)

    async def providers_missing_invoice(self, start: datetime, end: datetime) -> int:
        rows: Final[Sequence[object]] = await self._db.query_raw(
            _PROVIDERS_MISSING_INVOICE_SQL, start.isoformat(), end.isoformat()
        )
        return _count(rows)
