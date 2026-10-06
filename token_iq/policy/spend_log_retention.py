"""Age out request and response bodies from spend logs while keeping the accounting.

A spend log row carries two very different things. The accounting, who called what, when,
which model, how many tokens, what it cost, is small and wanted forever: it is what every
usage view and every invoice is built from. The bodies, the request the client sent and the
answer the provider returned, are large and only useful while someone might still want to
look at them.

Measured on a live gateway, a row with bodies is roughly two thousand times the size of one
without, so the bodies are effectively the whole cost of the table. They also hold the actual
text people typed, which is the part that should not sit around indefinitely by default.

This blanks the body columns past a cutoff and leaves the row itself alone. Usage reporting is
unaffected because it never reads them.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Final, Protocol

DEFAULT_RETENTION_DAYS: Final = 30

# Updating in slices keeps each statement's lock brief. A single UPDATE over months of rows
# would hold row locks for its whole duration and stall writers on a busy table.
DEFAULT_BATCH_SIZE: Final = 500

# How many batches one run may do. A backlog is worked down over successive runs rather than
# in one long transaction that competes with live traffic.
DEFAULT_MAX_BATCHES: Final = 20

# Columns holding request or response content. `messages` is included for completeness even
# though only realtime calls ever populate it; `proxy_server_request` is the one that actually
# carries the prompt for chat completions, and it carries the request headers with it.
BODY_COLUMNS: Final = ("proxy_server_request", "response", "messages")

# Postgres representations of "already blank", so a second pass skips rows the first cleared
# and the job converges on doing nothing instead of rewriting the same rows forever.
_BLANK_VALUES: Final = ("'{}'", "'null'")


class RawExecutor(Protocol):
    """The one database capability this needs: run a statement, say how many rows it hit.

    Injected rather than reaching for the Prisma client so the loop can be exercised without
    a database, and so nothing here depends on the shape of that client.
    """

    async def __call__(self, sql: str, cutoff: datetime) -> int: ...


def cutoff_for(retention_days: int, now: datetime | None = None) -> datetime:
    """The instant before which bodies should be cleared."""
    reference: Final = now or datetime.now(timezone.utc)
    return reference - timedelta(days=retention_days)


def is_enabled(retention_days: int | None) -> bool:
    """Whether to run at all.

    None or a non-positive number means keep bodies forever, which stays the default for
    anyone who has not chosen a window. Deleting content is not something to start doing to
    an existing deployment because it upgraded.
    """
    return retention_days is not None and retention_days > 0


def build_clear_bodies_sql(batch_size: int = DEFAULT_BATCH_SIZE) -> str:
    """SQL that blanks the bodies of one batch of rows older than the cutoff.

    Written as a bounded subquery rather than a plain UPDATE ... WHERE so the number of rows
    touched per statement is capped. The caller loops until nothing is left.

    Rows whose bodies are already blank are excluded, so repeat runs converge to doing nothing
    rather than rewriting the same rows and churning the heap.
    """
    blank: Final = ", ".join(_BLANK_VALUES)
    already_blank: Final = " AND ".join(f'"{column}"::text IN ({blank})' for column in BODY_COLUMNS)
    assignments: Final = ", ".join(f"\"{column}\" = '{{}}'::jsonb" for column in BODY_COLUMNS)
    return f"""
        UPDATE "LiteLLM_SpendLogs"
        SET {assignments}
        WHERE "request_id" IN (
            SELECT "request_id"
            FROM "LiteLLM_SpendLogs"
            WHERE "startTime" < $1::timestamp
              AND NOT ({already_blank})
            LIMIT {int(batch_size)}
        )
    """


async def clear_expired_bodies(
    execute: RawExecutor,
    retention_days: int | None = DEFAULT_RETENTION_DAYS,
    batch_size: int = DEFAULT_BATCH_SIZE,
    max_batches: int = DEFAULT_MAX_BATCHES,
    now: datetime | None = None,
) -> int:
    """Blank bodies older than the window. Returns how many rows were cleared."""
    if not is_enabled(retention_days):
        return 0

    from token_iq.gateway._logging import verbose_proxy_logger

    cutoff: Final = cutoff_for(int(retention_days or DEFAULT_RETENTION_DAYS), now=now)
    sql: Final = build_clear_bodies_sql(batch_size)

    cleared = 0  # rebind-ok: accumulates across batches, and the batch count is not known up front
    for _ in range(max_batches):
        try:
            affected: Final = await execute(sql, cutoff)
        except Exception as exc:  # noqa: BLE001  # housekeeping must never take the proxy down
            verbose_proxy_logger.warning("Spend log retention: batch failed, will retry next run: %s", exc)
            break
        if not affected:
            break
        cleared += int(affected)

    if cleared:
        verbose_proxy_logger.info(
            "Spend log retention: cleared bodies from %s row(s) older than %s, spend rows kept",
            cleared,
            cutoff.date().isoformat(),
        )
    return cleared
