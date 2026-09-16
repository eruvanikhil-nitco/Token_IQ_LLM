from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from litellm.types.proxy.provider_billing import ProviderSyncRun

STARTED = datetime(2026, 9, 16, 9, 0, tzinfo=timezone.utc)
FINISHED = datetime(2026, 9, 16, 9, 0, 4, tzinfo=timezone.utc)


def _run(outcome: str = "fetched") -> ProviderSyncRun:
    return ProviderSyncRun(
        provider="openai",
        credential_name="prod",
        started_at=STARTED,
        finished_at=FINISHED,
        outcome=outcome,
        facts_written=3,
        window_start=datetime(2026, 9, 15, 9, 0, tzinfo=timezone.utc),
        window_end=STARTED,
        detail=None,
    )


def _client() -> tuple[MagicMock, MagicMock]:
    table = MagicMock()
    table.create = AsyncMock()
    table.find_many = AsyncMock(return_value=[])
    client = MagicMock()
    client.db.litellm_providersyncrun = table
    return client, table


@pytest.mark.asyncio
async def test_a_run_is_written_with_its_outcome_and_window():
    from litellm.repositories.provider_sync_run_repository import ProviderSyncRunRepository

    client, table = _client()

    await ProviderSyncRunRepository(client).record(_run(outcome="failed"))

    written = table.create.await_args.kwargs["data"]
    assert written["provider"] == "openai"
    assert written["credential_name"] == "prod"
    assert written["outcome"] == "failed"
    assert written["facts_written"] == 3
    assert written["window_end"] == STARTED


@pytest.mark.asyncio
async def test_recent_runs_come_back_newest_first_and_bounded():
    """Sync History reads this on every page load and the table grows on every tick, so an
    unbounded newest-last read would page through a year of rows to show ten."""
    from litellm.repositories.provider_sync_run_repository import ProviderSyncRunRepository

    client, table = _client()

    await ProviderSyncRunRepository(client).recent(provider="openai", limit=10)

    call = table.find_many.await_args.kwargs
    assert call["where"] == {"provider": "openai"}
    assert call["order"] == {"started_at": "desc"}
    assert call["take"] == 10


@pytest.mark.asyncio
async def test_recent_without_a_provider_reads_every_provider():
    from litellm.repositories.provider_sync_run_repository import ProviderSyncRunRepository

    client, table = _client()

    await ProviderSyncRunRepository(client).recent(limit=200)

    assert table.find_many.await_args.kwargs["where"] == {}


@pytest.mark.asyncio
async def test_a_row_missing_its_outcome_is_dropped_rather_than_guessed():
    """Reporting an unreadable row as healthy would tell a customer their key works when we
    have no idea whether it does."""
    from litellm.repositories.provider_sync_run_repository import ProviderSyncRunRepository

    client, table = _client()
    table.find_many = AsyncMock(
        return_value=[
            SimpleNamespace(
                provider="openai",
                credential_name="prod",
                started_at=STARTED,
                finished_at=FINISHED,
                outcome="nonsense",
                facts_written=0,
                window_start=STARTED,
                window_end=FINISHED,
                detail=None,
            )
        ]
    )

    assert await ProviderSyncRunRepository(client).recent(provider="openai") == ()
