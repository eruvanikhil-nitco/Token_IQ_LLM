"""Reading a day and an amount out of a cloud billing response.

The three cloud billing systems answer in positional shapes. Azure returns bare `rows`
whose meaning comes from a separate `columns` array; BigQuery returns `rows[].f[].v`
matched against `schema.fields` in order. Reading either by position works until the
provider reorders its columns, at which point the wrong number is reported rather than an
error raised, which in a billing table is the worst available failure.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from types import MappingProxyType
from typing import Final

from litellm.types.proxy.provider_billing import DEFAULT_CURRENCY

TABLE_PATTERN: Final = re.compile(r"^(?:[A-Za-z0-9_-]+\.)?[A-Za-z0-9_]+\.[A-Za-z0-9_]+$")
"""A BigQuery table reference is `dataset.table` or `project.dataset.table`. GCP project ids
routinely contain hyphens, so the leading (optional) project segment allows them; BigQuery
dataset and table ids never do, so those two segments stay letters, digits and underscores
only. Anything else -- a statement separator, a backtick, a quote, a slash, an extra dot --
is refused before it ever reaches the SQL the Vertex connector interpolates it into.

It lives here rather than in that connector because the credential endpoints apply the same
pattern when a credential is saved, and saving a credential should not drag a connector's
import chain along with it."""


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


def exact_json(text: str) -> object:
    """A response body decoded so its numbers are exact.

    `json.loads` turns a JSON number into a binary float, so a cost has already lost digits
    before anything downstream can make a `Decimal` of it. Money is decoded here or not at
    all.
    """
    return json.loads(text, parse_float=Decimal)


def utc_day_start(value: datetime) -> datetime:
    """The UTC midnight this instant's day begins at.

    A connector that reports by day has to ask its provider for whole days. A window
    starting mid-day sums only the tail of that day, and the day-keyed fact it produces
    overwrites the day's complete total that an earlier run already stored.
    """
    return value.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)


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
    return utc_day_start(parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc))


def decimal_or_none(value: object) -> Decimal | None:
    """An exact amount, or None when the provider did not give one.

    None rather than zero: zero asserts the provider charged nothing, which is a different
    and far more dangerous claim than not knowing.
    """
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def currency_or_default(value: object) -> str:
    """The currency the provider said it billed in, or the default when it said none.

    A euro bill stored as dollars is compared against dollar gateway spend, and the
    difference reads as a leak that does not exist.
    """
    return value if isinstance(value, str) and value else DEFAULT_CURRENCY


def _json_safe(value: object) -> object:
    """One value in a shape `json.dumps` accepts, exact amounts kept as their own digits.

    Nested mappings come back as plain dicts rather than views, since `json.dumps` has no
    encoder for a `MappingProxyType` either; sequences become tuples, which it writes as
    arrays.
    """
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Mapping):
        nested: Final[Mapping[object, object]] = value
        return {  # mutable-ok: json.dumps stores this row and has no mappingproxy encoder
            str(key): _json_safe(item) for key, item in nested.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        items: Final[Sequence[object]] = value
        return tuple(_json_safe(item) for item in items)
    return value


def json_safe_row(fields: Mapping[str, object]) -> Mapping[str, object]:
    """The same row with its exact amounts carried as their own digits, at any depth.

    A fact's `raw` is stored as JSON and `Decimal` has no JSON encoder, so one exactly
    decoded amount would fail the write for the whole fact. The row is handed to
    `json.dumps` whole, so an amount nested inside a cell fails that write exactly as a
    top-level one would.
    """
    return MappingProxyType({key: _json_safe(value) for key, value in fields.items()})


def settling_cutoff(now: datetime, hours: int) -> datetime:
    """The latest instant whose day a cloud has finished billing.

    Cost Explorer, Azure Cost Management and the BigQuery billing export all land 24 to 48
    hours behind. A day still settling under-reports, and comparing it against the
    gateway's own figure would show a leak that does not exist.
    """
    return now - timedelta(hours=hours)
