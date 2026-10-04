# Project Management Endpoints Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose the project layer over the API, so the organisation → team → project half of the hierarchy can be managed without touching the database.

**Architecture:** A thin endpoint module over the existing `ProjectRepository`. Everything above and below this layer already exists: the table, the repository CRUD, the request models, the auth checks that block a project and enforce its budget, and the dashboard page. Only the endpoints are missing, and two of them are already allowlisted in the routes table, so they return 404 to callers the product says may reach them.

**Tech Stack:** Python 3.12, FastAPI, Prisma/Postgres, pytest.

**Spec:** No separate spec. The design rationale is in this header and in "Why this shape" below; the hierarchy it completes is described in `docs/superpowers/specs/2026-09-13-provider-billing-ingestion-design.md` under attribution.

## Global Constraints

- Python max line length 120. All Python work uses `C:\Users\NikhilEruva\litellm\.venv`, never system Python.
- No comments except genuinely complex business logic, tool directives, or a TODO/FIXME with a reason.
- Model failures as values where practical; endpoints raise `HTTPException` because that is this codebase's public error contract for management routes.
- Annotate variables `: Final` (LIT010). No rebinding parameters (LIT011). No `Any` or bare `dict` in new signatures.
- Never put a customer or company name in code, commits, or docs.
- Commit after every task.
- `tests/test_litellm/` mirrors `litellm/` in a parallel path. New endpoint module gets a new mapped test file.
- Every management endpoint takes `user_api_key_auth` as a dependency and authorises explicitly inside the handler. A route being reachable is not authorisation.

---

## Why this shape

Three facts from the codebase drive every decision below.

**The scaffolding already exists and is unused.** `NewProjectRequest` and `UpdateProjectRequest` sit in `litellm/proxy/_types.py` with docstrings that read "Request model for POST /project/new" and "/project/update". They are imported by `management_endpoints/common_utils.py`, re-exported in its `__all__`, and never called by anything. `ProjectRepository` has `create_project`, `update_project`, `delete_project`, `find_by_id`, `find_by_alias` and `find_by_team_id`, all written and all unreachable.

**Two routes are allowlisted but unimplemented.** `/project/list` and `/project/info` appear in the internal-user route allowlist in `_types.py`. The product therefore already says a non-admin user may call them, and they 404. Implementing those two is a bug fix as much as a feature.

**Projects are already enforced in the request path.** `auth_checks.py` refuses a request when `project_object.blocked` is true and raises when a project's budget is exceeded, and it says "Update via `/project/update` if you're an admin" in the failure message, pointing at an endpoint that does not exist. So a customer can hit a project block today with no documented way out.

That last one decides the ordering: `/project/update` matters more than it looks, because an error message already promises it.

## Authorisation model

A project belongs to a team, so project permission derives from team permission rather than inventing a parallel model.

| Action | Who |
|---|---|
| create, update, delete | proxy admin, or an admin of the project's team |
| info, list | proxy admin, team admin, or a member of the owning team |

`_is_user_team_admin(user_api_key_dict, team_obj)` in `management_endpoints/common_utils.py` is the existing helper for the team-admin half. A caller with no relationship to the team gets 403, not an empty list, because an empty list is indistinguishable from "the team has no projects" and hides a permissions problem.

## Scope, and what follows

This plan is the endpoints only. Two follow-on plans, each shippable on its own:

1. **Daily project spend rollup.** Organisation, Team, User, EndUser, Tag, Agent and Tool all have a `LiteLLM_Daily*Spend` table. Projects do not, so every project cost screen would scan raw spend logs. That plan touches the spend-write pipeline and deserves its own review.
2. **Person as a spend scope.** Joining provider-side per-user data, Claude Code and Copilot, to organisation members by email. Genuinely new, and the only way the employee half of the hierarchy gets real numbers.

---

## File Structure

| File | Responsibility |
|---|---|
| `litellm/proxy/management_endpoints/project_endpoints.py` | All five project routes and their authorisation |
| `litellm/proxy/proxy_server.py` | Register the router |
| `tests/test_litellm/proxy/management_endpoints/test_project_endpoints.py` | Tests for all five |

One module, because five small routes over one repository is not a package. It follows `team_endpoints.py` in shape while staying a fraction of its size.

---

### Task 1: Create a project

**Files:**
- Create: `litellm/proxy/management_endpoints/project_endpoints.py`
- Modify: `litellm/proxy/proxy_server.py`
- Test: `tests/test_litellm/proxy/management_endpoints/test_project_endpoints.py`

**Interfaces:**
- Consumes: `ProjectRepository` from `litellm.repositories.project_repository`, `NewProjectRequest` from `litellm.proxy._types`, `_is_user_team_admin` from `litellm.proxy.management_endpoints.common_utils`
- Produces: `router` (APIRouter), `async def new_project(data, user_api_key_dict) -> LiteLLM_ProjectTable`, and `async def _authorised_team_or_403(team_id, user_api_key_dict, prisma_client) -> LiteLLM_TeamTable` used by Tasks 2 to 4

- [ ] **Step 1: Write the failing test**

Create `tests/test_litellm/proxy/management_endpoints/test_project_endpoints.py`:

```python
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
    client.db.litellm_teamtable.find_unique = AsyncMock(return_value=team_row or _team_row())
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
    """Project permission derives from team permission. Without this a member of any team
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
    """A typo in team_id would otherwise create a project pointing at nothing, invisible
    in every hierarchy view."""
    from fastapi import HTTPException

    from litellm.proxy.management_endpoints.project_endpoints import new_project

    client = MagicMock()
    client.db.litellm_teamtable.find_unique = AsyncMock(return_value=None)

    with patch("litellm.proxy.proxy_server.prisma_client", client), pytest.raises(HTTPException) as exc:
        await new_project(data=NewProjectRequest(team_id="ghost"), user_api_key_dict=ADMIN)

    assert exc.value.status_code == 404
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_litellm/proxy/management_endpoints/test_project_endpoints.py -q -p no:randomly`
Expected: FAIL, `ModuleNotFoundError: No module named 'litellm.proxy.management_endpoints.project_endpoints'`

- [ ] **Step 3: Write the module**

Create `litellm/proxy/management_endpoints/project_endpoints.py`:

```python
"""Managing projects, the layer between a team and the keys that spend its budget.

Everything around this already existed: the table, the repository, the request models,
and the auth checks that block a project and enforce its budget. Only the endpoints were
missing, which left `/project/list` and `/project/info` allowlisted in the routes table
and answering 404, and left `auth_checks` telling a blocked project's owner to "update via
/project/update" when no such route existed.

Project permission derives from team permission rather than inventing a parallel model: a
project belongs to exactly one team, so whoever administers that team administers its
projects.
"""

from __future__ import annotations

from typing import Final

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


def _prisma_or_500() -> object:
    from litellm.proxy.proxy_server import prisma_client

    if prisma_client is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": CommonProxyErrors.db_not_connected_error.value},
        )
    return prisma_client


async def _team_or_404(team_id: str, prisma_client: object) -> LiteLLM_TeamTable:
    row: Final = await prisma_client.db.litellm_teamtable.find_unique(  # pyright: ignore[reportAttributeAccessIssue]  # untyped runtime wrapper
        where={"team_id": team_id}
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": f"Team not found, passed team id: {team_id}."},
        )
    return LiteLLM_TeamTable.model_validate(row.model_dump())


async def _authorised_team_or_403(
    team_id: str, user_api_key_dict: UserAPIKeyAuth, prisma_client: object, *, write: bool
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
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_litellm/proxy/management_endpoints/test_project_endpoints.py -q -p no:randomly`
Expected: `4 passed`

- [ ] **Step 5: Register the router**

In `litellm/proxy/proxy_server.py`, beside the other management router imports:

```python
from litellm.proxy.management_endpoints.project_endpoints import router as project_router
```

and beside `app.include_router(team_router)`:

```python
app.include_router(project_router)
```

- [ ] **Step 6: Verify the route mounts**

Run:
```bash
.venv/Scripts/python.exe -c "from litellm.proxy.proxy_server import app; print([r.path for r in app.routes if getattr(r,'path','').startswith('/project')])"
```
Expected: `['/project/new']`

- [ ] **Step 7: Prove the authorisation check has teeth**

Comment out the `raise HTTPException(...403...)` in `_authorised_team_or_403`, re-run,
confirm `test_someone_outside_the_team_cannot_create_a_project_in_it` FAILS, then restore.

- [ ] **Step 8: Commit**

```bash
git add litellm/proxy/management_endpoints/project_endpoints.py litellm/proxy/proxy_server.py tests/test_litellm/proxy/management_endpoints/test_project_endpoints.py
git commit -m "feat(projects): create a project over the API"
```

---

### Task 2: Read a project, and list a team's projects

**Files:**
- Modify: `litellm/proxy/management_endpoints/project_endpoints.py`
- Test: `tests/test_litellm/proxy/management_endpoints/test_project_endpoints.py` (extend)

**Interfaces:**
- Consumes: `_authorised_team_or_403`, `_prisma_or_500` from Task 1
- Produces: `async def project_info(project_id, user_api_key_dict)`, `async def project_list(team_id, user_api_key_dict)`

These are the two already allowlisted in `LiteLLMRoutes` and currently answering 404.

- [ ] **Step 1: Write the failing tests**

Append to the test file:

```python
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
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_litellm/proxy/management_endpoints/test_project_endpoints.py -q -p no:randomly`
Expected: FAIL, `ImportError: cannot import name 'project_info'`

- [ ] **Step 3: Add the two read routes**

Append to `litellm/proxy/management_endpoints/project_endpoints.py`:

```python
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
```

- [ ] **Step 4: Run to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_litellm/proxy/management_endpoints/test_project_endpoints.py -q -p no:randomly`
Expected: `9 passed`

- [ ] **Step 5: Confirm the allowlisted routes now exist**

Run:
```bash
.venv/Scripts/python.exe -c "
from litellm.proxy._types import LiteLLMRoutes
from litellm.proxy.proxy_server import app
mounted = {r.path for r in app.routes if getattr(r,'path','').startswith('/project')}
allowlisted = {r for r in LiteLLMRoutes.internal_user_routes.value if str(r).startswith('/project')}
print('mounted:', sorted(mounted))
print('allowlisted but missing:', sorted(allowlisted - mounted))
"
```
Expected: `allowlisted but missing: []`

- [ ] **Step 6: Commit**

```bash
git add litellm/proxy/management_endpoints/project_endpoints.py tests/test_litellm/proxy/management_endpoints/test_project_endpoints.py
git commit -m "feat(projects): implement the two routes that were already allowlisted"
```

---

### Task 3: Update and delete a project

**Files:**
- Modify: `litellm/proxy/management_endpoints/project_endpoints.py`
- Test: `tests/test_litellm/proxy/management_endpoints/test_project_endpoints.py` (extend)

**Interfaces:**
- Consumes: `_authorised_team_or_403`, `_prisma_or_500` from Task 1
- Produces: `async def update_project(data, user_api_key_dict)`, `async def delete_project(data, user_api_key_dict)`
- `delete_project` takes `ProjectDeleteRequest` with field `project_ids: list[str]`, matching `/team/delete`

`auth_checks.py` already tells a blocked project's owner to "Update via `/project/update` if
you're an admin", so this route is referenced by an error message that ships today.

- [ ] **Step 1: Write the failing tests**

Append to the test file:

```python
@pytest.mark.asyncio
async def test_unblocking_a_project_is_possible_because_an_error_message_promises_it():
    """auth_checks tells the owner of a blocked project to update it via this route. Until
    now that route did not exist, so the instruction was unfollowable."""
    from litellm.proxy._types import UpdateProjectRequest
    from litellm.proxy.management_endpoints.project_endpoints import update_project

    with (
        patch("litellm.proxy.proxy_server.prisma_client", _prisma()),
        patch(
            "litellm.repositories.project_repository.ProjectRepository.find_by_id",
            AsyncMock(return_value=_project()),
        ),
        patch(
            "litellm.repositories.project_repository.ProjectRepository.update_project",
            AsyncMock(return_value=_project()),
        ) as upd,
    ):
        await update_project(
            data=UpdateProjectRequest(project_id="p1", blocked=False), user_api_key_dict=ADMIN
        )

    assert upd.await_args.kwargs["blocked"] is False
    assert upd.await_args.kwargs["updated_by"] == "admin"


@pytest.mark.asyncio
async def test_a_field_not_sent_is_left_alone_rather_than_cleared():
    """A partial update that nulls everything it was not told about would wipe a project's
    model list on a rename."""
    from litellm.proxy._types import UpdateProjectRequest
    from litellm.proxy.management_endpoints.project_endpoints import update_project

    with (
        patch("litellm.proxy.proxy_server.prisma_client", _prisma()),
        patch(
            "litellm.repositories.project_repository.ProjectRepository.find_by_id",
            AsyncMock(return_value=_project()),
        ),
        patch(
            "litellm.repositories.project_repository.ProjectRepository.update_project",
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

    from litellm.proxy._types import UpdateProjectRequest
    from litellm.proxy.management_endpoints.project_endpoints import update_project

    with (
        patch("litellm.proxy.proxy_server.prisma_client", _prisma()),
        patch(
            "litellm.repositories.project_repository.ProjectRepository.find_by_id",
            AsyncMock(return_value=_project()),
        ),
        pytest.raises(HTTPException) as exc,
    ):
        await update_project(
            data=UpdateProjectRequest(project_id="p1", blocked=True), user_api_key_dict=OUTSIDER
        )

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_deleting_reports_which_projects_went():
    from litellm.proxy.management_endpoints.project_endpoints import ProjectDeleteRequest, delete_project

    with (
        patch("litellm.proxy.proxy_server.prisma_client", _prisma()),
        patch(
            "litellm.repositories.project_repository.ProjectRepository.find_by_id",
            AsyncMock(return_value=_project()),
        ),
        patch(
            "litellm.repositories.project_repository.ProjectRepository.delete_project",
            AsyncMock(return_value=_project()),
        ),
    ):
        result = await delete_project(
            data=ProjectDeleteRequest(project_ids=["p1"]), user_api_key_dict=ADMIN
        )

    assert result == {"deleted_projects": ["p1"]}


@pytest.mark.asyncio
async def test_deleting_is_authorised_per_project_not_once_for_the_batch():
    """A batch containing one project the caller may delete and one they may not must
    refuse, not delete the first and then fail."""
    from fastapi import HTTPException

    from litellm.proxy.management_endpoints.project_endpoints import ProjectDeleteRequest, delete_project

    deleter = AsyncMock(return_value=_project())
    with (
        patch("litellm.proxy.proxy_server.prisma_client", _prisma()),
        patch(
            "litellm.repositories.project_repository.ProjectRepository.find_by_id",
            AsyncMock(side_effect=[_project("p1", "t1"), _project("p2", "t-other")]),
        ),
        patch("litellm.repositories.project_repository.ProjectRepository.delete_project", deleter),
        pytest.raises(HTTPException),
    ):
        await delete_project(
            data=ProjectDeleteRequest(project_ids=["p1", "p2"]),
            user_api_key_dict=UserAPIKeyAuth(
                user_role=LitellmUserRoles.INTERNAL_USER, api_key="sk-l", user_id="lead", team_id="t1"
            ),
        )

    deleter.assert_not_awaited()
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_litellm/proxy/management_endpoints/test_project_endpoints.py -q -p no:randomly`
Expected: FAIL, `ImportError: cannot import name 'update_project'`

- [ ] **Step 3: Add the write routes**

Append to `litellm/proxy/management_endpoints/project_endpoints.py`:

```python
class ProjectDeleteRequest(LiteLLMPydanticObjectBase):
    """Request model for POST /project/delete"""

    project_ids: list[str]


async def _authorised_project_or_403(
    project_id: str, user_api_key_dict: UserAPIKeyAuth, prisma_client: object, *, write: bool
):
    """The project, once the caller is shown to administer its team."""
    project = await ProjectRepository(prisma_client).find_by_id(project_id)
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
```

Add to the imports at the top of the module:

```python
from litellm.proxy._types import UpdateProjectRequest
from litellm.types.llms.base import LiteLLMPydanticObjectBase
```

`UpdateProjectRequest` needs a `blocked` field. Check `litellm/proxy/_types.py`: if the
class has no `blocked: bool | None = None`, add it, since unblocking is the reason this
route is referenced by an error message.

- [ ] **Step 4: Run to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_litellm/proxy/management_endpoints/test_project_endpoints.py -q -p no:randomly`
Expected: `14 passed`

- [ ] **Step 5: Prove the batch authorisation has teeth**

Move the delete loop inside the authorisation loop so each project is deleted as it is
checked, re-run, confirm `test_deleting_is_authorised_per_project_not_once_for_the_batch`
FAILS, then restore the two-pass version.

- [ ] **Step 6: Commit**

```bash
git add litellm/proxy/management_endpoints/project_endpoints.py litellm/proxy/_types.py tests/test_litellm/proxy/management_endpoints/test_project_endpoints.py
git commit -m "feat(projects): update and delete a project"
```

---

### Task 4: Prove it against the running proxy

**Files:** none. This task is verification.

- [ ] **Step 1: Restart**

```bash
bash ~/.claude/scripts/litellm-dev-up.sh
```

- [ ] **Step 2: Create a project under a real team**

```bash
TEAM=cd4318d5-f2f7-4182-992d-46fad28beb9b   # nitco_dev
curl -s -X POST -H "Authorization: Bearer $LITELLM_MASTER_KEY" -H "Content-Type: application/json" \
  -d "{\"project_alias\":\"api-service\",\"team_id\":\"$TEAM\",\"models\":[]}" \
  http://127.0.0.1:4001/project/new | python -m json.tool
```
Expected: a project object with a `project_id` and `team_id` matching.

- [ ] **Step 3: Read it back, and list the team's projects**

```bash
curl -s -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  "http://127.0.0.1:4001/project/info?project_id=<the id>" | python -m json.tool
curl -s -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  "http://127.0.0.1:4001/project/list?team_id=$TEAM" | python -m json.tool
```
Expected: the same project both times. Before this plan both returned 404.

- [ ] **Step 4: Block it, and confirm the request path honours the block**

```bash
curl -s -X POST -H "Authorization: Bearer $LITELLM_MASTER_KEY" -H "Content-Type: application/json" \
  -d '{"project_id":"<the id>","blocked":true}' http://127.0.0.1:4001/project/update
```

Then create a key bound to that project and send one request through it. Expect a refusal
naming the blocked project, which proves the endpoint and the existing `auth_checks`
enforcement meet correctly. Unblock afterwards with `"blocked": false`, which is the
instruction that error message has always given and that now works.

- [ ] **Step 5: Delete the throwaway project**

```bash
curl -s -X POST -H "Authorization: Bearer $LITELLM_MASTER_KEY" -H "Content-Type: application/json" \
  -d '{"project_ids":["<the id>"]}' http://127.0.0.1:4001/project/delete
```
Expected: `{"deleted_projects":["<the id>"]}`

- [ ] **Step 6: Run every suite this could touch**

```bash
.venv/Scripts/python.exe -m pytest tests/test_litellm/proxy/management_endpoints/ tests/test_litellm/repositories/ -q -p no:randomly --timeout=300
```
Expected: no new failures. The known pre-existing failures are the six in `test_ui_sso.py`
and `test_project_org_authz.py`, and the fifty-two in `test_auto_router_endpoints.py` were
removed earlier, so anything else is yours.

- [ ] **Step 7: Commit the proof in the message**

```bash
git commit --allow-empty -m "test(projects): verified project CRUD against a running proxy"
```

---

## Self-review notes

**Coverage.** All five routes exist: new, info, list, update, delete. The two allowlisted
404s are fixed in Task 2 and Step 5 of that task asserts the allowlist and the mounted
routes now agree. The error message in `auth_checks` that promises `/project/update` is
made true in Task 3.

**Deliberately not covered.** Budget creation from the inherited `LiteLLM_BudgetTable`
fields on `NewProjectRequest`: the request model inherits them but the repository takes
only a `budget_id`, so creating a budget inline is a separate decision and would be
invented here rather than designed. Projects can reference an existing budget today. Also
no daily project rollup and no person-as-scope; both are named follow-on plans above.

**Type consistency.** `_prisma_or_500`, `_team_or_404`, `_authorised_team_or_403` are
defined in Task 1 and used in Tasks 2 and 3. `_authorised_project_or_403` is defined in
Task 3 and used only there. `ProjectDeleteRequest.project_ids` is a `list[str]` in both
its definition and its tests.

**Known risk.** Task 3 assumes `UpdateProjectRequest` has a `blocked` field. The plan says
to check and add it if absent, because the class was written before any endpoint consumed
it and its docstring is the only evidence of intent.
