"""The two counts the issues list cannot work out without the database.

Both are counts, and a count query that silently returns nothing looks exactly like a healthy
installation. So these assert the shape that comes back and that the reading, not just the query,
survives each form Prisma can hand back a row in.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest
from pydantic import ValidationError

from token_iq.repositories.data_quality_repository import DataQualityRepository

START = datetime(2026, 10, 1, tzinfo=timezone.utc)
END = datetime(2026, 11, 1, tzinfo=timezone.utc)


class _Db:
    """A stand-in for the Prisma client, recording what it was asked."""

    def __init__(self, rows: object) -> None:
        self._rows = rows
        self.queries: list[str] = []
        self.args: list[tuple[Any, ...]] = []

    async def query_raw(self, query: str, *args: Any) -> object:
        self.queries.append(query)
        self.args.append(args)
        return self._rows


class _Client:
    def __init__(self, rows: object) -> None:
        self.db = _Db(rows)


def _repo(rows: object) -> tuple[DataQualityRepository, _Client]:
    client = _Client(rows)
    return DataQualityRepository(client), client


class TestKeysWithNoProject:
    @pytest.mark.asyncio
    async def test_reads_the_count(self) -> None:
        repo, _ = _repo([{"count": 3}])

        assert await repo.keys_without_project() == 3

    @pytest.mark.asyncio
    async def test_reads_a_row_handed_back_as_an_object(self) -> None:
        """`query_raw` returns mappings here and attribute-bearing rows elsewhere in this codebase,
        so the reader has to survive both rather than assuming one."""

        class Row:
            count = 5

        repo, _ = _repo([Row()])

        assert await repo.keys_without_project() == 5

    @pytest.mark.asyncio
    async def test_no_rows_is_zero_rather_than_an_error(self) -> None:
        repo, _ = _repo([])

        assert await repo.keys_without_project() == 0

    @pytest.mark.asyncio
    async def test_it_asks_only_about_keys_with_no_project(self) -> None:
        # Without this the query could count every key and the number would look alarming and be
        # meaningless. Asserted on the query because the stand-in returns whatever it is given.
        repo, client = _repo([{"count": 0}])
        await repo.keys_without_project()

        asked = client.db.queries[0].lower()
        assert "project_id is null" in asked
        assert "litellm_verificationtoken" in asked


class TestProvidersWithNoInvoice:
    @pytest.mark.asyncio
    async def test_reads_the_count(self) -> None:
        repo, _ = _repo([{"count": 2}])

        assert await repo.providers_missing_invoice(START, END) == 2

    @pytest.mark.asyncio
    async def test_no_rows_is_zero(self) -> None:
        repo, _ = _repo([])

        assert await repo.providers_missing_invoice(START, END) == 0

    @pytest.mark.asyncio
    async def test_it_passes_the_period_it_was_given(self) -> None:
        repo, client = _repo([{"count": 0}])
        await repo.providers_missing_invoice(START, END)

        assert client.db.args[0] == (START.isoformat(), END.isoformat())

    @pytest.mark.asyncio
    async def test_the_invoice_has_to_cover_the_day_that_was_billed(self) -> None:
        """Any invoice for the provider is not enough; it has to span the day in question.

        This is where the rule lives now. An invoice for March does not make September's missing
        one appear, and a query matching on provider alone would report a clean period for a month
        nobody has billed for.
        """
        repo, client = _repo([{"count": 0}])
        await repo.providers_missing_invoice(START, END)

        asked = client.db.queries[0].lower()
        assert "period_start <=" in asked
        assert "period_end >" in asked
        assert "not exists" in asked

    @pytest.mark.asyncio
    async def test_it_only_counts_providers_that_actually_billed_something(self) -> None:
        """A provider nobody uses has no invoice and needs none. Counting it would put every
        unused provider on the issues list, which is the same trap `not_connected` is."""
        repo, client = _repo([{"count": 0}])
        await repo.providers_missing_invoice(START, END)

        asked = client.db.queries[0].lower()
        assert "providerusagefact" in asked
        assert "providerinvoice" in asked


class TestProvidersThatBilled:
    """The denominator of invoice coverage, which has to start from the same population as the
    missing count or the fraction is two unrelated numbers side by side."""

    @pytest.mark.asyncio
    async def test_reads_the_count(self) -> None:
        repo, _ = _repo([{"count": 6}])

        assert await repo.providers_billing(START, END) == 6

    @pytest.mark.asyncio
    async def test_no_rows_is_zero(self) -> None:
        repo, _ = _repo([])

        assert await repo.providers_billing(START, END) == 0

    @pytest.mark.asyncio
    async def test_it_passes_the_period_it_was_given(self) -> None:
        repo, client = _repo([{"count": 0}])
        await repo.providers_billing(START, END)

        assert client.db.args[0] == (START.isoformat(), END.isoformat())

    @pytest.mark.asyncio
    async def test_it_counts_each_provider_once_however_many_facts_it_has(self) -> None:
        """Without the distinct this returns a fact count, and coverage reads "0 of 50" for one
        provider that happens to have sent fifty rows."""
        repo, client = _repo([{"count": 0}])
        await repo.providers_billing(START, END)

        asked = client.db.queries[0].lower()
        assert "count(distinct f.provider)" in asked
        assert "providerusagefact" in asked

    @pytest.mark.asyncio
    async def test_it_asks_about_the_period_rather_than_all_of_history(self) -> None:
        repo, client = _repo([{"count": 0}])
        await repo.providers_billing(START, END)

        asked = client.db.queries[0].lower()
        assert "bucket_start >=" in asked
        assert "bucket_start <" in asked


class TestWhenTheCountCannotBeRead:
    @pytest.mark.asyncio
    async def test_a_row_with_no_count_raises_rather_than_reporting_zero(self) -> None:
        """The failure that looks most like success on this tab.

        A query whose result cannot be read has not counted zero of anything, and "0 issues" on the
        tab asking whether the data can be trusted is read as a clean bill of health.
        """
        repo, _ = _repo([{"total": 3}])

        with pytest.raises(ValidationError):
            await repo.keys_without_project()

    @pytest.mark.asyncio
    async def test_a_count_that_is_not_a_number_raises(self) -> None:
        repo, _ = _repo([{"count": "not a number"}])

        with pytest.raises(ValidationError):
            await repo.providers_billing(START, END)
