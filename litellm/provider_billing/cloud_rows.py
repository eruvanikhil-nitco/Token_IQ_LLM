"""Reading a day and an amount out of a cloud billing response.

The three cloud billing systems answer in positional shapes. Azure returns bare `rows`
whose meaning comes from a separate `columns` array; BigQuery returns `rows[].f[].v`
matched against `schema.fields` in order. Reading either by position works until the
provider reorders its columns, at which point the wrong number is reported rather than an
error raised, which in a billing table is the worst available failure.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Final


def by_column_name(columns: Sequence[object], row: Sequence[object], name_key: str = "name") -> dict[str, object]:
    """Pair a positional row with its column names.

    Empty when the row is shorter than its columns: a truncated row means the response is
    not the shape we believe it is, and filling the gap would put a null cost into a
    billing table.
    """
    names: list[str] = [  # mutable-ok: a comprehension target read back for its length
        name for column in columns if isinstance(column, Mapping) and isinstance(name := column.get(name_key), str)
    ]
    if len(names) != len(columns) or len(row) < len(names):
        return {}
    return dict(zip(names, row, strict=False))


def day_from_iso(value: object) -> datetime | None:
    """The UTC day an ISO date or timestamp belongs to, or None if it is not one.

    None rather than a default: filing an unparseable charge under today would corrupt the
    comparison silently.
    """
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    aware: Final = parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)
    return aware.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)


def decimal_or_none(value: object) -> Decimal | None:
    """An exact amount, or None when the provider did not give one.

    None rather than zero: zero asserts the provider charged nothing, which is a different
    and far more dangerous claim than not knowing.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def settling_cutoff(now: datetime, hours: int) -> datetime:
    """The latest instant whose day a cloud has finished billing.

    Cost Explorer, Azure Cost Management and the BigQuery billing export all land 24 to 48
    hours behind. A day still settling under-reports, and comparing it against the
    gateway's own figure would show a leak that does not exist.
    """
    return now - timedelta(hours=hours)
