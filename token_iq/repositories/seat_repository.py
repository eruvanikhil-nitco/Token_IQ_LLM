"""Persistence for the flat per-person subscriptions an admin entered.

Raw parameterised SQL rather than the generated Prisma model, for the reason written at the top
of `attribution_rule_repository.py`: the generated client only knows a table after
`prisma generate`, which is blocked on some machines. Nothing a caller supplies is interpolated;
the only thing in the statement text is this module's own column list.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Final, get_args
from uuid import uuid4

from token_iq.types.seat import Seat, SeatCadence

_CADENCES: Final[frozenset[str]] = frozenset(get_args(SeatCadence))

_COLUMNS: Final = "seat_id, tool, user_id, cadence, currency, amount, period_start, period_end, note"

_SELECT_SQL: Final = f'SELECT {_COLUMNS} FROM "LiteLLM_UserSeat" ORDER BY period_start DESC, user_id, tool'

_FOR_PERIOD_SQL: Final = (
    f'SELECT {_COLUMNS} FROM "LiteLLM_UserSeat" '
    "WHERE period_start >= $1::timestamp AND period_end <= $2::timestamp "
    "ORDER BY user_id, tool"
)

_UPSERT_SQL: Final = f"""
INSERT INTO "LiteLLM_UserSeat"
       (seat_id, tool, user_id, cadence, currency, amount, period_start, period_end, note, updated_at)
VALUES ($1, $2, $3, $4, $5, $6, $7::timestamp, $8::timestamp, $9, NOW())
ON CONFLICT (tool, user_id, period_start, period_end)
DO UPDATE SET cadence    = EXCLUDED.cadence,
              currency   = EXCLUDED.currency,
              amount     = EXCLUDED.amount,
              note       = EXCLUDED.note,
              updated_at = NOW()
RETURNING {_COLUMNS}
"""
"""The conflict target is the person, the tool and the period, so correcting a seat replaces it.

`seat_id` is absent from the DO UPDATE list on purpose: a corrected seat keeps the id it already
had, so anything referring to it still resolves."""

_DELETE_SQL: Final = 'DELETE FROM "LiteLLM_UserSeat" WHERE seat_id = $1 RETURNING seat_id'


def _read(row: object, key: str) -> object:
    return row.get(key) if isinstance(row, Mapping) else getattr(row, key, None)


def _decimal_or_none(value: object) -> Decimal | None:
    """A `float` is refused rather than converted: `amount` is stored as text precisely so the
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

    Only a live run reveals this: a fake database returns whatever the test put in, which is how
    the invoice repository passed every unit test while rejecting every real row.
    """
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _seat_or_none(row: object) -> Seat | None:
    """A row we cannot read is dropped rather than guessed at.

    A seat with no person would otherwise be charged to nobody and quietly vanish from every
    total, which is worse than not storing it.
    """
    cadence: Final = _read(row, "cadence")
    if cadence not in _CADENCES:
        return None
    seat_id: Final = _read(row, "seat_id")
    tool: Final = _read(row, "tool")
    user_id: Final = _read(row, "user_id")
    currency: Final = _read(row, "currency")
    if not all(isinstance(v, str) and v for v in (seat_id, tool, user_id, currency)):
        return None
    start: Final = _datetime_or_none(_read(row, "period_start"))
    end: Final = _datetime_or_none(_read(row, "period_end"))
    if start is None or end is None:
        return None
    amount: Final = _decimal_or_none(_read(row, "amount"))
    if amount is None:
        return None
    note: Final = _read(row, "note")
    return Seat(
        seat_id=str(seat_id),
        tool=str(tool),
        user_id=str(user_id),
        cadence=cadence,
        currency=str(currency),
        amount=amount,
        period_start=start,
        period_end=end,
        note=note if isinstance(note, str) else None,
    )


class SeatRepository:
    def __init__(self, prisma_client: object) -> None:
        self._prisma_client = prisma_client

    @property
    def _db(self) -> Any:  # any-ok: PrismaClient is an untyped runtime wrapper
        return self._prisma_client.db  # pyright: ignore[reportAttributeAccessIssue]  # object has no .db attr

    async def all(self) -> tuple[Seat, ...]:
        rows: Final[Sequence[Mapping[str, object]]] = await self._db.query_raw(_SELECT_SQL)
        return tuple(found for row in rows if (found := _seat_or_none(row)) is not None)

    async def for_period(self, *, period_start: datetime, period_end: datetime) -> tuple[Seat, ...]:
        """Every seat whose period sits inside the window asked for.

        Contained rather than overlapping: a seat that straddles the boundary covers time outside
        the window, and counting all of it would charge a person for days the reader did not ask
        about.
        """
        rows: Final[Sequence[Mapping[str, object]]] = await self._db.query_raw(
            _FOR_PERIOD_SQL, period_start.isoformat(), period_end.isoformat()
        )
        return tuple(found for row in rows if (found := _seat_or_none(row)) is not None)

    async def upsert(self, seat: Seat) -> Seat | None:
        """Store a seat, or correct the one already entered for that person, tool and period."""
        rows: Final[Sequence[Mapping[str, object]]] = await self._db.query_raw(
            _UPSERT_SQL,
            seat.seat_id or str(uuid4()),
            seat.tool,
            seat.user_id,
            seat.cadence,
            seat.currency,
            format(seat.amount, "f"),
            seat.period_start.isoformat(),
            seat.period_end.isoformat(),
            seat.note,
        )
        return _seat_or_none(rows[0]) if rows else None

    async def delete(self, seat_id: str) -> bool:
        """False when no seat had that id, so the endpoint can answer 404 rather than pretend."""
        rows: Final[Sequence[Mapping[str, object]]] = await self._db.query_raw(_DELETE_SQL, seat_id)
        return bool(rows)
