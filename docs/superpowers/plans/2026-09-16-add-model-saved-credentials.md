# Add Model Uses Saved Credentials Only Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Model stops offering a field for typing a provider key and offers a saved credential instead, with a New credential button beside the picker, credentials a team admin owns for their own team, credentials that hold connection details without a secret, and a one-click move of an existing model's typed key into a saved credential.

**Architecture:** A credential's owning team is recorded in the `credential_info` blob it already carries, so no database change is needed and the value travels into the in-memory credential list the router reads. The credential endpoints gain team-admin access with scoping by that field. The model endpoints gain two rules beside the existing one: a billing credential may never serve a model, and a team admin may only attach a credential their team owns. On the dashboard, Add Model loses the typed-key fields, gains a New credential dialog in place, and a model's detail page gains an action that saves its typed key as a credential and switches the model to it.

**Tech Stack:** FastAPI, pytest on the proxy; Next.js, react-hook-form, shadcn, vitest with Testing Library on the dashboard

**Spec:** `docs/superpowers/specs/2026-09-14-token-iq-product-design.md`, section "Add Model uses saved credentials only" with its four conditions, plus "Credentials" and "Phases" (Phase 2)

## Global Constraints

- All work goes on the branch `litellm_token_iq`. Never touch `main`, never create another branch
- Python runs from the repo venv, `.venv/Scripts/python`, never the system Python
- Never run the full vitest suite. Run `npx vitest run <paths>` from `ui/litellm-dashboard` with explicit paths
- No existing page or tab is removed or merged
- Use the words teams, projects and users. Never "employees"
- No customer-visible LiteLLM text
- Never port code from `enterprise/` or `litellm_enterprise`
- Never put secrets in code, tests, commits or logs; tests use obviously fake keys such as `sk-test-not-real`
- New Python follows the project CLAUDE.md: every variable annotated `Final`, no new `Any`, no mutable collections in annotations or construction, no `# type: ignore`, lines up to 120 characters, comments only where logic needs them
- Dashboard follows `ui/litellm-dashboard/CLAUDE.md`; never put tokens in `localStorage`
- Commit messages follow conventional commits and carry no Claude attribution (the project CLAUDE.md forbids it)
- Commit after each task. Push `litellm_token_iq` at the end

## What is already in place

From the previous plan, on this branch:

- A billing credential is `credential_info = {"purpose": "billing_ingestion", "provider": "<slug>"}`; `is_billing_credential(credential_info)` and `billing_credential_problem(...)` live in `litellm/provider_billing/credential_purpose.py`
- `GET /credentials` and `/credentials/by_name` return `credential_values: {}` for billing credentials
- `PATCH /credentials/{name}` merges `credential_info` and refuses a change of `purpose` or `provider`
- The dashboard helper `modelAccessCredentials(credentials)` already filters billing credentials out of every picker, and `buildCredentialPayload(values)` builds the create and update payloads
- `litellm_credential_name` is refused in client request bodies

Facts this plan builds on, each verified in the code:

- `LiteLLM_CredentialsTable` has no team column, and `credential_info` is free-form JSON that survives into `litellm.credential_list` and into every read response
- `/credentials` appears in no non-admin route list, so `RouteChecks.non_proxy_admin_allowed_routes_check` refuses every non-admin caller today
- `ModelManagementAuthChecks.can_user_attach_credential` (`litellm/proxy/management_endpoints/model_management_endpoints.py:1492`) allows a proxy admin, allows an unchanged credential name, and otherwise refuses. It is called from `patch_model` (:722), `add_new_model` (:1839) and `update_model` (:2016)
- `update_db_model` merges `litellm_params` and can only clear the pricing fields in `SPECIAL_MODEL_INFO_PARAMS`, so removing a typed key from a model needs a narrow clear path
- `GET /public/providers/fields` serves `litellm/proxy/public_endpoints/provider_create_fields.json`. Required fields are rare: OpenAI requires `api_key`, Azure requires `api_base`, Vertex requires `vertex_project` and `vertex_location`, and Bedrock and Ollama require nothing. So a credential that carries connection details without a secret already passes validation for the providers the spec names
- `POST /credentials` refuses only a `None` value blob, so `credential_values: {}` is already accepted

## Decisions this plan makes

| Question | Decision | Why |
|---|---|---|
| Where a credential's owning team is recorded | `credential_info.team_id` | No migration, and the value already travels into memory and into read responses |
| What a team admin sees | Their own teams' credentials only | The spec's condition 2 |
| What a proxy admin sees | Every credential, with the owning team shown | An admin has to be able to clean up |
| Who may edit or delete a team credential | A proxy admin, or a team admin of that team | Same rule as creating it |
| Attaching a credential to a model | A proxy admin may attach any model access credential; a team admin may attach one their team owns, to a model of that team | Matches the existing team-BYOK model rule |
| A billing credential attached to a model | Refused for everyone, on create and on update | It is a read-only cost key, and this closes a finding parked in the previous plan |
| Typing a key in Add Model | Removed from the dashboard only | The spec says the UI changes first and the API and config are decided later from real usage |
| Moving an existing model's typed key | One action that saves the key as a credential, switches the model to it, and clears the typed key | The spec's condition 4, and nothing is converted automatically |

## File Map

Backend:
- Create `litellm/proxy/credential_endpoints/credential_access.py`: who may read, create, change and attach a credential
- Create `tests/test_litellm/proxy/credential_endpoints/test_credential_access.py`
- Modify `litellm/proxy/credential_endpoints/endpoints.py`: scope reads, record the owning team on create, guard edit and delete
- Modify `tests/test_litellm/proxy/credential_endpoints/test_endpoints.py`
- Modify `litellm/proxy/_types.py`: `/credentials` reachable by non-admins, with the endpoints doing the scoping
- Modify `litellm/proxy/management_endpoints/model_management_endpoints.py`: the two new attach rules, and a clear path for a typed key
- Modify `tests/test_litellm/proxy/management_endpoints/test_model_management_endpoints.py`
- Regenerate `ui/litellm-dashboard/src/lib/http/schema.d.ts`

Dashboard (paths under `ui/litellm-dashboard/src`):
- Create `components/model_add/NewCredentialButton.tsx`
- Modify `components/add_model/AddModelForm.tsx`, `AddModelForm.test.tsx`
- Modify `components/add_model/handle_add_model_submit.tsx`
- Modify `components/model_add/CredentialsTableColumns.tsx`, `CredentialsTable.test.tsx`
- Modify `components/model_add/CredentialsPanel.tsx`, `CredentialsPanel.test.tsx`
- Create `components/model_info_view/moveKeyToCredential.ts` and `moveKeyToCredential.test.ts`
- Modify `components/model_info_view.tsx`, `model_info_view.test.tsx`

---

### Task 1: Who may read, create and change a credential

**Files:**
- Create: `litellm/proxy/credential_endpoints/credential_access.py`
- Create: `tests/test_litellm/proxy/credential_endpoints/test_credential_access.py`

**Interfaces:**
- Produces: `CREDENTIAL_TEAM_KEY: Final = "team_id"`
- Produces: `credential_team(credential_info: Mapping[str, object] | None) -> str | None`
- Produces: `teams_user_administers(user_api_key_dict: UserAPIKeyAuth, prisma_client: Any) -> Awaitable[frozenset[str]]`
- Produces: `may_read_credential(credential_info, *, is_admin: bool, administered_teams: frozenset[str]) -> bool`
- Produces: `may_change_credential(credential_info, *, is_admin: bool, administered_teams: frozenset[str]) -> bool`

A credential with no `team_id` belongs to the whole installation: every admin may read and change it, and a team admin may read it but not change it, because it is shared with teams they do not run.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_litellm/proxy/credential_endpoints/test_credential_access.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_litellm/proxy/credential_endpoints/test_credential_access.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'litellm.proxy.credential_endpoints.credential_access'`

- [ ] **Step 3: Implement**

Create `litellm/proxy/credential_endpoints/credential_access.py`:

```python
"""Who may read, create and change a stored credential.

A credential's owning team is recorded in `credential_info`, which the table already
carries as free-form JSON and which travels unchanged into the in-memory credential list
the router reads. A credential with no team belongs to the whole installation: a team
admin may use it, but may not edit or delete it, because it serves teams they do not run.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final

from litellm.proxy._types import LitellmUserRoles, UserAPIKeyAuth
from litellm.proxy.management_endpoints.common_utils import _is_user_team_admin
from litellm.models.team import LiteLLM_TeamTable

CREDENTIAL_TEAM_KEY: Final = "team_id"


def credential_team(credential_info: Mapping[str, object] | None) -> str | None:
    """The team that owns this credential, or None when the installation does."""
    if credential_info is None:
        return None
    team: Final = credential_info.get(CREDENTIAL_TEAM_KEY)
    return team if isinstance(team, str) and team else None


async def teams_user_administers(
    user_api_key_dict: UserAPIKeyAuth,
    prisma_client: Any,  # any-ok: PrismaClient is an untyped runtime wrapper
) -> frozenset[str]:
    """Every team this caller is an admin of. Empty for a proxy admin, who needs no list."""
    if user_api_key_dict.user_role == LitellmUserRoles.PROXY_ADMIN:
        return frozenset()
    rows: Final = await prisma_client.db.litellm_teamtable.find_many()
    return frozenset(
        team.team_id
        for team in (LiteLLM_TeamTable.model_validate(row.model_dump()) for row in rows)
        if _is_user_team_admin(user_api_key_dict=user_api_key_dict, team_obj=team)
    )


def may_read_credential(
    credential_info: Mapping[str, object] | None,
    *,
    is_admin: bool,
    administered_teams: frozenset[str],
) -> bool:
    """Whether this caller may see the credential at all."""
    if is_admin:
        return True
    if not administered_teams:
        return False
    owner: Final = credential_team(credential_info)
    return owner is None or owner in administered_teams


def may_change_credential(
    credential_info: Mapping[str, object] | None,
    *,
    is_admin: bool,
    administered_teams: frozenset[str],
) -> bool:
    """Whether this caller may edit or delete the credential."""
    if is_admin:
        return True
    owner: Final = credential_team(credential_info)
    return owner is not None and owner in administered_teams
```

Import `LiteLLM_TeamTable` from wherever `project_endpoints.py` imports it; if that import path differs, follow the one already used there and record the deviation.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_litellm/proxy/credential_endpoints/test_credential_access.py -q`
Expected: all PASS

- [ ] **Step 5: Lint and commit**

Run: `.venv/Scripts/python -m ruff check litellm/proxy/credential_endpoints/credential_access.py tests/test_litellm/proxy/credential_endpoints/test_credential_access.py`
Run: `.venv/Scripts/python scripts/check_type_discipline.py litellm/proxy/credential_endpoints/credential_access.py`
Expected: no errors

```bash
git add litellm/proxy/credential_endpoints/credential_access.py tests/test_litellm/proxy/credential_endpoints/test_credential_access.py
git commit -m "feat(credentials): decide who may read and change a team's credentials"
```

---

### Task 2: The credential endpoints scope to the caller's teams

**Files:**
- Modify: `litellm/proxy/credential_endpoints/endpoints.py` (`create_credential`, `get_credentials`, `get_credential_by_name`, `update_credential`, `delete_credential`)
- Modify: `litellm/proxy/_types.py` (route lists)
- Test: `tests/test_litellm/proxy/credential_endpoints/test_endpoints.py`

**Interfaces:**
- Consumes: everything Task 1 produces
- Produces: `POST /credentials` records `credential_info.team_id` for a team admin; a proxy admin may set it explicitly or leave it out
- Produces: `GET /credentials` returns only credentials the caller may read; every other credential route answers 403 for a credential they may not read or change
- Produces: `/credentials` reachable by non-admin callers, with the endpoints doing the scoping

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_litellm/proxy/credential_endpoints/test_endpoints.py`:

```python
TEAM_ADMIN = UserAPIKeyAuth(user_role=LitellmUserRoles.INTERNAL_USER, api_key="sk-lead", user_id="lead")


def _as_team_admin_request(method: str, path: str, body: dict | None = None):
    missing = object()
    previous_override = app.dependency_overrides.get(user_api_key_auth, missing)
    app.dependency_overrides[user_api_key_auth] = lambda: TEAM_ADMIN
    try:
        return client.request(method, path, json=body, headers={"Authorization": "Bearer sk-lead"})
    finally:
        if previous_override is missing:
            app.dependency_overrides.pop(user_api_key_auth, None)
        else:
            app.dependency_overrides[user_api_key_auth] = previous_override


def test_a_team_admin_creating_a_credential_gets_their_team_recorded_on_it():
    """Condition 2 of the spec: a team admin's credential belongs to their team, so the
    list can show them only their own."""
    with patch("litellm.proxy.proxy_server.prisma_client", MagicMock()), patch(
        "litellm.proxy.proxy_server.master_key", "sk-test-master"
    ), patch("litellm.proxy.credential_endpoints.endpoints.CredentialsRepository") as repository, patch(
        "litellm.proxy.credential_endpoints.endpoints.teams_user_administers",
        AsyncMock(return_value=frozenset({"team-a"})),
    ), patch("litellm.proxy.credential_endpoints.endpoints.CredentialAccessor.upsert_credentials"):
        repository.return_value.create = AsyncMock(return_value=None)

        response = _as_team_admin_request(
            "POST",
            "/credentials",
            {
                "credential_name": "team-a-openai",
                "credential_values": {"api_key": "sk-test-not-real"},
                "credential_info": {"custom_llm_provider": "openai"},
            },
        )

    assert response.status_code == 200, response.text
    written = repository.return_value.create.await_args.kwargs["data"]
    info = written["credential_info"]
    assert (json.loads(info) if isinstance(info, str) else info)["team_id"] == "team-a"


def test_a_team_admin_who_administers_no_team_cannot_create_a_credential():
    with patch("litellm.proxy.proxy_server.prisma_client", MagicMock()), patch(
        "litellm.proxy.credential_endpoints.endpoints.CredentialsRepository"
    ) as repository, patch(
        "litellm.proxy.credential_endpoints.endpoints.teams_user_administers",
        AsyncMock(return_value=frozenset()),
    ):
        repository.return_value.create = AsyncMock(return_value=None)

        response = _as_team_admin_request(
            "POST",
            "/credentials",
            {
                "credential_name": "nope",
                "credential_values": {"api_key": "sk-test-not-real"},
                "credential_info": {"custom_llm_provider": "openai"},
            },
        )

    assert response.status_code == 403, response.text
    repository.return_value.create.assert_not_awaited()


def test_a_team_admin_cannot_put_a_credential_in_another_team():
    with patch("litellm.proxy.proxy_server.prisma_client", MagicMock()), patch(
        "litellm.proxy.credential_endpoints.endpoints.CredentialsRepository"
    ) as repository, patch(
        "litellm.proxy.credential_endpoints.endpoints.teams_user_administers",
        AsyncMock(return_value=frozenset({"team-a"})),
    ):
        repository.return_value.create = AsyncMock(return_value=None)

        response = _as_team_admin_request(
            "POST",
            "/credentials",
            {
                "credential_name": "sneaky",
                "credential_values": {"api_key": "sk-test-not-real"},
                "credential_info": {"custom_llm_provider": "openai", "team_id": "team-b"},
            },
        )

    assert response.status_code == 403, response.text
    repository.return_value.create.assert_not_awaited()


def test_the_list_shows_a_team_admin_only_their_own_and_the_shared_credentials():
    import litellm

    mine = CredentialItem(
        credential_name="team-a-openai",
        credential_values={"api_key": "sk-test-not-real"},
        credential_info={"custom_llm_provider": "openai", "team_id": "team-a"},
    )
    theirs = CredentialItem(
        credential_name="team-b-openai",
        credential_values={"api_key": "sk-test-not-real"},
        credential_info={"custom_llm_provider": "openai", "team_id": "team-b"},
    )
    shared = CredentialItem(
        credential_name="shared-openai",
        credential_values={"api_key": "sk-test-not-real"},
        credential_info={"custom_llm_provider": "openai"},
    )
    with patch("litellm.proxy.proxy_server.prisma_client", MagicMock()), patch.object(
        litellm, "credential_list", [mine, theirs, shared]
    ), patch(
        "litellm.proxy.credential_endpoints.endpoints.teams_user_administers",
        AsyncMock(return_value=frozenset({"team-a"})),
    ):
        response = _as_team_admin_request("GET", "/credentials")

    assert response.status_code == 200, response.text
    names = {row["credential_name"] for row in response.json()["credentials"]}
    assert names == {"team-a-openai", "shared-openai"}


def test_a_team_admin_cannot_read_another_team_s_credential_by_name():
    import litellm

    theirs = CredentialItem(
        credential_name="team-b-openai",
        credential_values={"api_key": "sk-test-not-real"},
        credential_info={"custom_llm_provider": "openai", "team_id": "team-b"},
    )
    with patch("litellm.proxy.proxy_server.prisma_client", MagicMock()), patch.object(
        litellm, "credential_list", [theirs]
    ), patch(
        "litellm.proxy.credential_endpoints.endpoints.teams_user_administers",
        AsyncMock(return_value=frozenset({"team-a"})),
    ):
        response = _as_team_admin_request("GET", "/credentials/by_name/team-b-openai")

    assert response.status_code == 403, response.text


def test_a_team_admin_cannot_change_a_shared_credential():
    """A shared credential serves teams they do not run."""
    stored = CredentialItem(
        credential_name="shared-openai",
        credential_values={"api_key": "sk-test-not-real"},
        credential_info={"custom_llm_provider": "openai"},
    )
    with patch("litellm.proxy.proxy_server.prisma_client", MagicMock()), patch(
        "litellm.proxy.credential_endpoints.endpoints.CredentialsRepository"
    ) as repository, patch(
        "litellm.proxy.credential_endpoints.endpoints.teams_user_administers",
        AsyncMock(return_value=frozenset({"team-a"})),
    ):
        repository.return_value.find_by_name = AsyncMock(return_value=stored)
        repository.return_value.update_by_name = AsyncMock(return_value=None)
        repository.return_value.delete_by_name = AsyncMock(return_value=None)

        patched = _as_team_admin_request(
            "PATCH",
            "/credentials/shared-openai",
            {"credential_name": "shared-openai", "credential_values": {"api_key": "sk-test-not-real-2"}, "credential_info": {}},
        )
        deleted = _as_team_admin_request("DELETE", "/credentials/shared-openai")

    assert patched.status_code == 403, patched.text
    assert deleted.status_code == 403, deleted.text
    repository.return_value.update_by_name.assert_not_awaited()
    repository.return_value.delete_by_name.assert_not_awaited()


def test_a_team_admin_may_change_their_own_team_s_credential():
    stored = CredentialItem(
        credential_name="team-a-openai",
        credential_values={"api_key": "sk-test-not-real"},
        credential_info={"custom_llm_provider": "openai", "team_id": "team-a"},
    )
    with patch("litellm.proxy.proxy_server.prisma_client", MagicMock()), patch(
        "litellm.proxy.proxy_server.master_key", "sk-test-master"
    ), patch("litellm.proxy.credential_endpoints.endpoints.CredentialsRepository") as repository, patch(
        "litellm.proxy.credential_endpoints.endpoints.teams_user_administers",
        AsyncMock(return_value=frozenset({"team-a"})),
    ):
        repository.return_value.find_by_name = AsyncMock(return_value=stored)
        repository.return_value.update_by_name = AsyncMock(return_value=None)

        response = _as_team_admin_request(
            "PATCH",
            "/credentials/team-a-openai",
            {"credential_name": "team-a-openai", "credential_values": {"api_key": "sk-test-not-real-2"}, "credential_info": {}},
        )

    assert response.status_code == 200, response.text
    repository.return_value.update_by_name.assert_awaited_once()


def test_a_credential_with_connection_details_and_no_secret_is_accepted():
    """Condition 3 of the spec: Bedrock and Vertex on cloud permissions, and a local
    Ollama, carry a base URL or a region but no key."""
    with patch("litellm.proxy.proxy_server.prisma_client", MagicMock()), patch(
        "litellm.proxy.proxy_server.master_key", "sk-test-master"
    ), patch("litellm.proxy.credential_endpoints.endpoints.CredentialsRepository") as repository, patch(
        "litellm.proxy.credential_endpoints.endpoints.CredentialAccessor.upsert_credentials"
    ):
        repository.return_value.create = AsyncMock(return_value=None)

        response = _as_admin_request(
            "POST",
            "/credentials",
            {
                "credential_name": "local-ollama",
                "credential_values": {"api_base": "http://localhost:11434"},
                "credential_info": {"custom_llm_provider": "ollama"},
            },
        )

    assert response.status_code == 200, response.text
    repository.return_value.create.assert_awaited_once()
```

`_as_admin_request` already exists in this file from the previous plan. Add `from litellm.proxy._types import LitellmUserRoles` to the imports if it is not there, and `import json` if the file does not already import it.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_litellm/proxy/credential_endpoints/test_endpoints.py -q`
Expected: the new tests FAIL. The team admin gets 401 from the route check or the credential is written with no team recorded

- [ ] **Step 3: Make the routes reachable**

In `litellm/proxy/_types.py`, add the credential routes to `self_managed_routes`, next to the project routes added earlier, with this comment:

```python
        # Credential routes - the endpoints scope every read and write to the
        # teams the caller administers, and a non-admin who administers no team
        # is refused there.
        "/credentials",
        "/credentials/by_name/{credential_name}",
```

Do not add them to `internal_user_routes`. Check how the project routes were written (they are listed by path with no method) and follow the same form. If the delete and patch routes are matched by a different path pattern, add the pattern that `RouteChecks.check_route_access` matches, and prove it with the route-level test below.

- [ ] **Step 4: Scope the endpoints**

In `litellm/proxy/credential_endpoints/endpoints.py`, add to the imports:

```python
from litellm.proxy.credential_endpoints.credential_access import (
    CREDENTIAL_TEAM_KEY,
    credential_team,
    may_change_credential,
    may_read_credential,
    teams_user_administers,
)
```

Add this helper next to `_refuse_unfit_billing_credential`:

```python
async def _caller_scope(
    user_api_key_dict: UserAPIKeyAuth,
    prisma_client: Any,  # any-ok: PrismaClient is an untyped runtime wrapper
) -> tuple[bool, frozenset[str]]:
    """Whether the caller is an admin, and which teams they administer."""
    is_admin: Final = user_api_key_has_admin_view(user_api_key_dict)
    if is_admin:
        return True, frozenset()
    return False, await teams_user_administers(user_api_key_dict, prisma_client)
```

Add `user_api_key_has_admin_view` to the `litellm.proxy._types` import list, and `Any` and `Final` to the typing import if they are missing.

In `create_credential`, after the billing check, add:

```python
        is_admin, administered_teams = await _caller_scope(user_api_key_dict, prisma_client)
        requested_team: Final = credential_team(credential.credential_info)
        if not is_admin:
            if not administered_teams:
                raise HTTPException(
                    status_code=403,
                    detail="Only a proxy admin or a team admin can store a credential.",
                )
            if requested_team is not None and requested_team not in administered_teams:
                raise HTTPException(
                    status_code=403,
                    detail=f"You do not administer team {requested_team}, so you cannot store a credential for it.",
                )
            owning_team: Final = requested_team or sorted(administered_teams)[0]
            credential.credential_info = {**credential.credential_info, CREDENTIAL_TEAM_KEY: owning_team}
```

A team admin who administers exactly one team gets it recorded without choosing; one who administers several must name the team, which the dashboard does for them in Task 4.

In `get_credentials`, replace the list comprehension with a scoped one:

```python
        is_admin, administered_teams = await _caller_scope(user_api_key_dict, _prisma_or_none())
        masked_credentials: Final = [
            {
                "credential_name": credential.credential_name,
                "credential_values": {}
                if is_billing_credential(credential.credential_info)
                else _get_masked_values(credential.credential_values),
                "credential_info": credential.credential_info,
            }
            for credential in litellm.credential_list
            if may_read_credential(
                credential.credential_info, is_admin=is_admin, administered_teams=administered_teams
            )
        ]
```

Add a small `_prisma_or_none()` helper that imports `prisma_client` from `proxy_server` and returns it, so this read path does not fail when the database is not connected and the caller is an admin (an admin needs no team lookup).

In `get_credential_by_name`, after finding the credential and before returning it, refuse when `may_read_credential(...)` is False with 403 and the message "You do not administer the team that owns this credential."

In `update_credential`, after `db_credential` is found, refuse when `may_change_credential(db_credential.credential_info, ...)` is False, with the same 403 message. Also refuse a patch that changes `team_id` to a team the caller does not administer, in the same shape as the purpose guard added in the previous plan.

In `delete_credential`, read the credential first through `CredentialsRepository.find_by_name`, answer 404 when it is missing, and refuse with 403 when `may_change_credential(...)` is False. Only then delete.

- [ ] **Step 5: Add the route-level test**

In the route check test file (find it under `tests/test_litellm/proxy/auth/`, the same file the projects plan used for its route test), add a test that `RouteChecks.non_proxy_admin_allowed_routes_check` allows an internal user on `/credentials`, matching how that file's existing tests call it.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_litellm/proxy/credential_endpoints tests/test_litellm/proxy/auth -q`
Expected: PASS, apart from failures already recorded as pre-existing on this branch

- [ ] **Step 7: Lint and commit**

Run: `.venv/Scripts/python -m ruff check litellm/proxy/credential_endpoints/endpoints.py litellm/proxy/_types.py tests/test_litellm/proxy/credential_endpoints/test_endpoints.py`
Run: `.venv/Scripts/python scripts/check_type_discipline.py litellm/proxy/credential_endpoints/endpoints.py` and show the count is no higher than before your change
Expected: no new violations

```bash
git add litellm/proxy/credential_endpoints/endpoints.py litellm/proxy/_types.py tests/test_litellm/proxy/credential_endpoints tests/test_litellm/proxy/auth
git commit -m "feat(credentials): let team admins keep credentials for their own team"
```

---

### Task 3: A model may only use a credential that fits it

**Files:**
- Modify: `litellm/proxy/management_endpoints/model_management_endpoints.py` (`ModelManagementAuthChecks.can_user_attach_credential` at :1492 and its three call sites at :722, :1839, :2016)
- Test: `tests/test_litellm/proxy/management_endpoints/test_model_management_endpoints.py` (class `TestModelManagementAuthChecks`, the credential tests at :267-:391)

**Interfaces:**
- Consumes: `is_billing_credential` from `credential_purpose.py`, and `credential_team` from Task 1
- Produces: `can_user_attach_credential(litellm_params, user_api_key_dict, existing_litellm_params=None, *, credential_info=None, model_team_id=None) -> Literal[True]`, raising `ProxyException` otherwise

Rules, in order: an unchanged credential name is always allowed; a billing credential is refused for everyone; a proxy admin may attach any model access credential; a team admin may attach a credential their team owns to a model of that team; anyone else is refused.

- [ ] **Step 1: Write the failing tests**

Add to `TestModelManagementAuthChecks` in `tests/test_litellm/proxy/management_endpoints/test_model_management_endpoints.py`, following the style of the existing credential tests there:

```python
    def test_can_user_attach_credential_refuses_a_billing_credential_for_an_admin(self):
        """A billing credential is a read-only cost key. Serving models with it would spend
        against the organisation's admin key and, for OpenAI and Anthropic, would not work."""
        admin = UserAPIKeyAuth(user_role=LitellmUserRoles.PROXY_ADMIN, api_key="sk-a", user_id="admin")

        with pytest.raises(ProxyException) as exc:
            ModelManagementAuthChecks.can_user_attach_credential(
                litellm_params=GenericLiteLLMParams(litellm_credential_name="anthropic-costs"),
                user_api_key_dict=admin,
                credential_info={"purpose": "billing_ingestion", "provider": "anthropic"},
            )

        assert exc.value.code == "403"
        assert "billing" in str(exc.value.message).lower()

    def test_can_user_attach_credential_allows_a_team_admin_their_own_team_s_credential(self):
        lead = UserAPIKeyAuth(user_role=LitellmUserRoles.INTERNAL_USER, api_key="sk-l", user_id="lead")

        assert (
            ModelManagementAuthChecks.can_user_attach_credential(
                litellm_params=GenericLiteLLMParams(litellm_credential_name="team-a-openai"),
                user_api_key_dict=lead,
                credential_info={"custom_llm_provider": "openai", "team_id": "team-a"},
                model_team_id="team-a",
            )
            is True
        )

    def test_can_user_attach_credential_refuses_a_team_admin_another_team_s_credential(self):
        lead = UserAPIKeyAuth(user_role=LitellmUserRoles.INTERNAL_USER, api_key="sk-l", user_id="lead")

        with pytest.raises(ProxyException):
            ModelManagementAuthChecks.can_user_attach_credential(
                litellm_params=GenericLiteLLMParams(litellm_credential_name="team-b-openai"),
                user_api_key_dict=lead,
                credential_info={"custom_llm_provider": "openai", "team_id": "team-b"},
                model_team_id="team-a",
            )

    def test_can_user_attach_credential_refuses_a_team_credential_on_a_model_of_another_team(self):
        """Otherwise a team admin could lend their key to a model any other team can call."""
        lead = UserAPIKeyAuth(user_role=LitellmUserRoles.INTERNAL_USER, api_key="sk-l", user_id="lead")

        with pytest.raises(ProxyException):
            ModelManagementAuthChecks.can_user_attach_credential(
                litellm_params=GenericLiteLLMParams(litellm_credential_name="team-a-openai"),
                user_api_key_dict=lead,
                credential_info={"custom_llm_provider": "openai", "team_id": "team-a"},
                model_team_id=None,
            )

    def test_can_user_attach_credential_still_refuses_a_shared_credential_for_a_team_admin(self):
        lead = UserAPIKeyAuth(user_role=LitellmUserRoles.INTERNAL_USER, api_key="sk-l", user_id="lead")

        with pytest.raises(ProxyException):
            ModelManagementAuthChecks.can_user_attach_credential(
                litellm_params=GenericLiteLLMParams(litellm_credential_name="shared-openai"),
                user_api_key_dict=lead,
                credential_info={"custom_llm_provider": "openai"},
                model_team_id="team-a",
            )
```

Reuse the imports and helpers the existing tests in that class already use; if they build `GenericLiteLLMParams` differently, follow that.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/Scripts/python -m pytest "tests/test_litellm/proxy/management_endpoints/test_model_management_endpoints.py::TestModelManagementAuthChecks" -q`
Expected: FAIL with an unexpected keyword argument `credential_info`

- [ ] **Step 3: Implement**

In `model_management_endpoints.py`, add the two keyword-only parameters to `can_user_attach_credential` and the new rules, keeping the existing unchanged-name shortcut first:

```python
    @staticmethod
    def can_user_attach_credential(
        litellm_params: GenericLiteLLMParams | None,
        user_api_key_dict: UserAPIKeyAuth,
        existing_litellm_params: GenericLiteLLMParams | None = None,
        *,
        credential_info: Mapping[str, object] | None = None,
        model_team_id: str | None = None,
    ) -> Literal[True]:
        if litellm_params is None or litellm_params.litellm_credential_name is None:
            return True
        if existing_litellm_params is not None and existing_litellm_params.litellm_credential_name is not None:
            existing_credential_name: Final = decrypt_value_helper(
                value=existing_litellm_params.litellm_credential_name,
                key="litellm_credential_name",
                exception_type="debug",
                return_original_value=True,
            )
            if litellm_params.litellm_credential_name == existing_credential_name:
                return True
        if is_billing_credential(credential_info):
            raise ProxyException(
                message=(
                    f"Credential {litellm_params.litellm_credential_name} reads a provider's bill and cannot "
                    "serve models. Use a model access credential."
                ),
                type=ProxyErrorTypes.auth_error.value,
                code=status.HTTP_403_FORBIDDEN,
                param="litellm_credential_name",
            )
        if user_api_key_dict.user_role == LitellmUserRoles.PROXY_ADMIN:
            return True
        owner: Final = credential_team(credential_info)
        if owner is not None and model_team_id == owner and _is_team_admin_of(user_api_key_dict, owner):
            return True
        raise ProxyException(
            message=(
                "Only a proxy admin can attach a stored credential (litellm_credential_name) to a model, "
                "or a team admin attaching their own team's credential to that team's model. "
                f"Your role={user_api_key_dict.user_role}."
            ),
            type=ProxyErrorTypes.auth_error.value,
            code=status.HTTP_403_FORBIDDEN,
            param="litellm_credential_name",
        )
```

`_is_team_admin_of` needs the caller's membership. The existing team checks in this file already resolve a team; find how `allow_team_model_action` (:1517) proves team admin status and reuse that helper rather than adding a second way. If it needs the database and this function is synchronous, make the credential rules a separate `async` check called from the three call sites instead, and keep `can_user_attach_credential` synchronous for the admin and billing rules. Record whichever shape you choose.

At each of the three call sites (:722, :1839, :2016), look the credential up so `credential_info` can be passed: use `CredentialsRepository(prisma_client).find_by_name(...)`, or `litellm.credential_list` if the call site has no database handle. When the named credential does not exist, refuse with 400 and the message "Credential {name} was not found." Pass the model's team from the model's own `model_info.team_id` on that path.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_litellm/proxy/management_endpoints/test_model_management_endpoints.py -q`
Expected: PASS

- [ ] **Step 5: Lint and commit**

Run: `.venv/Scripts/python -m ruff check litellm/proxy/management_endpoints/model_management_endpoints.py tests/test_litellm/proxy/management_endpoints/test_model_management_endpoints.py`
Run: `.venv/Scripts/python scripts/check_type_discipline.py litellm/proxy/management_endpoints/model_management_endpoints.py` and show no new violations
Expected: no new violations

```bash
git add litellm/proxy/management_endpoints/model_management_endpoints.py tests/test_litellm/proxy/management_endpoints/test_model_management_endpoints.py
git commit -m "feat(models): refuse a billing credential on a model and let team admins use their own"
```

---

### Task 4: Add Model offers saved credentials only

**Files:**
- Create: `ui/litellm-dashboard/src/components/model_add/NewCredentialButton.tsx`
- Modify: `ui/litellm-dashboard/src/components/add_model/AddModelForm.tsx` (the credential block around lines 289-322)
- Modify: `ui/litellm-dashboard/src/components/add_model/handle_add_model_submit.tsx`
- Modify: `ui/litellm-dashboard/src/components/model_add/CredentialsTableColumns.tsx`
- Test: `ui/litellm-dashboard/src/components/add_model/AddModelForm.test.tsx`, `ui/litellm-dashboard/src/components/model_add/CredentialsTable.test.tsx`

**Interfaces:**
- Consumes: `modelAccessCredentials`, `buildCredentialPayload` from `credential_form_helpers.ts`; `useCredentials`; the backend rules from Tasks 2 and 3
- Produces: `NewCredentialButton({ provider, teamId, onCreated }: { provider?: string; teamId?: string | null; onCreated: (credentialName: string) => void })`, which opens the existing `CredentialModal` in add mode, saves through `credentialCreateCall`, refreshes the credential list, and calls `onCreated` with the new name

- [ ] **Step 1: Write the failing tests**

In `AddModelForm.test.tsx`, add to the top-level `describe("AddModelForm")`:

```tsx
  it("offers saved credentials and no field for typing a provider key", async () => {
    renderForm();

    expect(await screen.findByText("Existing Credentials")).toBeInTheDocument();
    expect(screen.queryByText(/Either select existing credentials OR enter new provider credentials/)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/^API Key/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /New credential/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Manage LLM Provider Credentials/ })).toHaveAttribute(
      "href",
      expect.stringContaining("llm-provider-credentials"),
    );
  });

  it("selects a credential created from the New credential dialog", async () => {
    const user = userEvent.setup();
    renderForm();

    await user.click(await screen.findByRole("button", { name: /New credential/ }));
    await user.click(await screen.findByTestId("credential-modal-add-submit"));

    await waitFor(() => expect(credentialCreateCall).toHaveBeenCalled());
    expect(await screen.findByText("new-cred")).toBeInTheDocument();
  });

  it("leaves billing credentials out of the picker", async () => {
    renderForm({
      credentials: [
        { credential_name: "openai-models", credential_values: {}, credential_info: { custom_llm_provider: "openai" } },
        {
          credential_name: "anthropic-costs",
          credential_values: {},
          credential_info: { purpose: "billing_ingestion", provider: "anthropic" },
        },
      ],
    });

    await user_openCredentialPicker();
    expect(screen.getByText("openai-models")).toBeInTheDocument();
    expect(screen.queryByText("anthropic-costs")).not.toBeInTheDocument();
  });
```

Match the file's existing render helper name and props, and its mock of `@/components/networking`; the file already builds a `credentials` array, so extend that path rather than inventing a new one. Replace `user_openCredentialPicker()` with however the file's other tests open a `SearchSelect` (the repo has a `chooseSelectOption` helper in the test utils). Stub `CredentialModal` the way `CredentialsPanel.test.tsx` does, so the dialog submits fixed values.

In `CredentialsTable.test.tsx`, add:

```tsx
  it("should show which team owns a credential", () => {
    renderTable({
      credentials: [
        { credential_name: "shared-openai", credential_values: {}, credential_info: { custom_llm_provider: "OpenAI" } },
        {
          credential_name: "team-a-openai",
          credential_values: {},
          credential_info: { custom_llm_provider: "OpenAI", team_id: "team-a" },
        },
      ],
    });

    expect(screen.getByRole("columnheader", { name: /Owner/ })).toBeInTheDocument();
    expect(screen.getByText("Whole installation")).toBeInTheDocument();
    expect(screen.getByText("team-a")).toBeInTheDocument();
  });
```

- [ ] **Step 2: Run the tests to verify they fail**

Run from `ui/litellm-dashboard`: `npx vitest run src/components/add_model/AddModelForm.test.tsx src/components/model_add/CredentialsTable.test.tsx`
Expected: FAIL. The OR text and typed fields are still there, there is no New credential button, and the table has no Owner column

- [ ] **Step 3: Build the New credential button**

Create `components/model_add/NewCredentialButton.tsx`:

```tsx
"use client";

import { Plus } from "lucide-react";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
import { credentialCreateCall } from "@/components/networking";
import { Button } from "@/components/ui/button";
import { toast } from "@/lib/toast";

import CredentialModal from "./CredentialModal";
import { buildCredentialPayload } from "./credential_form_helpers";

interface NewCredentialButtonProps {
  teamId?: string | null;
  onCreated: (credentialName: string) => void;
}

export default function NewCredentialButton({ teamId, onCreated }: NewCredentialButtonProps) {
  const { accessToken } = useAuthorized();
  const queryClient = useQueryClient();
  const [isOpen, setIsOpen] = useState(false);

  const handleSubmit = async (values: Record<string, unknown>) => {
    if (!accessToken) {
      return;
    }
    const payload = buildCredentialPayload(values);
    const withOwner = teamId
      ? { ...payload, credential_info: { ...payload.credential_info, team_id: teamId } }
      : payload;
    try {
      await credentialCreateCall(accessToken, withOwner);
      toast.success("Credential added");
      setIsOpen(false);
      await queryClient.invalidateQueries({ queryKey: ["credentials"] });
      onCreated(withOwner.credential_name);
    } catch (error) {
      toast.error(error instanceof Error && error.message ? error.message : "Failed to add credential");
    }
  };

  return (
    <>
      <Button type="button" variant="outline" onClick={() => setIsOpen(true)}>
        <Plus className="size-4" />
        New credential
      </Button>
      {isOpen && (
        <CredentialModal mode="add" open={isOpen} onCancel={() => setIsOpen(false)} onSubmit={handleSubmit} />
      )}
    </>
  );
}
```

Check the exact query key `useCredentials` uses (`createQueryKeys("credentials").list({})`) and invalidate that key rather than the string above if they differ. Check how `CredentialsPanel` shows an error and follow it, so both places behave the same.

- [ ] **Step 4: Change the Add Model form**

In `AddModelForm.tsx`:

1. Replace the "Either select existing credentials OR enter new provider credentials below" line with a short one: "Choose a saved credential for this provider."
2. Keep the `MountedFormField` for `litellm_credential_name`, and filter its options with `modelAccessCredentials(credentials)`
3. Beside the picker, render `<NewCredentialButton teamId={selectedTeamId} onCreated={(name) => form.setValue("litellm_credential_name", name)} />` and a link to the credentials page built with `migratedHref("llm-provider-credentials")`, labelled "Manage LLM Provider Credentials". Use the form's existing setter; read how the file sets other fields
4. Delete the `{!selectedCredentialName && (...)}` block that renders the OR divider and `<ProviderSpecificFields ... />`, so the form no longer offers typed provider fields. Leave `ProviderSpecificFields` itself alone: `CredentialModal` still uses it
5. Make the credential required: add a rule to the `MountedFormField` so submitting with nothing selected shows "Select a credential, or create one"

In `handle_add_model_submit.tsx`, nothing needs to change, since the credential name is already forwarded and typed fields simply stop arriving. Confirm by reading the loop, and if a field it strips is now always absent, leave that code as it is.

- [ ] **Step 5: Add the Owner column**

In `CredentialsTableColumns.tsx`, add after the Purpose column:

```tsx
    {
      id: "owner",
      meta: { title: "Owner" },
      header: "Owner",
      size: 160,
      enableSorting: false,
      cell: ({ row }) => (
        <span className="text-sm">{row.original.credential_info?.team_id ?? "Whole installation"}</span>
      ),
    },
```

Add `team_id?: string;` to `CredentialItem.credential_info` in `components/networking.tsx` if it is not already there from the previous plan.

- [ ] **Step 6: Run the tests to verify they pass**

Run from `ui/litellm-dashboard`: `npx vitest run src/components/add_model/AddModelForm.test.tsx src/components/model_add/CredentialsTable.test.tsx src/components/model_add/CredentialsPanel.test.tsx src/components/model_add/CredentialModal.test.tsx "src/app/(dashboard)/models-and-endpoints/page.test.tsx"`
Expected: PASS

Check `npx tsc --noEmit` for errors in the files you touched and fix those. Restore `ui/litellm-dashboard/tsconfig.tsbuildinfo` with `git checkout --` if it changed.

- [ ] **Step 7: Lint and commit**

Run from `ui/litellm-dashboard`: `npx eslint src/components/add_model src/components/model_add src/components/networking.tsx`
Expected: no errors on lines you changed

```bash
git add ui/litellm-dashboard/src/components/add_model ui/litellm-dashboard/src/components/model_add ui/litellm-dashboard/src/components/networking.tsx
git commit -m "feat(ui): add model picks a saved credential and can create one in place"
```

---

### Task 5: Move an existing model's typed key into a saved credential

**Files:**
- Create: `ui/litellm-dashboard/src/components/model_info_view/moveKeyToCredential.ts`
- Create: `ui/litellm-dashboard/src/components/model_info_view/moveKeyToCredential.test.ts`
- Modify: `ui/litellm-dashboard/src/components/model_info_view.tsx` (the Re-use Credentials button around line 643 and `handleReuseCredential` around line 286)
- Test: `ui/litellm-dashboard/src/components/model_info_view.test.tsx`
- Modify: `litellm/proxy/management_endpoints/model_management_endpoints.py` (`update_db_model`, the clear list)
- Test: `tests/test_litellm/proxy/management_endpoints/test_model_management_endpoints.py`

**Interfaces:**
- Produces: `buildMoveKeyRequests(modelId: string, credentialName: string, provider: string, litellmParams: Record<string, unknown>): { credential: { credential_name: string; model_id: string; credential_info: Record<string, unknown> }; modelUpdate: { model_id: string; litellm_params: Record<string, unknown> } }`
- Produces: a model update may clear the credential-carrying fields (`api_key`, `aws_access_key_id`, `aws_secret_access_key`, `aws_session_token`, `vertex_credentials`, `azure_ad_token`, `client_secret`) by sending them as null, only when `litellm_credential_name` is set in the same request

Today `handleReuseCredential` creates a credential from the model but leaves the model using its typed key, so nothing actually moves. The backend merges `litellm_params` and can only clear pricing fields, so the clear list has to grow for the key to go away.

- [ ] **Step 1: Write the failing backend test**

Add to `tests/test_litellm/proxy/management_endpoints/test_model_management_endpoints.py`, in the class that covers `update_db_model` (find it; if there is none, add the test to `TestModelManagementAuthChecks`'s file at module level following its style):

```python
def test_attaching_a_credential_clears_the_typed_key_it_replaces():
    """Moving a model onto a stored credential has to remove the key typed into the model,
    or the secret stays in the model row for ever."""
    db_model = Deployment(
        model_name="gpt-4o",
        litellm_params=LiteLLM_Params(model="gpt-4o", api_key="sk-test-not-real"),
        model_info=ModelInfo(id="m-1"),
    )
    patch_data = updateDeployment(
        litellm_params=updateLiteLLMParams(litellm_credential_name="openai-models", api_key=None),
    )

    updated = update_db_model(db_model=db_model, updated_patch=patch_data)

    assert "api_key" not in updated["litellm_params"]
    assert updated["litellm_params"]["litellm_credential_name"] is not None


def test_a_null_key_without_a_credential_does_not_clear_anything():
    """Only the move action may clear a key, so a stray null cannot strip a working model."""
    db_model = Deployment(
        model_name="gpt-4o",
        litellm_params=LiteLLM_Params(model="gpt-4o", api_key="sk-test-not-real"),
        model_info=ModelInfo(id="m-1"),
    )
    patch_data = updateDeployment(litellm_params=updateLiteLLMParams(api_key=None))

    updated = update_db_model(db_model=db_model, updated_patch=patch_data)

    assert updated["litellm_params"]["api_key"] is not None
```

Use the imports and construction the file's existing `update_db_model` tests use; if the model classes differ, follow them.

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_litellm/proxy/management_endpoints/test_model_management_endpoints.py -k "clears_the_typed_key or without_a_credential" -q`
Expected: FAIL, the key survives the update

- [ ] **Step 3: Implement the clear path**

In `model_management_endpoints.py`, add near `SPECIAL_MODEL_INFO_PARAMS`:

```python
CREDENTIAL_CARRYING_PARAMS: Final = (
    "api_key",
    "aws_access_key_id",
    "aws_secret_access_key",
    "aws_session_token",
    "vertex_credentials",
    "azure_ad_token",
    "client_secret",
)
"""Fields that hold a secret on the model row. They may be cleared only in the same update
that attaches a stored credential, which is how a typed key moves into one."""
```

In `update_db_model`, after the existing `SPECIAL_MODEL_INFO_PARAMS` clear loop, add:

```python
    if updated_patch.litellm_params and updated_patch.litellm_params.litellm_credential_name is not None:
        for field in updated_patch.litellm_params.model_fields_set:
            if field in CREDENTIAL_CARRYING_PARAMS and getattr(updated_patch.litellm_params, field) is None:
                merged_litellm_params.pop(field, None)
```

- [ ] **Step 4: Write the failing dashboard tests**

Create `components/model_info_view/moveKeyToCredential.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { buildMoveKeyRequests } from "./moveKeyToCredential";

describe("buildMoveKeyRequests", () => {
  it("saves the model's key as a credential and switches the model onto it", () => {
    const { credential, modelUpdate } = buildMoveKeyRequests("m-1", "openai-prod", "openai", {
      model: "gpt-4o",
      api_key: "sk-test-not-real",
    });

    expect(credential).toEqual({
      credential_name: "openai-prod",
      model_id: "m-1",
      credential_info: { custom_llm_provider: "openai" },
    });
    expect(modelUpdate.model_id).toBe("m-1");
    expect(modelUpdate.litellm_params.litellm_credential_name).toBe("openai-prod");
    expect(modelUpdate.litellm_params.api_key).toBeNull();
  });

  it("clears every secret the model carried, not only an api key", () => {
    const { modelUpdate } = buildMoveKeyRequests("m-2", "aws-prod", "bedrock", {
      model: "anthropic.claude-3",
      aws_access_key_id: "AKIATESTNOTREAL",
      aws_secret_access_key: "test-not-real",
      aws_region_name: "us-east-1",
    });

    expect(modelUpdate.litellm_params.aws_access_key_id).toBeNull();
    expect(modelUpdate.litellm_params.aws_secret_access_key).toBeNull();
    expect("aws_region_name" in modelUpdate.litellm_params).toBe(false);
  });

  it("asks for nothing to be cleared when the model carries no secret", () => {
    const { modelUpdate } = buildMoveKeyRequests("m-3", "ollama-local", "ollama", {
      model: "llama3",
      api_base: "http://localhost:11434",
    });

    expect(Object.keys(modelUpdate.litellm_params)).toEqual(["litellm_credential_name"]);
  });
});
```

In `model_info_view.test.tsx`, add a test in the block that already covers the Re-use Credentials button:

```tsx
  it("moves the model onto the credential it just saved", async () => {
    const user = userEvent.setup();
    renderView();

    await user.click(await screen.findByTestId("reuse-credentials-button"));
    await user.type(screen.getByLabelText(/Credential name/i), "openai-prod");
    await user.click(screen.getByRole("button", { name: /Save and use/i }));

    await waitFor(() => expect(credentialCreateCall).toHaveBeenCalled());
    const payload = vi.mocked(modelUpdateCall).mock.calls.at(-1)?.[1] as { litellm_params: Record<string, unknown> };
    expect(payload.litellm_params.litellm_credential_name).toBe("openai-prod");
    expect(payload.litellm_params.api_key).toBeNull();
  });
```

Match the file's existing render helper, its mocked networking names and the modal's real labels and button text; read `reuse_credentials.tsx` for them and change the button label there to "Save and use" if it differs.

- [ ] **Step 5: Run the dashboard tests to verify they fail**

Run from `ui/litellm-dashboard`: `npx vitest run src/components/model_info_view/moveKeyToCredential.test.ts src/components/model_info_view.test.tsx`
Expected: FAIL, the helper does not exist and the model is never updated

- [ ] **Step 6: Implement the dashboard side**

Create `components/model_info_view/moveKeyToCredential.ts`:

```ts
const SECRET_FIELDS = [
  "api_key",
  "aws_access_key_id",
  "aws_secret_access_key",
  "aws_session_token",
  "vertex_credentials",
  "azure_ad_token",
  "client_secret",
] as const;

export interface MoveKeyRequests {
  credential: { credential_name: string; model_id: string; credential_info: Record<string, unknown> };
  modelUpdate: { model_id: string; litellm_params: Record<string, unknown> };
}

export const buildMoveKeyRequests = (
  modelId: string,
  credentialName: string,
  provider: string,
  litellmParams: Record<string, unknown>,
): MoveKeyRequests => {
  const cleared = Object.fromEntries(
    SECRET_FIELDS.filter((field) => litellmParams[field] !== undefined && litellmParams[field] !== null).map(
      (field) => [field, null],
    ),
  );
  return {
    credential: {
      credential_name: credentialName,
      model_id: modelId,
      credential_info: { custom_llm_provider: provider },
    },
    modelUpdate: {
      model_id: modelId,
      litellm_params: { litellm_credential_name: credentialName, ...cleared },
    },
  };
};
```

In `model_info_view.tsx`, change `handleReuseCredential` so that after `credentialCreateCall` succeeds it also calls the model update with `modelUpdate` from `buildMoveKeyRequests`, refreshes the model view, and reports "Key moved into credential {name}". Use the file's existing model update call and its refresh path; read how `handleModelUpdate` does both. Keep the button disabled for anyone who cannot edit the model, as it is today, and change its label to "Move key into a credential" so it says what it does.

- [ ] **Step 7: Run every test in this task**

Run: `.venv/Scripts/python -m pytest tests/test_litellm/proxy/management_endpoints/test_model_management_endpoints.py -q`
Run from `ui/litellm-dashboard`: `npx vitest run src/components/model_info_view/moveKeyToCredential.test.ts src/components/model_info_view.test.tsx`
Expected: PASS

- [ ] **Step 8: Lint and commit**

Run: `.venv/Scripts/python -m ruff check litellm/proxy/management_endpoints/model_management_endpoints.py`
Run from `ui/litellm-dashboard`: `npx eslint src/components/model_info_view.tsx src/components/model_info_view`
Expected: no new errors

```bash
git add litellm/proxy/management_endpoints/model_management_endpoints.py tests/test_litellm/proxy/management_endpoints/test_model_management_endpoints.py ui/litellm-dashboard/src/components/model_info_view.tsx ui/litellm-dashboard/src/components/model_info_view ui/litellm-dashboard/src/components/model_info_view.test.tsx
git commit -m "feat(models): move a model's typed key into a saved credential in one action"
```

---

### Task 6: Check it end to end, then push

**Files:** none changed unless a check fails

- [ ] **Step 1: Regenerate the dashboard API types**

Start the proxy with `bash ~/.claude/scripts/litellm-dev-up.sh` (port 4001, dev key `sk-1234`), then run from `ui/litellm-dashboard`: `npm run gen:api`
Commit `src/lib/http/schema.d.ts` if it changed, with message `chore(ui): regenerate api types after the credential changes`

- [ ] **Step 2: Backend and dashboard checks**

Run: `.venv/Scripts/python -m pytest tests/test_litellm/proxy/credential_endpoints tests/test_litellm/proxy/management_endpoints/test_model_management_endpoints.py tests/test_litellm/provider_billing tests/test_litellm/proxy/auth -q`
Expected: PASS apart from failures already recorded as pre-existing on this branch

Run from `ui/litellm-dashboard`: `npx tsc --noEmit` and confirm no error falls in a file this plan changed

- [ ] **Step 3: Live check**

With the proxy running, as the dev admin key `sk-1234`:

```bash
curl -s -X POST http://localhost:4001/credentials -H "Authorization: Bearer sk-1234" -H "Content-Type: application/json" \
  -d '{"credential_name":"plan-check-ollama","credential_values":{"api_base":"http://localhost:11434"},"credential_info":{"custom_llm_provider":"ollama"}}'
curl -s -X POST http://localhost:4001/model/new -H "Authorization: Bearer sk-1234" -H "Content-Type: application/json" \
  -d '{"model_name":"plan-check-model","litellm_params":{"model":"ollama/llama3","litellm_credential_name":"plan-check-ollama"}}'
curl -s -X POST http://localhost:4001/model/new -H "Authorization: Bearer sk-1234" -H "Content-Type: application/json" \
  -d '{"model_name":"plan-check-bad","litellm_params":{"model":"gpt-4o","litellm_credential_name":"plan-check-billing"}}'
```

Expected: the credential with no secret is stored; the model using it is created; the third refuses, either because the credential does not exist or, if you first create a billing credential named `plan-check-billing`, because a billing credential cannot serve models. Delete whatever you created afterwards and confirm it is gone

- [ ] **Step 4: Push**

```bash
git push origin litellm_token_iq
```

Then hand the user these click-through steps, with the dashboard at `npx next dev -p 3001` in `ui/litellm-dashboard`:
1. Add Model shows a credential picker, a New credential button and a Manage LLM Provider Credentials link, and no field for typing a key
2. New credential saves and selects it without leaving the page
3. Adding a model with no credential selected is refused with "Select a credential, or create one"
4. The credentials list shows an Owner column
5. On a model created earlier with a typed key, "Move key into a credential" saves the key as a credential, switches the model onto it, and the model's parameters no longer show the key
6. As a team admin who is not a proxy admin: the credentials page lists only their own team's credentials and the shared ones, and creating one records their team
