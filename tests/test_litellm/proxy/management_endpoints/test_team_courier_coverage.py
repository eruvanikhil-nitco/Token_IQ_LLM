from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from token_iq.gateway.proxy._types import LitellmUserRoles, UserAPIKeyAuth
from token_iq.gateway.proxy.management_endpoints.team_endpoints import team_courier_coverage

ADMIN = UserAPIKeyAuth(user_role=LitellmUserRoles.PROXY_ADMIN, api_key="sk-admin", user_id="admin")

DEPLOYMENTS = (
    {"model_name": "or-gpt", "litellm_params": {"model": "openrouter/openai/gpt-4o-mini"}},
    {"model_name": "haiku", "litellm_params": {"model": "anthropic/claude-haiku-4-5"}},
)


def _team(**overrides):
    row = {
        "team_id": "t1",
        "models": [],
        "api_access_mode": "both",
        "blocked": False,
        **overrides,
    }
    return SimpleNamespace(model_dump=lambda: row)


def _prisma(team_row, unbound_key_count: int = 0):
    client = MagicMock()
    client.db.litellm_teamtable.find_unique = AsyncMock(return_value=team_row)
    client.db.litellm_verificationtoken.count = AsyncMock(return_value=unbound_key_count)
    return client


async def _call(team_row, *, unbound_key_count: int = 0, deployments=DEPLOYMENTS):
    router = SimpleNamespace(get_model_list=lambda: list(deployments))
    with (
        patch("token_iq.gateway.proxy.proxy_server.prisma_client", _prisma(team_row, unbound_key_count)),
        patch("token_iq.gateway.proxy.proxy_server.llm_router", router),
    ):
        return await team_courier_coverage(team_id="t1", user_api_key_dict=ADMIN)


@pytest.mark.asyncio
async def test_only_the_providers_this_team_can_reach_are_reported():
    """A warning about a provider the team was never granted is noise, and an admin who
    learns to skim these will skim the one that mattered."""
    result = await _call(_team(models=["or-gpt"]))

    assert [entry.provider for entry in result.providers] == ["openrouter"]


@pytest.mark.asyncio
async def test_a_team_granted_everything_sees_every_provider():
    result = await _call(_team(models=["*"]))

    assert [entry.provider for entry in result.providers] == ["anthropic", "openrouter"]


@pytest.mark.asyncio
async def test_keys_that_name_no_account_are_counted():
    """This is the number the panel warns on. A key naming no account is charged to
    whichever account the gateway finds first, which for a customer holding both a
    production and a test account at one provider may not be the one they chose."""
    result = await _call(_team(models=["*"]), unbound_key_count=3)

    assert result.unbound_key_count == 3


@pytest.mark.asyncio
async def test_the_teams_stored_setting_is_returned_rather_than_assumed():
    """The panel renders the switch from this. Defaulting it would show an admin the
    opposite of what their team is actually doing."""
    result = await _call(_team(api_access_mode="courier"))

    assert result.api_access_mode == "courier"


@pytest.mark.asyncio
async def test_a_provider_that_would_record_no_cost_is_reported_as_such():
    result = await _call(
        _team(models=["*"]),
        deployments=({"model_name": "v", "litellm_params": {"model": "voyage/voyage-3"}},),
    )

    assert result.providers[0].is_covered is False


@pytest.mark.asyncio
async def test_a_missing_team_is_a_404_rather_than_an_empty_report():
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        await _call(None)

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_someone_outside_the_team_cannot_read_its_coverage():
    """Coverage names the team's providers and how many of its keys are misconfigured,
    which is not something one customer's team should learn about another's."""
    from fastapi import HTTPException

    outsider = UserAPIKeyAuth(user_role=LitellmUserRoles.INTERNAL_USER, api_key="sk-other", user_id="other")
    router = SimpleNamespace(get_model_list=lambda: list(DEPLOYMENTS))
    with (
        patch("token_iq.gateway.proxy.proxy_server.prisma_client", _prisma(_team(models=["*"]))),
        patch("token_iq.gateway.proxy.proxy_server.llm_router", router),
        pytest.raises(HTTPException) as exc,
    ):
        await team_courier_coverage(team_id="t1", user_api_key_dict=outsider)

    assert exc.value.status_code == 403


class TestCourierModeSurvivesTheUpdateEndpoint:
    """Fourth instance of one defect: a courier field defined on the wrong model, accepted
    with a 200 and silently dropped. Every unit test passed each time, and only a real
    request through the endpoint showed the stored value unchanged. The admin panel's
    switch calls /team/update, so without this the switch is decorative."""

    def test_the_update_request_carries_the_mode(self):
        from token_iq.gateway.proxy._types import UpdateTeamRequest

        assert UpdateTeamRequest(team_id="t1", api_access_mode="courier").api_access_mode == "courier"

    def test_an_update_that_does_not_mention_it_leaves_it_alone(self):
        """None and False mean different things here: not mentioned versus turn it off.
        Collapsing them would switch a team back to translating mode on any unrelated edit."""
        from token_iq.gateway.proxy._types import UpdateTeamRequest

        assert UpdateTeamRequest(team_id="t1").api_access_mode is None

    def test_the_field_reaches_the_bytes_the_update_writes(self):
        """The model accepting it is not enough. /team/update writes whatever
        `json(exclude_unset=True)` produces, so a field that survives validation but not
        that call is exactly the 200-and-drop this bug was."""
        from token_iq.gateway.proxy._types import UpdateTeamRequest

        written = UpdateTeamRequest(team_id="t1", api_access_mode="courier").json(exclude_unset=True)

        assert written["api_access_mode"] == "courier"

    def test_an_unrelated_edit_writes_nothing_about_api_access_mode(self):
        from token_iq.gateway.proxy._types import UpdateTeamRequest

        written = UpdateTeamRequest(team_id="t1", team_alias="renamed").json(exclude_unset=True)

        assert "api_access_mode" not in written
