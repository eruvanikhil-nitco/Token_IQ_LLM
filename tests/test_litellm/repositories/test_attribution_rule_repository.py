from __future__ import annotations

from types import SimpleNamespace
from typing import Final
from unittest.mock import AsyncMock, MagicMock

import pytest
from prisma.errors import RecordNotFoundError

from litellm.types.proxy.attribution import AttributionRule


def _rule(rule_id: str = "r1") -> AttributionRule:
    return AttributionRule(
        rule_id=rule_id,
        provider="openai",
        match_type="cloud_account",
        match_value="finance-openai",
        owner_type="team",
        owner_id="t-7",
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

    assert stored.match_value == "finance-openai"
    assert (await repo.all())[0].owner_id == "t-7"


@pytest.mark.asyncio
async def test_upsert_keys_on_rule_id_and_writes_the_full_row_to_both_branches():
    """The unique constraint lives on (provider, match_type, match_value), but rule_id is
    the primary key: upserting on anything else would create a duplicate row for an edit
    instead of updating the one the caller meant to change."""
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
    assert call["where"] == {"rule_id": "r1"}
    for branch in ("create", "update"):
        row: Final = call["data"][branch]
        assert row["provider"] == "openai"
        assert row["match_type"] == "cloud_account"
        assert row["match_value"] == "finance-openai"
        assert row["owner_type"] == "team"
        assert row["owner_id"] == "t-7"


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
