from datetime import datetime, timedelta, timezone

import pytest

from token_iq.policy.spend_log_retention import (
    BODY_COLUMNS,
    build_clear_bodies_sql,
    clear_expired_bodies,
    cutoff_for,
    is_enabled,
)


class _Recorder:
    """Stands in for the database, returning a scripted row count per batch."""

    def __init__(self, affected_per_call: list[int]) -> None:
        self.affected_per_call = list(affected_per_call)
        self.calls: list[tuple[str, datetime]] = []

    async def __call__(self, sql: str, cutoff: datetime) -> int:
        self.calls.append((sql, cutoff))
        if not self.affected_per_call:
            return 0
        return self.affected_per_call.pop(0)


class _Exploder:
    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self, sql: str, cutoff: datetime) -> int:
        self.calls += 1
        raise RuntimeError("connection lost")


def test_disabled_when_no_window_is_configured() -> None:
    # Upgrading must never start deleting content on its own.
    assert is_enabled(None) is False
    assert is_enabled(0) is False
    assert is_enabled(-1) is False
    assert is_enabled(30) is True


@pytest.mark.asyncio
async def test_nothing_runs_when_disabled() -> None:
    execute = _Recorder([500])

    assert await clear_expired_bodies(execute, retention_days=None) == 0
    assert execute.calls == []


def test_cutoff_is_the_window_before_now() -> None:
    now = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)

    assert cutoff_for(30, now=now) == datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_the_cutoff_reaches_the_database() -> None:
    now = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)
    execute = _Recorder([3, 0])

    await clear_expired_bodies(execute, retention_days=7, now=now)

    assert execute.calls[0][1] == datetime(2026, 9, 3, 12, 0, tzinfo=timezone.utc)


def test_every_body_column_is_blanked_and_named_in_the_filter() -> None:
    sql = build_clear_bodies_sql()

    for column in BODY_COLUMNS:
        assert f'"{column}" = \'{{}}\'::jsonb' in sql
        assert f'"{column}"::text IN' in sql


def test_accounting_columns_are_never_touched() -> None:
    sql = build_clear_bodies_sql()

    # The row is what usage reporting and invoices are built from. Only bodies go.
    for column in ("spend", "total_tokens", "model", "team_id", "startTime", "api_key"):
        assert f'"{column}" =' not in sql


def test_each_statement_is_bounded_so_one_run_cannot_lock_the_table() -> None:
    sql = build_clear_bodies_sql(batch_size=250)

    assert "LIMIT 250" in sql


def test_already_blank_rows_are_skipped_so_repeat_runs_converge() -> None:
    sql = build_clear_bodies_sql()

    # Without this the job rewrites the same rows every run, churning the heap forever.
    assert "NOT (" in sql
    assert "'{}'" in sql and "'null'" in sql


@pytest.mark.asyncio
async def test_it_loops_until_the_backlog_is_empty() -> None:
    execute = _Recorder([500, 500, 120, 0])

    cleared = await clear_expired_bodies(execute, retention_days=30)

    assert cleared == 1120
    assert len(execute.calls) == 4


@pytest.mark.asyncio
async def test_one_run_is_capped_so_it_cannot_monopolise_the_database() -> None:
    execute = _Recorder([500] * 50)

    cleared = await clear_expired_bodies(execute, retention_days=30, max_batches=3)

    # A large backlog is worked down over successive runs, not in one long transaction.
    assert len(execute.calls) == 3
    assert cleared == 1500


@pytest.mark.asyncio
async def test_a_database_failure_is_swallowed_rather_than_taking_traffic_down() -> None:
    execute = _Exploder()

    cleared = await clear_expired_bodies(execute, retention_days=30)

    # Serving requests does not depend on housekeeping succeeding.
    assert cleared == 0
    assert execute.calls == 1


@pytest.mark.asyncio
async def test_a_failure_partway_keeps_what_was_already_cleared() -> None:
    class _FailsOnSecond:
        def __init__(self) -> None:
            self.calls = 0

        async def __call__(self, sql: str, cutoff: datetime) -> int:
            self.calls += 1
            if self.calls == 1:
                return 500
            raise RuntimeError("connection lost")

    execute = _FailsOnSecond()

    assert await clear_expired_bodies(execute, retention_days=30) == 500


@pytest.mark.asyncio
async def test_a_shorter_window_reaches_further_forward() -> None:
    now = datetime(2026, 9, 10, tzinfo=timezone.utc)
    seven = _Recorder([1, 0])
    ninety = _Recorder([1, 0])

    await clear_expired_bodies(seven, retention_days=7, now=now)
    await clear_expired_bodies(ninety, retention_days=90, now=now)

    # A 7 day window clears rows a 90 day window still keeps.
    assert seven.calls[0][1] > ninety.calls[0][1]
    assert seven.calls[0][1] - ninety.calls[0][1] == timedelta(days=83)
