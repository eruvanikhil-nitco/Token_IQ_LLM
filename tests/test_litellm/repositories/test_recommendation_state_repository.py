from typing import Final

import pytest

from litellm.repositories.recommendation_state_repository import RecommendationStateRepository


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


def _repo(rows: list[dict[str, object]]) -> tuple[RecommendationStateRepository, FakeDb]:
    db: Final = FakeDb(rows)
    return RecommendationStateRepository(FakePrisma(db)), db


@pytest.mark.asyncio
async def test_it_reads_back_the_decisions_that_were_made() -> None:
    repo, _ = _repo([{"rule_id": "escaped_spend", "state": "dismissed"}, {"rule_id": "stale_budget", "state": "done"}])

    assert dict(await repo.all()) == {"escaped_spend": "dismissed", "stale_budget": "done"}


@pytest.mark.asyncio
async def test_a_state_nobody_can_name_hides_no_card() -> None:
    """A row written by an older or newer version of the product, or by hand, must not silently
    hide a recommendation. The screen could not say why it was hidden, so the card stays open."""
    repo, _ = _repo([{"rule_id": "escaped_spend", "state": "snoozed"}, {"rule_id": "stale_budget", "state": "done"}])

    assert dict(await repo.all()) == {"stale_budget": "done"}


@pytest.mark.asyncio
async def test_a_row_with_no_rule_is_left_out_rather_than_keyed_on_none() -> None:
    repo, _ = _repo([{"rule_id": None, "state": "done"}, {"rule_id": "stale_budget", "state": "done"}])

    assert dict(await repo.all()) == {"stale_budget": "done"}


@pytest.mark.asyncio
async def test_a_decision_carries_who_made_it_and_why() -> None:
    repo, db = _repo([{"rule_id": "escaped_spend"}])

    assert await repo.decide(rule_id="escaped_spend", state="done", decided_by="u-1", note="fixed the key")
    assert db.last_args == ("escaped_spend", "done", "u-1", "fixed the key")


@pytest.mark.asyncio
async def test_deciding_twice_changes_the_decision_rather_than_failing() -> None:
    repo, db = _repo([{"rule_id": "escaped_spend"}])

    await repo.decide(rule_id="escaped_spend", state="done", decided_by=None, note=None)

    assert "ON CONFLICT (rule_id)" in db.last_sql


@pytest.mark.asyncio
async def test_undoing_a_decision_that_was_never_made_reports_it_rather_than_claiming_success() -> None:
    repo, _ = _repo([])

    assert await repo.clear("escaped_spend") is False


@pytest.mark.asyncio
async def test_undoing_a_decision_that_exists_reports_success() -> None:
    repo, db = _repo([{"rule_id": "escaped_spend"}])

    assert await repo.clear("escaped_spend") is True
    assert db.last_args == ("escaped_spend",)
