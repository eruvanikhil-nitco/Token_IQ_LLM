# Release Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a Token IQ installation buildable and presentable to a customer: production images that build from a clean checkout, an audit trail that works on both tabs and only for admins, and no LiteLLM branding in customer-facing messages

**Architecture:** Four independent fixes. The Dockerfiles stop referring to the deleted `enterprise/` folder, guarded by a check that every build context path they copy exists in the repository. The Logs page's Audit Logs tab renders the working audit view from Admin Settings instead of a panel that calls a deleted route. `/audit/list` refuses everyone except proxy admins and admin viewers. Remaining customer-facing messages are reworded and guarded by a check that fails when a new one names LiteLLM

**Tech Stack:** Docker, Python 3.12, FastAPI, pytest, Next.js with Vitest

**Spec:** `docs/superpowers/specs/2026-09-14-token-iq-product-design.md`, sections "How Token IQ is sold and delivered", "Licensing rules" and "Phases" (Phase 0)

## Global Constraints

- All Python runs in the repository venv: every command uses `.venv/Scripts/python`
- No existing page or tab is removed: the Logs page keeps its Audit Logs tab and only changes what renders inside it
- No text a customer can see mentions LiteLLM, except the exclusions listed in Task 4 with their reasons
- New code annotates variables `Final`, and Python line length is 120
- Tests check behaviour, not code structure
- CI supply-chain rules apply to anything added under `.github/`: pinned versions, no piping remote scripts into a shell
- Run this plan after `docs/superpowers/plans/2026-09-14-token-iq-plan-system.md`, because Task 4's check expects the licence wording that plan removes
- Deploying to a cloud is out of scope until the cloud provider is chosen. This plan ends with an image that builds and boots

## File map

| File | Responsibility |
|---|---|
| `tests/code_coverage_tests/check_dockerfile_context_paths_exist.py` (create) | Fails when a Dockerfile copies or mounts a path the repository does not track |
| `Dockerfile`, `docker/Dockerfile.non_root`, `docker/Dockerfile.database`, `backend/Dockerfile`, `gateway/Dockerfile`, `migrations/Dockerfile`, `docker-compose.yml` (modify) | Build without `enterprise/` |
| `ui/litellm-dashboard/src/components/view_logs/index.tsx`, `index.test.tsx` (modify) | Logs page Audit Logs tab renders the working audit view |
| `ui/litellm-dashboard/src/components/view_logs/AuditLogsPanel.tsx`, `AuditLogsTable.tsx`, `AuditLogsTable.test.tsx`, `AuditLogsTableColumns.tsx`, `AuditLogDrawer/` (delete) | The panel that called the deleted `/audit` route |
| `ui/litellm-dashboard/src/components/networking.tsx` (modify) | Remove `uiAuditLogsCall` |
| `litellm/proxy/management_endpoints/audit_log_endpoints.py` (modify) | Admin-only audit trail |
| `tests/test_litellm/proxy/management_endpoints/test_audit_log_endpoints.py` (create) | Who may read the audit trail |
| `tests/code_coverage_tests/check_customer_messages_do_not_name_litellm.py` (create) | Fails when a customer-facing message names LiteLLM |

---

### Task 1: Production images build from a clean checkout

Every main Dockerfile still copies `enterprise/pyproject.toml`, and three copy `/app/enterprise` into the runtime image. Commit `728daee2d8` deleted that folder, so a build from a clean checkout fails

**Files:**
- Create: `tests/code_coverage_tests/check_dockerfile_context_paths_exist.py`
- Modify: `Dockerfile:59,130-133`, `docker/Dockerfile.non_root:62,142-145`, `docker/Dockerfile.database:57,121-124`, `backend/Dockerfile:42`, `gateway/Dockerfile:42`, `migrations/Dockerfile:54`, `docker-compose.yml:7`

- [ ] **Step 1: Write the failing check**

```python
"""Every path a Dockerfile copies or bind-mounts from the build context must be tracked in git.

A path that exists only in someone's working copy, such as a deleted folder whose compiled files
linger on disk, builds locally and fails on a clean checkout.
"""

import re
import subprocess
import sys
from pathlib import Path
from typing import Final

REPO: Final = Path(__file__).resolve().parents[2]
DOCKERFILES: Final = (
    "Dockerfile",
    "docker/Dockerfile.non_root",
    "docker/Dockerfile.database",
    "backend/Dockerfile",
    "gateway/Dockerfile",
    "migrations/Dockerfile",
)
COPY_FROM_CONTEXT: Final = re.compile(r"^\s*COPY\s+(?!--from)(?:--\S+\s+)*(?P<args>\S.*)$")
BIND_SOURCE: Final = re.compile(r"type=bind,source=(?P<source>[^,\s]+)")


def context_paths(dockerfile_text: str) -> tuple[str, ...]:
    copied: Final = tuple(
        source
        for match in map(COPY_FROM_CONTEXT.match, dockerfile_text.splitlines())
        if match is not None
        for source in match.group("args").split()[:-1]
    )
    mounted: Final = tuple(match.group("source") for match in BIND_SOURCE.finditer(dockerfile_text))
    return tuple(path for path in (*copied, *mounted) if path not in (".", "./") and "*" not in path)


def is_tracked(path: str) -> bool:
    listed: Final = subprocess.run(
        ["git", "ls-files", "--", path.rstrip("/")], cwd=REPO, capture_output=True, text=True, check=True
    )
    return bool(listed.stdout.strip())


def main() -> int:
    missing: Final = tuple(
        f"{dockerfile}: {path}"
        for dockerfile in DOCKERFILES
        for path in context_paths((REPO / dockerfile).read_text(encoding="utf-8"))
        if not is_tracked(path)
    )
    for line in missing:
        print(f"untracked build context path  {line}")
    if missing:
        return 1
    print(f"Every build context path in {len(DOCKERFILES)} Dockerfiles is tracked.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/Scripts/python tests/code_coverage_tests/check_dockerfile_context_paths_exist.py`

Expected: exit code 1, listing `enterprise/pyproject.toml` for all six Dockerfiles

- [ ] **Step 3: Remove the enterprise references**

In `Dockerfile`, `docker/Dockerfile.non_root` and `docker/Dockerfile.database`, delete the line:

```dockerfile
COPY enterprise/pyproject.toml enterprise/
```

and delete this runtime block, including its three comment lines:

```dockerfile
# enterprise/ is imported by source path at runtime (proxy_cli puts the
# working directory on sys.path; litellm/proxy/hooks resolves
# enterprise.enterprise_hooks from it)
COPY --from=builder /app/enterprise /app/enterprise
```

In `backend/Dockerfile`, `gateway/Dockerfile` and `migrations/Dockerfile`, delete the line:

```dockerfile
    --mount=type=bind,source=enterprise/pyproject.toml,target=enterprise/pyproject.toml \
```

In `docker-compose.yml`, replace `image: docker.litellm.ai/berriai/litellm:main-stable` with `image: token-iq/gateway:local`

- [ ] **Step 4: Run the check to verify it passes**

Run: `.venv/Scripts/python tests/code_coverage_tests/check_dockerfile_context_paths_exist.py`

Expected: exit code 0 and `Every build context path in 6 Dockerfiles is tracked.`

- [ ] **Step 5: Build and boot the image from a clean clone**

A clean clone matters here, because this working copy still holds the deleted folder's compiled files. Docker Desktop must be running

```bash
rm -rf /tmp/token-iq-build
git clone --quiet --no-local . /tmp/token-iq-build
docker build --target runtime -t token-iq/gateway:phase0 /tmp/token-iq-build
K=$(grep -E '^LITELLM_MASTER_KEY' .env | cut -d= -f2- | tr -d ' "')
DB=$(grep -E '^\s*DATABASE_URL' .env | cut -d= -f2- | tr -d ' "' | sed 's/127\.0\.0\.1/host.docker.internal/')
docker run -d --name token-iq-phase0 -p 4002:4000 -e LITELLM_MASTER_KEY="$K" -e DATABASE_URL="$DB" token-iq/gateway:phase0
until curl -sf localhost:4002/health/liveliness; do sleep 5; done
docker rm -f token-iq-phase0
```

Expected: the build finishes without a `COPY` error, and the liveliness probe answers `"I'm alive!"`. Both secrets are read from `.env` into shell variables and never printed

- [ ] **Step 6: Commit**

```bash
git add tests/code_coverage_tests/check_dockerfile_context_paths_exist.py Dockerfile docker/Dockerfile.non_root docker/Dockerfile.database backend/Dockerfile gateway/Dockerfile migrations/Dockerfile docker-compose.yml
git commit -m "fix(docker): build images without the removed enterprise folder"
```

---

### Task 2: The Logs page Audit Logs tab shows the working audit trail

Admin Settings / Audit Log already works: `AuditLogView` reads `/audit/list`, a fresh implementation added on 2026-09-10. The Logs page's Audit Logs tab renders `AuditLogsPanel`, which calls `/audit`, a route that lived in the deleted enterprise code, so it shows nothing. The tab stays and renders `AuditLogView`. The Logs page keeps every tab mounted, so the view renders only while its tab is selected, which preserves the existing rule that background tabs do not query

**Files:**
- Modify: `ui/litellm-dashboard/src/components/view_logs/index.tsx`
- Modify: `ui/litellm-dashboard/src/components/view_logs/index.test.tsx`
- Modify: `ui/litellm-dashboard/src/components/networking.tsx` (delete `uiAuditLogsCall` and the `UiAuditLogsCallOptions` type it uses)
- Delete: `ui/litellm-dashboard/src/components/view_logs/AuditLogsPanel.tsx`, `AuditLogsTable.tsx`, `AuditLogsTable.test.tsx`, `AuditLogsTableColumns.tsx`, `AuditLogDrawer/`

**Interfaces:**
- Consumes: `AuditLogView` default export from `@/components/Settings/AdminSettings/AuditLog/AuditLogView`, which takes no props

- [ ] **Step 1: Update the tests to expect the working view**

In `index.test.tsx`, replace the `vi.mock("./AuditLogsPanel", ...)` block with:

```tsx
vi.mock("@/components/Settings/AdminSettings/AuditLog/AuditLogView", () => ({
  default: function AuditLogViewMock() {
    return <div data-testid="audit-log-view" />;
  },
}));
```

In `marks only the visible tab's panel active so background tabs do not query`, replace:

```tsx
    expect(await screen.findByTestId("audit-logs-panel")).toHaveTextContent("active");
```

with:

```tsx
    expect(await screen.findByTestId("audit-log-view")).toBeInTheDocument();
```

Replace every `queryByTestId("audit-logs-panel")` with `queryByTestId("audit-log-view")`

In `activates the panel the admin selected, not the one at the old hardcoded index` and `keeps the audit panel inert when an admin selects the last tab`, replace:

```tsx
      expect(screen.getByTestId("audit-logs-panel")).toHaveTextContent("inactive");
```

with:

```tsx
      expect(screen.queryByTestId("audit-log-view")).not.toBeInTheDocument();
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd ui/litellm-dashboard && npx vitest run src/components/view_logs/index.test.tsx`

Expected: FAIL, because `audit-log-view` never renders while the page still uses `AuditLogsPanel`

- [ ] **Step 3: Render the working view**

In `index.tsx`, replace:

```tsx
import AuditLogsPanel from "./AuditLogsPanel";
```

with:

```tsx
import AuditLogView from "@/components/Settings/AdminSettings/AuditLog/AuditLogView";
```

replace the `case "audit logs":` branch with:

```tsx
      case "audit logs":
        return activeTab === "audit logs" ? <AuditLogView /> : null;
```

and remove `premiumUser` from the destructured parameters of `SpendLogsTable`, keeping it in `SpendLogsTableProps` because callers still pass it

- [ ] **Step 4: Delete the dead panel**

```bash
cd ui/litellm-dashboard/src/components/view_logs
git rm AuditLogsPanel.tsx AuditLogsTable.tsx AuditLogsTable.test.tsx AuditLogsTableColumns.tsx
git rm -r AuditLogDrawer
```

In `networking.tsx`, delete `export const uiAuditLogsCall` and the `UiAuditLogsCallOptions` interface it takes

Run: `cd ui/litellm-dashboard && grep -rnE "AuditLogsPanel|uiAuditLogsCall|UiAuditLogsCallOptions|AuditLogsTable|AuditLogDrawer" src`

Expected: no output

- [ ] **Step 5: Run the tests and the type check**

Run: `cd ui/litellm-dashboard && npx vitest run src/components/view_logs src/components/Settings/AdminSettings/AuditLog && npx tsc --noEmit`

Expected: PASS and no type errors

- [ ] **Step 6: Commit**

```bash
git add -A ui/litellm-dashboard/src
git commit -m "fix(ui): show the working audit trail on the Logs page"
```

---

### Task 3: Only admins read the audit trail

`/audit/list` checks no role. Internal users are refused by the route rules, but organisation admins reach it through the `/audit` prefix in `LiteLLMRoutes.admin_viewer_routes`, which `org_admin_allowed_routes` includes, and the trail covers every team in the installation

**Files:**
- Modify: `litellm/proxy/management_endpoints/audit_log_endpoints.py` (`list_audit_logs`)
- Create: `tests/test_litellm/proxy/management_endpoints/test_audit_log_endpoints.py`

- [ ] **Step 1: Write the failing tests**

```python
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from litellm.proxy._types import LitellmUserRoles, UserAPIKeyAuth
from litellm.proxy.management_endpoints.audit_log_endpoints import list_audit_logs


def _prisma_with_no_rows() -> MagicMock:
    client = MagicMock()
    client.db.litellm_auditlog.count = AsyncMock(return_value=0)
    client.db.litellm_auditlog.find_many = AsyncMock(return_value=[])
    return client


async def _list_as(role: LitellmUserRoles):
    with patch("litellm.proxy.proxy_server.prisma_client", _prisma_with_no_rows()):
        return await list_audit_logs(
            user_api_key_dict=UserAPIKeyAuth(user_role=role),
            table_name=None,
            action=None,
            object_id=None,
            changed_by=None,
            start_date=None,
            end_date=None,
            page=1,
            size=50,
            include_noise=False,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [LitellmUserRoles.PROXY_ADMIN, LitellmUserRoles.PROXY_ADMIN_VIEW_ONLY])
async def test_admins_can_read_the_audit_trail(role):
    response = await _list_as(role)

    assert response.entries == []
    assert response.total == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "role",
    [LitellmUserRoles.ORG_ADMIN, LitellmUserRoles.INTERNAL_USER, LitellmUserRoles.INTERNAL_USER_VIEW_ONLY],
)
async def test_the_installation_wide_audit_trail_is_refused_to_everyone_else(role):
    with pytest.raises(HTTPException) as refused:
        await _list_as(role)

    assert refused.value.status_code == 403
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_litellm/proxy/management_endpoints/test_audit_log_endpoints.py -v`

Expected: the admin tests PASS and the three refusal tests FAIL with `DID NOT RAISE`

- [ ] **Step 3: Refuse non-admins**

In `audit_log_endpoints.py`, change `from litellm.proxy._types import UserAPIKeyAuth` to `from litellm.proxy._types import LitellmUserRoles, UserAPIKeyAuth`, and add as the first statement after the docstring of `list_audit_logs`:

```python
    if user_api_key_dict.user_role not in (LitellmUserRoles.PROXY_ADMIN, LitellmUserRoles.PROXY_ADMIN_VIEW_ONLY):
        raise HTTPException(status_code=403, detail={"error": "Only proxy admins can read the audit trail"})
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_litellm/proxy/management_endpoints/test_audit_log_endpoints.py tests/test_litellm/proxy/management_endpoints/test_audit_log_diff.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add litellm/proxy/management_endpoints/audit_log_endpoints.py tests/test_litellm/proxy/management_endpoints/test_audit_log_endpoints.py
git commit -m "fix(audit): only proxy admins read the audit trail"
```

---

### Task 4: Customer-facing messages stop naming LiteLLM

**Files:**
- Create: `tests/code_coverage_tests/check_customer_messages_do_not_name_litellm.py`
- Modify: `litellm/proxy/hooks/user_management_event_hooks.py:92`, `litellm/proxy/hooks/parallel_request_limiter.py:132`, `litellm/proxy/hooks/model_max_budget_limiter.py:326,346`, `litellm/proxy/batches_endpoints/endpoints.py:991`, `litellm/proxy/openai_files_endpoints/files_endpoints.py:897`, `litellm/proxy/proxy_server.py:14655,14663`, `litellm/proxy/management_endpoints/organization_endpoints.py:1296`, `litellm/proxy/auth/user_api_key_auth.py:1909`, `litellm/proxy/guardrails/guardrail_endpoints.py:2354`, `litellm/proxy/management_endpoints/cost_tracking_settings.py:223,361`, `litellm/proxy/management_endpoints/scim/scim_v2.py:887`, `litellm/proxy/management_endpoints/team_endpoints.py:1358`, `litellm/proxy/management_helpers/user_invitation.py:46`, `litellm/proxy/utils.py:4442`, `litellm/proxy/management_endpoints/key_management_endpoints.py:1247,1254`
- Test: `tests/test_litellm/proxy/management_endpoints/test_organization_endpoints.py:1063`, `tests/test_litellm/proxy/test_api_key_masking_in_errors.py:94`

Line numbers are from before Plan A ran and may have moved, so match each message by its text

These are deliberately left for later, each for a stated reason:

| Left as is | Reason |
|---|---|
| `example_config_yaml/custom_auth.py`, `post_call_rules.py` | Sample rules a customer copies and edits, not messages the product sends |
| The OpenRouter and Vercel site URL defaults and the email footer link, all `https://litellm.ai` | They need Token IQ's public web address, which is not decided |

- [ ] **Step 1: Write the failing check**

```python
"""Messages the proxy returns to callers must not name LiteLLM.

A message is a string literal assigned to detail, message, exceeded_message, event_message or an
"error" key. Files listed in ALLOWED are exempt, each for the reason given.
"""

import re
import sys
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Final

REPO: Final = Path(__file__).resolve().parents[2]
MESSAGE: Final = re.compile(
    r"""(?:\bdetail|\bmessage|\bexceeded_message|\bevent_message|["']error["'])\s*[:=]\s*f?"""
    r"""(?:"(?P<double>[^"\n]*LiteLLM[^"\n]*)"|'(?P<single>[^'\n]*LiteLLM[^'\n]*)')"""
)
ALLOWED: Final[Mapping[str, str]] = MappingProxyType(
    {
        "litellm/proxy/example_config_yaml/custom_auth.py": "sample code a customer copies and edits",
        "litellm/proxy/post_call_rules.py": "sample rule a customer copies and edits",
    }
)


def offending_messages() -> tuple[str, ...]:
    return tuple(
        f"{path.relative_to(REPO).as_posix()}:{number}  {(match.group('double') or match.group('single'))[:100]}"
        for path in sorted((REPO / "litellm" / "proxy").rglob("*.py"))
        if path.relative_to(REPO).as_posix() not in ALLOWED
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
        for match in MESSAGE.finditer(line)
    )


def main() -> int:
    found: Final = offending_messages()
    for line in found:
        print(f"customer-facing message names LiteLLM  {line}")
    if found:
        return 1
    print("No customer-facing proxy message names LiteLLM.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/Scripts/python tests/code_coverage_tests/check_customer_messages_do_not_name_litellm.py`

Expected: exit code 1, listing 19 messages (23 if Plan A has not run yet, because Plan A rewrites four of them) across the files in this task's Modify list. A double-quoted message may contain single quotes, such as `current['current_rpm']`, which is why the pattern handles each quote style separately

- [ ] **Step 3: Reword the messages**

| File | Replace | With |
|---|---|---|
| `user_management_event_hooks.py` | `event_message="Welcome to LiteLLM Proxy",` | `event_message="Welcome to Token IQ",` |
| `parallel_request_limiter.py` | `detail=f"LiteLLM Rate Limit Handler for rate limit type = {rate_limit_type}.` | `detail=f"Rate limit reached for rate limit type = {rate_limit_type}.` |
| `model_max_budget_limiter.py` | `exceeded_message=f"LiteLLM User: {user_id}, exceeded budget for model={model}",` | `exceeded_message=f"User {user_id} exceeded their budget for model={model}",` |
| `model_max_budget_limiter.py` | `exceeded_message=f"LiteLLM End User: {end_user_id}, exceeded budget for model={model}",` | `exceeded_message=f"End user {end_user_id} exceeded their budget for model={model}",` |
| `batches_endpoints/endpoints.py` | `"Invalid LiteLLM managed batch ID. Missing model_id."` | `"Invalid managed batch ID. Missing model_id."` |
| `files_endpoints.py` | `Use the LiteLLM managed file id returned when the file was created.` | `Use the managed file id returned when the file was created.` |
| `proxy_server.py` (both) | `or on the LiteLLM Admin UI. - https://docs.litellm.ai/docs/proxy/configs"` | `or in the Token IQ dashboard."` |
| `organization_endpoints.py` | `Potential duplicate OR non-existent user_email in LiteLLM_UserTable. Use 'user_id' instead.` | `Potential duplicate OR non-existent user_email. Use 'user_id' instead.` |
| `user_api_key_auth.py` | ``Unable to find token in cache or `LiteLLM_VerificationTokenTable` `` | `Unable to find token in cache or the database` |
| `guardrail_endpoints.py` | `Please ensure the guardrail is configured in your LiteLLM proxy.` | `Please ensure the guardrail is configured in Token IQ.` |
| `cost_tracking_settings.py` (first) | `Must be valid LiteLLM providers. See https://docs.litellm.ai/docs/providers for the full list.` | `Must be providers Token IQ supports.` |
| `cost_tracking_settings.py` (second) | `Must be valid LiteLLM providers or 'global'. See https://docs.litellm.ai/docs/providers for the full list.` | `Must be providers Token IQ supports, or 'global'.` |
| `scim_v2.py` | `names more than one LiteLLM user, so the ` | `names more than one Token IQ user, so the ` |
| `team_endpoints.py` | `is reserved for LiteLLM UI dashboard sessions` | `is reserved for Token IQ dashboard sessions` |
| `user_invitation.py` | `User id does not exist in 'LiteLLM_UserTable'.` | `User id does not exist.` |
| `utils.py` | `does not exist in LiteLLM_OrganizationTable.` | `does not exist.` |
| `key_management_endpoints.py` (both) | `LiteLLM Virtual Key must` | `A virtual key must` |

In `test_organization_endpoints.py`, replace `"non-existent user_email in LiteLLM_UserTable. Use 'user_id' instead."` with `"non-existent user_email. Use 'user_id' instead."`, and in `test_api_key_masking_in_errors.py` replace `LiteLLM Virtual Key must start with 'sk-'` with `A virtual key must start with 'sk-'`. Tests that match `Invalid proxy server token passed` keep passing, because only the end of that message changes

- [ ] **Step 4: Run the check and the affected tests**

Run: `.venv/Scripts/python tests/code_coverage_tests/check_customer_messages_do_not_name_litellm.py`

Expected: exit code 0

Run: `grep -rnE "Welcome to LiteLLM Proxy|LiteLLM Rate Limit Handler|LiteLLM User: |LiteLLM End User: |Invalid LiteLLM managed batch ID|LiteLLM managed file id|LiteLLM Admin UI|configured in your LiteLLM proxy|valid LiteLLM providers|more than one LiteLLM user|LiteLLM UI dashboard sessions|LiteLLM_VerificationTokenTable|LiteLLM Virtual Key must" tests --include=*.py`

Expected: no output. Update any test the command lists to the new wording

Run: `.venv/Scripts/python -m pytest tests/test_litellm/proxy/management_endpoints/test_organization_endpoints.py tests/test_litellm/proxy/test_api_key_masking_in_errors.py tests/test_litellm/proxy/auth tests/test_litellm/proxy/hooks -q`

Expected: PASS apart from failures that also fail on the commit before this task

- [ ] **Step 5: Commit**

```bash
git add tests/code_coverage_tests/check_customer_messages_do_not_name_litellm.py litellm/proxy tests/test_litellm/proxy/management_endpoints/test_organization_endpoints.py
git commit -m "fix(brand): customer-facing proxy messages stop naming LiteLLM"
```

---

## Status on 2026-09-30

Complete. Verified against the code rather than by the checkboxes below, which nobody ticked:
No Dockerfile copies the deleted enterprise folder and `tests/code_coverage_tests/check_dockerfile_context_paths_exist.py` keeps it that way, the Logs page Audit Logs tab renders the working audit trail, the audit endpoint refuses anyone who is not a proxy admin, and `tests/code_coverage_tests/check_customer_messages_do_not_name_litellm.py` passes.

That last gate covers error messages, which is what it was written for. The API documentation a customer reads was still naming the other product, and that is finished in `docs/superpowers/plans/2026-09-30-api-docs-branding.md`.
