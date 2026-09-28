from datetime import datetime, timezone
from decimal import Decimal
from typing import Final

import pytest

from litellm.repositories.gap_repository import GapRepository

_PROVIDER_CAST: Final = "SUM(f.billed_cost::numeric)::text"
_GATEWAY_CAST: Final = "SUM(s.spend)::numeric::text"


def _driver_decoded(sql: str, cast: str, value: object) -> object:
    """What prisma-client-py hands back for this column.

    A column left as a bare `numeric` is decoded into a Python float, which cannot hold
    arbitrarily many significant digits, and whatever the driver rounds away is gone before
    this module sees the row. Only a column cast to text arrives as exact digits. Mirroring
    that per cast is what makes each cast individually load-bearing: a single check for the
    substring `::text` would stay true after one of the two casts was dropped.
    """
    if not isinstance(value, str) or cast in sql:
        return value
    return float(value)


class FakeDb:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows: Final = rows
        self.last_sql: str = ""  # rebind-ok: a spy records the last call for the test to read
        self.last_args: tuple[object, ...] = ()  # rebind-ok: same spy

    async def query_raw(self, sql: str, *args: object) -> list[dict[str, object]]:
        self.last_sql = sql
        self.last_args = args
        return [
            {
                **row,
                "provider_cost": _driver_decoded(sql, _PROVIDER_CAST, row.get("provider_cost")),
                "gateway_cost": _driver_decoded(sql, _GATEWAY_CAST, row.get("gateway_cost")),
            }
            for row in self._rows
        ]


class FakePrisma:
    def __init__(self, db: FakeDb) -> None:
        self.db: Final = db


def _repo(rows: list[dict[str, object]]) -> tuple[GapRepository, FakeDb]:
    db: Final = FakeDb(rows)
    return GapRepository(FakePrisma(db)), db


def _row(**overrides: object) -> dict[str, object]:
    base: Final[dict[str, object]] = {
        "provider": "openai",
        "credential_name": "acct",
        "day": "2026-09-19",
        "provider_cost": "5",
        "gateway_cost": "2",
    }
    return {**base, **overrides}


@pytest.mark.asyncio
async def test_gap_rows_come_back_as_exact_decimals() -> None:
    repo, db = _repo([_row(provider_cost="0.30000000000000004", gateway_cost="0.10000000000000001")])
    rows: Final = await repo.rows(provider="openai", days=7)
    assert rows[0].provider_cost == Decimal("0.30000000000000004")
    assert rows[0].gateway_cost == Decimal("0.10000000000000001")
    assert _PROVIDER_CAST in db.last_sql
    assert _GATEWAY_CAST in db.last_sql


@pytest.mark.asyncio
async def test_a_provider_day_the_gateway_never_saw_counts_the_gateway_as_zero() -> None:
    repo, _ = _repo([_row(gateway_cost=None)])
    rows: Final = await repo.rows(provider="openai", days=7)
    assert rows[0].gateway_cost == Decimal(0)
    assert rows[0].provider_cost == Decimal("5")


@pytest.mark.asyncio
async def test_a_day_the_provider_reported_nothing_for_is_none_not_zero() -> None:
    repo, _ = _repo([_row(provider_cost=None)])
    rows: Final = await repo.rows(provider="openai", days=7)
    assert rows[0].provider_cost is None


@pytest.mark.asyncio
async def test_a_row_with_an_unreadable_cost_is_dropped_rather_than_zeroed() -> None:
    repo, _ = _repo([_row(provider_cost="not a number")])
    assert await repo.rows(provider="openai", days=7) == ()


@pytest.mark.asyncio
async def test_a_cost_the_driver_decoded_as_a_float_is_refused() -> None:
    repo, _ = _repo([_row(provider_cost=0.1)])
    assert await repo.rows(provider="openai", days=7) == ()


@pytest.mark.asyncio
async def test_facts_of_any_grain_are_summed_into_their_day() -> None:
    repo, db = _repo([_row(provider="openrouter", provider_cost="0.00780515", gateway_cost="0.00794405")])
    rows: Final = await repo.rows(provider="openrouter", days=7)
    assert rows[0].provider_cost == Decimal("0.00780515")
    assert "grain" not in db.last_sql


@pytest.mark.asyncio
async def test_a_spend_log_with_no_provider_recorded_cannot_inflate_a_gap() -> None:
    repo, db = _repo([_row()])
    await repo.rows(provider="openai", days=7)
    assert "custom_llm_provider = $1" in db.last_sql
    assert "custom_llm_provider IS NULL" not in db.last_sql
    assert "COALESCE(s.custom_llm_provider" not in db.last_sql


@pytest.mark.asyncio
async def test_the_day_arrives_as_a_utc_datetime() -> None:
    repo, _ = _repo([_row(day="2026-09-19")])
    rows: Final = await repo.rows(provider="openai", days=7)
    assert rows[0].day == datetime(2026, 9, 19, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_a_row_with_an_unreadable_day_is_dropped() -> None:
    repo, _ = _repo([_row(day="the nineteenth")])
    assert await repo.rows(provider="openai", days=7) == ()


@pytest.mark.asyncio
async def test_the_window_is_bounded_by_the_days_asked_for() -> None:
    repo, db = _repo([_row()])
    await repo.rows(provider="openai", days=30)
    assert db.last_args == ("openai", "30")


@pytest.mark.asyncio
async def test_every_row_keeps_the_account_that_produced_it() -> None:
    repo, _ = _repo([_row(credential_name="finance-openai"), _row(credential_name="research-openai")])
    rows: Final = await repo.rows(provider="openai", days=7)
    assert tuple(row.credential_name for row in rows) == ("finance-openai", "research-openai")


@pytest.mark.asyncio
async def test_every_provider_comes_back_when_none_is_asked_for() -> None:
    repo, db = _repo([_row(provider="openai"), _row(provider="anthropic")])
    rows: Final = await repo.rows(provider=None, days=7)
    assert tuple(row.provider for row in rows) == ("openai", "anthropic")
    assert db.last_args == ("7",)


@pytest.mark.asyncio
async def test_asking_for_one_provider_still_binds_it_as_a_parameter() -> None:
    repo, db = _repo([_row()])
    await repo.rows(provider="openai", days=7)
    assert db.last_args == ("openai", "7")


@pytest.mark.asyncio
async def test_the_gateway_side_is_matched_per_provider_not_smeared_across_them() -> None:
    repo, db = _repo([_row()])
    await repo.rows(provider=None, days=7)
    assert "ON theirs.day = ours.day AND theirs.provider = ours.provider" in db.last_sql


@pytest.mark.asyncio
async def test_a_spend_log_with_no_provider_is_excluded_from_the_all_providers_query_too() -> None:
    repo, db = _repo([_row()])
    await repo.rows(provider=None, days=7)
    assert "s.custom_llm_provider <> ''" in db.last_sql
    assert "COALESCE(s.custom_llm_provider" not in db.last_sql
