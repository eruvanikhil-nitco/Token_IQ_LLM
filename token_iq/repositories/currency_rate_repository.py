"""Persistence for the rates a customer booked a period at.

Raw SQL for the reason written at the top of `provider_rate_repository.py`, and read the same way:
one Pydantic model validates each row, so a row this cannot understand is dropped rather than
becoming a rate that converts every figure it touches by the wrong amount.

The rate is text in and out, so the digits a finance team booked survive exactly. A month-by-month
booked rate is a new row rather than an edit, because the old row converted months that have
already been reported.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Final, Protocol
from uuid import uuid4

from pydantic import BaseModel, Field, TypeAdapter, ValidationError

from token_iq.pricing.currency import CurrencyRate

_COLUMNS: Final = "rate_id, source_currency, target_currency, rate, effective_from, effective_to, source"

_SELECT_SQL: Final = (
    f'SELECT {_COLUMNS} FROM "LiteLLM_CurrencyRate" '
    "ORDER BY source_currency, target_currency, effective_from DESC, rate_id"
)

_INSERT_SQL: Final = f"""
INSERT INTO "LiteLLM_CurrencyRate"
       (rate_id, source_currency, target_currency, rate, effective_from, effective_to, source, updated_at)
VALUES ($1, $2, $3, $4, $5::timestamp, $6::timestamp, $7, NOW())
RETURNING {_COLUMNS}
"""
"""An insert, never an upsert. Two rates for one pair and period are a conflict a person resolves,
not something a write should silently collapse."""

_DELETE_SQL: Final = 'DELETE FROM "LiteLLM_CurrencyRate" WHERE rate_id = $1 RETURNING rate_id'


class _RateRow(BaseModel):
    """One stored rate, validated rather than read field by field.

    `from_attributes` covers both shapes `query_raw` hands back. The rate is declared as a string,
    and Pydantic will not turn a float into one, so a driver that decoded the column as a float
    fails here: the column is text precisely so the digits survive.
    """

    rate_id: str = Field(min_length=1)
    source_currency: str = Field(min_length=1)
    target_currency: str = Field(min_length=1)
    rate: str
    effective_from: datetime
    effective_to: datetime | None = None
    source: str = Field(min_length=1)


_RATE_ROW: Final = TypeAdapter(_RateRow)


class _Queries(Protocol):
    async def query_raw(self, sql: str, *args: object) -> Sequence[Mapping[str, object]]: ...


def _rate_or_none(row: object) -> CurrencyRate | None:
    """A row this cannot read is dropped rather than guessed at.

    A rate read wrongly converts a whole month and the figure still looks like a figure, so a
    half-understood row is worse than a missing one.
    """
    try:
        parsed: Final = _RATE_ROW.validate_python(row, from_attributes=True)
    except ValidationError:
        return None
    try:
        rate: Final = Decimal(parsed.rate)
    except InvalidOperation:
        return None
    if rate <= 0:
        return None
    return CurrencyRate(
        rate_id=parsed.rate_id,
        source_currency=parsed.source_currency,
        target_currency=parsed.target_currency,
        rate=rate,
        effective_from=parsed.effective_from.date(),
        effective_to=None if parsed.effective_to is None else parsed.effective_to.date(),
        source=parsed.source,
    )


class CurrencyRateRepository:
    def __init__(self, prisma_client: object) -> None:
        self._prisma_client = prisma_client

    @property
    def _db(self) -> _Queries:
        """The one hop to the untyped Prisma wrapper, suppressed here and nowhere else."""
        return self._prisma_client.db  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType, reportUnknownVariableType]  # untyped wrapper

    async def all(self) -> tuple[CurrencyRate, ...]:
        """Every rate recorded, newest period first within a pair."""
        rows: Final = await self._db.query_raw(_SELECT_SQL)
        return tuple(found for row in rows if (found := _rate_or_none(row)) is not None)

    async def add(self, rate: CurrencyRate) -> CurrencyRate | None:
        """Record a rate. None when the row could not be read back in a shape this understands."""
        rows: Final = await self._db.query_raw(
            _INSERT_SQL,
            rate.rate_id or str(uuid4()),
            rate.source_currency,
            rate.target_currency,
            format(rate.rate, "f"),
            rate.effective_from.isoformat(),
            None if rate.effective_to is None else rate.effective_to.isoformat(),
            rate.source,
        )
        return _rate_or_none(rows[0]) if rows else None

    async def delete(self, rate_id: str) -> bool:
        """False when no rate had that id, so the endpoint can answer 404 rather than pretend."""
        rows: Final = await self._db.query_raw(_DELETE_SQL, rate_id)
        return bool(rows)
