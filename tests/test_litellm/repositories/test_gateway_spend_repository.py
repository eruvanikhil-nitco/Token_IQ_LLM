from decimal import Decimal
from typing import Final

import pytest

from litellm.repositories.gateway_spend_repository import GatewaySpendRepository


class FakeDb:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows: Final = rows
        self.last_sql: str = ""  # rebind-ok: a spy records the last call for the test to read
        self.last_args: tuple[object, ...] = ()  # rebind-ok: same spy

    async def query_raw(self, sql: str, *args: object) -> list[dict[str, object]]:
        self.last_sql = sql
        self.last_args = args
        return self._rows


class FakePrisma:
    def __init__(self, db: FakeDb) -> None:
        self.db: Final = db


def _repo(rows: list[dict[str, object]]) -> tuple[GatewaySpendRepository, FakeDb]:
    db: Final = FakeDb(rows)
    return GatewaySpendRepository(FakePrisma(db)), db


@pytest.mark.asyncio
async def test_spend_comes_back_as_exact_decimals() -> None:
    repo, db = _repo([{"key": "t-1", "gateway_cost": "0.30000000000000004"}])
    slices: Final = await repo.by_dimension(dimension="team", days=7)
    assert slices[0].gateway_cost == Decimal("0.30000000000000004")
    assert "::text" in db.last_sql


@pytest.mark.asyncio
async def test_each_dimension_reads_the_table_that_actually_holds_it() -> None:
    for dimension, table, column in (
        ("team", "LiteLLM_DailyTeamSpend", "team_id"),
        ("project", "LiteLLM_DailyProjectSpend", "project_id"),
        ("user", "LiteLLM_DailyUserSpend", "user_id"),
        ("provider", "LiteLLM_DailyTeamSpend", "custom_llm_provider"),
        ("model", "LiteLLM_DailyTeamSpend", "model"),
    ):
        repo, db = _repo([{"key": "k", "gateway_cost": "1"}])
        await repo.by_dimension(dimension=dimension, days=7)  # pyright: ignore[reportArgumentType]  # looping the literal
        assert table in db.last_sql
        assert column in db.last_sql


@pytest.mark.asyncio
async def test_an_unknown_dimension_cannot_reach_the_database() -> None:
    repo, db = _repo([])
    with pytest.raises(KeyError):
        await repo.by_dimension(dimension="salary", days=7)  # pyright: ignore[reportArgumentType]  # the point of the test
    assert db.last_sql == ""


@pytest.mark.asyncio
async def test_a_dimension_cannot_smuggle_sql_because_nothing_formats_the_caller_s_value() -> None:
    repo, db = _repo([])
    with pytest.raises(KeyError):
        await repo.by_dimension(dimension='team"; DROP TABLE "LiteLLM_SpendLogs"; --', days=7)  # pyright: ignore[reportArgumentType]  # the point of the test
    assert db.last_sql == ""


@pytest.mark.asyncio
async def test_the_window_is_bound_as_a_parameter_not_interpolated() -> None:
    repo, db = _repo([{"key": "t-1", "gateway_cost": "1"}])
    await repo.by_dimension(dimension="team", days=30)
    assert db.last_args == ("30",)
    assert "30" not in db.last_sql


@pytest.mark.asyncio
async def test_a_row_with_an_unreadable_amount_is_dropped_rather_than_zeroed() -> None:
    repo, _ = _repo([{"key": "t-1", "gateway_cost": "not a number"}])
    assert await repo.by_dimension(dimension="team", days=7) == ()


@pytest.mark.asyncio
async def test_an_amount_the_driver_decoded_as_a_float_is_refused() -> None:
    repo, _ = _repo([{"key": "t-1", "gateway_cost": 0.1}])
    assert await repo.by_dimension(dimension="team", days=7) == ()


@pytest.mark.asyncio
async def test_a_row_with_no_owner_is_dropped_rather_than_grouped_under_blank() -> None:
    repo, _ = _repo([{"key": "", "gateway_cost": "5"}, {"key": "t-1", "gateway_cost": "5"}])
    slices: Final = await repo.by_dimension(dimension="team", days=7)
    assert tuple(s.key for s in slices) == ("t-1",)


@pytest.mark.asyncio
async def test_the_largest_spender_is_asked_for_first() -> None:
    repo, db = _repo([{"key": "t-1", "gateway_cost": "1"}])
    await repo.by_dimension(dimension="team", days=7)
    assert "ORDER BY SUM(d.spend)::numeric DESC" in db.last_sql


@pytest.mark.asyncio
async def test_the_window_compares_text_because_the_date_column_is_text() -> None:
    """The rollup tables store date as TEXT holding YYYY-MM-DD. Casting the column to date
    makes Postgres refuse the comparison outright, which no fake database would reveal."""
    repo, db = _repo([{"key": "t-1", "gateway_cost": "1"}])
    await repo.by_dimension(dimension="team", days=7)
    assert "to_char(NOW()" in db.last_sql
    assert "d.date::date" not in db.last_sql
    assert ")::date" not in db.last_sql
