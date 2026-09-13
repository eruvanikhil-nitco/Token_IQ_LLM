from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from litellm.proxy._types import LitellmUserRoles, NewProjectRequest, UserAPIKeyAuth

ADMIN = UserAPIKeyAuth(user_role=LitellmUserRoles.PROXY_ADMIN, api_key="sk-admin", user_id="admin")
OUTSIDER = UserAPIKeyAuth(user_role=LitellmUserRoles.INTERNAL_USER, api_key="sk-out", user_id="outsider")


def _team_row(team_id: str = "t1", members_with_roles: list | None = None) -> SimpleNamespace:
    row = {
        "team_id": team_id,
        "team_alias": "developer team",
        "models": [],
        "blocked": False,
        "members_with_roles": members_with_roles or [],
    }
    return SimpleNamespace(model_dump=lambda: row)


def _prisma(team_row: SimpleNamespace | None = None) -> MagicMock:
    client = MagicMock()
    client.db.litellm_teamtable.find_unique = AsyncMock(return_value=team_row if team_row is not None else _team_row())
    return client


@pytest.mark.asyncio
async def test_a_project_is_created_under_its_team():
    """A project with no team is an orphan the hierarchy cannot report on, which is why
    team_id is required on the request model rather than optional."""
    from litellm.proxy.management_endpoints.project_endpoints import new_project

    created = MagicMock(project_id="p1", project_alias="api-service", team_id="t1")
    with (
        patch("litellm.proxy.proxy_server.prisma_client", _prisma()),
        patch(
            "litellm.repositories.project_repository.ProjectRepository.create_project",
            AsyncMock(return_value=created),
        ) as create,
    ):
        result = await new_project(
            data=NewProjectRequest(project_alias="api-service", team_id="t1"),
            user_api_key_dict=ADMIN,
        )

    assert result.project_id == "p1"
    assert create.await_args.kwargs["team_id"] == "t1"
    assert create.await_args.kwargs["created_by"] == "admin"


@pytest.mark.asyncio
async def test_someone_outside_the_team_cannot_create_a_project_in_it():
    """Project permission derives from team permission. Without this, a member of any team
    could spend against another team's budget."""
    from fastapi import HTTPException

    from litellm.proxy.management_endpoints.project_endpoints import new_project

    with patch("litellm.proxy.proxy_server.prisma_client", _prisma()), pytest.raises(HTTPException) as exc:
        await new_project(
            data=NewProjectRequest(project_alias="sneaky", team_id="t1"),
            user_api_key_dict=OUTSIDER,
        )

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_a_team_admin_may_create_a_project_in_their_own_team():
    """Otherwise every project has to go through a proxy admin, which makes the hierarchy
    theatre rather than delegation."""
    from litellm.proxy._types import Member
    from litellm.proxy.management_endpoints.project_endpoints import new_project

    lead = UserAPIKeyAuth(user_role=LitellmUserRoles.INTERNAL_USER, api_key="sk-l", user_id="lead")
    team = _team_row(members_with_roles=[Member(user_id="lead", role="admin").model_dump()])
    created = MagicMock(project_id="p2", project_alias="batch", team_id="t1")

    with (
        patch("litellm.proxy.proxy_server.prisma_client", _prisma(team)),
        patch(
            "litellm.repositories.project_repository.ProjectRepository.create_project",
            AsyncMock(return_value=created),
        ),
    ):
        result = await new_project(
            data=NewProjectRequest(project_alias="batch", team_id="t1"), user_api_key_dict=lead
        )

    assert result.project_id == "p2"


@pytest.mark.asyncio
async def test_creating_under_a_team_that_does_not_exist_is_a_404():
    """A typo in team_id would otherwise create a project pointing at nothing, invisible in
    every hierarchy view."""
    from fastapi import HTTPException

    from litellm.proxy.management_endpoints.project_endpoints import new_project

    client = MagicMock()
    client.db.litellm_teamtable.find_unique = AsyncMock(return_value=None)

    with patch("litellm.proxy.proxy_server.prisma_client", client), pytest.raises(HTTPException) as exc:
        await new_project(data=NewProjectRequest(team_id="ghost"), user_api_key_dict=ADMIN)

    assert exc.value.status_code == 404


def _project(project_id: str = "p1", team_id: str = "t1") -> MagicMock:
    return MagicMock(project_id=project_id, project_alias="api-service", team_id=team_id)


@pytest.mark.asyncio
async def test_a_member_of_the_owning_team_may_read_a_project():
    """These two routes are already in the internal-user allowlist, so the product has
    said a non-admin may call them."""
    from litellm.proxy.management_endpoints.project_endpoints import project_info

    member = UserAPIKeyAuth(user_role=LitellmUserRoles.INTERNAL_USER, api_key="sk-m", user_id="m", team_id="t1")
    with (
        patch("litellm.proxy.proxy_server.prisma_client", _prisma()),
        patch(
            "litellm.repositories.project_repository.ProjectRepository.find_by_id",
            AsyncMock(return_value=_project()),
        ),
    ):
        result = await project_info(project_id="p1", user_api_key_dict=member)

    assert result.project_id == "p1"


@pytest.mark.asyncio
async def test_reading_a_project_of_another_team_is_refused():
    from fastapi import HTTPException

    from litellm.proxy.management_endpoints.project_endpoints import project_info

    with (
        patch("litellm.proxy.proxy_server.prisma_client", _prisma()),
        patch(
            "litellm.repositories.project_repository.ProjectRepository.find_by_id",
            AsyncMock(return_value=_project()),
        ),
        pytest.raises(HTTPException) as exc,
    ):
        await project_info(project_id="p1", user_api_key_dict=OUTSIDER)

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_an_unknown_project_is_a_404_not_an_empty_object():
    from fastapi import HTTPException

    from litellm.proxy.management_endpoints.project_endpoints import project_info

    with (
        patch("litellm.proxy.proxy_server.prisma_client", _prisma()),
        patch(
            "litellm.repositories.project_repository.ProjectRepository.find_by_id",
            AsyncMock(return_value=None),
        ),
        pytest.raises(HTTPException) as exc,
    ):
        await project_info(project_id="ghost", user_api_key_dict=ADMIN)

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_listing_returns_only_the_named_team_s_projects():
    from litellm.proxy.management_endpoints.project_endpoints import project_list

    with (
        patch("litellm.proxy.proxy_server.prisma_client", _prisma()),
        patch(
            "litellm.repositories.project_repository.ProjectRepository.find_by_team_id",
            AsyncMock(return_value=[_project("p1"), _project("p2")]),
        ) as by_team,
    ):
        result = await project_list(team_id="t1", user_api_key_dict=ADMIN)

    assert [p.project_id for p in result] == ["p1", "p2"]
    assert by_team.await_args.args[0] == "t1"


@pytest.mark.asyncio
async def test_listing_another_team_s_projects_is_refused_not_empty():
    """An empty list is indistinguishable from a team with no projects, which hides a
    permissions problem from whoever has to debug it."""
    from fastapi import HTTPException

    from litellm.proxy.management_endpoints.project_endpoints import project_list

    with patch("litellm.proxy.proxy_server.prisma_client", _prisma()), pytest.raises(HTTPException) as exc:
        await project_list(team_id="t1", user_api_key_dict=OUTSIDER)

    assert exc.value.status_code == 403
