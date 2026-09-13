"""Managing projects, the layer between a team and the keys that spend its budget.

Everything around this already existed: the table, the repository, the request models, and
the auth checks that block a project and enforce its budget. Only the endpoints were
missing, which left `/project/list` and `/project/info` allowlisted in the routes table and
answering 404, and left `auth_checks` telling a blocked project's owner to update it via
`/project/update` when no such route existed.

Project permission derives from team permission rather than inventing a parallel model: a
project belongs to exactly one team, so whoever administers that team administers its
projects.
"""

from __future__ import annotations

from typing import Any, Final

import fastapi
from fastapi import APIRouter, Depends, HTTPException, status

from litellm.proxy._types import (
    CommonProxyErrors,
    LiteLLM_TeamTable,
    LitellmUserRoles,
    NewProjectRequest,
    UpdateProjectRequest,
    UserAPIKeyAuth,
)
from litellm.proxy.auth.user_api_key_auth import user_api_key_auth
from litellm.proxy.management_endpoints.common_daily_activity import get_daily_activity
from litellm.proxy.management_endpoints.common_utils import _is_user_team_admin
from litellm.repositories.project_repository import ProjectRepository
from litellm.types.llms.base import LiteLLMPydanticObjectBase
from litellm.types.proxy.management_endpoints.common_daily_activity import (
    SpendAnalyticsPaginatedResponse,
)

router: Final = APIRouter()


def _prisma_or_500() -> Any:  # any-ok: PrismaClient is an untyped runtime wrapper
    from litellm.proxy.proxy_server import prisma_client

    if prisma_client is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": CommonProxyErrors.db_not_connected_error.value},
        )
    return prisma_client


async def _team_or_404(team_id: str, prisma_client: Any) -> LiteLLM_TeamTable:  # any-ok: untyped wrapper
    row: Final = await prisma_client.db.litellm_teamtable.find_unique(where={"team_id": team_id})
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": f"Team not found, passed team id: {team_id}."},
        )
    return LiteLLM_TeamTable.model_validate(row.model_dump())


async def _authorised_team_or_403(
    team_id: str,
    user_api_key_dict: UserAPIKeyAuth,
    prisma_client: Any,  # any-ok: untyped wrapper
    *,
    write: bool,
) -> LiteLLM_TeamTable:
    """The team this project belongs to, or a refusal.

    A caller with no relationship to the team is refused rather than shown nothing: an
    empty result is indistinguishable from a team with no projects, and hides the
    permissions problem from whoever has to debug it.
    """
    team: Final = await _team_or_404(team_id, prisma_client)
    if user_api_key_dict.user_role == LitellmUserRoles.PROXY_ADMIN:
        return team
    if _is_user_team_admin(user_api_key_dict=user_api_key_dict, team_obj=team):
        return team
    if not write and user_api_key_dict.team_id == team_id:
        return team
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"error": f"You do not administer team {team_id}, so you cannot manage its projects."},
    )


@router.post("/project/new", tags=["project management"], dependencies=[Depends(user_api_key_auth)])
async def new_project(
    data: NewProjectRequest,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    """Create a project under a team."""
    prisma_client: Final = _prisma_or_500()
    await _authorised_team_or_403(data.team_id, user_api_key_dict, prisma_client, write=True)

    return await ProjectRepository(prisma_client).create_project(
        created_by=user_api_key_dict.user_id or "unknown",
        project_id=data.project_id,
        project_alias=data.project_alias,
        description=data.description,
        team_id=data.team_id,
        budget_id=data.budget_id,
        metadata=data.metadata,
        models=data.models,
        model_rpm_limit=data.model_rpm_limit,
        model_tpm_limit=data.model_tpm_limit,
    )


@router.get("/project/info", tags=["project management"], dependencies=[Depends(user_api_key_auth)])
async def project_info(
    project_id: str = fastapi.Query(description="The project to read"),
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    """One project, if the caller belongs to the team that owns it."""
    prisma_client: Final = _prisma_or_500()
    project: Final = await ProjectRepository(prisma_client).find_by_id(project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": f"Project not found, passed project id: {project_id}."},
        )
    await _authorised_team_or_403(project.team_id or "", user_api_key_dict, prisma_client, write=False)
    return project


@router.get("/project/list", tags=["project management"], dependencies=[Depends(user_api_key_auth)])
async def project_list(
    team_id: str = fastapi.Query(description="List the projects of this team"),
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    """Every project under one team."""
    prisma_client: Final = _prisma_or_500()
    await _authorised_team_or_403(team_id, user_api_key_dict, prisma_client, write=False)
    return await ProjectRepository(prisma_client).find_by_team_id(team_id)


class ProjectDeleteRequest(LiteLLMPydanticObjectBase):
    """Request model for POST /project/delete"""

    project_ids: list[str]


async def _authorised_project_or_403(
    project_id: str,
    user_api_key_dict: UserAPIKeyAuth,
    prisma_client: Any,  # any-ok: untyped wrapper
    *,
    write: bool,
):
    """The project, once the caller is shown to administer its team."""
    project: Final = await ProjectRepository(prisma_client).find_by_id(project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": f"Project not found, passed project id: {project_id}."},
        )
    await _authorised_team_or_403(project.team_id or "", user_api_key_dict, prisma_client, write=write)
    return project


@router.post("/project/update", tags=["project management"], dependencies=[Depends(user_api_key_auth)])
async def update_project(
    data: UpdateProjectRequest,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    """Change a project. Fields left out are untouched, not cleared."""
    prisma_client: Final = _prisma_or_500()
    await _authorised_project_or_403(data.project_id, user_api_key_dict, prisma_client, write=True)

    return await ProjectRepository(prisma_client).update_project(
        project_id=data.project_id,
        updated_by=user_api_key_dict.user_id or "unknown",
        project_alias=data.project_alias,
        description=data.description,
        team_id=data.team_id,
        budget_id=data.budget_id,
        metadata=data.metadata,
        models=data.models,
        model_rpm_limit=data.model_rpm_limit,
        model_tpm_limit=data.model_tpm_limit,
        blocked=data.blocked,
    )


@router.post("/project/delete", tags=["project management"], dependencies=[Depends(user_api_key_auth)])
async def delete_project(
    data: ProjectDeleteRequest,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    """Delete projects. Every one is authorised before any is deleted."""
    prisma_client: Final = _prisma_or_500()
    for project_id in data.project_ids:
        await _authorised_project_or_403(project_id, user_api_key_dict, prisma_client, write=True)

    repository: Final = ProjectRepository(prisma_client)
    for project_id in data.project_ids:
        await repository.delete_project(project_id)
    return {"deleted_projects": list(data.project_ids)}


@router.get(
    "/project/daily/activity",
    response_model=SpendAnalyticsPaginatedResponse,
    tags=["project management"],
    dependencies=[Depends(user_api_key_auth)],
)
async def get_project_daily_activity(
    project_id: str = fastapi.Query(description="The project to report on"),
    start_date: str | None = None,
    end_date: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    page: int = 1,
    page_size: int = 10,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    """What one project spent, by day.

    Reads the project's daily rollup rather than the raw spend logs, so the cost of a
    report does not grow with the number of requests the project has made.
    """
    prisma_client: Final = _prisma_or_500()
    project: Final = await _authorised_project_or_403(project_id, user_api_key_dict, prisma_client, write=False)

    return await get_daily_activity(
        prisma_client=prisma_client,
        table_name="litellm_dailyprojectspend",
        entity_id_field="project_id",
        entity_id=project_id,
        entity_metadata_field={project_id: {"project_alias": project.project_alias}},
        start_date=start_date,
        end_date=end_date,
        model=model,
        api_key=api_key,
        page=page,
        page_size=page_size,
    )
