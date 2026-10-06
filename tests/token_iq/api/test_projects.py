from __future__ import annotations

from types import SimpleNamespace
from typing import Final
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from token_iq.gateway.proxy._types import GatewayUserRoles, NewProjectRequest, UserAPIKeyAuth

ADMIN = UserAPIKeyAuth(user_role=GatewayUserRoles.PROXY_ADMIN, api_key="sk-admin", user_id="admin")
OUTSIDER = UserAPIKeyAuth(user_role=GatewayUserRoles.INTERNAL_USER, api_key="sk-out", user_id="outsider")
VIEWER = UserAPIKeyAuth(user_role=GatewayUserRoles.PROXY_ADMIN_VIEW_ONLY, api_key="sk-view", user_id="viewer")


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


def _prisma_with_teams(*team_rows: SimpleNamespace) -> MagicMock:
    client = MagicMock()
    client.db.litellm_teamtable.find_many = AsyncMock(return_value=list(team_rows))
    return client


@pytest.mark.asyncio
async def test_a_project_is_created_under_its_team():
    """A project with no team is an orphan the hierarchy cannot report on, which is why
    team_id is required on the request model rather than optional."""
    from token_iq.api.projects import new_project

    created = MagicMock(project_id="p1", project_alias="api-service", team_id="t1")
    with (
        patch("token_iq.gateway.proxy.proxy_server.prisma_client", _prisma()),
        patch(
            "token_iq.gateway.repositories.project_repository.ProjectRepository.create_project",
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

    from token_iq.api.projects import new_project

    with patch("token_iq.gateway.proxy.proxy_server.prisma_client", _prisma()), pytest.raises(HTTPException) as exc:
        await new_project(
            data=NewProjectRequest(project_alias="sneaky", team_id="t1"),
            user_api_key_dict=OUTSIDER,
        )

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_a_team_admin_may_create_a_project_in_their_own_team():
    """Otherwise every project has to go through a proxy admin, which makes the hierarchy
    theatre rather than delegation."""
    from token_iq.gateway.proxy._types import Member
    from token_iq.api.projects import new_project

    lead = UserAPIKeyAuth(user_role=GatewayUserRoles.INTERNAL_USER, api_key="sk-l", user_id="lead")
    team = _team_row(members_with_roles=[Member(user_id="lead", role="admin").model_dump()])
    created = MagicMock(project_id="p2", project_alias="batch", team_id="t1")

    with (
        patch("token_iq.gateway.proxy.proxy_server.prisma_client", _prisma(team)),
        patch(
            "token_iq.gateway.repositories.project_repository.ProjectRepository.create_project",
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

    from token_iq.api.projects import new_project

    client = MagicMock()
    client.db.litellm_teamtable.find_unique = AsyncMock(return_value=None)

    with patch("token_iq.gateway.proxy.proxy_server.prisma_client", client), pytest.raises(HTTPException) as exc:
        await new_project(data=NewProjectRequest(team_id="ghost"), user_api_key_dict=ADMIN)

    assert exc.value.status_code == 404


def _project(project_id: str = "p1", team_id: str = "t1") -> MagicMock:
    return MagicMock(project_id=project_id, project_alias="api-service", team_id=team_id)


@pytest.mark.asyncio
async def test_a_member_of_the_owning_team_may_read_a_project():
    """These two routes are already in the internal-user allowlist, so the product has
    said a non-admin may call them."""
    from token_iq.api.projects import project_info

    member = UserAPIKeyAuth(user_role=GatewayUserRoles.INTERNAL_USER, api_key="sk-m", user_id="m", team_id="t1")
    with (
        patch("token_iq.gateway.proxy.proxy_server.prisma_client", _prisma()),
        patch(
            "token_iq.gateway.repositories.project_repository.ProjectRepository.find_by_id",
            AsyncMock(return_value=_project()),
        ),
    ):
        result = await project_info(project_id="p1", user_api_key_dict=member)

    assert result.project_id == "p1"


@pytest.mark.asyncio
async def test_reading_a_project_of_another_team_is_refused():
    from fastapi import HTTPException

    from token_iq.api.projects import project_info

    with (
        patch("token_iq.gateway.proxy.proxy_server.prisma_client", _prisma()),
        patch(
            "token_iq.gateway.repositories.project_repository.ProjectRepository.find_by_id",
            AsyncMock(return_value=_project()),
        ),
        pytest.raises(HTTPException) as exc,
    ):
        await project_info(project_id="p1", user_api_key_dict=OUTSIDER)

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_an_unknown_project_is_a_404_not_an_empty_object():
    from fastapi import HTTPException

    from token_iq.api.projects import project_info

    with (
        patch("token_iq.gateway.proxy.proxy_server.prisma_client", _prisma()),
        patch(
            "token_iq.gateway.repositories.project_repository.ProjectRepository.find_by_id",
            AsyncMock(return_value=None),
        ),
        pytest.raises(HTTPException) as exc,
    ):
        await project_info(project_id="ghost", user_api_key_dict=ADMIN)

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_listing_returns_only_the_named_team_s_projects():
    from token_iq.api.projects import project_list

    with (
        patch("token_iq.gateway.proxy.proxy_server.prisma_client", _prisma()),
        patch(
            "token_iq.gateway.repositories.project_repository.ProjectRepository.find_by_team_id",
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

    from token_iq.api.projects import project_list

    with patch("token_iq.gateway.proxy.proxy_server.prisma_client", _prisma()), pytest.raises(HTTPException) as exc:
        await project_list(team_id="t1", user_api_key_dict=OUTSIDER)

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_listing_without_a_team_shows_an_admin_every_project():
    """The Projects page asks for every project at once. Requiring a team made the page fail
    for everyone, admins included."""
    from token_iq.api.projects import project_list

    with (
        patch("token_iq.gateway.proxy.proxy_server.prisma_client", _prisma()),
        patch(
            "token_iq.gateway.repositories.project_repository.ProjectRepository.find_many",
            AsyncMock(return_value=[_project("p1", "t1"), _project("p2", "t2")]),
        ),
    ):
        result = await project_list(team_id=None, user_api_key_dict=ADMIN)

    assert [p.project_id for p in result] == ["p1", "p2"]


@pytest.mark.asyncio
async def test_listing_without_a_team_shows_a_team_admin_only_the_teams_they_run():
    from token_iq.gateway.proxy._types import Member
    from token_iq.api.projects import project_list

    lead = UserAPIKeyAuth(user_role=GatewayUserRoles.INTERNAL_USER, api_key="sk-l", user_id="lead")
    mine = _team_row("t1", members_with_roles=[Member(user_id="lead", role="admin").model_dump()])
    theirs = _team_row("t2", members_with_roles=[Member(user_id="someone-else", role="admin").model_dump()])
    by_teams = AsyncMock(return_value=[_project("p1", "t1")])

    with (
        patch("token_iq.gateway.proxy.proxy_server.prisma_client", _prisma_with_teams(mine, theirs)),
        patch("token_iq.gateway.repositories.project_repository.ProjectRepository.find_by_team_ids", by_teams),
    ):
        result = await project_list(team_id=None, user_api_key_dict=lead)

    assert [p.project_id for p in result] == ["p1"]
    assert by_teams.await_args.args[0] == ("t1",)


@pytest.mark.asyncio
async def test_listing_without_a_team_includes_the_team_the_caller_s_key_belongs_to():
    """A key's own team may already read one of its projects through /project/info, so the
    list has to agree with that rule."""
    from token_iq.api.projects import project_list

    member = UserAPIKeyAuth(user_role=GatewayUserRoles.INTERNAL_USER, api_key="sk-m", user_id="m", team_id="t2")
    by_teams = AsyncMock(return_value=[_project("p2", "t2")])

    with (
        patch("token_iq.gateway.proxy.proxy_server.prisma_client", _prisma_with_teams(_team_row("t1"), _team_row("t2"))),
        patch("token_iq.gateway.repositories.project_repository.ProjectRepository.find_by_team_ids", by_teams),
    ):
        await project_list(team_id=None, user_api_key_dict=member)

    assert by_teams.await_args.args[0] == ("t2",)


@pytest.mark.asyncio
async def test_listing_without_a_team_gives_an_outsider_nothing_without_querying_projects():
    from token_iq.api.projects import project_list

    by_teams = AsyncMock(return_value=[_project("p1", "t1")])

    with (
        patch("token_iq.gateway.proxy.proxy_server.prisma_client", _prisma_with_teams(_team_row("t1"))),
        patch("token_iq.gateway.repositories.project_repository.ProjectRepository.find_by_team_ids", by_teams),
    ):
        result = await project_list(team_id=None, user_api_key_dict=OUTSIDER)

    assert result == []
    by_teams.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_view_only_admin_may_read_a_project_but_not_change_it():
    """Admin viewers have read parity with proxy admins everywhere else in the dashboard."""
    from fastapi import HTTPException

    from token_iq.gateway.proxy._types import UpdateProjectRequest
    from token_iq.api.projects import project_info, update_project

    with (
        patch("token_iq.gateway.proxy.proxy_server.prisma_client", _prisma()),
        patch(
            "token_iq.gateway.repositories.project_repository.ProjectRepository.find_by_id",
            AsyncMock(return_value=_project()),
        ),
    ):
        read = await project_info(project_id="p1", user_api_key_dict=VIEWER)
        with pytest.raises(HTTPException) as exc:
            await update_project(data=UpdateProjectRequest(project_id="p1", blocked=True), user_api_key_dict=VIEWER)

    assert read.project_id == "p1"
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_unblocking_a_project_is_possible_because_an_error_message_promises_it():
    """auth_checks tells the owner of a blocked project to update it via this route. Until
    now that route did not exist, so the instruction was unfollowable."""
    from token_iq.gateway.proxy._types import UpdateProjectRequest
    from token_iq.api.projects import update_project

    with (
        patch("token_iq.gateway.proxy.proxy_server.prisma_client", _prisma()),
        patch(
            "token_iq.gateway.repositories.project_repository.ProjectRepository.find_by_id",
            AsyncMock(return_value=_project()),
        ),
        patch(
            "token_iq.gateway.repositories.project_repository.ProjectRepository.update_project",
            AsyncMock(return_value=_project()),
        ) as upd,
    ):
        await update_project(data=UpdateProjectRequest(project_id="p1", blocked=False), user_api_key_dict=ADMIN)

    assert upd.await_args.kwargs["blocked"] is False
    assert upd.await_args.kwargs["updated_by"] == "admin"


@pytest.mark.asyncio
async def test_a_field_not_sent_is_left_alone_rather_than_cleared():
    """A partial update that nulls everything it was not told about would wipe a project's
    model list on a rename."""
    from token_iq.gateway.proxy._types import UpdateProjectRequest
    from token_iq.api.projects import update_project

    with (
        patch("token_iq.gateway.proxy.proxy_server.prisma_client", _prisma()),
        patch(
            "token_iq.gateway.repositories.project_repository.ProjectRepository.find_by_id",
            AsyncMock(return_value=_project()),
        ),
        patch(
            "token_iq.gateway.repositories.project_repository.ProjectRepository.update_project",
            AsyncMock(return_value=_project()),
        ) as upd,
    ):
        await update_project(
            data=UpdateProjectRequest(project_id="p1", project_alias="renamed"), user_api_key_dict=ADMIN
        )

    assert upd.await_args.kwargs["project_alias"] == "renamed"
    assert upd.await_args.kwargs["models"] is None


@pytest.mark.asyncio
async def test_updating_another_team_s_project_is_refused():
    from fastapi import HTTPException

    from token_iq.gateway.proxy._types import UpdateProjectRequest
    from token_iq.api.projects import update_project

    with (
        patch("token_iq.gateway.proxy.proxy_server.prisma_client", _prisma()),
        patch(
            "token_iq.gateway.repositories.project_repository.ProjectRepository.find_by_id",
            AsyncMock(return_value=_project()),
        ),
        pytest.raises(HTTPException) as exc,
    ):
        await update_project(data=UpdateProjectRequest(project_id="p1", blocked=True), user_api_key_dict=OUTSIDER)

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_deleting_reports_which_projects_went():
    from token_iq.api.projects import ProjectDeleteRequest, delete_project

    with (
        patch("token_iq.gateway.proxy.proxy_server.prisma_client", _prisma()),
        patch(
            "token_iq.gateway.repositories.project_repository.ProjectRepository.find_by_id",
            AsyncMock(return_value=_project()),
        ),
        patch(
            "token_iq.gateway.repositories.project_repository.ProjectRepository.delete_project",
            AsyncMock(return_value=_project()),
        ),
    ):
        result = await delete_project(data=ProjectDeleteRequest(project_ids=["p1"]), user_api_key_dict=ADMIN)

    assert result == {"deleted_projects": ["p1"]}


@pytest.mark.asyncio
async def test_deleting_is_authorised_per_project_not_once_for_the_batch():
    """A batch containing one project the caller may delete and one they may not must
    refuse outright, not delete the first and then fail. The caller here genuinely
    administers t1 and genuinely does not administer t-other, so an interleaved
    authorise-then-delete loop would destroy p1 before refusing p2."""
    from fastapi import HTTPException

    from token_iq.gateway.proxy._types import Member
    from token_iq.api.projects import ProjectDeleteRequest, delete_project

    lead = UserAPIKeyAuth(user_role=GatewayUserRoles.INTERNAL_USER, api_key="sk-l", user_id="lead")
    mine = _team_row("t1", members_with_roles=[Member(user_id="lead", role="admin").model_dump()])
    theirs = _team_row("t-other")

    client = MagicMock()
    client.db.litellm_teamtable.find_unique = AsyncMock(side_effect=[mine, theirs])
    deleter = AsyncMock(return_value=_project())

    with (
        patch("token_iq.gateway.proxy.proxy_server.prisma_client", client),
        patch(
            "token_iq.gateway.repositories.project_repository.ProjectRepository.find_by_id",
            AsyncMock(side_effect=[_project("p1", "t1"), _project("p2", "t-other")]),
        ),
        patch("token_iq.gateway.repositories.project_repository.ProjectRepository.delete_project", deleter),
        pytest.raises(HTTPException) as exc,
    ):
        await delete_project(data=ProjectDeleteRequest(project_ids=["p1", "p2"]), user_api_key_dict=lead)

    assert exc.value.status_code == 403
    deleter.assert_not_awaited()


def _capture_daily_activity() -> tuple[dict, object]:
    recorded: dict = {}

    async def _capture(**kwargs):
        recorded.update(kwargs)
        return "report"

    return recorded, _capture


@pytest.mark.asyncio
async def test_daily_activity_reads_the_project_rollup_not_the_raw_spend_logs():
    from token_iq.api.projects import get_project_daily_activity

    recorded, capture = _capture_daily_activity()
    with (
        patch("token_iq.gateway.proxy.proxy_server.prisma_client", _prisma()),
        patch(
            "token_iq.gateway.repositories.project_repository.ProjectRepository.find_many",
            AsyncMock(return_value=[_project("p1"), _project("p2")]),
        ),
        patch("token_iq.api.projects.get_daily_activity", capture),
    ):
        result = await get_project_daily_activity(project_ids="p1", user_api_key_dict=ADMIN)

    assert result == "report"
    assert recorded["table_name"] == "litellm_dailyprojectspend"
    assert recorded["entity_id_field"] == "project_id"
    assert recorded["entity_id"] == ["p1"]
    assert recorded["entity_metadata_field"] == {"p1": {"project_alias": "api-service"}}


@pytest.mark.asyncio
async def test_daily_activity_without_named_projects_gives_an_admin_the_whole_total():
    """The Usage page's Project view opens before anything is picked and must show the total. Filtering
    to the projects that exist today would drop the spend of deleted projects and build an IN list as
    long as the project table."""
    from token_iq.api.projects import get_project_daily_activity

    recorded, capture = _capture_daily_activity()
    with (
        patch("token_iq.gateway.proxy.proxy_server.prisma_client", _prisma()),
        patch(
            "token_iq.gateway.repositories.project_repository.ProjectRepository.find_many",
            AsyncMock(return_value=(_project("p1"), _project("p2"))),
        ),
        patch("token_iq.api.projects.get_daily_activity", capture),
    ):
        await get_project_daily_activity(project_ids=None, user_api_key_dict=VIEWER)

    assert recorded["entity_id"] is None
    assert tuple(
        (project_id, metadata["project_alias"]) for project_id, metadata in recorded["entity_metadata_field"].items()
    ) == (("p1", "api-service"), ("p2", "api-service"))


@pytest.mark.asyncio
async def test_daily_activity_without_named_projects_gives_a_team_admin_only_their_projects():
    from token_iq.gateway.proxy._types import Member
    from token_iq.api.projects import get_project_daily_activity

    lead: Final = UserAPIKeyAuth(user_role=GatewayUserRoles.INTERNAL_USER, api_key="sk-l", user_id="lead")
    mine: Final = _team_row("t1", members_with_roles=(Member(user_id="lead", role="admin").model_dump(),))
    recorded, capture = _capture_daily_activity()
    with (
        patch("token_iq.gateway.proxy.proxy_server.prisma_client", _prisma_with_teams(mine, _team_row("t2"))),
        patch(
            "token_iq.gateway.repositories.project_repository.ProjectRepository.find_by_team_ids",
            AsyncMock(return_value=(_project("p1", "t1"),)),
        ),
        patch("token_iq.api.projects.get_daily_activity", capture),
    ):
        await get_project_daily_activity(project_ids=None, user_api_key_dict=lead)

    assert tuple(recorded["entity_id"]) == ("p1",)


@pytest.mark.asyncio
async def test_daily_activity_is_bucketed_in_the_caller_s_timezone():
    """The dashboard sends its timezone so a day in the chart is the caller's day, not a UTC day."""
    from token_iq.api.projects import get_project_daily_activity

    recorded, capture = _capture_daily_activity()
    with (
        patch("token_iq.gateway.proxy.proxy_server.prisma_client", _prisma()),
        patch(
            "token_iq.gateway.repositories.project_repository.ProjectRepository.find_many",
            AsyncMock(return_value=(_project("p1"),)),
        ),
        patch("token_iq.api.projects.get_daily_activity", capture),
    ):
        await get_project_daily_activity(project_ids="p1", timezone=-330, user_api_key_dict=ADMIN)

    assert recorded["timezone_offset_minutes"] == -330


@pytest.mark.asyncio
async def test_daily_activity_asking_for_a_readable_and_an_unreadable_project_is_refused_naming_the_unreadable_one():
    from fastapi import HTTPException

    from token_iq.gateway.proxy._types import Member
    from token_iq.api.projects import get_project_daily_activity

    lead: Final = UserAPIKeyAuth(user_role=GatewayUserRoles.INTERNAL_USER, api_key="sk-l", user_id="lead")
    mine: Final = _team_row("t1", members_with_roles=(Member(user_id="lead", role="admin").model_dump(),))
    report: Final = AsyncMock()
    with (
        patch("token_iq.gateway.proxy.proxy_server.prisma_client", _prisma_with_teams(mine, _team_row("t2"))),
        patch(
            "token_iq.gateway.repositories.project_repository.ProjectRepository.find_by_team_ids",
            AsyncMock(return_value=(_project("p1", "t1"),)),
        ),
        patch("token_iq.api.projects.get_daily_activity", report),
        pytest.raises(HTTPException) as exc,
    ):
        await get_project_daily_activity(project_ids="p1,p2", user_api_key_dict=lead)

    assert exc.value.status_code == 403
    assert "p2" in str(exc.value.detail)
    assert "p1" not in str(exc.value.detail)
    report.assert_not_awaited()


@pytest.mark.asyncio
async def test_daily_activity_for_a_caller_with_no_projects_filters_to_nothing_not_everything():
    """An empty id list reaches the query as an empty IN filter. Passing None instead would drop
    the filter and report every project's spend to someone who can read none of them."""
    from token_iq.api.projects import get_project_daily_activity

    recorded, capture = _capture_daily_activity()
    with (
        patch("token_iq.gateway.proxy.proxy_server.prisma_client", _prisma_with_teams(_team_row("t1"))),
        patch("token_iq.api.projects.get_daily_activity", capture),
    ):
        await get_project_daily_activity(project_ids=None, user_api_key_dict=OUTSIDER)

    assert recorded["entity_id"] == []


@pytest.mark.asyncio
async def test_daily_activity_of_a_project_the_caller_cannot_read_is_refused_not_empty():
    from fastapi import HTTPException

    from token_iq.api.projects import get_project_daily_activity

    with (
        patch("token_iq.gateway.proxy.proxy_server.prisma_client", _prisma_with_teams(_team_row("t1"))),
        pytest.raises(HTTPException) as exc,
    ):
        await get_project_daily_activity(project_ids="p1", user_api_key_dict=OUTSIDER)

    assert exc.value.status_code == 403
    assert "p1" in str(exc.value.detail)


@pytest.mark.asyncio
async def test_daily_activity_for_an_unknown_project_is_refused_without_confirming_it_exists():
    """Answering 404 for unknown ids and 403 for other teams' ids would let anyone probe which
    project ids exist."""
    from fastapi import HTTPException

    from token_iq.api.projects import get_project_daily_activity

    with (
        patch("token_iq.gateway.proxy.proxy_server.prisma_client", _prisma()),
        patch(
            "token_iq.gateway.repositories.project_repository.ProjectRepository.find_many",
            AsyncMock(return_value=[]),
        ),
        pytest.raises(HTTPException) as exc,
    ):
        await get_project_daily_activity(project_ids="ghost", user_api_key_dict=ADMIN)

    assert exc.value.status_code == 403
    assert "ghost" in str(exc.value.detail)


@pytest.mark.asyncio
async def test_attaching_a_budget_to_a_project_is_actually_saved():
    """/project/update answered 200 while dropping budget_id, which left the project
    budget check in auth_checks comparing spend against a budget nothing could set."""
    from token_iq.gateway.proxy._types import UpdateProjectRequest
    from token_iq.api.projects import update_project

    saved = AsyncMock(return_value=_project())
    with (
        patch("token_iq.gateway.proxy.proxy_server.prisma_client", _prisma()),
        patch(
            "token_iq.gateway.repositories.project_repository.ProjectRepository.find_by_id",
            AsyncMock(return_value=_project()),
        ),
        patch("token_iq.gateway.repositories.project_repository.ProjectRepository.update_project", saved),
    ):
        await update_project(
            data=UpdateProjectRequest(project_id="p1", budget_id="b-monthly"),
            user_api_key_dict=ADMIN,
        )

    assert saved.await_args.kwargs["budget_id"] == "b-monthly"


@pytest.mark.asyncio
async def test_a_view_only_admin_cannot_create_a_project():
    """The project write routes are open at the route layer to anyone, so the endpoint's own
    write check is the only thing standing between an admin viewer and a new project."""
    from fastapi import HTTPException

    from token_iq.api.projects import new_project

    create: Final = AsyncMock()
    with (
        patch("token_iq.gateway.proxy.proxy_server.prisma_client", _prisma()),
        patch("token_iq.gateway.repositories.project_repository.ProjectRepository.create_project", create),
        pytest.raises(HTTPException) as exc,
    ):
        await new_project(data=NewProjectRequest(project_alias="viewer-made", team_id="t1"), user_api_key_dict=VIEWER)

    assert exc.value.status_code == 403
    create.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_view_only_admin_cannot_delete_a_project():
    from fastapi import HTTPException

    from token_iq.api.projects import ProjectDeleteRequest, delete_project

    deleter: Final = AsyncMock()
    with (
        patch("token_iq.gateway.proxy.proxy_server.prisma_client", _prisma()),
        patch(
            "token_iq.gateway.repositories.project_repository.ProjectRepository.find_by_id",
            AsyncMock(return_value=_project()),
        ),
        patch("token_iq.gateway.repositories.project_repository.ProjectRepository.delete_project", deleter),
        pytest.raises(HTTPException) as exc,
    ):
        await delete_project(data=ProjectDeleteRequest(project_ids=("p1",)), user_api_key_dict=VIEWER)

    assert exc.value.status_code == 403
    deleter.assert_not_awaited()


def _lead_of_t1() -> tuple[UserAPIKeyAuth, SimpleNamespace]:
    from token_iq.gateway.proxy._types import Member

    lead: Final = UserAPIKeyAuth(user_role=GatewayUserRoles.INTERNAL_USER, api_key="sk-l", user_id="lead")
    return lead, _team_row("t1", members_with_roles=(Member(user_id="lead", role="admin").model_dump(),))


@pytest.mark.asyncio
async def test_a_team_admin_cannot_move_their_project_into_a_team_they_do_not_run():
    """Checking only the project's current team would let the admin of t1 hand a project, and
    the keys spending through it, to t2."""
    from fastapi import HTTPException

    from token_iq.gateway.proxy._types import UpdateProjectRequest
    from token_iq.api.projects import update_project

    lead, mine = _lead_of_t1()
    client: Final = MagicMock()
    client.db.litellm_teamtable.find_unique = AsyncMock(side_effect=(mine, _team_row("t2")))
    saved: Final = AsyncMock(return_value=_project())

    with (
        patch("token_iq.gateway.proxy.proxy_server.prisma_client", client),
        patch(
            "token_iq.gateway.repositories.project_repository.ProjectRepository.find_by_id",
            AsyncMock(return_value=_project("p1", "t1")),
        ),
        patch("token_iq.gateway.repositories.project_repository.ProjectRepository.update_project", saved),
        pytest.raises(HTTPException) as exc,
    ):
        await update_project(data=UpdateProjectRequest(project_id="p1", team_id="t2"), user_api_key_dict=lead)

    assert exc.value.status_code == 403
    assert "t2" in str(exc.value.detail)
    saved.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_proxy_admin_may_move_a_project_to_another_team():
    from token_iq.gateway.proxy._types import UpdateProjectRequest
    from token_iq.api.projects import update_project

    saved: Final = AsyncMock(return_value=_project("p1", "t2"))
    with (
        patch("token_iq.gateway.proxy.proxy_server.prisma_client", _prisma()),
        patch(
            "token_iq.gateway.repositories.project_repository.ProjectRepository.find_by_id",
            AsyncMock(return_value=_project("p1", "t1")),
        ),
        patch("token_iq.gateway.repositories.project_repository.ProjectRepository.update_project", saved),
    ):
        await update_project(data=UpdateProjectRequest(project_id="p1", team_id="t2"), user_api_key_dict=ADMIN)

    assert saved.await_args.kwargs["team_id"] == "t2"


@pytest.mark.asyncio
async def test_a_team_admin_cannot_attach_a_budget_when_creating_a_project():
    """Budgets are made on the admin-only Budgets page, so only a proxy admin decides which one
    a project spends against."""
    from fastapi import HTTPException

    from token_iq.api.projects import new_project

    lead, mine = _lead_of_t1()
    create: Final = AsyncMock()
    with (
        patch("token_iq.gateway.proxy.proxy_server.prisma_client", _prisma(mine)),
        patch("token_iq.gateway.repositories.project_repository.ProjectRepository.create_project", create),
        pytest.raises(HTTPException) as exc,
    ):
        await new_project(
            data=NewProjectRequest(project_alias="batch", team_id="t1", budget_id="b-big"), user_api_key_dict=lead
        )

    assert exc.value.status_code == 403
    assert "budget" in str(exc.value.detail)
    create.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_team_admin_cannot_attach_a_budget_when_updating_a_project():
    from fastapi import HTTPException

    from token_iq.gateway.proxy._types import UpdateProjectRequest
    from token_iq.api.projects import update_project

    lead, mine = _lead_of_t1()
    saved: Final = AsyncMock()
    with (
        patch("token_iq.gateway.proxy.proxy_server.prisma_client", _prisma(mine)),
        patch(
            "token_iq.gateway.repositories.project_repository.ProjectRepository.find_by_id",
            AsyncMock(return_value=_project("p1", "t1")),
        ),
        patch("token_iq.gateway.repositories.project_repository.ProjectRepository.update_project", saved),
        pytest.raises(HTTPException) as exc,
    ):
        await update_project(data=UpdateProjectRequest(project_id="p1", budget_id="b-big"), user_api_key_dict=lead)

    assert exc.value.status_code == 403
    assert "budget" in str(exc.value.detail)
    saved.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_team_admin_may_still_update_their_project_without_touching_the_budget():
    from token_iq.gateway.proxy._types import UpdateProjectRequest
    from token_iq.api.projects import update_project

    lead, mine = _lead_of_t1()
    saved: Final = AsyncMock(return_value=_project())
    with (
        patch("token_iq.gateway.proxy.proxy_server.prisma_client", _prisma(mine)),
        patch(
            "token_iq.gateway.repositories.project_repository.ProjectRepository.find_by_id",
            AsyncMock(return_value=_project("p1", "t1")),
        ),
        patch("token_iq.gateway.repositories.project_repository.ProjectRepository.update_project", saved),
    ):
        await update_project(
            data=UpdateProjectRequest(project_id="p1", team_id="t1", project_alias="renamed"), user_api_key_dict=lead
        )

    assert saved.await_args.kwargs["project_alias"] == "renamed"


@pytest.mark.asyncio
async def test_a_proxy_admin_may_attach_a_budget_when_creating_a_project():
    from token_iq.api.projects import new_project

    create: Final = AsyncMock(return_value=_project())
    with (
        patch("token_iq.gateway.proxy.proxy_server.prisma_client", _prisma()),
        patch("token_iq.gateway.repositories.project_repository.ProjectRepository.create_project", create),
    ):
        await new_project(data=NewProjectRequest(team_id="t1", budget_id="b-monthly"), user_api_key_dict=ADMIN)

    assert create.await_args.kwargs["budget_id"] == "b-monthly"
