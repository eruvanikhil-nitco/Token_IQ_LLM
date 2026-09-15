# Projects and Teams Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make projects a working, default part of Token IQ for proxy admins and team admins. The Projects page lists projects without naming a team and shows spend and budget. Spend by model comes from the daily report. Teams get Projects and Budget tabs, and Project joins the Gateway usage view picker.

**Architecture:** On the backend, one helper in `project_endpoints.py` decides which projects a caller may read. `/project/list` and `/project/daily/activity` both use it, so the page, the report and the usage view agree on who sees what. The projects switch becomes an ordinary UI setting that defaults on. On the dashboard, project hooks live in `hooks/projects`, the new team tabs are small presentational components, and the existing `EntityUsage` component gains a `project` entity.

**Tech Stack:** FastAPI, Prisma, pytest on the proxy; Next.js, React Query, shadcn, vitest with Testing Library on the dashboard

**Spec:** `docs/superpowers/specs/2026-09-14-token-iq-product-design.md`, sections "Hierarchy and who sees what", "Full sidebar" (ORGANISATION, and ANALYTICS / Usage) and "Phases" (Phase 1)

## Global Constraints

- All work goes on the branch `litellm_token_iq`. Never touch `main`, never create another branch
- Python runs from the repo venv, `.venv/Scripts/python`, never the system Python
- Never run the full vitest suite. Run `npx vitest run <paths>` from `ui/litellm-dashboard` with explicit paths
- No existing page or tab is removed or merged
- Use the words teams, projects and users. Never "employees"
- No customer-visible LiteLLM text
- Never port code from `enterprise/` or `litellm_enterprise`. `tests/test_litellm/proxy/management_endpoints/test_project_org_authz.py` imports `litellm_enterprise` and is not part of this work
- New Python follows the project CLAUDE.md: every variable annotated `Final`, no new `Any`, no mutable dict or list built up over time, lines up to 120 characters, comments only where logic needs them
- Commit messages follow conventional commits and carry no Claude attribution (the project CLAUDE.md forbids it)
- Commit after each task. Push `litellm_token_iq` in the last task

## Who may read and change a project

This is the rule every task implements, taken from the spec's "A proxy admin sees the whole company. A team admin sees their own team, its projects and its users. A user sees only their own cost."

| Caller | Read projects | Change projects |
|---|---|---|
| Proxy admin | all | all |
| Admin viewer (`PROXY_ADMIN_VIEW_ONLY`) | all | none |
| Team admin | projects of teams they administer | the same |
| Key that belongs to a team | that team's projects (the existing `/project/info` rule) | none |
| Anyone else | none | none |

The sidebar shows Projects to admins and to users who administer at least one team

## File Map

Backend:
- Modify `litellm/repositories/project_repository.py`: `find_by_team_ids`
- Modify `litellm/proxy/management_endpoints/project_endpoints.py`: visibility helper, `/project/list` without a team, admin viewer reads, `/project/daily/activity` for many projects
- Modify `litellm/proxy/ui_crud_endpoints/proxy_setting_endpoints.py`: `enable_projects_ui` defaults on and stops being enterprise-only
- Modify `tests/test_litellm/proxy/management_endpoints/test_project_endpoints.py`
- Modify `tests/test_litellm/proxy/ui_crud_endpoints/test_proxy_setting_endpoints.py`
- Regenerate `ui/litellm-dashboard/src/lib/http/schema.d.ts`

Dashboard (paths under `ui/litellm-dashboard/src`):
- Modify `app/(dashboard)/components/SidebarProvider.tsx`, `components/leftnav.tsx`, `components/leftnav.test.tsx`
- Modify `app/(dashboard)/hooks/projects/useProjects.ts`, `app/(dashboard)/hooks/projects/useProjectDetails.ts`
- Create `app/(dashboard)/hooks/projects/useProjectDetails.test.tsx`
- Create `app/(dashboard)/hooks/projects/useProjectSpendByModel.ts`
- Modify `components/Settings/AdminSettings/UISettings/UISettings.tsx`
- Create `app/(dashboard)/projects/_components/projectBudget.ts` and `projectBudget.test.ts`
- Create `app/(dashboard)/projects/_components/spendByModel.ts` and `spendByModel.test.ts`
- Modify `app/(dashboard)/projects/_components/ProjectsTableColumns.tsx`, `ProjectsTable.test.tsx`
- Modify `app/(dashboard)/projects/_components/ProjectDetailsPage.tsx`, `ProjectDetailsPage.test.tsx`
- Modify `components/networking.tsx`: `projectDailyActivityCall`
- Modify `components/team/tabVisibilityUtils.ts`, `tabVisibilityUtils.test.ts`, `TeamInfo.tsx`, `TeamInfo.test.tsx`
- Create `components/team/TeamProjectsTab.tsx`, `TeamProjectsTab.test.tsx`, `TeamBudgetTab.tsx`, `TeamBudgetTab.test.tsx`
- Modify `components/EntityUsageExport/types.ts`
- Modify `app/(dashboard)/usage/_components/components/EntityUsage/EntityUsage.tsx`, `EntityUsage.test.tsx`
- Modify `app/(dashboard)/usage/_components/components/UsageViewSelect/UsageViewSelect.tsx`, `UsageViewSelect.test.tsx`
- Modify `app/(dashboard)/usage/_components/components/UsagePageView.tsx`, `UsagePageView.test.tsx`

---

### Task 1: List projects without naming a team

The dashboard calls `GET /project/list` with no `team_id`, and the route requires one, so the Projects page fails for everyone today

**Files:**
- Modify: `litellm/repositories/project_repository.py:34-36`
- Modify: `litellm/proxy/management_endpoints/project_endpoints.py:21-32` (imports), `:62-85` (`_authorised_team_or_403`), `:128-136` (`project_list`)
- Test: `tests/test_litellm/proxy/management_endpoints/test_project_endpoints.py`

**Interfaces:**
- Produces: `ProjectRepository.find_by_team_ids(team_ids: Sequence[str]) -> list[LiteLLM_ProjectTable]`
- Produces: `async def _projects_visible_to(user_api_key_dict: UserAPIKeyAuth, prisma_client: Any) -> list[LiteLLM_ProjectTable]` in `project_endpoints.py`
- Produces: `GET /project/list?team_id=` where `team_id` is optional
- Produces: test helpers `VIEWER` and `_prisma_with_teams(*team_rows)` in the test file, used again in Task 2

- [ ] **Step 1: Write the failing tests**

In `test_project_endpoints.py`, add below the `OUTSIDER` constant:

```python
VIEWER = UserAPIKeyAuth(user_role=LitellmUserRoles.PROXY_ADMIN_VIEW_ONLY, api_key="sk-view", user_id="viewer")
```

Add below the `_prisma` helper:

```python
def _prisma_with_teams(*team_rows: SimpleNamespace) -> MagicMock:
    client = MagicMock()
    client.db.litellm_teamtable.find_many = AsyncMock(return_value=list(team_rows))
    return client
```

Add these tests directly after `test_listing_another_team_s_projects_is_refused_not_empty`:

```python
@pytest.mark.asyncio
async def test_listing_without_a_team_shows_an_admin_every_project():
    """The Projects page asks for every project at once. Requiring a team made the page fail
    for everyone, admins included."""
    from litellm.proxy.management_endpoints.project_endpoints import project_list

    with (
        patch("litellm.proxy.proxy_server.prisma_client", _prisma()),
        patch(
            "litellm.repositories.project_repository.ProjectRepository.find_many",
            AsyncMock(return_value=[_project("p1", "t1"), _project("p2", "t2")]),
        ),
    ):
        result = await project_list(team_id=None, user_api_key_dict=ADMIN)

    assert [p.project_id for p in result] == ["p1", "p2"]


@pytest.mark.asyncio
async def test_listing_without_a_team_shows_a_team_admin_only_the_teams_they_run():
    from litellm.proxy._types import Member
    from litellm.proxy.management_endpoints.project_endpoints import project_list

    lead = UserAPIKeyAuth(user_role=LitellmUserRoles.INTERNAL_USER, api_key="sk-l", user_id="lead")
    mine = _team_row("t1", members_with_roles=[Member(user_id="lead", role="admin").model_dump()])
    theirs = _team_row("t2", members_with_roles=[Member(user_id="someone-else", role="admin").model_dump()])
    by_teams = AsyncMock(return_value=[_project("p1", "t1")])

    with (
        patch("litellm.proxy.proxy_server.prisma_client", _prisma_with_teams(mine, theirs)),
        patch("litellm.repositories.project_repository.ProjectRepository.find_by_team_ids", by_teams),
    ):
        result = await project_list(team_id=None, user_api_key_dict=lead)

    assert [p.project_id for p in result] == ["p1"]
    assert by_teams.await_args.args[0] == ("t1",)


@pytest.mark.asyncio
async def test_listing_without_a_team_includes_the_team_the_caller_s_key_belongs_to():
    """A key's own team may already read one of its projects through /project/info, so the
    list has to agree with that rule."""
    from litellm.proxy.management_endpoints.project_endpoints import project_list

    member = UserAPIKeyAuth(user_role=LitellmUserRoles.INTERNAL_USER, api_key="sk-m", user_id="m", team_id="t2")
    by_teams = AsyncMock(return_value=[_project("p2", "t2")])

    with (
        patch("litellm.proxy.proxy_server.prisma_client", _prisma_with_teams(_team_row("t1"), _team_row("t2"))),
        patch("litellm.repositories.project_repository.ProjectRepository.find_by_team_ids", by_teams),
    ):
        await project_list(team_id=None, user_api_key_dict=member)

    assert by_teams.await_args.args[0] == ("t2",)


@pytest.mark.asyncio
async def test_listing_without_a_team_gives_an_outsider_nothing_without_querying_projects():
    from litellm.proxy.management_endpoints.project_endpoints import project_list

    by_teams = AsyncMock(return_value=[_project("p1", "t1")])

    with (
        patch("litellm.proxy.proxy_server.prisma_client", _prisma_with_teams(_team_row("t1"))),
        patch("litellm.repositories.project_repository.ProjectRepository.find_by_team_ids", by_teams),
    ):
        result = await project_list(team_id=None, user_api_key_dict=OUTSIDER)

    assert result == []
    by_teams.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_view_only_admin_may_read_a_project_but_not_change_it():
    """Admin viewers have read parity with proxy admins everywhere else in the dashboard."""
    from fastapi import HTTPException

    from litellm.proxy._types import UpdateProjectRequest
    from litellm.proxy.management_endpoints.project_endpoints import project_info, update_project

    with (
        patch("litellm.proxy.proxy_server.prisma_client", _prisma()),
        patch(
            "litellm.repositories.project_repository.ProjectRepository.find_by_id",
            AsyncMock(return_value=_project()),
        ),
    ):
        read = await project_info(project_id="p1", user_api_key_dict=VIEWER)
        with pytest.raises(HTTPException) as exc:
            await update_project(data=UpdateProjectRequest(project_id="p1", blocked=True), user_api_key_dict=VIEWER)

    assert read.project_id == "p1"
    assert exc.value.status_code == 403
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_litellm/proxy/management_endpoints/test_project_endpoints.py -v`
Expected: the five new tests FAIL. The listing tests fail inside `_team_or_404` on a `None` team id or on the missing `find_by_team_ids`, and the viewer test gets 403 from `project_info`. The existing tests PASS

- [ ] **Step 3: Add the repository query**

In `project_repository.py`, add `Sequence` to the imports:

```python
from collections.abc import Sequence
```

Add below `find_by_team_id`:

```python
    async def find_by_team_ids(self, team_ids: Sequence[str]) -> list[LiteLLM_ProjectTable]:
        """Every project owned by any of these teams."""
        return await self.find_many(where={"team_id": {"in": list(team_ids)}})
```

- [ ] **Step 4: Add the visibility helper and use it**

In `project_endpoints.py`, add `from litellm.models.project import LiteLLM_ProjectTable` to the imports and add `user_api_key_has_admin_view` to the `litellm.proxy._types` import list

In `_authorised_team_or_403`, replace:

```python
    if user_api_key_dict.user_role == LitellmUserRoles.PROXY_ADMIN:
        return team
```

with:

```python
    if user_api_key_dict.user_role == LitellmUserRoles.PROXY_ADMIN:
        return team
    if not write and user_api_key_has_admin_view(user_api_key_dict):
        return team
```

Add this helper directly after `_authorised_team_or_403`:

```python
async def _projects_visible_to(
    user_api_key_dict: UserAPIKeyAuth,
    prisma_client: Any,  # any-ok: untyped wrapper
) -> list[LiteLLM_ProjectTable]:
    """Every project the caller may read.

    Admins read all of them. Anyone else reads the projects of the teams they administer and
    of the team their key belongs to, which is the same rule `_authorised_team_or_403` applies
    to a single project. Prisma cannot filter the members JSON column, so teams are filtered here.
    """
    repository: Final = ProjectRepository(prisma_client)
    if user_api_key_has_admin_view(user_api_key_dict):
        return await repository.find_many()

    team_rows: Final = await prisma_client.db.litellm_teamtable.find_many()
    readable_team_ids: Final = tuple(
        team.team_id
        for team in (LiteLLM_TeamTable.model_validate(row.model_dump()) for row in team_rows)
        if team.team_id == user_api_key_dict.team_id
        or _is_user_team_admin(user_api_key_dict=user_api_key_dict, team_obj=team)
    )
    if not readable_team_ids:
        return []
    return await repository.find_by_team_ids(readable_team_ids)
```

Replace `project_list` with:

```python
@router.get("/project/list", tags=["project management"], dependencies=[Depends(user_api_key_auth)])
async def project_list(
    team_id: str | None = None,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    """Projects the caller may read. Pass `team_id` to list only that team's projects."""
    prisma_client: Final = _prisma_or_500()
    if team_id is None:
        return await _projects_visible_to(user_api_key_dict, prisma_client)
    await _authorised_team_or_403(team_id, user_api_key_dict, prisma_client, write=False)
    return await ProjectRepository(prisma_client).find_by_team_id(team_id)
```

`team_id` is a plain default rather than `fastapi.Query(...)`, so calling the function directly in tests passes a real `None` instead of a `FieldInfo` object

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_litellm/proxy/management_endpoints/test_project_endpoints.py -v`
Expected: all PASS

- [ ] **Step 6: Lint the changed files**

Run: `.venv/Scripts/python -m ruff check litellm/repositories/project_repository.py litellm/proxy/management_endpoints/project_endpoints.py tests/test_litellm/proxy/management_endpoints/test_project_endpoints.py`
Expected: no errors

- [ ] **Step 7: Commit**

```bash
git add litellm/repositories/project_repository.py litellm/proxy/management_endpoints/project_endpoints.py tests/test_litellm/proxy/management_endpoints/test_project_endpoints.py
git commit -m "fix(projects): list the projects a caller can read without naming a team"
```

---

### Task 2: Report daily spend for many projects

The Usage page's Project view (Task 8) opens before anything is picked and needs the total across every project the caller can read. Today `/project/daily/activity` takes exactly one project

**Files:**
- Modify: `litellm/proxy/management_endpoints/project_endpoints.py:203-239` (`get_project_daily_activity`)
- Test: `tests/test_litellm/proxy/management_endpoints/test_project_endpoints.py:330-392`

**Interfaces:**
- Consumes: `_projects_visible_to`, `VIEWER`, `_prisma_with_teams` from Task 1
- Produces: `GET /project/daily/activity?project_ids=p1,p2&start_date=&end_date=&model=&api_key=&page=&page_size=` where `project_ids` is optional and replaces `project_id`. Nothing calls the old parameter: the dashboard has no caller yet

- [ ] **Step 1: Write the failing tests**

Replace the three tests `test_daily_activity_reads_the_project_rollup_not_the_raw_spend_logs`, `test_daily_activity_of_another_team_s_project_is_refused_not_empty` and `test_daily_activity_for_an_unknown_project_is_a_404` with:

```python
def _capture_daily_activity() -> tuple[dict, object]:
    recorded: dict = {}

    async def _capture(**kwargs):
        recorded.update(kwargs)
        return "report"

    return recorded, _capture


@pytest.mark.asyncio
async def test_daily_activity_reads_the_project_rollup_not_the_raw_spend_logs():
    from litellm.proxy.management_endpoints.project_endpoints import get_project_daily_activity

    recorded, capture = _capture_daily_activity()
    with (
        patch("litellm.proxy.proxy_server.prisma_client", _prisma()),
        patch(
            "litellm.repositories.project_repository.ProjectRepository.find_many",
            AsyncMock(return_value=[_project("p1"), _project("p2")]),
        ),
        patch("litellm.proxy.management_endpoints.project_endpoints.get_daily_activity", capture),
    ):
        result = await get_project_daily_activity(project_ids="p1", user_api_key_dict=ADMIN)

    assert result == "report"
    assert recorded["table_name"] == "litellm_dailyprojectspend"
    assert recorded["entity_id_field"] == "project_id"
    assert recorded["entity_id"] == ["p1"]
    assert recorded["entity_metadata_field"] == {"p1": {"project_alias": "api-service"}}


@pytest.mark.asyncio
async def test_daily_activity_without_named_projects_covers_every_project_the_caller_can_read():
    """The Usage page's Project view opens before anything is picked and must show the total."""
    from litellm.proxy.management_endpoints.project_endpoints import get_project_daily_activity

    recorded, capture = _capture_daily_activity()
    with (
        patch("litellm.proxy.proxy_server.prisma_client", _prisma()),
        patch(
            "litellm.repositories.project_repository.ProjectRepository.find_many",
            AsyncMock(return_value=[_project("p1"), _project("p2")]),
        ),
        patch("litellm.proxy.management_endpoints.project_endpoints.get_daily_activity", capture),
    ):
        await get_project_daily_activity(project_ids=None, user_api_key_dict=VIEWER)

    assert recorded["entity_id"] == ["p1", "p2"]


@pytest.mark.asyncio
async def test_daily_activity_for_a_caller_with_no_projects_filters_to_nothing_not_everything():
    """An empty id list reaches the query as an empty IN filter. Passing None instead would drop
    the filter and report every project's spend to someone who can read none of them."""
    from litellm.proxy.management_endpoints.project_endpoints import get_project_daily_activity

    recorded, capture = _capture_daily_activity()
    with (
        patch("litellm.proxy.proxy_server.prisma_client", _prisma_with_teams(_team_row("t1"))),
        patch("litellm.proxy.management_endpoints.project_endpoints.get_daily_activity", capture),
    ):
        await get_project_daily_activity(project_ids=None, user_api_key_dict=OUTSIDER)

    assert recorded["entity_id"] == []


@pytest.mark.asyncio
async def test_daily_activity_of_a_project_the_caller_cannot_read_is_refused_not_empty():
    from fastapi import HTTPException

    from litellm.proxy.management_endpoints.project_endpoints import get_project_daily_activity

    with (
        patch("litellm.proxy.proxy_server.prisma_client", _prisma_with_teams(_team_row("t1"))),
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

    from litellm.proxy.management_endpoints.project_endpoints import get_project_daily_activity

    with (
        patch("litellm.proxy.proxy_server.prisma_client", _prisma()),
        patch(
            "litellm.repositories.project_repository.ProjectRepository.find_many",
            AsyncMock(return_value=[]),
        ),
        pytest.raises(HTTPException) as exc,
    ):
        await get_project_daily_activity(project_ids="ghost", user_api_key_dict=ADMIN)

    assert exc.value.status_code == 403
    assert "ghost" in str(exc.value.detail)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_litellm/proxy/management_endpoints/test_project_endpoints.py -k daily_activity -v`
Expected: FAIL with `TypeError: get_project_daily_activity() got an unexpected keyword argument 'project_ids'`

- [ ] **Step 3: Implement**

In `project_endpoints.py`, add `from types import MappingProxyType` to the imports and replace `get_project_daily_activity` with:

```python
@router.get(
    "/project/daily/activity",
    response_model=SpendAnalyticsPaginatedResponse,
    tags=["project management"],
    dependencies=[Depends(user_api_key_auth)],
)
async def get_project_daily_activity(
    project_ids: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    page: int = 1,
    page_size: int = 10,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    """What projects spent, by day.

    `project_ids` is comma-separated. Leaving it out reports on every project the caller can
    read. Reads the project daily rollup rather than the raw spend logs, so the cost of a report
    does not grow with the number of requests.
    """
    prisma_client: Final = _prisma_or_500()
    readable: Final = MappingProxyType(
        {project.project_id: project for project in await _projects_visible_to(user_api_key_dict, prisma_client)}
    )
    requested: Final = tuple(project_ids.split(",")) if project_ids else tuple(readable)
    unreadable: Final = sorted(set(requested).difference(readable))
    if unreadable:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": f"You cannot read the spend of project(s) {unreadable}."},
        )

    return await get_daily_activity(
        prisma_client=prisma_client,
        table_name="litellm_dailyprojectspend",
        entity_id_field="project_id",
        entity_id=list(requested),
        entity_metadata_field={
            project_id: {"project_alias": readable[project_id].project_alias} for project_id in requested
        },
        start_date=start_date,
        end_date=end_date,
        model=model,
        api_key=api_key,
        page=page,
        page_size=page_size,
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_litellm/proxy/management_endpoints/test_project_endpoints.py -v`
Expected: all PASS

- [ ] **Step 5: Lint and commit**

Run: `.venv/Scripts/python -m ruff check litellm/proxy/management_endpoints/project_endpoints.py tests/test_litellm/proxy/management_endpoints/test_project_endpoints.py`
Expected: no errors

```bash
git add litellm/proxy/management_endpoints/project_endpoints.py tests/test_litellm/proxy/management_endpoints/test_project_endpoints.py
git commit -m "feat(projects): report daily spend across every project a caller can read"
```

---

### Task 3: Projects are on by default and not a paid feature

`enable_projects_ui` is listed as an enterprise-only setting, so saving it answers 403, and nothing declares it, so it reads as off. This task makes it an ordinary setting that defaults on

**Files:**
- Modify: `litellm/proxy/ui_crud_endpoints/proxy_setting_endpoints.py:302-305` (after `enable_chat_ui`), `:313-329` (`ALLOWED_UI_SETTINGS_FIELDS`), `:377-381` and `:1577-1589` (enterprise-only gate)
- Test: `tests/test_litellm/proxy/ui_crud_endpoints/test_proxy_setting_endpoints.py`
- Regenerate: `ui/litellm-dashboard/src/lib/http/schema.d.ts`

**Interfaces:**
- Produces: `GET /get/ui_settings` returns `values.enable_projects_ui`, `true` unless an admin saved `false`
- Produces: `PATCH /update/ui_settings` accepts `enable_projects_ui`

- [ ] **Step 1: Write the failing tests**

Append to `test_proxy_setting_endpoints.py`:

```python
def test_projects_show_on_a_fresh_installation(monkeypatch):
    """Projects are part of Token IQ's teams, projects and users hierarchy, so an installation
    that has never saved UI settings must show them."""
    from unittest.mock import AsyncMock, MagicMock

    fake_prisma = MagicMock()
    fake_prisma.db.litellm_uisettings.find_unique = AsyncMock(return_value=None)
    monkeypatch.setattr("litellm.proxy.proxy_server.prisma_client", fake_prisma)

    response = client.get("/get/ui_settings")

    assert response.status_code == 200, response.text
    assert response.json()["values"]["enable_projects_ui"] is True


def test_an_admin_can_turn_projects_off_without_a_paid_feature_refusal(monkeypatch):
    """Saving this switch used to answer 403 as an enterprise feature, so it could never be
    changed on this build."""
    from unittest.mock import AsyncMock, MagicMock

    import litellm.proxy.proxy_server as proxy_server_module
    from litellm.proxy._types import UserAPIKeyAuth
    from litellm.proxy.auth.user_api_key_auth import user_api_key_auth

    upsert = AsyncMock()
    fake_prisma = MagicMock()
    fake_prisma.db.litellm_uisettings.find_unique = AsyncMock(return_value=None)
    fake_prisma.db.litellm_uisettings.upsert = upsert
    monkeypatch.setattr(proxy_server_module, "prisma_client", fake_prisma)
    monkeypatch.setattr("litellm.proxy.proxy_server.store_model_in_db", True)

    async def _admin_auth():
        return UserAPIKeyAuth(
            user_id="settings-admin",
            api_key="hashed-admin-key",
            user_role=LitellmUserRoles.PROXY_ADMIN,
        )

    app.dependency_overrides[user_api_key_auth] = _admin_auth
    try:
        response = client.patch("/update/ui_settings", json={"enable_projects_ui": False})
    finally:
        app.dependency_overrides.pop(user_api_key_auth, None)

    assert response.status_code == 200, response.text
    saved = json.loads(upsert.await_args.kwargs["data"]["update"]["ui_settings"])
    assert saved["enable_projects_ui"] is False
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_litellm/proxy/ui_crud_endpoints/test_proxy_setting_endpoints.py -k "projects" -v`
Expected: FAIL. The first gets a `KeyError` for `enable_projects_ui`, the second gets 403 with "Enterprise feature"

- [ ] **Step 3: Implement**

In `proxy_setting_endpoints.py`, add this field to `UISettings` directly after the `enable_chat_ui` field:

```python
    enable_projects_ui: bool = Field(
        default=True,
        description="Shows the Projects page in the sidebar and the project field on virtual keys.",
    )
```

Add `"enable_projects_ui",` to `ALLOWED_UI_SETTINGS_FIELDS`, after `"enable_chat_ui",`

Delete the enterprise-only constant and its comment:

```python
# Settings OSS knows about as enterprise-gated. If a caller sends one of
# these keys and no extension package has registered it, the PATCH
# endpoint returns 403 instead of silently dropping the value, so the
# client gets a clear signal that the feature requires LiteLLM Enterprise.
_ENTERPRISE_ONLY_UI_SETTINGS: Final[set[str]] = {"enable_projects_ui"}
```

Delete the gate in `update_ui_settings`:

```python
    # Reject enterprise-only settings up front so the caller gets a clear
    # signal instead of a silent drop.
    blocked_enterprise_keys = sorted((settings_dict.keys() & _ENTERPRISE_ONLY_UI_SETTINGS) - ALLOWED_UI_SETTINGS_FIELDS)
    if blocked_enterprise_keys:
        raise HTTPException(
            status_code=403,
            detail={
                "error": (
                    f"Setting(s) {blocked_enterprise_keys} are a LiteLLM "
                    "Enterprise feature and are not available on this build."
                )
            },
        )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_litellm/proxy/ui_crud_endpoints/test_proxy_setting_endpoints.py -v`
Expected: all PASS

Run: `grep -rn "_ENTERPRISE_ONLY_UI_SETTINGS" litellm tests`
Expected: no output

- [ ] **Step 5: Regenerate the dashboard API types for Tasks 1 to 3**

Read `ui/litellm-dashboard/scripts/gen-api-types.mjs` to see where it reads the OpenAPI spec from. If it fetches a running proxy, start one with `~/.claude/scripts/litellm-dev-up.sh` first. Then run from `ui/litellm-dashboard`: `npm run gen:api`
Expected: `src/lib/http/schema.d.ts` changes to show `team_id` optional on `/project/list`, `project_ids` on `/project/daily/activity` and `enable_projects_ui` on the UI settings model, and nothing unrelated

- [ ] **Step 6: Lint and commit**

Run: `.venv/Scripts/python -m ruff check litellm/proxy/ui_crud_endpoints/proxy_setting_endpoints.py tests/test_litellm/proxy/ui_crud_endpoints/test_proxy_setting_endpoints.py`
Expected: no errors

```bash
git add litellm/proxy/ui_crud_endpoints/proxy_setting_endpoints.py tests/test_litellm/proxy/ui_crud_endpoints/test_proxy_setting_endpoints.py ui/litellm-dashboard/src/lib/http/schema.d.ts
git commit -m "feat(projects): switch projects on by default and let admins save the setting"
```

---

### Task 4: Team admins reach projects in the dashboard

**Files:**
- Modify: `ui/litellm-dashboard/src/app/(dashboard)/components/SidebarProvider.tsx:23`
- Modify: `ui/litellm-dashboard/src/components/leftnav.tsx:59-65` (roles import), `:189-199` (Projects entry), `:350-405` (component body and filter)
- Modify: `ui/litellm-dashboard/src/app/(dashboard)/hooks/projects/useProjects.ts:45`
- Modify: `ui/litellm-dashboard/src/app/(dashboard)/hooks/projects/useProjectDetails.ts:3,40`
- Modify: `ui/litellm-dashboard/src/components/Settings/AdminSettings/UISettings/UISettings.tsx` (projects toggle label)
- Test: `ui/litellm-dashboard/src/components/leftnav.test.tsx`
- Create: `ui/litellm-dashboard/src/app/(dashboard)/hooks/projects/useProjectDetails.test.tsx`

**Interfaces:**
- Produces: `export const projectReaderRoles: string[]` from `useProjects.ts`, used in Tasks 6 and 7
- Produces: a Projects sidebar entry labelled `Projects` with `roles: [...all_admin_roles, ...internalUserRoles]`, shown to admins and to users who administer a team

- [ ] **Step 1: Write the failing sidebar tests**

In `leftnav.test.tsx`, add `mockIsTeamAdmin` to the existing `vi.hoisted` block so it reads:

```tsx
const { mockUseAuthorized, mockUseOrganizations, mockIsTeamAdmin } = vi.hoisted(() => {
```

and, inside that block before its `return`, add:

```tsx
  const mockIsTeamAdmin = vi.fn(() => false);
```

and change its `return` to `return { mockUseAuthorized, mockUseOrganizations, mockIsTeamAdmin };`

In the `vi.mock("../utils/roles", ...)` factory, replace `isUserTeamAdminForAnyTeam: () => false,` with:

```tsx
    isUserTeamAdminForAnyTeam: () => mockIsTeamAdmin(),
```

Add this block at the end of `describe("Sidebar (leftnav)")`:

```tsx
  describe("Projects entry", () => {
    const internalAuth = {
      userId: "lead-user-id",
      accessToken: "test-access-token",
      userRole: "internal",
      isViewOnly: false,
      token: "test-token",
      userEmail: "lead@example.com",
      premiumUser: false,
      disabledPersonalKeyCreation: false,
      showSSOBanner: false,
    };

    afterEach(() => {
      mockIsTeamAdmin.mockReset();
    });

    it("shows Projects to an admin without a Beta label", () => {
      const { container } = renderWithProviders(<Sidebar {...defaultProps} enableProjectsUI />);

      const projects = container.querySelector('a[href*="projects"]');
      expect(projects).toHaveTextContent("Projects");
      expect(projects).not.toHaveTextContent("Beta");
    });

    it("shows Projects to a user who administers a team", () => {
      mockUseAuthorized.mockReturnValue(internalAuth);
      mockIsTeamAdmin.mockReturnValue(true);
      const { container } = renderWithProviders(<Sidebar {...defaultProps} enableProjectsUI />);

      expect(container.querySelector('a[href*="projects"]')).not.toBeNull();
    });

    it("hides Projects from a user who administers no team", () => {
      mockUseAuthorized.mockReturnValue(internalAuth);
      mockIsTeamAdmin.mockReturnValue(false);
      const { container } = renderWithProviders(<Sidebar {...defaultProps} enableProjectsUI />);

      expect(container.querySelector('a[href*="projects"]')).toBeNull();
      expect(screen.getByText("Logs")).toBeInTheDocument();
    });
  });
```

- [ ] **Step 2: Write the failing hook test**

Create `useProjectDetails.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { internalUserRoles } from "@/utils/roles";
import { useProjectDetails } from "./useProjectDetails";

vi.mock("@/app/(dashboard)/hooks/useAuthorized", () => ({
  default: () => ({ accessToken: "sk-team-admin", userRole: internalUserRoles[0] }),
}));

vi.mock("@/components/networking", () => ({
  getProxyBaseUrl: () => "",
  getGlobalLitellmHeaderName: () => "Authorization",
  deriveErrorMessage: () => "error",
  handleError: vi.fn(),
}));

describe("useProjectDetails", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads a project for a team admin, not only for proxy admins", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ project_id: "p1" }) });
    vi.stubGlobal("fetch", fetchMock);
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });

    const { result } = renderHook(() => useProjectDetails("p1"), {
      wrapper: ({ children }: { children: React.ReactNode }) => (
        <QueryClientProvider client={client}>{children}</QueryClientProvider>
      ),
    });

    await waitFor(() => expect(result.current.data?.project_id).toBe("p1"));
    expect(fetchMock.mock.calls[0][0]).toBe("/project/info?project_id=p1");
  });
});
```

- [ ] **Step 3: Run the tests to verify they fail**

Run from `ui/litellm-dashboard`: `npx vitest run src/components/leftnav.test.tsx "src/app/(dashboard)/hooks/projects/useProjectDetails.test.tsx"`
Expected: FAIL. The admin test finds "Beta" in the Projects link, the team admin test finds no Projects link, and the hook test times out because the query is disabled for internal user roles

- [ ] **Step 4: Implement**

`useProjects.ts`: change `const projectReaderRoles = [...all_admin_roles, ...internalUserRoles];` to:

```ts
export const projectReaderRoles = [...all_admin_roles, ...internalUserRoles];
```

`useProjectDetails.ts`: delete the line `import { all_admin_roles } from "@/utils/roles";`, change the `./useProjects` import to `import { ProjectResponse, projectKeys, projectReaderRoles } from "./useProjects";`, and change the `enabled` line to:

```ts
    enabled: Boolean(accessToken && projectId) && projectReaderRoles.includes(userRole || ""),
```

`SidebarProvider.tsx`: change `useState<boolean>(false)` for `enableProjectsUI` to:

```tsx
  const [enableProjectsUI, setEnableProjectsUI] = useState<boolean>(true);
```

`leftnav.tsx`:

1. Add the import `import { useTeams } from "@/app/(dashboard)/hooks/teams/useTeams";` below the `useIsOrgAdmin` import
2. Add `isUserTeamAdminForAnyTeam,` to the `../utils/roles` import list
3. Replace the Projects entry with:

```tsx
      {
        key: "projects",
        page: "projects",
        label: "Projects",
        icon: <Folder {...ICON} />,
        roles: [...all_admin_roles, ...internalUserRoles],
      },
```

4. In `Sidebar_`, below `const isOrgAdmin = useIsOrgAdmin();`, add:

```tsx
  const { data: teams } = useTeams();
```

5. In `filterItemsByRole`, replace `if (item.key === "projects" && !enableProjectsUI) return false;` with:

```tsx
        if (item.key === "projects") {
          if (!enableProjectsUI) return false;
          if (!isAdmin && !isUserTeamAdminForAnyTeam(teams ?? null, userId ?? "")) return false;
        }
```

`UISettings.tsx`: change `label="[BETA] Enable Projects (page will refresh)"` to:

```tsx
                label="Enable Projects (page will refresh)"
```

- [ ] **Step 5: Run the tests to verify they pass**

Run from `ui/litellm-dashboard`: `npx vitest run src/components/leftnav.test.tsx "src/app/(dashboard)/hooks/projects/useProjectDetails.test.tsx" src/components/Settings/AdminSettings/UISettings`
Expected: PASS

- [ ] **Step 6: Lint and commit**

Run from `ui/litellm-dashboard`: `npx eslint src/components/leftnav.tsx src/components/leftnav.test.tsx "src/app/(dashboard)/components/SidebarProvider.tsx" "src/app/(dashboard)/hooks/projects" src/components/Settings/AdminSettings/UISettings/UISettings.tsx`
Expected: no errors

```bash
git add ui/litellm-dashboard/src/components/leftnav.tsx ui/litellm-dashboard/src/components/leftnav.test.tsx "ui/litellm-dashboard/src/app/(dashboard)/components/SidebarProvider.tsx" "ui/litellm-dashboard/src/app/(dashboard)/hooks/projects" ui/litellm-dashboard/src/components/Settings/AdminSettings/UISettings/UISettings.tsx
git commit -m "feat(ui): open projects to team admins and drop the beta label"
```

---

### Task 5: Spend and budget on the project list

**Files:**
- Create: `ui/litellm-dashboard/src/app/(dashboard)/projects/_components/projectBudget.ts`
- Create: `ui/litellm-dashboard/src/app/(dashboard)/projects/_components/projectBudget.test.ts`
- Modify: `ui/litellm-dashboard/src/app/(dashboard)/projects/_components/ProjectsTableColumns.tsx` (after the `team` column)
- Test: `ui/litellm-dashboard/src/app/(dashboard)/projects/_components/ProjectsTable.test.tsx`

**Interfaces:**
- Produces: `formatProjectSpend(spend: number): string` returning `"$42.00"`
- Produces: `projectBudgetLabel(project: Pick<ProjectResponse, "spend" | "litellm_budget_table">): string` returning `"No limit"` or `"$100.00 (42% used)"`. Both are used again in Task 7

- [ ] **Step 1: Write the failing tests**

Create `projectBudget.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import type { ProjectBudget } from "@/app/(dashboard)/hooks/projects/useProjects";
import { formatProjectSpend, projectBudgetLabel } from "./projectBudget";

const budget = (maxBudget: number | null): ProjectBudget => ({
  budget_id: "b1",
  max_budget: maxBudget,
  soft_budget: null,
  max_parallel_requests: null,
  tpm_limit: null,
  rpm_limit: null,
  model_max_budget: null,
  budget_duration: "30d",
});

describe("projectBudgetLabel", () => {
  it("says there is no limit when the project has no budget", () => {
    expect(projectBudgetLabel({ spend: 12, litellm_budget_table: null })).toBe("No limit");
  });

  it("treats a zero budget as no limit rather than dividing by zero", () => {
    expect(projectBudgetLabel({ spend: 12, litellm_budget_table: budget(0) })).toBe("No limit");
  });

  it("shows the budget and how much of it is used", () => {
    expect(projectBudgetLabel({ spend: 42, litellm_budget_table: budget(100) })).toBe("$100.00 (42% used)");
  });

  it("keeps counting past 100% so an overspent project stands out", () => {
    expect(projectBudgetLabel({ spend: 150, litellm_budget_table: budget(100) })).toBe("$100.00 (150% used)");
  });
});

describe("formatProjectSpend", () => {
  it("shows dollars to the cent", () => {
    expect(formatProjectSpend(3.5)).toBe("$3.50");
  });
});
```

Add to the end of `ProjectsTable.test.tsx`:

```tsx
describe("ProjectsTable spend and budget", () => {
  it("shows each project's spend next to its budget", () => {
    const budgeted: ProjectResponse = {
      ...makeProject(1),
      spend: 42,
      litellm_budget_table: {
        budget_id: "b1",
        max_budget: 100,
        soft_budget: null,
        max_parallel_requests: null,
        tpm_limit: null,
        rpm_limit: null,
        model_max_budget: null,
        budget_duration: "30d",
      },
    };
    const unbudgeted: ProjectResponse = { ...makeProject(2), spend: 3.5 };

    renderTable({ projects: [budgeted, unbudgeted] });

    expect(screen.getByRole("columnheader", { name: /Spend/ })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /Budget/ })).toBeInTheDocument();
    expect(firstDataRow().getByText("$42.00")).toBeInTheDocument();
    expect(firstDataRow().getByText("$100.00 (42% used)")).toBeInTheDocument();
    const secondRow = within(screen.getAllByRole("row")[2]);
    expect(secondRow.getByText("$3.50")).toBeInTheDocument();
    expect(secondRow.getByText("No limit")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run from `ui/litellm-dashboard`: `npx vitest run "src/app/(dashboard)/projects/_components/projectBudget.test.ts" "src/app/(dashboard)/projects/_components/ProjectsTable.test.tsx"`
Expected: FAIL. `projectBudget.test.ts` cannot resolve `./projectBudget`, and the table test finds no Spend column

- [ ] **Step 3: Implement**

Create `projectBudget.ts`:

```ts
import type { ProjectResponse } from "@/app/(dashboard)/hooks/projects/useProjects";

export const formatProjectSpend = (spend: number): string => `$${spend.toFixed(2)}`;

export const projectBudgetLabel = (project: Pick<ProjectResponse, "spend" | "litellm_budget_table">): string => {
  const maxBudget = project.litellm_budget_table?.max_budget ?? null;
  if (maxBudget === null || maxBudget <= 0) return "No limit";
  const percentUsed = Math.round((project.spend / maxBudget) * 100);
  return `$${maxBudget.toFixed(2)} (${percentUsed}% used)`;
};
```

In `ProjectsTableColumns.tsx`, add `import { formatProjectSpend, projectBudgetLabel } from "./projectBudget";` below the other imports, and add these two columns directly after the `team` column:

```tsx
  {
    id: "spend",
    accessorKey: "spend",
    meta: { title: "Spend" },
    header: ({ column }) => <DataTableSortHeader column={column} title="Spend" />,
    size: 110,
    enableSorting: true,
    cell: ({ row }) => <span className="text-sm tabular-nums">{formatProjectSpend(row.original.spend)}</span>,
  },
  {
    id: "budget",
    meta: { title: "Budget" },
    header: "Budget",
    size: 170,
    enableSorting: false,
    cell: ({ row }) => <span className="text-sm tabular-nums">{projectBudgetLabel(row.original)}</span>,
  },
```

- [ ] **Step 4: Run the tests to verify they pass**

Run from `ui/litellm-dashboard`: `npx vitest run "src/app/(dashboard)/projects/_components/projectBudget.test.ts" "src/app/(dashboard)/projects/_components/ProjectsTable.test.tsx" "src/app/(dashboard)/projects/_components/ProjectsPage.test.tsx"`
Expected: PASS

- [ ] **Step 5: Lint and commit**

Run from `ui/litellm-dashboard`: `npx eslint "src/app/(dashboard)/projects/_components"`
Expected: no errors

```bash
git add "ui/litellm-dashboard/src/app/(dashboard)/projects/_components"
git commit -m "feat(ui): show spend and budget on the projects list"
```

---

### Task 6: Spend by Model comes from the daily report

No code writes a project's `model_spend` column; the spend writer only increments `spend`. So the Spend by Model chart on a project can never show anything. The project daily rollup does record spend per model, and Task 2 exposes it

**Files:**
- Modify: `ui/litellm-dashboard/src/components/networking.tsx` (after `teamDailyActivityAggregatedCall`)
- Create: `ui/litellm-dashboard/src/app/(dashboard)/projects/_components/spendByModel.ts`
- Create: `ui/litellm-dashboard/src/app/(dashboard)/projects/_components/spendByModel.test.ts`
- Create: `ui/litellm-dashboard/src/app/(dashboard)/hooks/projects/useProjectSpendByModel.ts`
- Modify: `ui/litellm-dashboard/src/app/(dashboard)/projects/_components/ProjectDetailsPage.tsx:1-52,170-192`
- Test: `ui/litellm-dashboard/src/app/(dashboard)/projects/_components/ProjectDetailsPage.test.tsx`

**Interfaces:**
- Consumes: `GET /project/daily/activity?project_ids=` from Task 2, `projectReaderRoles` from Task 4
- Produces: `projectDailyActivityCall(accessToken: string, startTime: Date, endTime: Date, page?: number, projectIds?: string[] | null)`, used again in Task 8
- Produces: `interface ModelSpend { model: string; spend: number }` and `spendByModel(days: readonly DailyData[]): ModelSpend[]`
- Produces: `PROJECT_SPEND_WINDOW_DAYS = 30` and `useProjectSpendByModel(projectId: string)`

The dashboard asks for daily activity with a page size of 1000 (`DEFAULT_DAILY_ACTIVITY_PAGE_SIZE` in `networking.tsx`), so 30 days of one project always fits on the first page

- [ ] **Step 1: Write the failing tests**

Create `spendByModel.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import type { DailyData, SpendMetrics } from "@/components/UsagePage/types";
import { spendByModel } from "./spendByModel";

const metrics = (spend: number): SpendMetrics => ({
  spend,
  prompt_tokens: 0,
  completion_tokens: 0,
  total_tokens: 0,
  api_requests: 0,
  successful_requests: 0,
  failed_requests: 0,
  cache_read_input_tokens: 0,
  cache_creation_input_tokens: 0,
});

const day = (date: string, models: Record<string, number>): DailyData => ({
  date,
  metrics: metrics(Object.values(models).reduce((total, spend) => total + spend, 0)),
  breakdown: {
    models: Object.fromEntries(
      Object.entries(models).map(([model, spend]) => [
        model,
        { metrics: metrics(spend), metadata: {}, api_key_breakdown: {} },
      ]),
    ),
    model_groups: {},
    mcp_servers: {},
    providers: {},
    api_keys: {},
    entities: {},
  },
});

describe("spendByModel", () => {
  it("adds up each model's spend across days, biggest spender first", () => {
    const days = [day("2026-09-01", { "gpt-5.2": 1.5, "claude-sonnet-5": 4 }), day("2026-09-02", { "gpt-5.2": 3 })];

    expect(spendByModel(days)).toEqual([
      { model: "gpt-5.2", spend: 4.5 },
      { model: "claude-sonnet-5", spend: 4 },
    ]);
  });

  it("is empty when the project has no recorded days", () => {
    expect(spendByModel([])).toEqual([]);
  });
});
```

In `ProjectDetailsPage.test.tsx`, add below the `useTeams` mock:

```tsx
const mockUseProjectSpendByModel = vi.fn();
vi.mock("@/app/(dashboard)/hooks/projects/useProjectSpendByModel", () => ({
  PROJECT_SPEND_WINDOW_DAYS: 30,
  useProjectSpendByModel: (id: string) => mockUseProjectSpendByModel(id),
}));
```

In the top-level `beforeEach` of `describe("ProjectDetail")`, add after the `mockUseTeam` line:

```tsx
    mockUseProjectSpendByModel.mockReturnValue({ data: [] });
```

Replace the whole `describe("Spend by Model chart", ...)` block with:

```tsx
    describe("Spend by Model chart", () => {
      const multiModelSpend = [
        { model: "gpt-5.2", spend: 10 },
        { model: "gpt-5.2-codex", spend: 5.5 },
        { model: "claude-opus-4-8", spend: 2.75 },
        { model: "claude-sonnet-5", spend: 0.5 },
      ];

      beforeEach(() => {
        mockUseProjectDetails.mockReturnValue({ data: mockProject, isLoading: false });
      });

      it("should read spend by model from the daily report rather than the project's stored model_spend", () => {
        mockUseProjectDetails.mockReturnValue({
          data: { ...mockProject, model_spend: { "stale-model": 99 } },
          isLoading: false,
        });
        mockUseProjectSpendByModel.mockReturnValue({ data: [{ model: "gpt-5.2", spend: 1 }] });
        const { container } = renderWithProviders(<ProjectDetail projectId="proj-1" onBack={onBack} />);

        expect(mockUseProjectSpendByModel).toHaveBeenCalledWith("proj-1");
        expect(yAxisTickLabels(container)).toEqual(["gpt-5.2"]);
        expect(screen.getByText("Spend by Model, last 30 days")).toBeInTheDocument();
      });

      it("should render one cyan bar per model without a legend", () => {
        mockUseProjectSpendByModel.mockReturnValue({ data: multiModelSpend });
        const { container } = renderWithProviders(<ProjectDetail projectId="proj-1" onBack={onBack} />);

        expect(container.querySelectorAll(".recharts-bar")).toHaveLength(1);
        expect(container.querySelectorAll("path.recharts-rectangle")).toHaveLength(4);
        expect(rectangleFills(container)).toEqual(new Set(["var(--color-cyan-500, #06b6d4)"]));
        expect(container.querySelector(".recharts-legend-wrapper")).toBeNull();
      });

      it("should list models on the category axis in the order the report ranks them", () => {
        mockUseProjectSpendByModel.mockReturnValue({ data: multiModelSpend });
        const { container } = renderWithProviders(<ProjectDetail projectId="proj-1" onBack={onBack} />);

        expect(yAxisTickLabels(container)).toEqual(["gpt-5.2", "gpt-5.2-codex", "claude-opus-4-8", "claude-sonnet-5"]);
      });

      it("should format value axis ticks as dollars with four decimals", () => {
        mockUseProjectSpendByModel.mockReturnValue({ data: multiModelSpend });
        const { container } = renderWithProviders(<ProjectDetail projectId="proj-1" onBack={onBack} />);

        expect(container.querySelector(".recharts-xAxis-tick-labels")?.textContent).toMatch(/\$\d+\.\d{4}/);
      });

      it("should scale the chart height at 40px per model with a 120px floor", () => {
        mockUseProjectSpendByModel.mockReturnValue({ data: multiModelSpend });
        const { container } = renderWithProviders(<ProjectDetail projectId="proj-1" onBack={onBack} />);
        expect(container.querySelector<HTMLElement>('[data-slot="chart"]')?.style.height).toBe("160px");

        mockUseProjectSpendByModel.mockReturnValue({ data: [{ model: "gpt-4", spend: 12.5 }] });
        const { container: singleModelContainer } = renderWithProviders(
          <ProjectDetail projectId="proj-1" onBack={onBack} />,
        );
        expect(singleModelContainer.querySelector<HTMLElement>('[data-slot="chart"]')?.style.height).toBe("120px");
      });

      it("should show the empty state when the report has no model spend", () => {
        mockUseProjectSpendByModel.mockReturnValue({ data: [] });
        const { container } = renderWithProviders(<ProjectDetail projectId="proj-1" onBack={onBack} />);

        expect(screen.getByText("No model spend in the last 30 days")).toBeInTheDocument();
        expect(container.querySelector('[data-slot="chart"]')).toBeNull();
      });
    });
```

- [ ] **Step 2: Run the tests to verify they fail**

Run from `ui/litellm-dashboard`: `npx vitest run "src/app/(dashboard)/projects/_components/spendByModel.test.ts" "src/app/(dashboard)/projects/_components/ProjectDetailsPage.test.tsx"`
Expected: FAIL. `./spendByModel` cannot be resolved, and the details test shows `stale-model` and "No model spend recorded yet" because the page still reads `model_spend`

- [ ] **Step 3: Implement**

In `networking.tsx`, add directly after `teamDailyActivityAggregatedCall`:

```ts
export const projectDailyActivityCall = async (
  accessToken: string,
  startTime: Date,
  endTime: Date,
  page: number = 1,
  projectIds: string[] | null = null,
) => {
  return fetchDailyActivity({
    accessToken,
    endpoint: "/project/daily/activity",
    startTime,
    endTime,
    page,
    extraQueryParams: { project_ids: projectIds },
  });
};
```

Create `spendByModel.ts`:

```ts
import type { DailyData } from "@/components/UsagePage/types";

export interface ModelSpend {
  model: string;
  spend: number;
}

export const spendByModel = (days: readonly DailyData[]): ModelSpend[] => {
  const totals = days
    .flatMap((day) => Object.entries(day.breakdown.models))
    .reduce(
      (sums, [model, entry]) => sums.set(model, (sums.get(model) ?? 0) + entry.metrics.spend),
      new Map<string, number>(),
    );
  return Array.from(totals, ([model, spend]) => ({ model, spend })).sort((a, b) => b.spend - a.spend);
};
```

Create `useProjectSpendByModel.ts`:

```ts
import { useQuery } from "@tanstack/react-query";
import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
import { spendByModel, type ModelSpend } from "@/app/(dashboard)/projects/_components/spendByModel";
import { projectDailyActivityCall } from "@/components/networking";
import type { DailyData } from "@/components/UsagePage/types";
import { projectKeys, projectReaderRoles } from "./useProjects";

export const PROJECT_SPEND_WINDOW_DAYS = 30;

const DAY_MS = 24 * 60 * 60 * 1000;

export const useProjectSpendByModel = (projectId: string) => {
  const { accessToken, userRole } = useAuthorized();

  return useQuery<ModelSpend[]>({
    queryKey: [...projectKeys.detail(projectId), "spend-by-model"],
    queryFn: async () => {
      const endTime = new Date();
      const startTime = new Date(endTime.getTime() - PROJECT_SPEND_WINDOW_DAYS * DAY_MS);
      const report: { results: DailyData[] } = await projectDailyActivityCall(accessToken!, startTime, endTime, 1, [
        projectId,
      ]);
      return spendByModel(report.results);
    },
    enabled: Boolean(accessToken && projectId) && projectReaderRoles.includes(userRole ?? ""),
  });
};
```

In `ProjectDetailsPage.tsx`:

1. Add `import { PROJECT_SPEND_WINDOW_DAYS, useProjectSpendByModel } from "@/app/(dashboard)/hooks/projects/useProjectSpendByModel";` below the `useProjectDetails` import
2. Change `import { useMemo, useState } from "react";` to `import { useState } from "react";`
3. Below `const { data: project, isLoading } = useProjectDetails(projectId);` add:

```tsx
  const { data: modelSpendData = [] } = useProjectSpendByModel(projectId);
```

4. Delete the whole `const modelSpendData = useMemo(() => { ... }, [project?.model_spend]);` block
5. Change `<CardTitle>Spend by Model</CardTitle>` to:

```tsx
            <CardTitle>Spend by Model, last {PROJECT_SPEND_WINDOW_DAYS} days</CardTitle>
```

6. Change the empty state paragraph to:

```tsx
              <p className="py-8 text-center text-sm text-muted-foreground">
                No model spend in the last {PROJECT_SPEND_WINDOW_DAYS} days
              </p>
```

- [ ] **Step 4: Run the tests to verify they pass**

Run from `ui/litellm-dashboard`: `npx vitest run "src/app/(dashboard)/projects/_components/spendByModel.test.ts" "src/app/(dashboard)/projects/_components/ProjectDetailsPage.test.tsx"`
Expected: PASS

- [ ] **Step 5: Lint and commit**

Run from `ui/litellm-dashboard`: `npx eslint "src/app/(dashboard)/projects/_components" "src/app/(dashboard)/hooks/projects" src/components/networking.tsx`
Expected: no errors

```bash
git add ui/litellm-dashboard/src/components/networking.tsx "ui/litellm-dashboard/src/app/(dashboard)/projects/_components" "ui/litellm-dashboard/src/app/(dashboard)/hooks/projects"
git commit -m "fix(ui): chart a project's spend by model from its daily report"
```

---

### Task 7: Projects and Budget tabs on a team

**Files:**
- Modify: `ui/litellm-dashboard/src/components/team/tabVisibilityUtils.ts`, `tabVisibilityUtils.test.ts`
- Modify: `ui/litellm-dashboard/src/app/(dashboard)/hooks/projects/useProjects.ts` (fetch function and new hook)
- Create: `ui/litellm-dashboard/src/components/team/TeamProjectsTab.tsx`, `TeamProjectsTab.test.tsx`
- Create: `ui/litellm-dashboard/src/components/team/TeamBudgetTab.tsx`, `TeamBudgetTab.test.tsx`
- Modify: `ui/litellm-dashboard/src/components/team/TeamInfo.tsx` (imports, `tabItems` around line 1112)
- Test: `ui/litellm-dashboard/src/components/team/TeamInfo.test.tsx`

**Interfaces:**
- Consumes: `formatProjectSpend`, `projectBudgetLabel` from Task 5; `projectReaderRoles` from Task 4; `GET /project/list?team_id=` from Task 1
- Produces: `TEAM_INFO_TAB_KEYS.PROJECTS = "projects"`, `TEAM_INFO_TAB_KEYS.BUDGET = "budget"`
- Produces: `useTeamProjects(teamId: string)`
- Produces: `TeamProjectsTab({ teamId })` and `TeamBudgetTab({ spend, maxBudget, budgetDuration, budgetResetAt, memberBudget })`

Team detail tabs become Overview, My User, Virtual Keys, Members, Member Permissions, Projects, Budget, Settings, as the spec lists them. Someone who cannot edit the team sees Overview, My User, Virtual Keys and Budget. The Overview budget card stays where it is

- [ ] **Step 1: Write the failing tests**

In `tabVisibilityUtils.test.ts`, replace the `TEAM_INFO_TAB_LABELS` test body with:

```ts
      expect(TEAM_INFO_TAB_LABELS[TEAM_INFO_TAB_KEYS.OVERVIEW]).toBe("Overview");
      expect(TEAM_INFO_TAB_LABELS[TEAM_INFO_TAB_KEYS.MY_USER]).toBe("My User");
      expect(TEAM_INFO_TAB_LABELS[TEAM_INFO_TAB_KEYS.VIRTUAL_KEYS]).toBe("Virtual Keys");
      expect(TEAM_INFO_TAB_LABELS[TEAM_INFO_TAB_KEYS.MEMBERS]).toBe("Members");
      expect(TEAM_INFO_TAB_LABELS[TEAM_INFO_TAB_KEYS.MEMBER_PERMISSIONS]).toBe("Member Permissions");
      expect(TEAM_INFO_TAB_LABELS[TEAM_INFO_TAB_KEYS.PROJECTS]).toBe("Projects");
      expect(TEAM_INFO_TAB_LABELS[TEAM_INFO_TAB_KEYS.BUDGET]).toBe("Budget");
      expect(TEAM_INFO_TAB_LABELS[TEAM_INFO_TAB_KEYS.SETTINGS]).toBe("Settings");
```

Replace the whole `describe("getTeamInfoVisibleTabs", ...)` block with:

```ts
  describe("getTeamInfoVisibleTabs", () => {
    it("returns overview, my user, virtual keys and budget when user cannot edit team", () => {
      expect(getTeamInfoVisibleTabs(false)).toEqual([
        TEAM_INFO_TAB_KEYS.OVERVIEW,
        TEAM_INFO_TAB_KEYS.MY_USER,
        TEAM_INFO_TAB_KEYS.VIRTUAL_KEYS,
        TEAM_INFO_TAB_KEYS.BUDGET,
      ]);
    });

    it("returns all tabs, with projects and budget before settings, when user can edit team", () => {
      expect(getTeamInfoVisibleTabs(true)).toEqual([
        TEAM_INFO_TAB_KEYS.OVERVIEW,
        TEAM_INFO_TAB_KEYS.MY_USER,
        TEAM_INFO_TAB_KEYS.VIRTUAL_KEYS,
        TEAM_INFO_TAB_KEYS.MEMBERS,
        TEAM_INFO_TAB_KEYS.MEMBER_PERMISSIONS,
        TEAM_INFO_TAB_KEYS.PROJECTS,
        TEAM_INFO_TAB_KEYS.BUDGET,
        TEAM_INFO_TAB_KEYS.SETTINGS,
      ]);
    });
  });
```

Add inside `describe("isTeamInfoTabVisible")`:

```ts
    it("shows projects only to someone who can edit the team, since the list carries spend", () => {
      expect(isTeamInfoTabVisible(TEAM_INFO_TAB_KEYS.PROJECTS, false)).toBe(false);
      expect(isTeamInfoTabVisible(TEAM_INFO_TAB_KEYS.PROJECTS, true)).toBe(true);
    });

    it("always shows budget, which the overview already shows to every member", () => {
      expect(isTeamInfoTabVisible(TEAM_INFO_TAB_KEYS.BUDGET, false)).toBe(true);
      expect(isTeamInfoTabVisible(TEAM_INFO_TAB_KEYS.BUDGET, true)).toBe(true);
    });
```

Create `TeamProjectsTab.test.tsx`:

```tsx
import { describe, expect, it, vi } from "vitest";
import type { ProjectResponse } from "@/app/(dashboard)/hooks/projects/useProjects";
import { renderWithProviders, screen } from "../../../tests/test-utils";
import TeamProjectsTab from "./TeamProjectsTab";

const mockUseTeamProjects = vi.fn();
vi.mock("@/app/(dashboard)/hooks/projects/useProjects", () => ({
  useTeamProjects: (teamId: string) => mockUseTeamProjects(teamId),
}));

const project = (overrides: Partial<ProjectResponse>): ProjectResponse => ({
  project_id: "proj-1",
  project_alias: "Search",
  description: null,
  team_id: "team-1",
  budget_id: null,
  metadata: null,
  models: [],
  spend: 0,
  model_spend: null,
  model_rpm_limit: null,
  model_tpm_limit: null,
  blocked: false,
  object_permission_id: null,
  created_at: "2026-09-01T00:00:00Z",
  created_by: "admin",
  updated_at: "2026-09-01T00:00:00Z",
  updated_by: "admin",
  litellm_budget_table: null,
  ...overrides,
});

describe("TeamProjectsTab", () => {
  it("lists the team's projects with spend, budget and a link to each one", () => {
    mockUseTeamProjects.mockReturnValue({
      isLoading: false,
      data: [
        project({
          spend: 42,
          litellm_budget_table: {
            budget_id: "b1",
            max_budget: 100,
            soft_budget: null,
            max_parallel_requests: null,
            tpm_limit: null,
            rpm_limit: null,
            model_max_budget: null,
            budget_duration: "30d",
          },
        }),
      ],
    });

    renderWithProviders(<TeamProjectsTab teamId="team-1" />);

    expect(mockUseTeamProjects).toHaveBeenCalledWith("team-1");
    expect(screen.getByRole("link", { name: "Search" })).toHaveAttribute("href", "/ui/projects?project=proj-1");
    expect(screen.getByText("$42.00")).toBeInTheDocument();
    expect(screen.getByText("$100.00 (42% used)")).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
  });

  it("says so when the team has no projects", () => {
    mockUseTeamProjects.mockReturnValue({ isLoading: false, data: [] });

    renderWithProviders(<TeamProjectsTab teamId="team-1" />);

    expect(screen.getByText("This team has no projects yet.")).toBeInTheDocument();
  });
});
```

Create `TeamBudgetTab.test.tsx`:

```tsx
import { describe, expect, it } from "vitest";
import { renderWithProviders, screen } from "../../../tests/test-utils";
import TeamBudgetTab from "./TeamBudgetTab";

describe("TeamBudgetTab", () => {
  it("shows spend against the limit, when it resets, and that the gateway enforces it", () => {
    renderWithProviders(
      <TeamBudgetTab spend={25} maxBudget={100} budgetDuration="30d" budgetResetAt={null} memberBudget={null} />,
    );

    expect(screen.getByText("$25.00")).toBeInTheDocument();
    expect(screen.getByText("of $100.00 budget")).toBeInTheDocument();
    expect(screen.getByRole("meter")).toHaveAttribute("aria-valuenow", "25");
    expect(screen.getByText("Resets every 30d")).toBeInTheDocument();
    expect(screen.getByText(/the gateway blocks further requests/)).toBeInTheDocument();
    expect(screen.getByText("No per-member budget")).toBeInTheDocument();
  });

  it("says there is no limit and draws no meter for a team without a budget", () => {
    renderWithProviders(
      <TeamBudgetTab spend={25} maxBudget={null} budgetDuration={null} budgetResetAt={null} memberBudget={null} />,
    );

    expect(screen.getByText("No budget limit")).toBeInTheDocument();
    expect(screen.queryByRole("meter")).not.toBeInTheDocument();
    expect(screen.getByText("Never resets")).toBeInTheDocument();
  });

  it("shows the per-member budget when the team sets one", () => {
    renderWithProviders(
      <TeamBudgetTab
        spend={0}
        maxBudget={null}
        budgetDuration={null}
        budgetResetAt={null}
        memberBudget={{ max_budget: 500, budget_duration: "7d" }}
      />,
    );

    expect(screen.getByText("$500.00 per member, resets every 7d")).toBeInTheDocument();
  });
});
```

In `TeamInfo.test.tsx`, add below the `member_permissions` mock:

```tsx
vi.mock("@/components/team/TeamProjectsTab", () => ({
  default: ({ teamId }: { teamId: string }) => <div data-testid="team-projects-tab">{teamId}</div>,
}));
```

Add this test in the same `describe` block as `should display virtual keys information`:

```tsx
    it("adds Projects and Budget tabs before Settings for someone who can edit the team", async () => {
      vi.mocked(networking.teamInfoCall).mockResolvedValue(createMockTeamData({ max_budget: 100, spend: 25 }));

      renderWithProviders(<TeamInfoView {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByRole("tab", { name: "Projects" })).toBeInTheDocument();
      });
      expect(screen.getAllByRole("tab").map((tab) => tab.textContent)).toEqual([
        "Overview",
        "My User",
        "Virtual Keys",
        "Members",
        "Member Permissions",
        "Projects",
        "Budget",
        "Settings",
      ]);

      await userEvent.setup({ delay: null }).click(screen.getByRole("tab", { name: "Budget" }));
      expect(await screen.findByText("of $100.00 budget")).toBeInTheDocument();
    });
```

- [ ] **Step 2: Run the tests to verify they fail**

Run from `ui/litellm-dashboard`: `npx vitest run src/components/team/tabVisibilityUtils.test.ts src/components/team/TeamProjectsTab.test.tsx src/components/team/TeamBudgetTab.test.tsx src/components/team/TeamInfo.test.tsx`
Expected: FAIL. The new tab keys are undefined, the two new components cannot be resolved, and TeamInfo shows no Projects tab

- [ ] **Step 3: Implement the tab rules**

Replace `tabVisibilityUtils.ts` from the top of the file down to the end of `getTeamInfoVisibleTabs` with:

```ts
/**
 * Team info tab configuration and permission logic.
 * Extracted for testability - permission rules can be unit tested in isolation.
 */

export const TEAM_INFO_TAB_KEYS = {
  OVERVIEW: "overview",
  MY_USER: "my-user",
  VIRTUAL_KEYS: "virtual-keys",
  MEMBERS: "members",
  MEMBER_PERMISSIONS: "member-permissions",
  PROJECTS: "projects",
  BUDGET: "budget",
  SETTINGS: "settings",
} as const;

export const TEAM_INFO_TAB_LABELS: Record<string, string> = {
  [TEAM_INFO_TAB_KEYS.OVERVIEW]: "Overview",
  [TEAM_INFO_TAB_KEYS.MY_USER]: "My User",
  [TEAM_INFO_TAB_KEYS.VIRTUAL_KEYS]: "Virtual Keys",
  [TEAM_INFO_TAB_KEYS.MEMBERS]: "Members",
  [TEAM_INFO_TAB_KEYS.MEMBER_PERMISSIONS]: "Member Permissions",
  [TEAM_INFO_TAB_KEYS.PROJECTS]: "Projects",
  [TEAM_INFO_TAB_KEYS.BUDGET]: "Budget",
  [TEAM_INFO_TAB_KEYS.SETTINGS]: "Settings",
};

/**
 * Returns the list of tab keys that should be visible based on permissions.
 * - Overview, My User, Virtual Keys, Budget: always visible
 * - Members, Member Permissions, Projects, Settings: only when canEditTeam is true
 */
export function getTeamInfoVisibleTabs(canEditTeam: boolean): readonly string[] {
  const baseTabs = [TEAM_INFO_TAB_KEYS.OVERVIEW, TEAM_INFO_TAB_KEYS.MY_USER, TEAM_INFO_TAB_KEYS.VIRTUAL_KEYS];
  if (canEditTeam) {
    return [
      ...baseTabs,
      TEAM_INFO_TAB_KEYS.MEMBERS,
      TEAM_INFO_TAB_KEYS.MEMBER_PERMISSIONS,
      TEAM_INFO_TAB_KEYS.PROJECTS,
      TEAM_INFO_TAB_KEYS.BUDGET,
      TEAM_INFO_TAB_KEYS.SETTINGS,
    ];
  }
  return [...baseTabs, TEAM_INFO_TAB_KEYS.BUDGET];
}
```

- [ ] **Step 4: Add the team projects hook**

In `useProjects.ts`, replace the `fetchProjects` function signature and URL lines:

```ts
const fetchProjects = async (accessToken: string): Promise<ProjectResponse[]> => {
  const baseUrl = getProxyBaseUrl();
  const url = `${baseUrl}/project/list`;
```

with:

```ts
const fetchProjects = async (accessToken: string, teamId?: string): Promise<ProjectResponse[]> => {
  const baseUrl = getProxyBaseUrl();
  const teamQuery = teamId ? `?team_id=${encodeURIComponent(teamId)}` : "";
  const url = `${baseUrl}/project/list${teamQuery}`;
```

Add at the end of the file:

```ts
export const useTeamProjects = (teamId: string) => {
  const { accessToken, userRole } = useAuthorized();

  return useQuery<ProjectResponse[]>({
    queryKey: projectKeys.list({ filters: { team_id: teamId } }),
    queryFn: async () => fetchProjects(accessToken!, teamId),
    enabled: Boolean(accessToken && teamId) && projectReaderRoles.includes(userRole ?? ""),
  });
};
```

- [ ] **Step 5: Create the two tab components**

Create `TeamProjectsTab.tsx`:

```tsx
"use client";

import { useTeamProjects } from "@/app/(dashboard)/hooks/projects/useProjects";
import { formatProjectSpend, projectBudgetLabel } from "@/app/(dashboard)/projects/_components/projectBudget";
import { StatusBadge } from "@/components/shared/table_cells";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { migratedHref } from "@/utils/migratedPages";

interface TeamProjectsTabProps {
  teamId: string;
}

export default function TeamProjectsTab({ teamId }: TeamProjectsTabProps) {
  const { data: projects, isLoading } = useTeamProjects(teamId);

  if (isLoading) {
    return <p className="py-8 text-center text-sm text-muted-foreground">Loading projects…</p>;
  }
  if (!projects || projects.length === 0) {
    return <p className="py-8 text-center text-sm text-muted-foreground">This team has no projects yet.</p>;
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Name</TableHead>
          <TableHead>Spend</TableHead>
          <TableHead>Budget</TableHead>
          <TableHead>Status</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {projects.map((project) => (
          <TableRow key={project.project_id}>
            <TableCell>
              <a
                className="font-medium text-primary hover:underline"
                href={`${migratedHref("projects")}?project=${encodeURIComponent(project.project_id)}`}
              >
                {project.project_alias ?? project.project_id}
              </a>
            </TableCell>
            <TableCell className="tabular-nums">{formatProjectSpend(project.spend)}</TableCell>
            <TableCell className="tabular-nums">{projectBudgetLabel(project)}</TableCell>
            <TableCell>
              <StatusBadge
                tone={project.blocked ? "error" : "success"}
                label={project.blocked ? "Blocked" : "Active"}
              />
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
```

Create `TeamBudgetTab.tsx`:

```tsx
"use client";

import { Meter, MeterIndicator, MeterTrack } from "@/components/shared/Meter";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatNumberWithCommas } from "@/utils/dataUtils";

interface TeamBudgetTabProps {
  spend: number;
  maxBudget: number | null;
  budgetDuration: string | null;
  budgetResetAt: string | null;
  memberBudget: { max_budget: number; budget_duration: string | null } | null;
}

const utilisationTone = (percent: number) => (percent >= 90 ? "over" : percent >= 70 ? "warning" : "default");

export default function TeamBudgetTab({
  spend,
  maxBudget,
  budgetDuration,
  budgetResetAt,
  memberBudget,
}: TeamBudgetTabProps) {
  const limit = maxBudget !== null && maxBudget > 0 ? maxBudget : null;
  const percentUsed = limit === null ? 0 : Math.round(Math.min((spend / limit) * 100, 100));

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>Team budget</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3 text-sm">
          <p className="text-[28px] leading-none font-medium text-foreground">${formatNumberWithCommas(spend, 2)}</p>
          <p className="text-muted-foreground">
            {limit === null ? "No budget limit" : `of $${formatNumberWithCommas(limit, 2)} budget`}
          </p>
          {limit !== null && (
            <Meter value={percentUsed}>
              <MeterTrack>
                <MeterIndicator tone={utilisationTone(percentUsed)} />
              </MeterTrack>
            </Meter>
          )}
          <p>{budgetDuration ? `Resets every ${budgetDuration}` : "Never resets"}</p>
          {budgetResetAt && (
            <p className="text-muted-foreground">Next reset: {new Date(budgetResetAt).toLocaleString()}</p>
          )}
          <p className="text-muted-foreground">
            When the budget is reached, the gateway blocks further requests from this team&apos;s keys.
          </p>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Budget per member</CardTitle>
        </CardHeader>
        <CardContent className="text-sm">
          {memberBudget ? (
            <p>
              {`$${formatNumberWithCommas(memberBudget.max_budget, 2)} per member, ${
                memberBudget.budget_duration ? `resets every ${memberBudget.budget_duration}` : "never resets"
              }`}
            </p>
          ) : (
            <p className="text-muted-foreground">No per-member budget</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
```

- [ ] **Step 6: Wire the tabs into TeamInfo**

In `TeamInfo.tsx`, add with the other `@/components/team` imports near the top:

```tsx
import TeamBudgetTab from "@/components/team/TeamBudgetTab";
import TeamProjectsTab from "@/components/team/TeamProjectsTab";
```

In `tabItems`, add these two entries between the `MEMBER_PERMISSIONS` entry and the `SETTINGS` entry:

```tsx
    {
      key: TEAM_INFO_TAB_KEYS.PROJECTS,
      label: TEAM_INFO_TAB_LABELS[TEAM_INFO_TAB_KEYS.PROJECTS],
      children: <TeamProjectsTab teamId={teamId} />,
    },
    {
      key: TEAM_INFO_TAB_KEYS.BUDGET,
      label: TEAM_INFO_TAB_LABELS[TEAM_INFO_TAB_KEYS.BUDGET],
      children: (
        <TeamBudgetTab
          spend={info.spend}
          maxBudget={info.max_budget}
          budgetDuration={info.budget_duration}
          budgetResetAt={info.budget_reset_at}
          memberBudget={info.team_member_budget_table}
        />
      ),
    },
```

- [ ] **Step 7: Run the tests to verify they pass**

Run from `ui/litellm-dashboard`: `npx vitest run src/components/team/tabVisibilityUtils.test.ts src/components/team/TeamProjectsTab.test.tsx src/components/team/TeamBudgetTab.test.tsx src/components/team/TeamInfo.test.tsx`
Expected: PASS

- [ ] **Step 8: Lint and commit**

Run from `ui/litellm-dashboard`: `npx eslint src/components/team "src/app/(dashboard)/hooks/projects/useProjects.ts"`
Expected: no errors

```bash
git add ui/litellm-dashboard/src/components/team "ui/litellm-dashboard/src/app/(dashboard)/hooks/projects/useProjects.ts"
git commit -m "feat(ui): add projects and budget tabs to a team"
```

---

### Task 8: Project in the Gateway usage view picker

**Files:**
- Modify: `ui/litellm-dashboard/src/components/EntityUsageExport/types.ts:6`
- Modify: `ui/litellm-dashboard/src/app/(dashboard)/usage/_components/components/EntityUsage/EntityUsage.tsx:28-40` (networking import), `:91-100` (`ENTITY_FETCH_FNS`)
- Test: `ui/litellm-dashboard/src/app/(dashboard)/usage/_components/components/EntityUsage/EntityUsage.test.tsx`
- Modify: `ui/litellm-dashboard/src/app/(dashboard)/usage/_components/components/UsageViewSelect/UsageViewSelect.tsx:1,7-17,70`
- Test: `ui/litellm-dashboard/src/app/(dashboard)/usage/_components/components/UsageViewSelect/UsageViewSelect.test.tsx`
- Modify: `ui/litellm-dashboard/src/app/(dashboard)/usage/_components/components/UsagePageView.tsx` (hooks at the top of `UsagePage`, render block after the team block near line 932)
- Test: `ui/litellm-dashboard/src/app/(dashboard)/usage/_components/components/UsagePageView.test.tsx`

**Interfaces:**
- Consumes: `projectDailyActivityCall` from Task 6, `useProjects` from `hooks/projects/useProjects.ts`, `GET /project/daily/activity` from Task 2
- Produces: `UsageOption` and `EntityType` both gain `"project"`

The option is offered to every role, as Team Usage is, because the proxy limits the report to projects the caller can read

- [ ] **Step 1: Write the failing tests**

In `EntityUsage.test.tsx`, add `projectDailyActivityCall: vi.fn(),` to the `@/components/networking` mock. Below `const mockUserDailyActivityCall = ...` add:

```tsx
  const mockProjectDailyActivityCall = vi.mocked(networking.projectDailyActivityCall);
```

Add after `should render with team entity type and call team API`:

```tsx
  it("should render with project entity type and call the project API", async () => {
    mockProjectDailyActivityCall.mockResolvedValue(mockSpendData);

    render(<EntityUsage {...defaultProps} entityType="project" />);

    await waitFor(() => {
      expect(mockProjectDailyActivityCall).toHaveBeenCalled();
    });
    expect(screen.getByText("Project Spend Overview")).toBeInTheDocument();
  });
```

In `UsageViewSelect.test.tsx`, add inside `describe("UsageViewSelect")`:

```tsx
  it("offers Project Usage to a user who is not an admin, since the proxy limits it to their teams", async () => {
    const user = userEvent.setup();
    const { container } = render(<UsageViewSelect value="global" onChange={mockOnChange} userRole="Internal User" />);

    await openMenu(user);

    expect(offers(container, "Project Usage")).toBe(true);
  });

  it("should call onChange with project when Project Usage is chosen", async () => {
    const user = userEvent.setup();
    render(<UsageViewSelect value="global" onChange={mockOnChange} userRole="Admin" />);

    await chooseSelectOption(user, screen.getByRole("combobox"), /^Project Usage/);

    expect(mockOnChange.mock.calls[0][0]).toBe("project");
  });
```

In `UsagePageView.test.tsx`, add below the `useUsers` mock:

```tsx
vi.mock("@/app/(dashboard)/hooks/projects/useProjects", () => ({
  useProjects: vi.fn(() => ({
    data: [
      { project_id: "proj-1", project_alias: "Search" },
      { project_id: "proj-2", project_alias: null },
    ],
  })),
}));
```

In the mocked `UsageViewSelect`, add this option directly after the Team Usage option:

```tsx
      React.createElement("option", { value: "project" }, "Project Usage"),
```

Add after `should drop the previous range's tags as soon as the range changes`:

```tsx
  it("shows project usage with the caller's projects to filter by", async () => {
    renderWithProviders(<UsagePage {...defaultProps} />);

    act(() => {
      fireEvent.change(screen.getByTestId("usage-view-select"), { target: { value: "project" } });
    });

    const entityUsage = await screen.findByTestId("entity-usage");
    expect(entityUsage).toHaveAttribute("data-entity-type", "project");
    expect(entityUsage).toHaveAttribute(
      "data-entity-list",
      JSON.stringify([
        { label: "Search", value: "proj-1" },
        { label: "proj-2", value: "proj-2" },
      ]),
    );
  });
```

- [ ] **Step 2: Run the tests to verify they fail**

Run from `ui/litellm-dashboard`: `npx vitest run "src/app/(dashboard)/usage/_components/components/EntityUsage/EntityUsage.test.tsx" "src/app/(dashboard)/usage/_components/components/UsageViewSelect/UsageViewSelect.test.tsx" "src/app/(dashboard)/usage/_components/components/UsagePageView.test.tsx"`
Expected: FAIL. EntityUsage has no fetch function for `project`, the picker has no Project Usage option, and the usage page renders nothing for `project`

- [ ] **Step 3: Implement**

`types.ts`:

```ts
export type EntityType = "tag" | "team" | "organization" | "customer" | "agent" | "user" | "project";
```

`EntityUsage.tsx`: add `projectDailyActivityCall,` to the `@/components/networking` import list and add this entry to `ENTITY_FETCH_FNS` after `team`:

```tsx
  project: projectDailyActivityCall,
```

`UsageViewSelect.tsx`:

1. Add `Folder` to the `lucide-react` import: `import { BarChart3, Bot, Building2, Folder, Globe, LineChart, ShoppingCart, Tags, User, Users } from "lucide-react";`
2. Add `| "project"` to `UsageOption` directly after `| "team"`
3. Add this entry to `OPTIONS` directly after the `team` entry:

```tsx
  {
    value: "project",
    label: "Project Usage",
    description: "View usage by project",
    icon: <Folder className="size-4" />,
  },
```

`UsagePageView.tsx`:

1. Add `import { useProjects } from "@/app/(dashboard)/hooks/projects/useProjects";` with the other hook imports
2. At the top of `UsagePage`, next to the other data hooks, add:

```tsx
  const { data: projects } = useProjects();
```

3. Directly after the `{usageView === "team" && ( ... )}` block, add:

```tsx
          {usageView === "project" && (
            <EntityUsage
              accessToken={accessToken}
              entityType="project"
              userID={userID}
              userRole={userRole}
              entityList={
                projects?.map((project) => ({
                  label: project.project_alias ?? project.project_id,
                  value: project.project_id,
                })) ?? null
              }
              premiumUser={premiumUser}
              dateValue={dateValue}
            />
          )}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run the same command as Step 2
Expected: PASS

- [ ] **Step 5: Lint and commit**

Run from `ui/litellm-dashboard`: `npx eslint "src/app/(dashboard)/usage/_components/components" src/components/EntityUsageExport/types.ts`
Expected: no errors

```bash
git add ui/litellm-dashboard/src/components/EntityUsageExport/types.ts "ui/litellm-dashboard/src/app/(dashboard)/usage/_components/components"
git commit -m "feat(ui): add project usage to the gateway usage view picker"
```

---

### Task 9: Check everything together, then push

**Files:** none changed unless a check fails

- [ ] **Step 1: Backend tests and lint**

Run: `.venv/Scripts/python -m pytest tests/test_litellm/proxy/management_endpoints/test_project_endpoints.py tests/test_litellm/proxy/ui_crud_endpoints/test_proxy_setting_endpoints.py tests/test_litellm/proxy/auth -q`
Expected: all PASS, apart from failures already recorded as pre-existing on this branch

Run `make lint` with a long timeout. It may print "all N machine-wide slots are busy; queueing" and wait; let it. If a budget gate reports lowered violations, run `make lint-budget-update` and commit the lowered limits
Expected: no new violations

- [ ] **Step 2: Dashboard type-check**

Run from `ui/litellm-dashboard`: `npx tsc --noEmit`
Expected: exit code 0. Fix only errors in files this plan touched, and commit each fix with a message naming what it fixes

- [ ] **Step 3: Try it against a live proxy**

Start the proxy with `~/.claude/scripts/litellm-dev-up.sh` (port 4001). Load the master key from `.env` without printing it, then:

```bash
set -a; . ./.env; set +a
curl -s http://localhost:4001/project/list -H "Authorization: Bearer $LITELLM_MASTER_KEY"
curl -s "http://localhost:4001/project/daily/activity?start_date=2026-08-16&end_date=2026-09-15" -H "Authorization: Bearer $LITELLM_MASTER_KEY"
curl -s http://localhost:4001/get/ui_settings | grep -o '"enable_projects_ui":[a-z]*'
```

Expected: a JSON list of projects (not a 422 about a missing `team_id`), a daily activity report, and `"enable_projects_ui":true`

Then start the dashboard with `npm run dev` in `ui/litellm-dashboard` and check as a proxy admin:

1. Projects is in the sidebar without a Beta label and the page lists projects with Spend and Budget columns
2. A project's page shows "Spend by Model, last 30 days" with bars for a project that has sent requests
3. A team's page has Projects and Budget tabs before Settings
4. Usage offers Project Usage, and choosing it shows project spend

Log in as a user who administers one team (not a proxy admin) and check that Projects appears and lists only that team's projects

- [ ] **Step 4: Push**

```bash
git push origin litellm_token_iq
```
