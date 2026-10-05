from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from typing import Final

import pytest

from token_iq.repositories.invoice_repository import InvoiceRepository
from token_iq.types.invoice import InvoiceAdjustment, ProviderInvoice

START: Final = datetime(2026, 9, 1, tzinfo=timezone.utc)
END: Final = datetime(2026, 9, 30, tzinfo=timezone.utc)

INVOICE: Final = ProviderInvoice(
    invoice_id="",
    provider="openrouter",
    period_start=START,
    period_end=END,
    currency="USD",
    total=Decimal("1234.56"),
    adjustments=(InvoiceAdjustment("credit", Decimal("-10"), "goodwill"),),
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


def _repo(rows: list[dict[str, object]]) -> tuple[InvoiceRepository, FakeDb]:
    db: Final = FakeDb(rows)
    return InvoiceRepository(FakePrisma(db)), db


def _stored(**overrides: object) -> dict[str, object]:
    base: Final[dict[str, object]] = {
        "invoice_id": "i1",
        "provider": "openrouter",
        "period_start": START,
        "period_end": END,
        "currency": "USD",
        "total": "1234.56",
        "adjustments": [{"kind": "credit", "amount": "-10", "note": "goodwill"}],
        "note": None,
    }
    return {**base, **overrides}


@pytest.mark.asyncio
async def test_an_invoice_round_trips_with_its_adjustments() -> None:
    repo, _ = _repo([_stored()])
    saved: Final = await repo.upsert(INVOICE)
    assert saved is not None
    assert saved.total == Decimal("1234.56")
    assert saved.adjustments[0].kind == "credit"
    assert saved.adjustments[0].amount == Decimal("-10")


@pytest.mark.asyncio
async def test_the_amount_is_exact_to_the_last_digit_the_bill_showed() -> None:
    repo, _ = _repo([_stored(total="1234.567890123456789")])
    saved: Final = await repo.upsert(INVOICE)
    assert saved is not None
    assert saved.total == Decimal("1234.567890123456789")


@pytest.mark.asyncio
async def test_an_amount_the_driver_decoded_as_a_float_is_refused() -> None:
    repo, _ = _repo([_stored(total=1234.56)])
    assert await repo.upsert(INVOICE) is None


@pytest.mark.asyncio
async def test_an_adjustment_of_an_unknown_kind_is_dropped_rather_than_guessed() -> None:
    repo, _ = _repo([_stored(adjustments=[{"kind": "vibes", "amount": "1", "note": None}])])
    saved: Final = await repo.upsert(INVOICE)
    assert saved is not None
    assert saved.adjustments == ()


@pytest.mark.asyncio
async def test_an_adjustment_with_an_unreadable_amount_is_dropped() -> None:
    repo, _ = _repo([_stored(adjustments=[{"kind": "credit", "amount": "not a number", "note": None}])])
    saved: Final = await repo.upsert(INVOICE)
    assert saved is not None
    assert saved.adjustments == ()


@pytest.mark.asyncio
async def test_re_entering_a_period_corrects_it_rather_than_storing_two_bills() -> None:
    repo, db = _repo([_stored()])
    await repo.upsert(INVOICE)
    assert "ON CONFLICT (provider, period_start, period_end)" in db.last_sql
    assert "invoice_id   =" not in db.last_sql


@pytest.mark.asyncio
async def test_a_new_invoice_is_given_an_id_rather_than_writing_an_empty_one() -> None:
    repo, db = _repo([_stored()])
    await repo.upsert(INVOICE)
    assert db.last_args[0] != ""
    assert len(str(db.last_args[0])) >= 32


@pytest.mark.asyncio
async def test_the_note_is_bound_as_a_parameter_never_interpolated() -> None:
    hostile: Final = 'note\'; DROP TABLE "LiteLLM_ProviderInvoice"; --'
    repo, db = _repo([_stored()])
    await repo.upsert(replace(INVOICE, note=hostile))
    assert hostile not in db.last_sql
    assert hostile in db.last_args


@pytest.mark.asyncio
async def test_the_currency_the_bill_was_written_in_survives() -> None:
    repo, _ = _repo([_stored(currency="EUR")])
    saved: Final = await repo.upsert(replace(INVOICE, currency="EUR"))
    assert saved is not None
    assert saved.currency == "EUR"


@pytest.mark.asyncio
async def test_a_period_with_no_bill_entered_is_none_rather_than_an_empty_invoice() -> None:
    repo, _ = _repo([])
    assert await repo.for_period(provider="openrouter", period_start=START, period_end=END) is None


@pytest.mark.asyncio
async def test_deleting_a_bill_that_never_existed_reports_false() -> None:
    repo, _ = _repo([])
    assert await repo.delete("nope") is False


@pytest.mark.asyncio
async def test_deleting_a_bill_that_existed_reports_true() -> None:
    repo, db = _repo([{"invoice_id": "i1"}])
    assert await repo.delete("i1") is True
    assert db.last_args == ("i1",)


@pytest.mark.asyncio
async def test_every_readable_invoice_comes_back() -> None:
    repo, _ = _repo([_stored(invoice_id="i1"), _stored(invoice_id="i2", provider="openai")])
    invoices: Final = await repo.all()
    assert tuple(i.provider for i in invoices) == ("openrouter", "openai")


@pytest.mark.asyncio
async def test_a_timestamp_returned_as_an_iso_string_is_read_not_rejected() -> None:
    """A raw query hands Postgres timestamps back as strings. Requiring a datetime here made
    every real invoice unreadable while every fake-backed test still passed."""
    repo, _ = _repo([_stored(period_start="2026-09-01T00:00:00+00:00", period_end="2026-09-30T00:00:00+00:00")])
    saved: Final = await repo.upsert(INVOICE)
    assert saved is not None
    assert saved.period_start == START
    assert saved.period_end == END


@pytest.mark.asyncio
async def test_a_timestamp_that_is_neither_a_datetime_nor_a_date_is_dropped() -> None:
    repo, _ = _repo([_stored(period_start="the first of September")])
    assert await repo.upsert(INVOICE) is None
