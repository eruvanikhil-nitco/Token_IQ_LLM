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
from decimal import Decimal, InvalidOperation
from types import MappingProxyType
from typing import Any, Final, Literal

ExplorerDimension = Literal["team", "project", "user", "provider", "model"]


@dataclass(frozen=True, slots=True)
class SpendSlice:
    key: str
    gateway_cost: Decimal


def _statement(table: str, column: str) -> str:
    """Built once, at import, from this module's own literals. Never from a caller's value."""
    window: Final = "to_char(NOW() - ($1 || ' days')::interval, 'YYYY-MM-DD')"
    return (
        f'SELECT d."{column}"                AS key, '
        f"SUM(d.spend)::numeric::text AS gateway_cost "
        f'FROM "{table}" d '
        f"WHERE d.date >= {window} "
        f'AND d."{column}" IS NOT NULL '
        f"AND d.\"{column}\" <> '' "
        f"GROUP BY 1 "
        f"ORDER BY SUM(d.spend)::numeric DESC"
    )


_STATEMENTS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "team": _statement("LiteLLM_DailyTeamSpend", "team_id"),
        "project": _statement("LiteLLM_DailyProjectSpend", "project_id"),
        "user": _statement("LiteLLM_DailyUserSpend", "user_id"),
        "provider": _statement("LiteLLM_DailyTeamSpend", "custom_llm_provider"),
        "model": _statement("LiteLLM_DailyTeamSpend", "model"),
    }
)
"""Provider and model read the team table because it carries both columns and has rows on every
installation. Reading them from their own tables would double count a request that appears in
the team, user and project rollups alike."""


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
    return SpendSlice(key=key, gateway_cost=cost)


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
