"""The two data-quality counts that need the database.

The rules about what counts as a problem live in `token_iq/overview/data_quality.py` and are tested
without a database. This only fetches the two numbers that rule cannot work out for itself.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Final

from pydantic import BaseModel, TypeAdapter

_KEYS_WITHOUT_PROJECT_SQL: Final = """
    SELECT COUNT(*)::int AS count
      FROM "LiteLLM_VerificationToken"
     WHERE project_id IS NULL
"""

_PROVIDERS_BILLING_SQL: Final = """
    SELECT COUNT(DISTINCT f.provider)::int AS count
      FROM "LiteLLM_ProviderUsageFact" f
     WHERE f.bucket_start >= $1::timestamp
       AND f.bucket_start < $2::timestamp
"""
"""Providers that billed anything in the period: the denominator of invoice coverage.

The same population the missing-invoice query starts from, so the two figures are a fraction of
each other rather than two numbers that happen to sit beside one another.
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


class _CountRow(BaseModel):
    """One row of a `SELECT COUNT(...) AS count` result.

    `query_raw` hands back mappings on some paths and attribute-bearing rows on others, so the
    validation accepts both rather than assuming one and reading nothing from the other. A row that
    is neither raises: a count query whose result cannot be read is not a count of zero, and on this
    tab a silent zero is the failure that looks most like success.
    """

    count: int


_COUNT_ROWS: Final = TypeAdapter(tuple[_CountRow, ...])


class DataQualityRepository:
    def __init__(self, prisma_client: object) -> None:
        self._prisma_client = prisma_client

    @property
    def _db(self) -> Any:  # any-ok: PrismaClient is an untyped runtime wrapper
        return self._prisma_client.db  # pyright: ignore[reportAttributeAccessIssue]  # object has no .db attr

    async def _count(self, sql: str, *args: str) -> int:
        """The first row's count, or zero when the query matched nothing.

        The one place that touches the untyped client. Every query goes through it, so the result is
        validated into a typed row once rather than each caller reading an untyped mapping and
        falling back to zero when it cannot.
        """
        rows: Final = _COUNT_ROWS.validate_python(await self._db.query_raw(sql, *args), from_attributes=True)
        return rows[0].count if rows else 0

    async def keys_without_project(self) -> int:
        return await self._count(_KEYS_WITHOUT_PROJECT_SQL)

    async def providers_billing(self, start: datetime, end: datetime) -> int:
        return await self._count(_PROVIDERS_BILLING_SQL, start.isoformat(), end.isoformat())

    async def providers_missing_invoice(self, start: datetime, end: datetime) -> int:
        return await self._count(_PROVIDERS_MISSING_INVOICE_SQL, start.isoformat(), end.isoformat())
