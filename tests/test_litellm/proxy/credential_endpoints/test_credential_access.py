from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from litellm.proxy._types import LitellmUserRoles, Member, UserAPIKeyAuth
from litellm.proxy.credential_endpoints.credential_access import (
    credential_team,
    may_change_credential,
    may_read_credential,
    teams_user_administers,
)

SHARED = {"custom_llm_provider": "openai"}
TEAM_A = {"custom_llm_provider": "openai", "team_id": "team-a"}
TEAM_B = {"custom_llm_provider": "openai", "team_id": "team-b"}


def test_a_credential_with_no_team_belongs_to_the_installation():
    assert credential_team(SHARED) is None
    assert credential_team(TEAM_A) == "team-a"
    assert credential_team(None) is None


def test_an_admin_reads_and_changes_everything():
    for info in (SHARED, TEAM_A, TEAM_B):
        assert may_read_credential(info, is_admin=True, administered_teams=frozenset()) is True
        assert may_change_credential(info, is_admin=True, administered_teams=frozenset()) is True


def test_a_team_admin_reads_their_own_team_and_the_shared_ones():
    teams = frozenset({"team-a"})

    assert may_read_credential(TEAM_A, is_admin=False, administered_teams=teams) is True
    assert may_read_credential(SHARED, is_admin=False, administered_teams=teams) is True
    assert may_read_credential(TEAM_B, is_admin=False, administered_teams=teams) is False


def test_a_team_admin_changes_only_their_own_team_s_credentials():
    """A shared credential serves teams they do not run, so editing or deleting it would
    break models they cannot see."""
    teams = frozenset({"team-a"})

    assert may_change_credential(TEAM_A, is_admin=False, administered_teams=teams) is True
    assert may_change_credential(SHARED, is_admin=False, administered_teams=teams) is False
    assert may_change_credential(TEAM_B, is_admin=False, administered_teams=teams) is False


def test_someone_who_administers_no_team_may_neither_read_nor_change():
    assert may_read_credential(TEAM_A, is_admin=False, administered_teams=frozenset()) is False
    assert may_change_credential(SHARED, is_admin=False, administered_teams=frozenset()) is False


@pytest.mark.asyncio
async def test_the_teams_a_user_administers_come_from_their_membership():
    caller = UserAPIKeyAuth(user_role=LitellmUserRoles.INTERNAL_USER, api_key="sk-l", user_id="lead")
    rows = [
        MagicMock(model_dump=lambda: {"team_id": "team-a", "members_with_roles": [Member(user_id="lead", role="admin").model_dump()]}),
        MagicMock(model_dump=lambda: {"team_id": "team-b", "members_with_roles": [Member(user_id="lead", role="user").model_dump()]}),
    ]
    prisma = MagicMock()
    prisma.db.litellm_teamtable.find_many = AsyncMock(return_value=rows)

    assert await teams_user_administers(caller, prisma) == frozenset({"team-a"})


@pytest.mark.asyncio
async def test_an_admin_needs_no_team_lookup():
    """The lookup reads every team row, so it must not run for a caller who can see them all."""
    admin = UserAPIKeyAuth(user_role=LitellmUserRoles.PROXY_ADMIN, api_key="sk-a", user_id="admin")
    prisma = MagicMock()
    prisma.db.litellm_teamtable.find_many = AsyncMock(return_value=[])

    assert await teams_user_administers(admin, prisma) == frozenset()
    prisma.db.litellm_teamtable.find_many.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_malformed_team_row_is_skipped_not_fatal():
    """One bad row must not deny every team admin access to every credential."""
    caller = UserAPIKeyAuth(user_role=LitellmUserRoles.INTERNAL_USER, api_key="sk-l", user_id="lead")
    rows = [
        MagicMock(model_dump=lambda: {"team_id": None, "members_with_roles": []}),
        MagicMock(model_dump=lambda: {"team_id": "team-a", "members_with_roles": [Member(user_id="lead", role="admin").model_dump()]}),
    ]
    prisma = MagicMock()
    prisma.db.litellm_teamtable.find_many = AsyncMock(return_value=rows)

    assert await teams_user_administers(caller, prisma) == frozenset({"team-a"})


@pytest.mark.asyncio
async def test_every_row_malformed_yields_an_empty_set_not_an_exception():
    caller = UserAPIKeyAuth(user_role=LitellmUserRoles.INTERNAL_USER, api_key="sk-l", user_id="lead")
    rows = [
        MagicMock(model_dump=lambda: {"team_id": None, "members_with_roles": []}),
        MagicMock(model_dump=lambda: {"team_id": "team-b", "members_with_roles": [{"user_id": "lead", "role": "owner"}]}),
    ]
    prisma = MagicMock()
    prisma.db.litellm_teamtable.find_many = AsyncMock(return_value=rows)

    assert await teams_user_administers(caller, prisma) == frozenset()
