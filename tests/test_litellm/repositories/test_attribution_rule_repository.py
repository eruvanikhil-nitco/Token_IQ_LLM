from typing import Final

import pytest

from litellm.repositories.attribution_rule_repository import AttributionRuleRepository
from litellm.types.proxy.attribution import AttributionRule


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


def _repo(rows: list[dict[str, object]]) -> tuple[AttributionRuleRepository, FakeDb]:
    db: Final = FakeDb(rows)
    return AttributionRuleRepository(FakePrisma(db)), db


def _stored(**overrides: object) -> dict[str, object]:
    base: Final[dict[str, object]] = {
        "rule_id": "r1",
        "provider": "openai",
        "match_type": "cloud_account",
        "match_value": "finance-openai",
        "owner_type": "team",
        "owner_id": "t-7",
        "note": None,
    }
    return {**base, **overrides}


RULE: Final = AttributionRule(
    rule_id="r1",
    provider="openai",
    match_type="cloud_account",
    match_value="finance-openai",
    owner_type="team",
    owner_id="t-7",
    note=None,
)


@pytest.mark.asyncio
async def test_a_rule_round_trips_with_its_owner_and_match() -> None:
    repo, _ = _repo([_stored()])
    stored: Final = await repo.upsert(RULE)
    assert stored is not None
    assert stored.match_value == "finance-openai"
    assert stored.owner_id == "t-7"
    assert stored.owner_type == "team"


@pytest.mark.asyncio
async def test_a_row_with_an_unknown_match_type_is_dropped_rather_than_guessed() -> None:
    repo, _ = _repo([_stored(match_type="telepathy")])
    assert await repo.all() == ()


@pytest.mark.asyncio
async def test_a_row_with_an_unknown_owner_type_is_dropped_rather_than_guessed() -> None:
    repo, _ = _repo([_stored(owner_type="departmnet")])
    assert await repo.all() == ()


@pytest.mark.asyncio
async def test_a_row_missing_its_owner_id_is_dropped() -> None:
    repo, _ = _repo([_stored(owner_id="")])
    assert await repo.all() == ()


@pytest.mark.asyncio
async def test_reassigning_an_account_keeps_the_rule_id_it_already_had() -> None:
    repo, db = _repo([_stored(owner_id="t-9")])
    stored: Final = await repo.upsert(AttributionRule("", "openai", "cloud_account", "finance-openai", "team", "t-9"))
    assert stored is not None
    assert stored.rule_id == "r1"
    assert "ON CONFLICT (provider, match_type, match_value)" in db.last_sql
    assert "rule_id   =" not in db.last_sql


@pytest.mark.asyncio
async def test_a_new_rule_is_given_an_id_rather_than_writing_an_empty_one() -> None:
    repo, db = _repo([_stored()])
    await repo.upsert(AttributionRule("", "openai", "cloud_account", "finance-openai", "team", "t-7"))
    assert db.last_args[0] != ""
    assert len(str(db.last_args[0])) >= 32


@pytest.mark.asyncio
async def test_the_account_and_owner_are_bound_as_parameters_never_interpolated() -> None:
    hostile: Final = 'acct\'; DROP TABLE "LiteLLM_AttributionRule"; --'
    repo, db = _repo([_stored()])
    await repo.upsert(AttributionRule("", "openai", "cloud_account", hostile, "team", "t-7"))
    assert hostile not in db.last_sql
    assert hostile in db.last_args


@pytest.mark.asyncio
async def test_a_write_that_returns_nothing_is_none_rather_than_a_guess() -> None:
    repo, _ = _repo([])
    assert await repo.upsert(RULE) is None


@pytest.mark.asyncio
async def test_a_write_read_back_in_a_shape_we_cannot_interpret_is_none() -> None:
    repo, _ = _repo([_stored(owner_type="departmnet")])
    assert await repo.upsert(RULE) is None


@pytest.mark.asyncio
async def test_deleting_a_rule_that_existed_reports_true() -> None:
    repo, db = _repo([{"rule_id": "r1"}])
    assert await repo.delete("r1") is True
    assert db.last_args == ("r1",)


@pytest.mark.asyncio
async def test_deleting_a_rule_that_never_existed_reports_false() -> None:
    repo, _ = _repo([])
    assert await repo.delete("nope") is False


@pytest.mark.asyncio
async def test_every_readable_rule_comes_back() -> None:
    repo, _ = _repo([_stored(rule_id="r1"), _stored(rule_id="r2", match_value="research-openai")])
    rules: Final = await repo.all()
    assert tuple(rule.match_value for rule in rules) == ("finance-openai", "research-openai")
