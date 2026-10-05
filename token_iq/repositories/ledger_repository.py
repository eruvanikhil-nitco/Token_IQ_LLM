"""Every cost line the product holds, with its source, evidence level and currency.

The ledger is the provider facts and nothing else. Gateway spend is deliberately absent: the
gateway's figure and the provider's figure describe the same money, so a ledger that listed both
would double count, which is the one thing the counting rule forbids. Who owns a line comes from
the attribution rules at the endpoint, not from here.

`total` answers a mapping keyed by currency rather than one number. A provider billing in two
currencies has two totals, and adding them would produce a figure in no currency at all.

Raw parameterised SQL, like every other new billing table here. One statement covers an optional
provider and an optional cursor through null-guarded parameters rather than four assembled
variants, so there is only ever one piece of SQL text to audit.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from types import MappingProxyType
from typing import Any, Final, get_args

from litellm.types.proxy.provider_billing import EvidenceLevel

_EVIDENCE_LEVELS: Final[frozenset[str]] = frozenset(get_args(EvidenceLevel))

_LINES_SQL: Final = """
SELECT f.bucket_start                AS day,
       f.fact_key                    AS fact_key,
       f.provider                    AS provider,
       f.credential_name             AS credential_name,
       f.model                       AS model,
       f.evidence                    AS evidence,
       f.billing_currency            AS currency,
       f.billed_cost::numeric::text  AS amount
  FROM "LiteLLM_ProviderUsageFact" f
 WHERE ($1::text IS NULL OR f.provider = $1)
   AND f.bucket_start >= $2::timestamp
   AND f.bucket_start <= $3::timestamp
   AND ($4::text IS NULL
        OR f.bucket_start < $4::timestamp
        OR (f.bucket_start = $4::timestamp AND f.fact_key < $5::text))
 ORDER BY f.bucket_start DESC, f.fact_key DESC
 LIMIT $6::int
"""
"""Keyset paged on (bucket_start, fact_key).

bucket_start alone is not unique: every fact one connector run writes shares that run's
watermark. A boundary inside such a group that then filtered on bucket_start alone would hide
every row at that value, including ones the earlier page never returned.

The cursor is compared as two explicit conditions rather than as a row constructor, and its
null check reads the parameter as text. A row comparison against `($4::timestamp, $5::text)`
binds in a format Postgres refuses, which only a real resume reveals: the first page has a null
cursor and succeeds either way."""

_TOTAL_SQL: Final = """
SELECT f.billing_currency               AS currency,
       SUM(f.billed_cost::numeric)::text AS total
  FROM "LiteLLM_ProviderUsageFact" f
 WHERE f.provider = $1
   AND f.bucket_start >= $2::timestamp
   AND f.bucket_start <= $3::timestamp
 GROUP BY 1
"""


@dataclass(frozen=True, slots=True)
class LedgerLine:
    day: datetime
    provider: str
    credential_name: str
    model: str | None
    evidence: EvidenceLevel
    currency: str
    amount: Decimal


@dataclass(frozen=True, slots=True)
class LedgerPage:
    lines: tuple[LedgerLine, ...]
    next_cursor: tuple[datetime, str] | None


def _read(row: object, key: str) -> object:
    return row.get(key) if isinstance(row, Mapping) else getattr(row, key, None)


def _decimal_or_none(value: object) -> Decimal | None:
    """A `float` is refused: every money column here leaves Postgres as text, so a float means
    a cast was lost and the digits are already gone."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def _datetime_or_none(value: object) -> datetime | None:
    """A raw query hands a Postgres timestamp back as an ISO string, not a datetime."""
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _line_or_none(row: object) -> LedgerLine | None:
    """A row we cannot read is dropped rather than guessed at.

    Evidence is checked first because it is the claim the line makes about how much authority
    its figure has. A line whose evidence nobody can name would be shown beside honest ones
    with no way to say how it was arrived at.
    """
    evidence: Final = _read(row, "evidence")
    if evidence not in _EVIDENCE_LEVELS:
        return None
    provider: Final = _read(row, "provider")
    credential_name: Final = _read(row, "credential_name")
    currency: Final = _read(row, "currency")
    if not all(isinstance(v, str) and v for v in (provider, credential_name, currency)):
        return None
    day: Final = _datetime_or_none(_read(row, "day"))
    if day is None:
        return None
    amount: Final = _decimal_or_none(_read(row, "amount"))
    if amount is None:
        return None
    model: Final = _read(row, "model")
    return LedgerLine(
        day=day,
        provider=str(provider),
        credential_name=str(credential_name),
        model=model if isinstance(model, str) else None,
        evidence=evidence,
        currency=str(currency),
        amount=amount,
    )


def _cursor_from_row(row: object) -> tuple[datetime, str] | None:
    """Read off the database's last row, not off a parsed line: a row that failed parsing still
    counts toward a full page, so the cursor has to reflect where the database stopped."""
    day: Final = _datetime_or_none(_read(row, "day"))
    fact_key: Final = _read(row, "fact_key")
    return (day, fact_key) if day is not None and isinstance(fact_key, str) else None


class LedgerRepository:
    def __init__(self, prisma_client: object) -> None:
        self._prisma_client = prisma_client

    @property
    def _db(self) -> Any:  # any-ok: PrismaClient is an untyped runtime wrapper
        return self._prisma_client.db  # pyright: ignore[reportAttributeAccessIssue]  # object has no .db attr

    async def lines(
        self,
        *,
        provider: str | None,
        period_start: datetime,
        period_end: datetime,
        limit: int,
        cursor: tuple[datetime, str] | None,
    ) -> LedgerPage:
        """One page of cost lines, newest first."""
        rows: Final[Sequence[Mapping[str, object]]] = await self._db.query_raw(
            _LINES_SQL,
            provider,
            period_start.isoformat(),
            period_end.isoformat(),
            cursor[0].isoformat() if cursor is not None else None,
            cursor[1] if cursor is not None else None,
            limit,
        )
        lines: Final = tuple(found for row in rows if (found := _line_or_none(row)) is not None)
        next_cursor: Final = _cursor_from_row(rows[-1]) if len(rows) == limit and rows else None
        return LedgerPage(lines=lines, next_cursor=next_cursor)

    async def total(self, *, provider: str, period_start: datetime, period_end: datetime) -> Mapping[str, Decimal]:
        """What the ledger says the period cost, one figure per currency."""
        rows: Final[Sequence[Mapping[str, object]]] = await self._db.query_raw(
            _TOTAL_SQL, provider, period_start.isoformat(), period_end.isoformat()
        )
        return MappingProxyType(
            {
                str(currency): amount
                for row in rows
                if isinstance(currency := _read(row, "currency"), str)
                and (amount := _decimal_or_none(_read(row, "total"))) is not None
            }
        )
