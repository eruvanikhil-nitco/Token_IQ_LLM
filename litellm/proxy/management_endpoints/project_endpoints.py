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
    UserAPIKeyAuth,
)
from litellm.proxy.auth.user_api_key_auth import user_api_key_auth
from litellm.proxy.management_endpoints.common_utils import _is_user_team_admin
from litellm.repositories.project_repository import ProjectRepository

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
