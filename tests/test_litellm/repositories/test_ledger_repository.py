from datetime import datetime, timezone
from decimal import Decimal
from typing import Final

import pytest

from litellm.repositories.ledger_repository import LedgerRepository

START: Final = datetime(2026, 9, 1, tzinfo=timezone.utc)
END: Final = datetime(2026, 9, 30, tzinfo=timezone.utc)


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


def _repo(rows: list[dict[str, object]]) -> tuple[LedgerRepository, FakeDb]:
    db: Final = FakeDb(rows)
    return LedgerRepository(FakePrisma(db)), db


def _row(**overrides: object) -> dict[str, object]:
    base: Final[dict[str, object]] = {
        "day": "2026-09-15T00:00:00+00:00",
        "fact_key": "openrouter:acct:2026-09-15",
        "provider": "openrouter",
        "credential_name": "openrouter-billing",
        "model": "openai/gpt-4o",
        "evidence": "reconciled",
        "currency": "USD",
        "amount": "0.00774700",
    }
    return {**base, **overrides}


async def _lines(repo: LedgerRepository, limit: int = 50, cursor=None):
    return await repo.lines(provider=None, period_start=START, period_end=END, limit=limit, cursor=cursor)


@pytest.mark.asyncio
async def test_a_line_keeps_its_source_evidence_and_currency() -> None:
    repo, _ = _repo([_row(evidence="reconciled", currency="EUR")])
    page: Final = await _lines(repo)
    assert page.lines[0].evidence == "reconciled"
    assert page.lines[0].currency == "EUR"
    assert page.lines[0].provider == "openrouter"


@pytest.mark.asyncio
async def test_amounts_stay_exact() -> None:
    repo, db = _repo([_row(amount="0.30000000000000004")])
    page: Final = await _lines(repo)
    assert page.lines[0].amount == Decimal("0.30000000000000004")
    assert "::text" in db.last_sql


@pytest.mark.asyncio
async def test_an_amount_the_driver_decoded_as_a_float_is_refused() -> None:
    repo, _ = _repo([_row(amount=0.1)])
    assert (await _lines(repo)).lines == ()


@pytest.mark.asyncio
async def test_an_evidence_level_we_do_not_know_is_dropped_rather_than_guessed() -> None:
    repo, _ = _repo([_row(evidence="vibes")])
    assert (await _lines(repo)).lines == ()


@pytest.mark.asyncio
async def test_a_timestamp_returned_as_an_iso_string_is_read_not_rejected() -> None:
    repo, _ = _repo([_row(day="2026-09-15T00:00:00+00:00")])
    page: Final = await _lines(repo)
    assert page.lines[0].day == datetime(2026, 9, 15, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_the_gateway_is_not_in_the_ledger_at_all() -> None:
    repo, db = _repo([_row()])
    await _lines(repo)
    assert "LiteLLM_SpendLogs" not in db.last_sql
    assert "LiteLLM_DailyTeamSpend" not in db.last_sql
    assert "LiteLLM_ProviderUsageFact" in db.last_sql


@pytest.mark.asyncio
async def test_two_currencies_total_separately_rather_than_being_summed() -> None:
    repo, _ = _repo([{"currency": "USD", "total": "10"}, {"currency": "EUR", "total": "5"}])
    totals: Final = await repo.total(provider="openai", period_start=START, period_end=END)
    assert totals == {"USD": Decimal("10"), "EUR": Decimal("5")}


@pytest.mark.asyncio
async def test_a_currency_whose_total_cannot_be_read_is_left_out_rather_than_zeroed() -> None:
    repo, _ = _repo([{"currency": "USD", "total": "10"}, {"currency": "EUR", "total": "not a number"}])
    totals: Final = await repo.total(provider="openai", period_start=START, period_end=END)
    assert totals == {"USD": Decimal("10")}


@pytest.mark.asyncio
async def test_a_full_page_is_decided_from_the_rows_the_database_returned() -> None:
    rows: Final = [_row(fact_key=f"k{n}") for n in range(49)] + [_row(amount="bad", fact_key="k49")]
    repo, _ = _repo(rows)
    page: Final = await _lines(repo, limit=50)
    assert len(page.lines) == 49
    assert page.next_cursor is not None


@pytest.mark.asyncio
async def test_a_short_page_is_the_end_and_carries_no_cursor() -> None:
    repo, _ = _repo([_row()])
    assert (await _lines(repo, limit=50)).next_cursor is None


@pytest.mark.asyncio
async def test_the_cursor_carries_both_halves_so_a_shared_day_cannot_hide_rows() -> None:
    repo, _ = _repo([_row(fact_key=f"k{n}") for n in range(50)])
    page: Final = await _lines(repo, limit=50)
    assert page.next_cursor == (datetime(2026, 9, 15, tzinfo=timezone.utc), "k49")


@pytest.mark.asyncio
async def test_resuming_from_a_cursor_binds_both_halves_as_parameters() -> None:
    repo, db = _repo([_row()])
    await _lines(repo, cursor=(datetime(2026, 9, 15, tzinfo=timezone.utc), "k1"))
    assert "k1" in db.last_args
    assert "k1" not in db.last_sql


@pytest.mark.asyncio
async def test_one_provider_can_be_asked_for_and_is_bound_not_interpolated() -> None:
    repo, db = _repo([_row()])
    await repo.lines(provider="openrouter", period_start=START, period_end=END, limit=50, cursor=None)
    assert "openrouter" in db.last_args
    assert "openrouter" not in db.last_sql
