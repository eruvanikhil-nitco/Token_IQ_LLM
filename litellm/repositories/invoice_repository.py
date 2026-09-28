"""Persistence for provider bills an admin entered.

Raw parameterised SQL rather than the generated Prisma model, for the reason written at the top
of `attribution_rule_repository.py`: the generated client only knows a table after
`prisma generate`, which is blocked on some machines, and every other new billing table here is
read the same way. Nothing a caller supplies is interpolated; the only thing in the statement
text is this module's own column list.

Adjustments live in a JSON column rather than their own table. They are only ever read back with
their invoice and never queried across invoices, so a second table would buy a join and nothing
else.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Final, get_args
from uuid import uuid4

from litellm.types.proxy.invoice import AdjustmentKind, InvoiceAdjustment, ProviderInvoice

_ADJUSTMENT_KINDS: Final[frozenset[str]] = frozenset(get_args(AdjustmentKind))

_COLUMNS: Final = "invoice_id, provider, period_start, period_end, currency, total, adjustments, note"

_SELECT_SQL: Final = f'SELECT {_COLUMNS} FROM "LiteLLM_ProviderInvoice" ORDER BY period_start DESC, provider'

_FOR_PERIOD_SQL: Final = (
    f'SELECT {_COLUMNS} FROM "LiteLLM_ProviderInvoice" '
    "WHERE provider = $1 AND period_start = $2::timestamp AND period_end = $3::timestamp"
)

_UPSERT_SQL: Final = f"""
INSERT INTO "LiteLLM_ProviderInvoice"
       (invoice_id, provider, period_start, period_end, currency, total, adjustments, note, updated_at)
VALUES ($1, $2, $3::timestamp, $4::timestamp, $5, $6, $7::jsonb, $8, NOW())
ON CONFLICT (provider, period_start, period_end)
DO UPDATE SET currency    = EXCLUDED.currency,
              total       = EXCLUDED.total,
              adjustments = EXCLUDED.adjustments,
              note        = EXCLUDED.note,
              updated_at  = NOW()
RETURNING {_COLUMNS}
"""
"""The conflict target is the period, so re-entering a corrected bill replaces it.

`invoice_id` is absent from the DO UPDATE list on purpose: a corrected bill keeps the id it
already had, so anything referring to that invoice still resolves."""

_DELETE_SQL: Final = 'DELETE FROM "LiteLLM_ProviderInvoice" WHERE invoice_id = $1 RETURNING invoice_id'


def _read(row: object, key: str) -> object:
    return row.get(key) if isinstance(row, Mapping) else getattr(row, key, None)


def _decimal_or_none(value: object) -> Decimal | None:
    """A `float` is refused rather than converted: `total` is stored as text precisely so the
    digits survive, and a float here means they already did not."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def _datetime_or_none(value: object) -> datetime | None:
    """A raw query hands a Postgres timestamp back as an ISO string, not a datetime.

    Only a live run reveals this: a fake database returns whatever the test put in, so every
    unit test here passed against a reader that rejected every real row.
    """
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _adjustment_or_none(entry: object) -> InvoiceAdjustment | None:
    """An adjustment nobody can name is dropped.

    Keeping it would subtract money from a customer's unexplained remainder for a reason the
    screen cannot state, which is the one thing reconciliation must never do.
    """
    if not isinstance(entry, Mapping):
        return None
    kind: Final = entry.get("kind")
    if kind not in _ADJUSTMENT_KINDS:
        return None
    amount: Final = _decimal_or_none(entry.get("amount"))
    if amount is None:
        return None
    note: Final = entry.get("note")
    return InvoiceAdjustment(kind=kind, amount=amount, note=note if isinstance(note, str) else None)


def _adjustments_of(value: object) -> tuple[InvoiceAdjustment, ...]:
    raw: Final = json.loads(value) if isinstance(value, str) else value
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        return ()
    return tuple(found for entry in raw if (found := _adjustment_or_none(entry)) is not None)


def _invoice_or_none(row: object) -> ProviderInvoice | None:
    """A row we cannot read is dropped rather than guessed at. An invoice with an unreadable
    total would otherwise be compared against the ledger as if it said something."""
    invoice_id: Final = _read(row, "invoice_id")
    provider: Final = _read(row, "provider")
    currency: Final = _read(row, "currency")
    if not all(isinstance(v, str) and v for v in (invoice_id, provider, currency)):
        return None
    start: Final = _datetime_or_none(_read(row, "period_start"))
    end: Final = _datetime_or_none(_read(row, "period_end"))
    if start is None or end is None:
        return None
    total: Final = _decimal_or_none(_read(row, "total"))
    if total is None:
        return None
    note: Final = _read(row, "note")
    return ProviderInvoice(
        invoice_id=str(invoice_id),
        provider=str(provider),
        period_start=start,
        period_end=end,
        currency=str(currency),
        total=total,
        adjustments=_adjustments_of(_read(row, "adjustments")),
        note=note if isinstance(note, str) else None,
    )


class InvoiceRepository:
    def __init__(self, prisma_client: object) -> None:
        self._prisma_client = prisma_client

    @property
    def _db(self) -> Any:  # any-ok: PrismaClient is an untyped runtime wrapper
        return self._prisma_client.db  # pyright: ignore[reportAttributeAccessIssue]  # object has no .db attr

    async def all(self) -> tuple[ProviderInvoice, ...]:
        rows: Final[Sequence[Mapping[str, object]]] = await self._db.query_raw(_SELECT_SQL)
        return tuple(found for row in rows if (found := _invoice_or_none(row)) is not None)

    async def for_period(
        self, *, provider: str, period_start: datetime, period_end: datetime
    ) -> ProviderInvoice | None:
        """None means no bill has been entered for that period, which reconciliation reports as
        such rather than treating the whole ledger as unexplained."""
        rows: Final[Sequence[Mapping[str, object]]] = await self._db.query_raw(
            _FOR_PERIOD_SQL, provider, period_start.isoformat(), period_end.isoformat()
        )
        return _invoice_or_none(rows[0]) if rows else None

    async def upsert(self, invoice: ProviderInvoice) -> ProviderInvoice | None:
        """Store a bill, or correct the one already entered for that period."""
        adjustments: Final = json.dumps(
            [  # mutable-ok: json.dumps has no encoder for a tuple of MappingProxyType, proven on this branch
                {"kind": a.kind, "amount": format(a.amount, "f"), "note": a.note}  # mutable-ok: same json.dumps gap
                for a in invoice.adjustments
            ]
        )
        rows: Final[Sequence[Mapping[str, object]]] = await self._db.query_raw(
            _UPSERT_SQL,
            invoice.invoice_id or str(uuid4()),
            invoice.provider,
            invoice.period_start.isoformat(),
            invoice.period_end.isoformat(),
            invoice.currency,
            format(invoice.total, "f"),
            adjustments,
            invoice.note,
        )
        return _invoice_or_none(rows[0]) if rows else None

    async def delete(self, invoice_id: str) -> bool:
        """False when no bill had that id, so the endpoint can answer 404 rather than pretend."""
        rows: Final[Sequence[Mapping[str, object]]] = await self._db.query_raw(_DELETE_SQL, invoice_id)
        return bool(rows)
