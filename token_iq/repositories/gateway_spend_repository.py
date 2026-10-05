"""Gateway spend grouped by whichever dimension a reader chose.

This module interpolates a table and column name into SQL, which is the one genuinely
dangerous thing in the Combined screen. The guard is that it never formats a caller's string:
`_STATEMENTS` maps a closed literal to a complete, fixed statement, and a dimension that is not
a key raises before any query exists. There is deliberately no template to fill in, because a
template invites the next caller to pass something through it.

The window is bounded and the summing happens in the database. These rollup tables grow every
day a customer uses the gateway, so adding the rows up in Python would make the cost of drawing
the screen grow with their whole history.

The `date` column in every one of these rollup tables is TEXT holding `YYYY-MM-DD`, not a date,
so the window is compared as text. That is correct rather than a shortcut: ISO-8601 dates sort
lexicographically in the same order they sort chronologically. Casting the column to `date`
instead would fail outright, because Postgres will not compare text to date, and would also
stop any index on the column being used.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from types import MappingProxyType
from typing import Any, Final, Literal

ExplorerDimension = Literal["team", "project", "user", "provider", "model"]


@dataclass(frozen=True, slots=True)
class SpendSlice:
    key: str
    gateway_cost: Decimal
    label: str | None = None
    """What a person calls this spender, when anything in the database knows. `None` means the
    caller shows the key, because a row with no name still has spend that has to be reported."""


@dataclass(frozen=True, slots=True)
class _Named:
    """Where the name of a grouping key lives, for the dimensions whose key is an identifier.

    `columns` is tried in order, so a person with an alias is called that and one without falls
    back to their email rather than to a uuid.
    """

    table: str
    id_column: str
    columns: tuple[str, ...]


def _statement(table: str, column: str, named: _Named | None = None) -> str:
    """Built once, at import, from this module's own literals. Never from a caller's value."""
    window: Final = "to_char(NOW() - ($1 || ' days')::interval, 'YYYY-MM-DD')"
    # LEFT JOIN, not JOIN: a team deleted from the team table still has spend on the rollup, and
    # dropping that row would quietly lower the page's own total.
    join: Final = "" if named is None else f'LEFT JOIN "{named.table}" n ON n."{named.id_column}" = d."{column}" '
    label: Final = (
        "NULL::text"
        if named is None
        else "COALESCE(" + ", ".join(f"NULLIF(n.\"{name}\", '')" for name in named.columns) + ")"
    )
    return (
        f'SELECT d."{column}"                AS key, '
        f"{label} AS label, "
        f"SUM(d.spend)::numeric::text AS gateway_cost "
        f'FROM "{table}" d '
        f"{join}"
        f"WHERE d.date >= {window} "
        f'AND d."{column}" IS NOT NULL '
        f"AND d.\"{column}\" <> '' "
        # The join is on a primary key, so the name is one value per key and the grouping is
        # unchanged. Postgres refuses the statement outright if a selected column is left out.
        f"GROUP BY 1, 2 "
        f"ORDER BY SUM(d.spend)::numeric DESC"
    )


_STATEMENTS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "team": _statement(
            "LiteLLM_DailyTeamSpend", "team_id", _Named("LiteLLM_TeamTable", "team_id", ("team_alias",))
        ),
        "project": _statement("LiteLLM_DailyProjectSpend", "project_id"),
        "user": _statement(
            "LiteLLM_DailyUserSpend", "user_id", _Named("LiteLLM_UserTable", "user_id", ("user_alias", "user_email"))
        ),
        "provider": _statement("LiteLLM_DailyTeamSpend", "custom_llm_provider"),
        "model": _statement("LiteLLM_DailyTeamSpend", "model"),
    }
)
"""Provider and model read the team table because it carries both columns and has rows on every
installation. Reading them from their own tables would double count a request that appears in
the team, user and project rollups alike. They also need no name lookup: the column they group
by already reads as a name. Project has no name anywhere in the schema, so it keeps its id."""


def _total_statement(table: str) -> str:
    """The same table's whole spend for the window, with no key filter.

    Measured against the same table the slices come from, never against `LiteLLM_SpendLogs`:
    comparing a rollup's slices to a different table's total would report a difference that is
    two tables disagreeing rather than spend the dimension could not place.
    """
    window: Final = "to_char(NOW() - ($1 || ' days')::interval, 'YYYY-MM-DD')"
    return f'SELECT SUM(d.spend)::numeric::text AS total FROM "{table}" d WHERE d.date >= {window}'


_TOTALS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "team": _total_statement("LiteLLM_DailyTeamSpend"),
        "project": _total_statement("LiteLLM_DailyProjectSpend"),
        "user": _total_statement("LiteLLM_DailyUserSpend"),
        "provider": _total_statement("LiteLLM_DailyTeamSpend"),
        "model": _total_statement("LiteLLM_DailyTeamSpend"),
    }
)


def _read(row: object, key: str) -> object:
    return row.get(key) if isinstance(row, Mapping) else getattr(row, key, None)


def _decimal_or_none(value: object) -> Decimal | None:
    """A `float` is refused rather than converted: every money column here leaves Postgres as
    text, so a float means a cast was lost and the digits are already gone."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def _slice_or_none(row: object) -> SpendSlice | None:
    """A row we cannot read is dropped rather than guessed at. Defaulting an unreadable amount
    to zero would understate a team's spend, which is worse than leaving the line out."""
    key: Final = _read(row, "key")
    if not isinstance(key, str) or key == "":
        return None
    cost: Final = _decimal_or_none(_read(row, "gateway_cost"))
    if cost is None:
        return None
    label: Final = _read(row, "label")
    return SpendSlice(key=key, gateway_cost=cost, label=label if isinstance(label, str) and label != "" else None)


_BY_USER_FOR_PERIOD_SQL: Final = (
    "SELECT d.user_id AS key, SUM(d.spend)::numeric::text AS gateway_cost "
    'FROM "LiteLLM_DailyUserSpend" d '
    "WHERE d.date >= $1 AND d.date <= $2 "
    "AND d.user_id IS NOT NULL AND d.user_id <> '' "
    "GROUP BY 1"
)
"""Spend per person over a period with a start and an end, because a seat covers a period.

The window is compared as text: `date` in this table is TEXT holding `YYYY-MM-DD`, not a date,
and ISO dates sort in the same order they fall. Casting the column to `date` makes Postgres
refuse the comparison outright, which is a defect no fake database can show."""


class GatewaySpendRepository:
    def __init__(self, prisma_client: object) -> None:
        self._prisma_client = prisma_client

    @property
    def _db(self) -> Any:  # any-ok: PrismaClient is an untyped runtime wrapper
        return self._prisma_client.db  # pyright: ignore[reportAttributeAccessIssue]  # object has no .db attr

    async def by_dimension(self, *, dimension: ExplorerDimension, days: int) -> tuple[SpendSlice, ...]:
        """Gateway spend for the window, grouped by the chosen dimension, largest first."""
        statement: Final = _STATEMENTS[dimension]
        rows: Final[Sequence[Mapping[str, object]]] = await self._db.query_raw(statement, str(days))
        return tuple(found for row in rows if (found := _slice_or_none(row)) is not None)

    async def total(self, *, dimension: ExplorerDimension, days: int) -> Decimal:
        """Everything that table holds for the window, including rows with no key.

        The slices drop a row whose key is blank, because grouping spend under an empty name
        tells a reader nothing. This total still counts it, so the caller can report the
        difference as spend the dimension cannot place rather than let a chart quietly fail to
        add up.
        """
        statement: Final = _TOTALS[dimension]
        rows: Final[Sequence[Mapping[str, object]]] = await self._db.query_raw(statement, str(days))
        found: Final = _decimal_or_none(_read(rows[0], "total")) if rows else None
        return found if found is not None else Decimal(0)

    async def by_user_for_period(self, *, period_start: datetime, period_end: datetime) -> Mapping[str, Decimal]:
        """What each person's gateway traffic cost over the period, keyed by user id.

        A row carrying no person is left out rather than grouped under a blank name: spend
        nobody can be identified with tells a reader nothing, and giving it a blank owner would
        put it in someone's column.
        """
        rows: Final[Sequence[Mapping[str, object]]] = await self._db.query_raw(
            _BY_USER_FOR_PERIOD_SQL, period_start.date().isoformat(), period_end.date().isoformat()
        )
        return MappingProxyType(
            {
                str(key): amount
                for row in rows
                if isinstance(key := _read(row, "key"), str)
                and key != ""
                and (amount := _decimal_or_none(_read(row, "gateway_cost"))) is not None
            }
        )
