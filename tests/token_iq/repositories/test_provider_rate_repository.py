"""Reading and writing what a customer pays.

A rate read wrongly prices every figure it touches and the figure still looks like a figure, so a
row this cannot understand is dropped rather than guessed at. The two things worth asserting are
that: the digits surviving in both directions, and a half-read row never becoming a rate.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Final

import pytest

from token_iq.pricing.rates import Discount, RateRule, UnitPrice
from token_iq.repositories.provider_rate_repository import ProviderRateRepository


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


def _repo(rows: list[dict[str, object]]) -> tuple[ProviderRateRepository, FakeDb]:
    db: Final = FakeDb(rows)
    return ProviderRateRepository(FakePrisma(db)), db


def _stored(**overrides: object) -> dict[str, object]:
    base: Final[dict[str, object]] = {
        "rate_id": "r1",
        "provider": "anthropic",
        "model": None,
        "field": None,
        "basis": "discount",
        "percent_off": "13.5",
        "per_million": None,
        "effective_from": "2026-09-01T00:00:00+00:00",
        "effective_to": None,
        "source": "contract",
    }
    return {**base, **overrides}


class TestReadingWhatWasRecorded:
    @pytest.mark.asyncio
    async def test_a_discount_comes_back_with_its_digits(self) -> None:
        repo, _ = _repo([_stored(percent_off="13.5")])

        rates = await repo.all()

        assert rates[0].basis == Discount(percent_off=Decimal("13.5"))

    @pytest.mark.asyncio
    async def test_a_committed_price_comes_back_with_its_digits(self) -> None:
        repo, _ = _repo(
            [_stored(basis="unit_price", percent_off=None, per_million="2.50", model="claude-sonnet", field="input_cost_per_token")]
        )

        rates = await repo.all()

        assert rates[0].basis == UnitPrice(per_million=Decimal("2.50"))

    @pytest.mark.asyncio
    async def test_a_timestamp_is_read_as_the_day_it_names(self) -> None:
        # A raw query hands a Postgres timestamp back as an ISO string, which only a live run shows:
        # a fake database returns whatever the test put in.
        repo, _ = _repo([_stored(effective_from="2026-09-01T00:00:00+00:00", effective_to="2026-12-31T00:00:00+00:00")])

        rates = await repo.all()

        assert (rates[0].effective_from, rates[0].effective_to) == (date(2026, 9, 1), date(2026, 12, 31))

    @pytest.mark.asyncio
    async def test_an_open_ended_rate_has_no_end(self) -> None:
        repo, _ = _repo([_stored(effective_to=None)])

        assert (await repo.all())[0].effective_to is None

    @pytest.mark.asyncio
    async def test_a_rate_covering_every_model_keeps_its_nulls(self) -> None:
        repo, _ = _repo([_stored(model=None, field=None)])

        rate = (await repo.all())[0]
        assert (rate.model, rate.field) == (None, None)


class TestARowItCannotUnderstand:
    @pytest.mark.asyncio
    async def test_a_basis_nobody_can_name_is_dropped(self) -> None:
        """Kept, it would be a rate the pricing match statement cannot handle, found at the moment
        somebody asks what a model costs."""
        repo, _ = _repo([_stored(basis="vibes")])

        assert await repo.all() == ()

    @pytest.mark.asyncio
    async def test_a_discount_with_no_figure_is_dropped(self) -> None:
        repo, _ = _repo([_stored(percent_off=None)])

        assert await repo.all() == ()

    @pytest.mark.asyncio
    async def test_an_amount_the_driver_decoded_as_a_float_is_dropped(self) -> None:
        # The column is text precisely so the digits survive. A float here means they already did
        # not, and pricing a year of spend with it would be wrong by a rounding nobody chose.
        repo, _ = _repo([_stored(percent_off=13.5)])

        assert await repo.all() == ()

    @pytest.mark.asyncio
    async def test_a_rate_with_no_period_is_dropped(self) -> None:
        repo, _ = _repo([_stored(effective_from=None)])

        assert await repo.all() == ()

    @pytest.mark.asyncio
    async def test_a_rate_with_no_source_is_dropped(self) -> None:
        # The source is how somebody later dares to correct a rate. Without it the row is a figure
        # with no provenance, which nobody will touch and everybody will doubt.
        repo, _ = _repo([_stored(source="")])

        assert await repo.all() == ()


class TestRecording:
    @pytest.mark.asyncio
    async def test_a_discount_is_stored_as_text_on_its_own_column(self) -> None:
        repo, db = _repo([_stored()])
        await repo.add(
            RateRule(
                rate_id="r1",
                provider="anthropic",
                model=None,
                field=None,
                basis=Discount(percent_off=Decimal("13.5")),
                effective_from=date(2026, 9, 1),
                effective_to=None,
                source="contract",
            )
        )

        assert "discount" in db.last_args
        assert "13.5" in db.last_args

    @pytest.mark.asyncio
    async def test_a_committed_price_is_stored_as_text_on_its_own_column(self) -> None:
        repo, db = _repo([_stored(basis="unit_price", percent_off=None, per_million="2.50")])
        await repo.add(
            RateRule(
                rate_id="u1",
                provider="anthropic",
                model="claude-sonnet",
                field="input_cost_per_token",
                basis=UnitPrice(per_million=Decimal("2.50")),
                effective_from=date(2026, 9, 1),
                effective_to=None,
                source="committed-use agreement",
            )
        )

        assert "unit_price" in db.last_args
        assert "2.50" in db.last_args

    @pytest.mark.asyncio
    async def test_recording_never_updates_an_existing_rate(self) -> None:
        """A renegotiation is a new row. The old one priced months that have already been reported,
        and a reported figure must not move under a reader."""
        repo, db = _repo([_stored()])
        await repo.add(
            RateRule(
                rate_id="",
                provider="anthropic",
                model=None,
                field=None,
                basis=Discount(percent_off=Decimal("20")),
                effective_from=date(2026, 10, 1),
                effective_to=None,
                source="renegotiated",
            )
        )

        assert "on conflict" not in db.last_sql.lower()

    @pytest.mark.asyncio
    async def test_a_rate_with_no_id_is_given_one(self) -> None:
        repo, db = _repo([_stored()])
        await repo.add(
            RateRule(
                rate_id="",
                provider="anthropic",
                model=None,
                field=None,
                basis=Discount(percent_off=Decimal("20")),
                effective_from=date(2026, 10, 1),
                effective_to=None,
                source="contract",
            )
        )

        assert db.last_args[0] != ""

    @pytest.mark.asyncio
    async def test_removing_a_rate_that_was_not_there_says_so(self) -> None:
        repo, _ = _repo([])

        assert await repo.delete("nobody") is False

    @pytest.mark.asyncio
    async def test_removing_a_rate_that_was_there_says_so(self) -> None:
        repo, _ = _repo([{"rate_id": "r1"}])

        assert await repo.delete("r1") is True
