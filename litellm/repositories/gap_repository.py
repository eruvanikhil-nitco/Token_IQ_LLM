"""What a provider billed against what the gateway recorded, per account per day.

The difference is spend that reached the provider without passing through the gateway. Three
things about this query are deliberate and easy to get wrong:

The provider side is grouped by account and the gateway side is not. A gateway spend log
records the virtual key that made the call, never the provider account the provider later
billed, so splitting the gateway figure per account would invent a link the data does not
contain. For a customer with one account per provider, the common case, the two sides line up
exactly; for one with several accounts on a provider, the per-account split is the provider's
view alone.

Nothing filters on `grain`. The grain says how finely a provider answered, not what period the
money belongs to, and a request-grain fact still lands in a day. The shipped daily comparison
endpoint carried `AND f.grain = 'day'` and therefore reported zero for the only provider that
had real data, since every stored fact is request-grain.

The join holds only because a connector's `provider` and a spend log's `custom_llm_provider`
are spelled the same. Measured on 2026-09-20: spend logs carry `openrouter`, `openai`,
`anthropic` and `gemini`, and the connectors use `openai`, `anthropic`, `openrouter`,
`bedrock`, `azure` and `vertex_ai`. The six line up, but `gemini` is Google AI Studio and is
not `vertex_ai`, so that traffic has no billing connector and must never surface as an
unallocated Vertex gap. A spend log with an empty `custom_llm_provider` matches no provider and
so sits in no gap at all, which is preferred to charging it against a provider at random.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Final

from litellm.attribution.gap_owner import GapRow

_GAP_SQL: Final = """
WITH theirs AS (
    SELECT f.provider,
           f.credential_name,
           date_trunc('day', f.bucket_start)  AS day,
           SUM(f.billed_cost::numeric)::text  AS provider_cost
      FROM "LiteLLM_ProviderUsageFact" f
     WHERE f.provider = $1
       AND f.bucket_start >= NOW() - ($2 || ' days')::interval
     GROUP BY 1, 2, 3
), ours AS (
    SELECT date_trunc('day', s."startTime") AS day,
           SUM(s.spend)::numeric::text      AS gateway_cost
      FROM "LiteLLM_SpendLogs" s
     WHERE s.custom_llm_provider = $1
       AND s."startTime" >= NOW() - ($2 || ' days')::interval
     GROUP BY 1
)
SELECT theirs.provider,
       theirs.credential_name,
       to_char(theirs.day, 'YYYY-MM-DD') AS day,
       theirs.provider_cost,
       ours.gateway_cost
  FROM theirs LEFT JOIN ours ON theirs.day = ours.day
 ORDER BY theirs.day DESC, theirs.credential_name
"""


_ALL_PROVIDERS_GAP_SQL: Final = """
WITH theirs AS (
    SELECT f.provider,
           f.credential_name,
           date_trunc('day', f.bucket_start)  AS day,
           SUM(f.billed_cost::numeric)::text  AS provider_cost
      FROM "LiteLLM_ProviderUsageFact" f
     WHERE f.bucket_start >= NOW() - ($1 || ' days')::interval
     GROUP BY 1, 2, 3
), ours AS (
    SELECT s.custom_llm_provider            AS provider,
           date_trunc('day', s."startTime") AS day,
           SUM(s.spend)::numeric::text      AS gateway_cost
      FROM "LiteLLM_SpendLogs" s
     WHERE s.custom_llm_provider <> ''
       AND s."startTime" >= NOW() - ($1 || ' days')::interval
     GROUP BY 1, 2
)
SELECT theirs.provider,
       theirs.credential_name,
       to_char(theirs.day, 'YYYY-MM-DD') AS day,
       theirs.provider_cost,
       ours.gateway_cost
  FROM theirs LEFT JOIN ours
    ON theirs.day = ours.day AND theirs.provider = ours.provider
 ORDER BY theirs.day DESC, theirs.provider, theirs.credential_name
"""
"""Every provider in one query, for the Combined screen.

A whole second statement rather than the single-provider one with its filter assembled on a
branch: two statements each readable on their own beat one built from fragments, and the join
here is genuinely different, matching the gateway side on provider as well as day so one
provider's spend can never be compared against another's bill."""


def _read(row: object, key: str) -> object:
    return row.get(key) if isinstance(row, Mapping) else getattr(row, key, None)


def _decimal_or_none(value: object) -> Decimal | None:
    """An exact amount, or None when there is not one to read.

    A `float` is refused rather than converted. Every money column in this query leaves
    Postgres as text, so a float here means a cast was lost and the digits are already gone;
    converting it would answer with a plausible wrong number instead of failing.
    """
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def _day_or_none(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _gap_row_or_none(row: object) -> GapRow | None:
    """A row we cannot read is dropped rather than guessed at.

    `provider_cost` is the exception that carries meaning: absent means the provider reported
    nothing for that day, which `attribute` turns into `no_provider_data` rather than claiming
    the two sources agreed. A cost that is present but unparseable is not evidence of anything,
    so that row leaves entirely.
    """
    provider: Final = _read(row, "provider")
    credential_name: Final = _read(row, "credential_name")
    if not isinstance(provider, str) or not isinstance(credential_name, str):
        return None
    day: Final = _day_or_none(_read(row, "day"))
    if day is None:
        return None

    raw_provider_cost: Final = _read(row, "provider_cost")
    provider_cost: Final = None if raw_provider_cost is None else _decimal_or_none(raw_provider_cost)
    if raw_provider_cost is not None and provider_cost is None:
        return None

    raw_gateway_cost: Final = _read(row, "gateway_cost")
    gateway_cost: Final = Decimal(0) if raw_gateway_cost is None else _decimal_or_none(raw_gateway_cost)
    if gateway_cost is None:
        return None

    return GapRow(
        provider=provider,
        credential_name=credential_name,
        day=day,
        provider_cost=provider_cost,
        gateway_cost=gateway_cost,
    )


class GapRepository:
    def __init__(self, prisma_client: object) -> None:
        self._prisma_client = prisma_client

    @property
    def _db(self) -> Any:  # any-ok: PrismaClient is an untyped runtime wrapper
        return self._prisma_client.db  # pyright: ignore[reportAttributeAccessIssue]  # object has no .db attr

    async def rows(self, *, provider: str | None, days: int) -> tuple[GapRow, ...]:
        """One row per account per day a provider billed for, newest first.

        `provider` of None reads every provider at once, which is what the Combined screen
        needs: six round trips would be six chances for one to fail and leave a screen that
        silently under-reports.

        Summed in the database and bounded by the window: this table grows on every scheduler
        tick, so pulling its rows into Python to add them up would make the cost of drawing
        the screen grow with the customer's whole billing history.
        """
        raw: Final[Sequence[Mapping[str, object]]] = (
            await self._db.query_raw(_ALL_PROVIDERS_GAP_SQL, str(days))
            if provider is None
            else await self._db.query_raw(_GAP_SQL, provider, str(days))
        )
        return tuple(row for r in raw if (row := _gap_row_or_none(r)) is not None)
