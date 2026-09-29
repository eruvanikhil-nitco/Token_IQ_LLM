from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Final

import pytest

from litellm.repositories.tool_usage_fact_repository import ToolUsageFactRepository, fact_key_for
from litellm.types.proxy.tool_usage import ToolUsageFact

DAY: Final = datetime(2026, 9, 1, tzinfo=timezone.utc)


def _fact(**over: object) -> ToolUsageFact:
    base: Final[dict[str, object]] = {
        "tool": "claude_code",
        "person": "dev@example.test",
        "day": DAY,
        "cost": Decimal("1.86"),
        "currency": "USD",
        "basis": "new_money",
        "model": "claude-opus-5",
    }
    return ToolUsageFact(**{**base, **over})  # pyright: ignore[reportArgumentType]  # test builder spreads a dict


@dataclass
class FakeDb:
    rows: Sequence[Mapping[str, object]] = ()
    calls: list[tuple[object, ...]] = field(default_factory=list)  # mutable-ok: a spy the test reads

    async def query_raw(self, sql: str, *args: object) -> Sequence[Mapping[str, object]]:
        self.calls.append((sql, *args))
        return self.rows


@dataclass
class FakePrisma:
    db: FakeDb


def _repo(rows: Sequence[Mapping[str, object]] = ()) -> tuple[ToolUsageFactRepository, FakeDb]:
    db: Final = FakeDb(rows=rows)
    return ToolUsageFactRepository(FakePrisma(db=db)), db


def test_the_same_person_day_and_model_is_the_same_row() -> None:
    assert fact_key_for(_fact()) == fact_key_for(_fact(cost=Decimal("99")))


def test_a_different_day_is_a_different_row() -> None:
    other: Final = datetime(2026, 9, 2, tzinfo=timezone.utc)

    assert fact_key_for(_fact()) != fact_key_for(_fact(day=other))


def test_a_different_model_is_a_different_row_so_a_day_keeps_its_breakdown() -> None:
    assert fact_key_for(_fact()) != fact_key_for(_fact(model="claude-sonnet-5"))


def test_a_different_person_is_a_different_row() -> None:
    assert fact_key_for(_fact()) != fact_key_for(_fact(person="other@example.test"))


@pytest.mark.asyncio
async def test_writing_the_same_window_twice_overwrites_rather_than_doubling() -> None:
    """A window is refetched on every tick. Inserting rather than overwriting would multiply a
    customer's tool spend by the number of times we looked at it."""
    repo, db = _repo(rows=({"fact_key": "k"},))

    await repo.upsert_many([_fact()], credential_name="acme")

    assert "ON CONFLICT (fact_key)" in str(db.calls[0][0])


@pytest.mark.asyncio
async def test_the_cost_reaches_the_database_as_exact_digits_not_a_float() -> None:
    repo, db = _repo(rows=({"fact_key": "k"},))

    await repo.upsert_many([_fact(cost=Decimal("0.00000186"))], credential_name="acme")

    assert "0.00000186" in db.calls[0]


@pytest.mark.asyncio
async def test_a_tiny_cost_is_not_written_in_scientific_notation() -> None:
    """`str()` on a small Decimal gives 1.86E-6, which Postgres accepts into a text column and
    which then reads back as something no one can sum. Asserted on the cost argument alone: a
    sweep over every argument matches the hyphen in a model name like claude-opus-5."""
    repo, db = _repo(rows=({"fact_key": "k"},))

    await repo.upsert_many([_fact(cost=Decimal("0.00000186"))], credential_name="acme")

    cost_sent: Final = db.calls[0][6]
    assert cost_sent == "0.00000186"
    assert "E" not in str(cost_sent).upper()


@pytest.mark.asyncio
async def test_it_reports_how_many_rows_the_database_accepted() -> None:
    repo, _ = _repo(rows=({"fact_key": "k"},))

    assert await repo.upsert_many([_fact()], credential_name="acme") == 1


@pytest.mark.asyncio
async def test_a_total_leaves_out_money_already_counted_on_a_provider_bill() -> None:
    """The one rule this whole feature turns on. A Claude Code row billed to an API
    organisation is already on the Anthropic bill, so adding it here counts it twice."""
    repo, db = _repo(rows=())

    await repo.spend_per_person(tool="claude_code", period_start=DAY, period_end=DAY)

    assert "basis = 'new_money'" in str(db.calls[0][0])


@pytest.mark.asyncio
async def test_a_total_is_summed_in_sql_and_cast_to_text() -> None:
    """Pulling the rows into Python would make drawing the screen cost more every month, and a
    float on the way out would lose digits before anything could make a Decimal of it."""
    repo, db = _repo(rows=())

    await repo.spend_per_person(tool="cursor", period_start=DAY, period_end=DAY)

    assert "::text" in str(db.calls[0][0])
    assert "SUM(" in str(db.calls[0][0])


@pytest.mark.asyncio
async def test_counts_per_account_come_back_keyed_by_account() -> None:
    repo, _ = _repo(rows=({"credential_name": "acme", "stored": 7},))

    assert dict(await repo.counts_by_credential("cursor")) == {"acme": 7}


@pytest.mark.asyncio
async def test_a_row_the_database_returned_without_a_name_is_left_out() -> None:
    repo, _ = _repo(rows=({"credential_name": None, "stored": 7}, {"credential_name": "acme", "stored": 2}))

    assert dict(await repo.counts_by_credential("cursor")) == {"acme": 2}
