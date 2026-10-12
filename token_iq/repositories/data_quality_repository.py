"""The data-quality facts that need the database.

The rules about what counts as a problem live in `token_iq/overview/data_quality.py` and are tested
without a database. This only fetches what that rule cannot work out for itself.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Final, TypeVar

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
    SELECT DISTINCT f.provider AS provider
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
     ORDER BY provider
"""
"""Providers that billed something in the period and have no invoice covering it.

Only providers that actually billed: one nobody uses has no invoice and needs none, and counting it
would put every unused provider on the issues list, which is the same trap `not_connected` is on the
connections side.

Names rather than a count, because the Overview tab's figure and the Uploads tab's rows are the
same question asked twice, and two statements built from two queries eventually disagree about one
provider.
"""


_ACCOUNTS_DOUBLE_COUNTED_SQL: Final = """
    SELECT COUNT(*)::int AS count
      FROM (
            SELECT f.provider,
                   f.bucket_start,
                   f.model,
                   f.meter,
                   f.billing_currency,
                   f.billed_cost::numeric AS amount
              FROM "LiteLLM_ProviderUsageFact" f
             WHERE f.bucket_start >= $1::timestamp
               AND f.bucket_start < $2::timestamp
               AND f.billed_cost::numeric <> 0
             GROUP BY 1, 2, 3, 4, 5, 6
            HAVING COUNT(DISTINCT f.credential_name) > 1
           ) AS doubled
"""
"""Figures that two or more connections on one provider both reported.

Grouped on the amount as a number rather than as the stored text, so "5.00" and "5.0" are the one
figure they are. Zero is excluded because two accounts reporting nothing against a model is the
commonest figure a provider publishes, and pairing those would put a risk on the list for every
unused model a customer has.

The rule and the reason it reports rather than drops are in `token_iq/truth/dedup.py`.
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


class _ProviderRow(BaseModel):
    """One row of a query that selects provider names, read the same two ways as `_CountRow`."""

    provider: str


_PROVIDER_ROWS: Final = TypeAdapter(tuple[_ProviderRow, ...])

_RowT: Final = TypeVar("_RowT", bound=BaseModel)


class DataQualityRepository:
    def __init__(self, prisma_client: object) -> None:
        self._prisma_client = prisma_client

    @property
    def _db(self) -> Any:  # any-ok: PrismaClient is an untyped runtime wrapper
        return self._prisma_client.db  # pyright: ignore[reportAttributeAccessIssue]  # object has no .db attr

    async def _rows(self, adapter: TypeAdapter[tuple[_RowT, ...]], sql: str, *args: str) -> tuple[_RowT, ...]:
        """The one place that touches the untyped client.

        Every query goes through it with the rows it expects, so an unreadable result raises here
        rather than each caller reading an untyped mapping and falling back to zero. On this tab a
        silent zero is the failure that looks most like success.
        """
        return adapter.validate_python(await self._db.query_raw(sql, *args), from_attributes=True)

    async def _count(self, sql: str, *args: str) -> int:
        """The first row's count, or zero when the query matched nothing."""
        rows: Final = await self._rows(_COUNT_ROWS, sql, *args)
        return rows[0].count if rows else 0

    async def keys_without_project(self) -> int:
        return await self._count(_KEYS_WITHOUT_PROJECT_SQL)

    async def providers_billing(self, start: datetime, end: datetime) -> int:
        return await self._count(_PROVIDERS_BILLING_SQL, start.isoformat(), end.isoformat())

    async def accounts_double_counted(self, start: datetime, end: datetime) -> int:
        """How many figures two or more connections on one provider both reported."""
        return await self._count(_ACCOUNTS_DOUBLE_COUNTED_SQL, start.isoformat(), end.isoformat())

    async def providers_missing_invoice_names(self, start: datetime, end: datetime) -> tuple[str, ...]:
        rows: Final = await self._rows(
            _PROVIDER_ROWS, _PROVIDERS_MISSING_INVOICE_SQL, start.isoformat(), end.isoformat()
        )
        return tuple(row.provider for row in rows)

    async def providers_missing_invoice(self, start: datetime, end: datetime) -> int:
        """How many, over the same query that says which. Counted here rather than in SQL so the
        figure on Overview and the rows on Uploads cannot come from two different statements."""
        return len(await self.providers_missing_invoice_names(start, end))
