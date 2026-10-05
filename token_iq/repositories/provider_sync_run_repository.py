"""Persistence for provider fetch attempts.

A row is written whether the fetch worked or not: a connection that has been failing for a
day is the single thing this table exists to make visible.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Final, get_args
from uuid import uuid4

from token_iq.types.provider_billing import ProviderSyncRun, SyncOutcome

_OUTCOMES: Final[frozenset[str]] = frozenset(get_args(SyncOutcome))


def _run_or_none(row: object) -> ProviderSyncRun | None:
    """A row we cannot read is dropped rather than guessed at.

    Reporting an unreadable row as a success would tell a customer their key works when we
    have no evidence either way.
    """
    outcome: Final = getattr(row, "outcome", None)
    if outcome not in _OUTCOMES:
        return None
    provider: Final = getattr(row, "provider", None)
    credential_name: Final = getattr(row, "credential_name", None)
    if not isinstance(provider, str) or not isinstance(credential_name, str):
        return None
    started: Final = getattr(row, "started_at", None)
    if not isinstance(started, datetime):
        return None
    finished: Final = getattr(row, "finished_at", None)
    if not isinstance(finished, datetime):
        return None
    window_start: Final = getattr(row, "window_start", None)
    if not isinstance(window_start, datetime):
        return None
    window_end: Final = getattr(row, "window_end", None)
    if not isinstance(window_end, datetime):
        return None
    detail: Final = getattr(row, "detail", None)
    return ProviderSyncRun(
        provider=provider,
        credential_name=credential_name,
        started_at=started,
        finished_at=finished,
        outcome=outcome,
        facts_written=written if isinstance(written := getattr(row, "facts_written", 0), int) else 0,
        window_start=window_start,
        window_end=window_end,
        detail=detail if isinstance(detail, str) else None,
    )


class ProviderSyncRunRepository:
    def __init__(self, prisma_client: object) -> None:
        self._prisma_client = prisma_client

    @property
    def _table(self) -> Any:  # any-ok: PrismaClient is an untyped runtime wrapper
        db: Final = self._prisma_client.db  # pyright: ignore[reportAttributeAccessIssue]  # object has no .db attr
        return db.litellm_providersyncrun

    async def record(self, run: ProviderSyncRun) -> None:
        await self._table.create(
            data={
                "id": str(uuid4()),
                "provider": run.provider,
                "credential_name": run.credential_name,
                "started_at": run.started_at,
                "finished_at": run.finished_at,
                "outcome": run.outcome,
                "facts_written": run.facts_written,
                "window_start": run.window_start,
                "window_end": run.window_end,
                "detail": run.detail,
            }
        )

    async def recent(self, *, provider: str | None = None, limit: int = 50) -> tuple[ProviderSyncRun, ...]:
        """The newest attempts, newest first. Bounded: this table grows on every tick."""
        rows: Final = await self._table.find_many(
            where={} if provider is None else {"provider": provider},
            order={"started_at": "desc"},
            take=limit,
        )
        return tuple(run for row in rows if (run := _run_or_none(row)) is not None)
