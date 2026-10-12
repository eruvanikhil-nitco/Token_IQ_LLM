"""Persistence for what a customer actually pays.

Raw SQL for the reason written at the top of `attribution_rule_repository.py`: the generated Prisma
client only knows a table after `prisma generate`, which is blocked on some machines, and every
other new billing table here is read the same way. Nothing a caller supplies is interpolated.

Every amount is text, in and out, so the digits a person read off a contract survive exactly. A
rate is never edited: a renegotiation is a new row with its own period, because the old row priced
months that have already been reported and reported figures must not move under a reader.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Final, Protocol
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from token_iq.pricing.rates import Discount, RateRule, UnitPrice

DISCOUNT: Final = "discount"
UNIT_PRICE: Final = "unit_price"

_COLUMNS: Final = (
    "rate_id, provider, model, field, basis, percent_off, per_million, effective_from, effective_to, source"
)

_SELECT_SQL: Final = f'SELECT {_COLUMNS} FROM "LiteLLM_ProviderRate" ORDER BY provider, effective_from DESC, rate_id'

_INSERT_SQL: Final = f"""
INSERT INTO "LiteLLM_ProviderRate"
       (rate_id, provider, model, field, basis, percent_off, per_million,
        effective_from, effective_to, source, updated_at)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8::timestamp, $9::timestamp, $10, NOW())
RETURNING {_COLUMNS}
"""
"""An insert, never an upsert. Two rates for one model and period are a conflict a person resolves,
not something a write should silently collapse: see `token_iq/pricing/rates.py`."""

_DELETE_SQL: Final = 'DELETE FROM "LiteLLM_ProviderRate" WHERE rate_id = $1 RETURNING rate_id'


class _RateRow(BaseModel):
    """One stored rate, validated rather than read field by field.

    `from_attributes` is what makes this work for both shapes `query_raw` hands back: a mapping on
    some paths and an attribute-bearing row on others. A row that does not fit raises, and the
    caller drops that one row rather than the batch, because a rate read wrongly prices every
    figure it touches and the figure still looks like a figure.

    Amounts are declared as strings on purpose. Pydantic will not turn a float into one, so a
    driver that decoded the column as a float fails here, which is the point: the column is text
    precisely so the digits survive.
    """

    model_config = ConfigDict(protected_namespaces=())

    rate_id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model: str | None = None
    field: str | None = None
    basis: str
    percent_off: str | None = None
    per_million: str | None = None
    effective_from: datetime
    effective_to: datetime | None = None
    source: str = Field(min_length=1)


_RATE_ROW: Final = TypeAdapter(_RateRow)


def _decimal_or_none(value: str | None) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


def _basis_or_none(row: _RateRow) -> Discount | UnitPrice | None:
    if row.basis == DISCOUNT:
        percentage: Final = _decimal_or_none(row.percent_off)
        return None if percentage is None else Discount(percent_off=percentage)
    if row.basis == UNIT_PRICE:
        price: Final = _decimal_or_none(row.per_million)
        return None if price is None else UnitPrice(per_million=price)
    return None


def _rate_or_none(row: object) -> RateRule | None:
    """A row this cannot read is dropped rather than guessed at."""
    try:
        parsed: Final = _RATE_ROW.validate_python(row, from_attributes=True)
    except ValidationError:
        return None
    basis: Final = _basis_or_none(parsed)
    if basis is None:
        return None
    return RateRule(
        rate_id=parsed.rate_id,
        provider=parsed.provider,
        model=parsed.model,
        field=parsed.field,
        basis=basis,
        effective_from=parsed.effective_from.date(),
        effective_to=None if parsed.effective_to is None else parsed.effective_to.date(),
        source=parsed.source,
    )


def _stored(rule: RateRule) -> tuple[str, str | None, str | None]:
    """The basis as three columns: which kind, and whichever amount that kind carries."""
    match rule.basis:
        case Discount(percent_off=percent_off):
            return (DISCOUNT, format(percent_off, "f"), None)
        case UnitPrice(per_million=per_million):
            return (UNIT_PRICE, None, format(per_million, "f"))


class _Queries(Protocol):
    """The one method this needs of the Prisma client, which is otherwise untyped.

    A protocol rather than `Any`: what comes back is still validated row by row, and the hop to the
    untyped wrapper is one line with its own suppression instead of a type that spreads.
    """

    async def query_raw(self, sql: str, *args: object) -> Sequence[Mapping[str, object]]: ...


class ProviderRateRepository:
    def __init__(self, prisma_client: object) -> None:
        self._prisma_client = prisma_client

    @property
    def _db(self) -> _Queries:
        """The one hop to the untyped Prisma wrapper, suppressed here and nowhere else.

        What comes back is validated row by row by `_rate_or_none`, so the type system losing sight
        of the client costs nothing beyond this line.
        """
        return self._prisma_client.db  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType, reportUnknownVariableType]  # untyped wrapper

    async def all(self) -> tuple[RateRule, ...]:
        """Every rate recorded, newest period first within a provider."""
        rows: Final = await self._db.query_raw(_SELECT_SQL)
        return tuple(found for row in rows if (found := _rate_or_none(row)) is not None)

    async def add(self, rule: RateRule) -> RateRule | None:
        """Record a rate. None when the row could not be read back in a shape this understands."""
        basis, percent_off, per_million = _stored(rule)
        rows: Final = await self._db.query_raw(
            _INSERT_SQL,
            rule.rate_id or str(uuid4()),
            rule.provider,
            rule.model,
            rule.field,
            basis,
            percent_off,
            per_million,
            rule.effective_from.isoformat(),
            None if rule.effective_to is None else rule.effective_to.isoformat(),
            rule.source,
        )
        return _rate_or_none(rows[0]) if rows else None

    async def delete(self, rate_id: str) -> bool:
        """False when no rate had that id, so the endpoint can answer 404 rather than pretend."""
        rows: Final = await self._db.query_raw(_DELETE_SQL, rate_id)
        return bool(rows)
