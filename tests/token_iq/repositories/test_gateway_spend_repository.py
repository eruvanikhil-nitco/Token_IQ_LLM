from decimal import Decimal
from typing import Final

import pytest

from token_iq.repositories.gateway_spend_repository import GatewaySpendRepository


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


@pytest.mark.asyncio
async def test_the_total_counts_rows_the_slices_drop() -> None:
    repo, _ = _repo([{"total": "10"}])
    assert await repo.total(dimension="team", days=7) == Decimal("10")


@pytest.mark.asyncio
async def test_the_total_reads_the_same_table_the_slices_came_from() -> None:
    repo, db = _repo([{"total": "1"}])
    await repo.total(dimension="project", days=7)
    assert "LiteLLM_DailyProjectSpend" in db.last_sql
    assert "LiteLLM_SpendLogs" not in db.last_sql


@pytest.mark.asyncio
async def test_the_total_has_no_key_filter_so_unowned_rows_still_count() -> None:
    repo, db = _repo([{"total": "1"}])
    await repo.total(dimension="team", days=7)
    assert "IS NOT NULL" not in db.last_sql
    assert "<> ''" not in db.last_sql


@pytest.mark.asyncio
async def test_a_window_with_no_spend_totals_zero_rather_than_failing() -> None:
    repo, _ = _repo([{"total": None}])
    assert await repo.total(dimension="team", days=7) == Decimal(0)


@pytest.mark.asyncio
async def test_an_unknown_dimension_cannot_reach_the_database_through_the_total_either() -> None:
    repo, db = _repo([])
    with pytest.raises(KeyError):
        await repo.total(dimension="salary", days=7)  # pyright: ignore[reportArgumentType]  # the point of the test
    assert db.last_sql == ""


START: Final = __import__("datetime").datetime(2026, 9, 1, tzinfo=__import__("datetime").timezone.utc)
END: Final = __import__("datetime").datetime(2026, 9, 30, tzinfo=__import__("datetime").timezone.utc)


@pytest.mark.asyncio
async def test_spend_comes_back_per_person_and_exact() -> None:
    repo, db = _repo([{"key": "u-1", "gateway_cost": "0.30000000000000004"}])
    spend: Final = await repo.by_user_for_period(period_start=START, period_end=END)
    assert spend["u-1"] == Decimal("0.30000000000000004")
    assert "::text" in db.last_sql


@pytest.mark.asyncio
async def test_the_period_is_bound_as_text_because_the_date_column_is_text() -> None:
    repo, db = _repo([{"key": "u-1", "gateway_cost": "1"}])
    await repo.by_user_for_period(period_start=START, period_end=END)
    assert db.last_args == ("2026-09-01", "2026-09-30")
    assert "d.date::date" not in db.last_sql


@pytest.mark.asyncio
async def test_a_row_with_no_person_is_left_out_rather_than_grouped_under_blank() -> None:
    repo, _ = _repo([{"key": "", "gateway_cost": "5"}, {"key": "u-1", "gateway_cost": "5"}])
    spend: Final = await repo.by_user_for_period(period_start=START, period_end=END)
    assert tuple(spend) == ("u-1",)


@pytest.mark.asyncio
async def test_a_person_whose_amount_cannot_be_read_is_left_out_rather_than_zeroed() -> None:
    repo, _ = _repo([{"key": "u-1", "gateway_cost": "not a number"}])
    assert await repo.by_user_for_period(period_start=START, period_end=END) == {}


@pytest.mark.asyncio
async def test_the_per_person_read_uses_the_user_rollup_table() -> None:
    repo, db = _repo([{"key": "u-1", "gateway_cost": "1"}])
    await repo.by_user_for_period(period_start=START, period_end=END)
    assert "LiteLLM_DailyUserSpend" in db.last_sql


@pytest.mark.asyncio
async def test_a_team_is_named_rather_than_shown_as_a_uuid() -> None:
    repo, _ = _repo([{"key": "t-1", "label": "Platform", "gateway_cost": "4"}])
    slices: Final = await repo.by_dimension(dimension="team", days=7)
    assert slices[0].label == "Platform"
    assert slices[0].key == "t-1"


@pytest.mark.asyncio
async def test_the_name_is_read_from_the_table_that_holds_it() -> None:
    for dimension, table, column in (
        ("team", "LiteLLM_TeamTable", "team_alias"),
        ("user", "LiteLLM_UserTable", "user_alias"),
    ):
        repo, db = _repo([{"key": "k", "label": "Name", "gateway_cost": "1"}])
        await repo.by_dimension(dimension=dimension, days=7)  # pyright: ignore[reportArgumentType]  # looping the literal
        assert table in db.last_sql
        assert column in db.last_sql


@pytest.mark.asyncio
async def test_a_spender_whose_name_row_is_gone_still_appears() -> None:
    """A team deleted from the team table still has spend on the rollup, and that spend has to be
    reported. An inner join would drop the row, which would quietly lower the page's own total."""
    repo, db = _repo([{"key": "t-gone", "label": None, "gateway_cost": "4"}])
    slices: Final = await repo.by_dimension(dimension="team", days=7)
    assert slices[0].key == "t-gone"
    assert slices[0].label is None
    assert "LEFT JOIN" in db.last_sql


@pytest.mark.asyncio
async def test_a_blank_name_is_treated_as_no_name_rather_than_shown() -> None:
    repo, db = _repo([{"key": "t-1", "label": "", "gateway_cost": "4"}])
    slices: Final = await repo.by_dimension(dimension="team", days=7)
    assert slices[0].label is None
    assert "NULLIF" in db.last_sql


@pytest.mark.asyncio
async def test_a_person_falls_back_to_their_email_when_they_have_no_alias() -> None:
    repo, db = _repo([{"key": "u-1", "label": "someone@example.com", "gateway_cost": "4"}])
    slices: Final = await repo.by_dimension(dimension="user", days=7)
    assert slices[0].label == "someone@example.com"
    assert "user_email" in db.last_sql
    assert db.last_sql.index("user_alias") < db.last_sql.index("user_email")


@pytest.mark.asyncio
async def test_a_dimension_that_is_already_a_name_asks_for_no_second_table() -> None:
    """Provider and model group by a column that already reads as a name, so there is nothing to
    join to. Joining anyway would add a table scan to draw the same words."""
    for dimension in ("provider", "model", "project"):
        repo, db = _repo([{"key": "gpt-4o", "label": None, "gateway_cost": "1"}])
        slices: Final = await repo.by_dimension(dimension=dimension, days=7)  # pyright: ignore[reportArgumentType]  # looping the literal
        assert "JOIN" not in db.last_sql
        assert slices[0].label is None


@pytest.mark.asyncio
async def test_the_name_does_not_change_which_rows_are_grouped_together() -> None:
    """The join is on a primary key, so each key has one name and the grouping is unchanged. A
    name column left out of GROUP BY makes Postgres refuse the statement outright."""
    repo, db = _repo([{"key": "t-1", "label": "Platform", "gateway_cost": "4"}])
    await repo.by_dimension(dimension="team", days=7)
    assert "GROUP BY 1, 2" in db.last_sql
