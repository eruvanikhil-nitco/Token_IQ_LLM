from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from typing import Final

import pytest

from litellm.repositories.seat_repository import SeatRepository
from litellm.types.proxy.seat import Seat

START: Final = datetime(2026, 9, 1, tzinfo=timezone.utc)
END: Final = datetime(2026, 9, 30, tzinfo=timezone.utc)

SEAT: Final = Seat(
    seat_id="",
    tool="claude-code",
    user_id="u-1",
    cadence="monthly",
    currency="USD",
    amount=Decimal("30.00"),
    period_start=START,
    period_end=END,
    note=None,
)


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


def _repo(rows: list[dict[str, object]]) -> tuple[SeatRepository, FakeDb]:
    db: Final = FakeDb(rows)
    return SeatRepository(FakePrisma(db)), db


def _stored(**overrides: object) -> dict[str, object]:
    base: Final[dict[str, object]] = {
        "seat_id": "s1",
        "tool": "claude-code",
        "user_id": "u-1",
        "cadence": "monthly",
        "currency": "USD",
        "amount": "30.00",
        "period_start": START,
        "period_end": END,
        "note": None,
    }
    return {**base, **overrides}


@pytest.mark.asyncio
async def test_a_seat_round_trips_with_its_tool_and_person() -> None:
    repo, _ = _repo([_stored()])
    saved: Final = await repo.upsert(SEAT)
    assert saved is not None
    assert saved.tool == "claude-code"
    assert saved.user_id == "u-1"
    assert saved.amount == Decimal("30.00")


@pytest.mark.asyncio
async def test_the_amount_is_exact_to_the_last_digit_the_contract_showed() -> None:
    repo, _ = _repo([_stored(amount="30.123456789012345")])
    saved: Final = await repo.upsert(SEAT)
    assert saved is not None
    assert saved.amount == Decimal("30.123456789012345")


@pytest.mark.asyncio
async def test_an_amount_the_driver_decoded_as_a_float_is_refused() -> None:
    repo, _ = _repo([_stored(amount=30.0)])
    assert await repo.upsert(SEAT) is None


@pytest.mark.asyncio
async def test_a_cadence_we_do_not_know_is_dropped_rather_than_guessed() -> None:
    repo, _ = _repo([_stored(cadence="fortnightly")])
    assert await repo.all() == ()


@pytest.mark.asyncio
async def test_a_seat_with_no_person_is_dropped_rather_than_charged_to_nobody() -> None:
    repo, _ = _repo([_stored(user_id="")])
    assert await repo.all() == ()


@pytest.mark.asyncio
async def test_a_timestamp_returned_as_an_iso_string_is_read_not_rejected() -> None:
    repo, _ = _repo([_stored(period_start="2026-09-01T00:00:00+00:00", period_end="2026-09-30T00:00:00+00:00")])
    saved: Final = await repo.upsert(SEAT)
    assert saved is not None
    assert saved.period_start == START
    assert saved.period_end == END


@pytest.mark.asyncio
async def test_a_period_that_is_not_a_date_is_dropped() -> None:
    repo, _ = _repo([_stored(period_start="the first of September")])
    assert await repo.upsert(SEAT) is None


@pytest.mark.asyncio
async def test_re_entering_a_persons_seat_corrects_it_rather_than_charging_twice() -> None:
    repo, db = _repo([_stored()])
    await repo.upsert(SEAT)
    assert "ON CONFLICT (tool, user_id, period_start, period_end)" in db.last_sql
    assert "seat_id    =" not in db.last_sql


@pytest.mark.asyncio
async def test_a_new_seat_is_given_an_id_rather_than_writing_an_empty_one() -> None:
    repo, db = _repo([_stored()])
    await repo.upsert(SEAT)
    assert db.last_args[0] != ""
    assert len(str(db.last_args[0])) >= 32


@pytest.mark.asyncio
async def test_the_note_is_bound_as_a_parameter_never_interpolated() -> None:
    hostile: Final = 'x\'; DROP TABLE "LiteLLM_UserSeat"; --'
    repo, db = _repo([_stored()])
    await repo.upsert(replace(SEAT, note=hostile))
    assert hostile not in db.last_sql
    assert hostile in db.last_args


@pytest.mark.asyncio
async def test_the_currency_the_contract_was_written_in_survives() -> None:
    repo, _ = _repo([_stored(currency="EUR")])
    saved: Final = await repo.upsert(replace(SEAT, currency="EUR"))
    assert saved is not None
    assert saved.currency == "EUR"


@pytest.mark.asyncio
async def test_seats_for_a_period_bind_both_ends_as_parameters() -> None:
    repo, db = _repo([_stored()])
    await repo.for_period(period_start=START, period_end=END)
    assert db.last_args == (START.isoformat(), END.isoformat())


@pytest.mark.asyncio
async def test_deleting_a_seat_that_never_existed_reports_false() -> None:
    repo, _ = _repo([])
    assert await repo.delete("nope") is False


@pytest.mark.asyncio
async def test_deleting_a_seat_that_existed_reports_true() -> None:
    repo, db = _repo([{"seat_id": "s1"}])
    assert await repo.delete("s1") is True
    assert db.last_args == ("s1",)


@pytest.mark.asyncio
async def test_every_readable_seat_comes_back() -> None:
    repo, _ = _repo([_stored(seat_id="s1"), _stored(seat_id="s2", user_id="u-2")])
    seats: Final = await repo.all()
    assert tuple(s.user_id for s in seats) == ("u-1", "u-2")
