from __future__ import annotations

from collections.abc import Mapping
from types import SimpleNamespace
from typing import Final
from unittest.mock import AsyncMock, MagicMock

import pytest
from prisma.errors import RecordNotFoundError

from litellm.types.proxy.attribution import AttributionRule


def _rule(rule_id: str = "r1", match_value: str = "finance-openai", owner_id: str = "t-7") -> AttributionRule:
    return AttributionRule(
        rule_id=rule_id,
        provider="openai",
        match_type="cloud_account",
        match_value=match_value,
        owner_type="team",
        owner_id=owner_id,
        note=None,
    )


def _client() -> tuple[MagicMock, MagicMock]:
    table = MagicMock()
    table.upsert = AsyncMock()
    table.find_many = AsyncMock(return_value=[])
    table.delete = AsyncMock()
    client = MagicMock()
    client.db.litellm_attributionrule = table
    return client, table


class _FakeAttributionTable:
    """Matches enough of Prisma's compound-unique upsert to prove reassignment: a create
    versus update decision keyed on (provider, match_type, match_value), never on rule_id."""

    def __init__(self) -> None:
        self._rows: dict[str, SimpleNamespace] = {}

    async def find_many(self) -> tuple[SimpleNamespace, ...]:
        return tuple(self._rows.values())

    async def upsert(self, *, where: Mapping[str, object], data: Mapping[str, object]) -> SimpleNamespace:
        natural_key: Final = where["provider_match_type_match_value"]
        assert isinstance(natural_key, Mapping)
        existing: Final = next(
            (
                row
                for row in self._rows.values()
                if row.provider == natural_key["provider"]
                and row.match_type == natural_key["match_type"]
                and row.match_value == natural_key["match_value"]
            ),
            None,
        )
        create_data: Final = data["create"]
        update_data: Final = data["update"]
        assert isinstance(create_data, Mapping) and isinstance(update_data, Mapping)
        if existing is None:
            created: Final = SimpleNamespace(**dict(create_data))
            self._rows[created.rule_id] = created
            return created
        merged: Final = SimpleNamespace(**{**vars(existing), **dict(update_data)})
        self._rows[existing.rule_id] = merged
        return merged


@pytest.mark.asyncio
async def test_a_rule_round_trips_with_its_owner_and_match():
    from litellm.repositories.attribution_rule_repository import AttributionRuleRepository

    client, table = _client()
    stored_row: Final = SimpleNamespace(
        rule_id="r1",
        provider="openai",
        match_type="cloud_account",
        match_value="finance-openai",
        owner_type="team",
        owner_id="t-7",
        note=None,
    )
    table.upsert.return_value = stored_row
    table.find_many.return_value = [stored_row]
    repo: Final = AttributionRuleRepository(client)

    stored: Final = await repo.upsert(_rule())

    assert stored is not None
    assert stored.match_value == "finance-openai"
    assert (await repo.all())[0].owner_id == "t-7"


@pytest.mark.asyncio
async def test_upsert_keys_on_the_account_not_rule_id_and_only_stamps_rule_id_on_create():
    """The unique constraint lives on (provider, match_type, match_value). Keying the
    upsert's `where` on `rule_id` instead would make a second write for an account that
    already has a rule collide with the unique index rather than update it, and sending
    `rule_id` into the update branch would let a reassignment change the row's identity."""
    from litellm.repositories.attribution_rule_repository import AttributionRuleRepository

    client, table = _client()
    table.upsert.return_value = SimpleNamespace(
        rule_id="r1",
        provider="openai",
        match_type="cloud_account",
        match_value="finance-openai",
        owner_type="team",
        owner_id="t-7",
        note=None,
    )

    await AttributionRuleRepository(client).upsert(_rule())

    call: Final = table.upsert.await_args.kwargs
    assert call["where"] == {
        "provider_match_type_match_value": {
            "provider": "openai",
            "match_type": "cloud_account",
            "match_value": "finance-openai",
        }
    }
    assert call["data"]["create"]["rule_id"] == "r1"
    assert "rule_id" not in call["data"]["update"]
    for branch in ("create", "update"):
        row: Final = call["data"][branch]
        assert row["owner_type"] == "team"
        assert row["owner_id"] == "t-7"


@pytest.mark.asyncio
async def test_reassigning_an_existing_account_updates_the_owner_not_a_new_row():
    from litellm.repositories.attribution_rule_repository import AttributionRuleRepository

    client = MagicMock()
    client.db.litellm_attributionrule = _FakeAttributionTable()
    repo: Final = AttributionRuleRepository(client)

    await repo.upsert(_rule(rule_id="r1", owner_id="t-7"))
    await repo.upsert(_rule(rule_id="r2", owner_id="t-9"))

    rules: Final = await repo.all()
    assert len(rules) == 1
    assert rules[0].owner_id == "t-9"


@pytest.mark.asyncio
async def test_reassigning_an_existing_account_keeps_its_original_rule_id():
    from litellm.repositories.attribution_rule_repository import AttributionRuleRepository

    client = MagicMock()
    client.db.litellm_attributionrule = _FakeAttributionTable()
    repo: Final = AttributionRuleRepository(client)

    first: Final = await repo.upsert(_rule(rule_id="r1", owner_id="t-7"))
    second: Final = await repo.upsert(_rule(rule_id="r2", owner_id="t-9"))

    assert first is not None and second is not None
    assert first.rule_id == "r1"
    assert second.rule_id == "r1"


@pytest.mark.asyncio
async def test_two_accounts_on_the_same_provider_keep_two_separate_rows():
    from litellm.repositories.attribution_rule_repository import AttributionRuleRepository

    client = MagicMock()
    client.db.litellm_attributionrule = _FakeAttributionTable()
    repo: Final = AttributionRuleRepository(client)

    await repo.upsert(_rule(rule_id="r1", match_value="finance-openai", owner_id="t-7"))
    await repo.upsert(_rule(rule_id="r2", match_value="eng-openai", owner_id="t-9"))

    rules: Final = await repo.all()
    assert len(rules) == 2
    assert {rule.match_value for rule in rules} == {"finance-openai", "eng-openai"}


@pytest.mark.asyncio
async def test_upsert_reports_an_unreadable_stored_row_as_none_not_a_throw():
    from litellm.repositories.attribution_rule_repository import AttributionRuleRepository

    client, table = _client()
    table.upsert.return_value = SimpleNamespace(
        rule_id="r1",
        provider="openai",
        match_type="telepathy",
        match_value="finance-openai",
        owner_type="team",
        owner_id="t-7",
        note=None,
    )

    assert await AttributionRuleRepository(client).upsert(_rule()) is None


@pytest.mark.asyncio
async def test_a_row_with_an_unknown_match_type_is_dropped_rather_than_guessed():
    from litellm.repositories.attribution_rule_repository import AttributionRuleRepository

    client, table = _client()
    table.find_many.return_value = [
        SimpleNamespace(
            rule_id="r1",
            provider="openai",
            match_type="telepathy",
            match_value="x",
            owner_type="team",
            owner_id="t",
            note=None,
        )
    ]

    assert await AttributionRuleRepository(client).all() == ()


def _valid_row_fields() -> dict[str, object]:
    return {
        "rule_id": "r1",
        "provider": "openai",
        "match_type": "cloud_account",
        "match_value": "finance-openai",
        "owner_type": "team",
        "owner_id": "t-7",
        "note": None,
    }


@pytest.mark.parametrize(
    ("field", "bad_value"),
    [
        pytest.param("match_type", "provider_api_key", id="match-type-not-a-known-literal"),
        pytest.param("owner_type", "employee", id="owner-type-not-team-project-or-user"),
        pytest.param("rule_id", 123, id="rule-id-not-a-string"),
        pytest.param("provider", 123, id="provider-not-a-string"),
        pytest.param("match_value", 123, id="match-value-not-a-string"),
        pytest.param("owner_id", 123, id="owner-id-not-a-string"),
    ],
)
@pytest.mark.asyncio
async def test_a_row_failing_any_guard_is_dropped_rather_than_guessed(field: str, bad_value: object):
    """A rule with a meaning nobody can name must not silently own someone's money. Every
    guard below must independently drop the row, not just the match_type check."""
    from litellm.repositories.attribution_rule_repository import AttributionRuleRepository

    row_fields: Final = _valid_row_fields() | {field: bad_value}
    client, table = _client()
    table.find_many.return_value = [SimpleNamespace(**row_fields)]

    assert await AttributionRuleRepository(client).all() == ()


@pytest.mark.asyncio
async def test_deleting_an_existing_rule_reports_success():
    from litellm.repositories.attribution_rule_repository import AttributionRuleRepository

    client, table = _client()

    assert await AttributionRuleRepository(client).delete("r1") is True
    assert table.delete.await_args.kwargs["where"] == {"rule_id": "r1"}


@pytest.mark.asyncio
async def test_deleting_a_rule_that_is_already_gone_reports_failure_not_an_exception():
    from litellm.repositories.attribution_rule_repository import AttributionRuleRepository

    client, table = _client()
    table.delete.side_effect = RecordNotFoundError({}, message="already gone")

    assert await AttributionRuleRepository(client).delete("r1") is False
