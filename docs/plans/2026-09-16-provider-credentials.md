# LLM Provider Credentials Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give credentials their home under a new Data Sources sidebar group as "LLM Provider Credentials", label each credential by purpose (model access or billing access), keep billing credentials read-only and never shown back, and check a billing key is the right kind before it is saved.

**Architecture:** A billing credential is recognised by one marker already used by the billing ingestion job: `credential_info = {"purpose": "billing_ingestion", "provider": "<slug>"}`. One small backend module owns that marker and the key checks, and the credential endpoints call it on create, update and read. The dashboard gets a page route for the existing credentials panel, a purpose choice in the credential form with its own small billing-fields component, a Purpose column, and a helper that keeps billing credentials out of every "pick a credential" list.

**Tech Stack:** FastAPI, pytest on the proxy; Next.js, react-hook-form, shadcn, vitest with Testing Library on the dashboard

**Spec:** `docs/superpowers/specs/2026-09-14-token-iq-product-design.md` ("Credentials", "Full sidebar" DATA SOURCES, "Phases" Phase 2), with `docs/superpowers/specs/2026-09-15-cost-platform-reference.md` ("Connections": read-only admin key, key type checked before saving)

## Global Constraints

- All work goes on the branch `litellm_token_iq`. Never touch `main`, never create another branch
- Python runs from the repo venv, `.venv/Scripts/python`, never the system Python
- Never run the full vitest suite. Run `npx vitest run <paths>` from `ui/litellm-dashboard` with explicit paths
- No existing page or tab is removed or merged. A tab may move to become a page
- The eight pages without a sidebar entry stay hidden: Organizations, Agents, Workflows, Memory, Caching, Vector Stores, Search Tools, Tool Policies
- Use the words teams, projects and users. Never "employees"
- No customer-visible LiteLLM text
- Never port code from `enterprise/` or `litellm_enterprise`
- Never put secrets in code, tests, commits or logs; tests use obviously fake keys such as `sk-admin-test-not-real`
- New Python follows the project CLAUDE.md: every variable annotated `Final`, no new `Any`, no mutable collections in annotations, lines up to 120 characters, comments only where logic needs them
- Commit messages follow conventional commits and carry no Claude attribution (the project CLAUDE.md forbids it)
- Commit after each task. Push `litellm_token_iq` at the end

## Phase 2 breakdown

Phase 2 in the spec covers several independent pieces, so it is split into plans that each ship on their own, in this order:

1. **LLM Provider Credentials** (this plan): the Data Sources home for credentials, purpose labels, billing key checks
2. **Add Model uses saved credentials only**: the credential picker with New credential, team-owned credentials for team admins, credentials without a secret, and a one-click move of a typed key into a saved credential
3. **Provider connections**: sync history, connection states, raw provider rows stored, several accounts per provider, and the Data Sources / Provider APIs page (Connection, What We Fetch, Sync History)
4. **Azure and Vertex connectors**
5. **Usage / APIs**: the Usage page gains Gateway and APIs tabs; each provider gets Summary and Raw Data

Not in Phase 2:
- **Usage / Combined** belongs to Phase 3 with attribution rules. Until it exists, Gateway stays the tab Usage opens on, and Combined becomes the default when it ships
- **Checking the OpenAI, Anthropic and Bedrock connectors on real read-only accounts** needs the customer's admin keys. Plan 3 ends with the steps to run once those keys are available
- **Three ideas from the cost platform research** wait for a product decision and are not planned: cost per customer or feature, request-level logs from outside the gateway, and spend beyond AI

## What "billing access" means in this plan

| Provider slug | Billing credential values | Key check |
|---|---|---|
| `openai` | `api_key` | must start with `sk-admin-` (an organisation admin key) |
| `anthropic` | `api_key` | must start with `sk-ant-admin` (an organisation admin key) |
| `openrouter` | `api_key` | any non-empty key |
| `bedrock` | `aws_access_key_id`, `aws_secret_access_key`, optional `aws_session_token`, optional `service_name` | both AWS keys non-empty |

These four are the providers this build has billing connectors for. Bedrock's connector exists but is not registered today; Task 1 registers it so a Bedrock billing credential is not silently ignored.

Model access credentials are everything else, and they behave exactly as today.

## File Map

Backend:
- Create `litellm/provider_billing/credential_purpose.py`: the billing marker, the provider list, and the key checks
- Create `tests/test_litellm/provider_billing/test_credential_purpose.py`
- Modify `litellm/provider_billing/startup.py`: register the Bedrock connector
- Modify `tests/test_litellm/provider_billing/test_startup.py`
- Modify `litellm/proxy/credential_endpoints/endpoints.py`: check billing credentials on create and update, never return their values
- Modify `tests/test_litellm/proxy/credential_endpoints/test_endpoints.py`

Dashboard (paths under `ui/litellm-dashboard/src`):
- Create `app/(dashboard)/llm-provider-credentials/page.tsx`
- Modify `utils/migratedPages.ts`, `components/leftnav.tsx`, `components/leftnav.test.tsx`, `components/page_metadata.ts`
- Modify `app/(dashboard)/models-and-endpoints/page.tsx`, `app/(dashboard)/models-and-endpoints/page.test.tsx`; delete `app/(dashboard)/models-and-endpoints/panels/LlmCredentialsPanel.tsx`
- Modify `components/networking.tsx` (`CredentialItem.credential_info` type)
- Modify `components/model_add/credential_form_helpers.ts`, `components/model_add/credential_form_helpers.test.ts`
- Create `components/model_add/BillingCredentialFields.tsx`
- Modify `components/model_add/CredentialModal.tsx`, `components/model_add/CredentialModal.test.tsx`
- Modify `components/model_add/CredentialsPanel.tsx`, `components/model_add/CredentialsPanel.test.tsx`
- Modify `components/model_add/CredentialsTableColumns.tsx`, `components/model_add/CredentialsTable.test.tsx`
- Modify `components/add_model/AddModelForm.tsx`, `app/(dashboard)/vector-stores/_components/VectorStoreForm.tsx`, `app/(dashboard)/vector-stores/_components/vector_store_info.tsx`

E2E:
- Modify `tests/e2e/ui/tests/modelsPage/credentials.spec.ts`

---

### Task 1: Recognise and check billing credentials, and register Bedrock

**Files:**
- Create: `litellm/provider_billing/credential_purpose.py`
- Create: `tests/test_litellm/provider_billing/test_credential_purpose.py`
- Modify: `litellm/provider_billing/startup.py`
- Modify: `tests/test_litellm/provider_billing/test_startup.py`

**Interfaces:**
- Produces: `BILLING_PURPOSE: Final = "billing_ingestion"`
- Produces: `BILLING_PROVIDERS: Final[frozenset[str]]` equal to `{"openai", "anthropic", "openrouter", "bedrock"}`
- Produces: `is_billing_credential(credential_info: Mapping[str, object] | None) -> bool`
- Produces: `billing_credential_problem(credential_info: Mapping[str, object], credential_values: Mapping[str, object], *, require_keys: bool) -> str | None`. `require_keys=True` on create (every required value must be present); `require_keys=False` on update (only values actually sent are checked, since the stored ones were checked when they were saved)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_litellm/provider_billing/test_credential_purpose.py`:

```python
from __future__ import annotations

import pytest

from litellm.provider_billing.credential_purpose import (
    BILLING_PROVIDERS,
    billing_credential_problem,
    is_billing_credential,
)


def test_a_credential_is_for_billing_only_when_it_says_so():
    assert is_billing_credential({"purpose": "billing_ingestion", "provider": "openai"}) is True
    assert is_billing_credential({"custom_llm_provider": "openai"}) is False
    assert is_billing_credential(None) is False


def test_the_billing_providers_are_the_ones_this_build_has_connectors_for():
    assert BILLING_PROVIDERS == frozenset({"openai", "anthropic", "openrouter", "bedrock"})


@pytest.mark.parametrize(
    ("provider", "values"),
    [
        ("openai", {"api_key": "sk-admin-test-not-real"}),
        ("anthropic", {"api_key": "sk-ant-admin01-test-not-real"}),
        ("openrouter", {"api_key": "sk-or-v1-test-not-real"}),
        ("bedrock", {"aws_access_key_id": "AKIATESTNOTREAL", "aws_secret_access_key": "test-not-real"}),
    ],
)
def test_a_complete_billing_credential_has_no_problem(provider, values):
    info = {"purpose": "billing_ingestion", "provider": provider}

    assert billing_credential_problem(info, values, require_keys=True) is None


def test_an_ordinary_openai_key_is_refused_because_cost_reports_need_an_admin_key():
    """Saving a model key as a billing credential would fail on every sync with a 401,
    long after the admin who pasted it has moved on."""
    problem = billing_credential_problem(
        {"purpose": "billing_ingestion", "provider": "openai"},
        {"api_key": "sk-proj-test-not-real"},
        require_keys=True,
    )

    assert problem is not None
    assert "sk-admin-" in problem


def test_an_ordinary_anthropic_key_is_refused():
    problem = billing_credential_problem(
        {"purpose": "billing_ingestion", "provider": "anthropic"},
        {"api_key": "sk-ant-api03-test-not-real"},
        require_keys=True,
    )

    assert problem is not None
    assert "sk-ant-admin" in problem


def test_an_unknown_provider_is_refused_and_the_message_lists_the_supported_ones():
    problem = billing_credential_problem(
        {"purpose": "billing_ingestion", "provider": "cohere"}, {"api_key": "x"}, require_keys=True
    )

    assert problem is not None
    assert "anthropic, bedrock, openai, openrouter" in problem


def test_a_missing_key_is_refused_on_create():
    problem = billing_credential_problem(
        {"purpose": "billing_ingestion", "provider": "openrouter"}, {}, require_keys=True
    )

    assert problem is not None
    assert "api_key" in problem


def test_a_bedrock_credential_without_both_aws_keys_is_refused_on_create():
    problem = billing_credential_problem(
        {"purpose": "billing_ingestion", "provider": "bedrock"},
        {"aws_access_key_id": "AKIATESTNOTREAL"},
        require_keys=True,
    )

    assert problem is not None
    assert "aws_secret_access_key" in problem


def test_an_update_that_sends_no_key_keeps_the_stored_one_and_is_accepted():
    """The stored key was checked when it was saved and is never sent back to the form,
    so an edit that renames nothing and sends no key must not be refused."""
    assert (
        billing_credential_problem({"purpose": "billing_ingestion", "provider": "openai"}, {}, require_keys=False)
        is None
    )


def test_an_update_that_sends_a_wrong_kind_of_key_is_refused():
    problem = billing_credential_problem(
        {"purpose": "billing_ingestion", "provider": "openai"},
        {"api_key": "sk-proj-test-not-real"},
        require_keys=False,
    )

    assert problem is not None
```

In `tests/test_litellm/provider_billing/test_startup.py`, change the expected set in `test_every_shipped_connector_is_registered` to:

```python
    assert {connector.provider for connector in registered_connectors()} == {
        "openrouter",
        "anthropic",
        "openai",
        "bedrock",
    }
```

and in `test_registering_twice_is_harmless` change `assert len(registered_connectors()) == 3` to:

```python
    assert len(registered_connectors()) == 4
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_litellm/provider_billing/test_credential_purpose.py tests/test_litellm/provider_billing/test_startup.py -q`
Expected: FAIL. The purpose tests fail with `ModuleNotFoundError: No module named 'litellm.provider_billing.credential_purpose'`; the startup tests fail because `bedrock` is not registered

- [ ] **Step 3: Implement the purpose module**

Create `litellm/provider_billing/credential_purpose.py`:

```python
"""Which stored credentials read a provider's bill, and whether one is fit to.

A billing credential is an organisation admin key that can read an account's costs. It is
never used to serve models and is never shown back, so one marker on `credential_info`
identifies it for the ingestion job, the credential endpoints and the dashboard alike.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

BILLING_PURPOSE: Final = "billing_ingestion"

BILLING_PROVIDERS: Final[frozenset[str]] = frozenset({"openai", "anthropic", "openrouter", "bedrock"})

_ADMIN_KEY_PREFIXES: Final = MappingProxyType({"openai": "sk-admin-", "anthropic": "sk-ant-admin"})
"""Cost reports answer only to an organisation admin key. An ordinary key saves fine and then
fails every sync with a 401, so the kind of key is checked before it is stored."""

_BEDROCK_REQUIRED: Final = ("aws_access_key_id", "aws_secret_access_key")


def is_billing_credential(credential_info: Mapping[str, object] | None) -> bool:
    """Whether this credential is marked for reading a provider's bill."""
    return credential_info is not None and credential_info.get("purpose") == BILLING_PURPOSE


def _present(value: object) -> bool:
    return isinstance(value, str) and value != ""


def billing_credential_problem(
    credential_info: Mapping[str, object],
    credential_values: Mapping[str, object],
    *,
    require_keys: bool,
) -> str | None:
    """Why this billing credential cannot read its provider's bill, or None when it can."""
    provider: Final = credential_info.get("provider")
    if not isinstance(provider, str) or provider not in BILLING_PROVIDERS:
        return f"A billing credential needs a provider, one of: {', '.join(sorted(BILLING_PROVIDERS))}."

    if provider == "bedrock":
        missing: Final = tuple(name for name in _BEDROCK_REQUIRED if not _present(credential_values.get(name)))
        if require_keys and missing:
            return f"A Bedrock billing credential needs {' and '.join(missing)}."
        return None

    api_key: Final = credential_values.get("api_key")
    if not _present(api_key):
        return f"A {provider} billing credential needs an api_key." if require_keys else None

    prefix: Final = _ADMIN_KEY_PREFIXES.get(provider)
    if prefix is not None and isinstance(api_key, str) and not api_key.startswith(prefix):
        return (
            f"This is not a {provider} admin key. Cost reports need an organisation admin key, "
            f"which starts with {prefix}."
        )
    return None
```

- [ ] **Step 4: Register the Bedrock connector**

In `litellm/provider_billing/startup.py`, add this import inside `register_billing_connectors`, after the anthropic import:

```python
    from litellm.provider_billing.bedrock import BedrockBillingConnector, build_cost_explorer
```

and add this entry at the end of the `candidates` tuple:

```python
        BedrockBillingConnector(cost_explorer_factory=build_cost_explorer),
```

`build_cost_explorer` imports `boto3` only when a Bedrock billing credential is actually used, so registration adds no import cost.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_litellm/provider_billing -q`
Expected: all PASS

- [ ] **Step 6: Lint and commit**

Run: `.venv/Scripts/python -m ruff check litellm/provider_billing/credential_purpose.py litellm/provider_billing/startup.py tests/test_litellm/provider_billing/test_credential_purpose.py tests/test_litellm/provider_billing/test_startup.py`
Run: `.venv/Scripts/python scripts/check_type_discipline.py litellm/provider_billing/credential_purpose.py`
Expected: no errors for lines this task added

```bash
git add litellm/provider_billing/credential_purpose.py litellm/provider_billing/startup.py tests/test_litellm/provider_billing/test_credential_purpose.py tests/test_litellm/provider_billing/test_startup.py
git commit -m "feat(billing): recognise billing credentials, check their key type, and register bedrock"
```

---

### Task 2: The credential endpoints check billing credentials and never return their values

**Files:**
- Modify: `litellm/proxy/credential_endpoints/endpoints.py` (`create_credential`, `get_credentials`, `get_credential_by_name`, `update_credential`)
- Test: `tests/test_litellm/proxy/credential_endpoints/test_endpoints.py`

**Interfaces:**
- Consumes: `is_billing_credential`, `billing_credential_problem` from Task 1
- Produces: `POST /credentials` and `PATCH /credentials/{name}` answer 400 `{"error": "<problem>"}` for a billing credential that fails the check
- Produces: `GET /credentials` and `GET /credentials/by_name/{name}` return `credential_values: {}` for billing credentials

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_litellm/proxy/credential_endpoints/test_endpoints.py`:

```python
def _as_admin_request(method: str, path: str, body: dict | None = None):
    missing = object()
    previous_override = app.dependency_overrides.get(user_api_key_auth, missing)
    app.dependency_overrides[user_api_key_auth] = _as_admin
    try:
        return client.request(method, path, json=body, headers={"Authorization": "Bearer test-key"})
    finally:
        if previous_override is missing:
            app.dependency_overrides.pop(user_api_key_auth, None)
        else:
            app.dependency_overrides[user_api_key_auth] = previous_override


def test_creating_a_billing_credential_with_an_ordinary_key_is_refused_before_anything_is_stored():
    """An ordinary OpenAI key saves fine and then fails every cost sync with a 401."""
    with patch("litellm.proxy.proxy_server.prisma_client", MagicMock()), patch(
        "litellm.proxy.credential_endpoints.endpoints.CredentialsRepository"
    ) as repository:
        repository.return_value.create = AsyncMock(return_value=None)

        response = _as_admin_request(
            "POST",
            "/credentials",
            {
                "credential_name": "openai-billing",
                "credential_values": {"api_key": "sk-proj-test-not-real"},
                "credential_info": {"purpose": "billing_ingestion", "provider": "openai"},
            },
        )

    assert response.status_code == 400, response.text
    assert "sk-admin-" in response.text
    repository.return_value.create.assert_not_awaited()


def test_creating_a_billing_credential_with_an_admin_key_is_stored():
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
                "credential_name": "openai-billing",
                "credential_values": {"api_key": "sk-admin-test-not-real"},
                "credential_info": {"purpose": "billing_ingestion", "provider": "openai"},
            },
        )

    assert response.status_code == 200, response.text
    repository.return_value.create.assert_awaited_once()


def test_updating_a_billing_credential_with_an_ordinary_key_is_refused():
    stored = CredentialItem(
        credential_name="openai-billing",
        credential_values={"api_key": "encrypted-stored-value"},
        credential_info={"purpose": "billing_ingestion", "provider": "openai"},
    )
    with patch("litellm.proxy.proxy_server.prisma_client", MagicMock()), patch(
        "litellm.proxy.credential_endpoints.endpoints.CredentialsRepository"
    ) as repository:
        repository.return_value.find_by_name = AsyncMock(return_value=stored)
        repository.return_value.update_by_name = AsyncMock(return_value=None)

        response = _patch_credential(
            "openai-billing",
            {
                "credential_name": "openai-billing",
                "credential_values": {"api_key": "sk-proj-test-not-real"},
                "credential_info": {},
            },
        )

    assert response.status_code == 400, response.text
    repository.return_value.update_by_name.assert_not_awaited()


def test_listing_credentials_never_returns_any_part_of_a_billing_key():
    """Billing keys read a whole organisation's costs. Even a masked prefix narrows a
    leaked key down, so the list returns nothing for them."""
    import litellm

    billing = CredentialItem(
        credential_name="anthropic-billing",
        credential_values={"api_key": "sk-ant-admin01-test-not-real"},
        credential_info={"purpose": "billing_ingestion", "provider": "anthropic"},
    )
    model_access = CredentialItem(
        credential_name="openai-models",
        credential_values={"api_key": "sk-proj-test-not-real"},
        credential_info={"custom_llm_provider": "openai"},
    )
    with patch.object(litellm, "credential_list", [billing, model_access]):
        listed = _as_admin_request("GET", "/credentials")
        by_name = _as_admin_request("GET", "/credentials/by_name/anthropic-billing")

    assert listed.status_code == 200, listed.text
    rows = {row["credential_name"]: row for row in listed.json()["credentials"]}
    assert rows["anthropic-billing"]["credential_values"] == {}
    assert rows["openai-models"]["credential_values"] != {}
    assert by_name.status_code == 200, by_name.text
    assert by_name.json()["credential_values"] == {}
    assert "sk-ant-admin" not in listed.text + by_name.text
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_litellm/proxy/credential_endpoints/test_endpoints.py -q`
Expected: the four new tests FAIL (the ordinary key is stored with 200, the update is written, the list shows a masked key)

- [ ] **Step 3: Implement**

In `litellm/proxy/credential_endpoints/endpoints.py`, add to the imports:

```python
from litellm.provider_billing.credential_purpose import billing_credential_problem, is_billing_credential
```

Add `from collections.abc import Mapping` to the imports, and this helper after `CredentialHelperUtils`:

```python
def _refuse_unfit_billing_credential(
    credential_info: Mapping[str, object], credential_values: Mapping[str, object], *, require_keys: bool
) -> None:
    """A billing credential that cannot read its provider's bill is refused before it is stored."""
    if not is_billing_credential(credential_info):
        return
    problem: Final = billing_credential_problem(credential_info, credential_values, require_keys=require_keys)
    if problem is not None:
        raise HTTPException(status_code=400, detail={"error": problem})
```

In `create_credential`, directly after the `if credential.credential_values is None:` block that raises 400, add:

```python
        _refuse_unfit_billing_credential(
            credential.credential_info, credential.credential_values, require_keys=True
        )
```

In `get_credentials`, replace the list comprehension value for `credential_values` so the comprehension reads:

```python
        masked_credentials: Final = [
            {
                "credential_name": credential.credential_name,
                "credential_values": {}
                if is_billing_credential(credential.credential_info)
                else _get_masked_values(credential.credential_values),
                "credential_info": credential.credential_info,
            }
            for credential in litellm.credential_list
        ]
```

In `get_credential_by_name`, replace the `masked_credential = CredentialItem(...)` construction with:

```python
                masked_credential = CredentialItem(
                    credential_name=credential.credential_name,
                    credential_values={}
                    if is_billing_credential(credential.credential_info)
                    else _get_masked_values(
                        credential.credential_values,
                        unmasked_length=4,
                        number_of_asterisks=4,
                    ),
                    credential_info=credential.credential_info,
                )
```

In `update_credential`, directly after the `if db_credential is None:` block, add:

```python
        _refuse_unfit_billing_credential(
            {**(db_credential.credential_info or {}), **(credential.credential_info or {})},
            credential.credential_values or {},
            require_keys=False,
        )
```

The update check uses only the values the request sends: the stored values are encrypted, and they were checked when they were saved.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_litellm/proxy/credential_endpoints/test_endpoints.py tests/test_litellm/provider_billing -q`
Expected: all PASS

- [ ] **Step 5: Lint and commit**

Run: `.venv/Scripts/python -m ruff check litellm/proxy/credential_endpoints/endpoints.py tests/test_litellm/proxy/credential_endpoints/test_endpoints.py`
Run: `.venv/Scripts/python scripts/check_type_discipline.py litellm/proxy/credential_endpoints/endpoints.py`
Expected: no new errors on lines this task changed

```bash
git add litellm/proxy/credential_endpoints/endpoints.py tests/test_litellm/proxy/credential_endpoints/test_endpoints.py
git commit -m "feat(credentials): refuse unfit billing keys and never return billing credential values"
```

---

### Task 3: LLM Provider Credentials becomes a page under Data Sources

The LLM Credentials tab on Models + Endpoints moves to its own page, renamed, in a new DATA SOURCES sidebar group between ORGANISATION and GATEWAY. The tab keeps no URL today, so no address changes; the new page gets its own route

**Files:**
- Create: `ui/litellm-dashboard/src/app/(dashboard)/llm-provider-credentials/page.tsx`
- Modify: `ui/litellm-dashboard/src/utils/migratedPages.ts`
- Modify: `ui/litellm-dashboard/src/components/leftnav.tsx`, `ui/litellm-dashboard/src/components/leftnav.test.tsx`
- Modify: `ui/litellm-dashboard/src/components/page_metadata.ts`
- Modify: `ui/litellm-dashboard/src/app/(dashboard)/models-and-endpoints/page.tsx`, `.../page.test.tsx`
- Delete: `ui/litellm-dashboard/src/app/(dashboard)/models-and-endpoints/panels/LlmCredentialsPanel.tsx`
- Modify: `tests/e2e/ui/tests/modelsPage/credentials.spec.ts`

**Interfaces:**
- Produces: page id and route segment `llm-provider-credentials`; sidebar label "LLM Provider Credentials"; group label `DATA SOURCES`, breadcrumb section "Data Sources"

- [ ] **Step 1: Write the failing tests**

In `leftnav.test.tsx`, in the test `places every page in its agreed sidebar group, with nothing lost and nothing nested`, add this line between the `ORGANISATION` and `GATEWAY` entries of the expected object:

```tsx
      "DATA SOURCES": ["llm-provider-credentials"],
```

In `renders the agreed group labels and page names for an admin`, change the group label array to:

```tsx
    ["ANALYTICS", "ORGANISATION", "DATA SOURCES", "GATEWAY", "SAFETY", "BUILD", "SETTINGS"].forEach((label) => {
```

and add `"LLM Provider Credentials",` to the page-name list directly after `"Budgets",`.

In `describe("getBreadcrumb")`, add to `resolves a page to its new section and title`:

```tsx
    expect(getBreadcrumb("llm-provider-credentials")).toEqual({
      section: "Data Sources",
      title: "LLM Provider Credentials",
    });
```

Add inside `describe("capability-gated nav entries")`:

```tsx
    it("hides LLM Provider Credentials from internal users", () => {
      mockUseAuthorized.mockReturnValue(internalAuth);
      renderWithProviders(<Sidebar {...defaultProps} />);

      expect(screen.getByText("Usage")).toBeInTheDocument();
      expect(screen.queryByText("LLM Provider Credentials")).not.toBeInTheDocument();
    });
```

In `models-and-endpoints/page.test.tsx`:
- delete the line `vi.mock("./panels/LlmCredentialsPanel", ...)`
- in `renders the admin tab bar and the All Models panel by default`, replace the `LLM Credentials` assertion with `expect(screen.queryByRole("tab", { name: "LLM Credentials" })).not.toBeInTheDocument();`
- in `hides admin-only tabs for a non-admin user`, delete the `LLM Credentials` assertion line

- [ ] **Step 2: Run the tests to verify they fail**

Run from `ui/litellm-dashboard`: `npx vitest run src/components/leftnav.test.tsx "src/app/(dashboard)/models-and-endpoints/page.test.tsx"`
Expected: FAIL. The placement test has no `DATA SOURCES` group, the label is missing, the breadcrumb section is `null`, and Models still shows the LLM Credentials tab

- [ ] **Step 3: Implement**

Create `app/(dashboard)/llm-provider-credentials/page.tsx`:

```tsx
"use client";

import { LockKeyhole } from "lucide-react";

import CredentialsPanel from "@/components/model_add/CredentialsPanel";
import { PageHeader } from "@/components/shared/PageHeader";

export default function LlmProviderCredentialsPage() {
  return (
    <main className="flex h-full flex-col gap-6 p-8">
      <PageHeader
        icon={<LockKeyhole />}
        title="LLM Provider Credentials"
        subtitle="Keys for serving models and read-only keys for reading provider costs."
      />
      <CredentialsPanel />
    </main>
  );
}
```

In `utils/migratedPages.ts`, add to `MIGRATED_PAGES` after the `budgets` entry:

```ts
  "llm-provider-credentials": "llm-provider-credentials",
```

In `components/leftnav.tsx`:
1. Add `LockKeyhole,` to the `lucide-react` import, in alphabetical position after `LayoutGrid,`
2. Add this group to `menuGroups` directly after the `ORGANISATION` group:

```tsx
  {
    groupLabel: "DATA SOURCES",
    items: [
      {
        key: "llm-provider-credentials",
        page: "llm-provider-credentials",
        label: "LLM Provider Credentials",
        icon: <LockKeyhole {...ICON} />,
        roles: all_admin_roles,
      },
    ],
  },
```

3. Add `"DATA SOURCES": "Data Sources",` to `SECTION_DISPLAY` after `ORGANISATION`

In `components/page_metadata.ts`, add after the `budgets` line:

```ts
  "llm-provider-credentials": "Store provider keys for serving models and read-only keys for reading costs",
```

In `app/(dashboard)/models-and-endpoints/page.tsx`:
1. Delete `import LlmCredentialsPanel from "@/app/(dashboard)/models-and-endpoints/panels/LlmCredentialsPanel";`
2. Delete `| "llm-credentials"` from `ModelTabSlug`
3. Delete `"llm-credentials": "LLM Credentials",` from `TAB_LABELS`
4. Delete the two lines `case "llm-credentials":` and `return <LlmCredentialsPanel />;` from `renderPanel`
5. Delete `"llm-credentials",` from the admin list in `visibleSlugs`

Delete `app/(dashboard)/models-and-endpoints/panels/LlmCredentialsPanel.tsx`. Run `grep -rn "LlmCredentialsPanel" src` and expect no output.

In `tests/e2e/ui/tests/modelsPage/credentials.spec.ts`, replace:

```ts
    await page.getByText("Models + Endpoints").click();
    await page.getByRole("tab", { name: "LLM Credentials" }).click();
```

with:

```ts
    await page.getByRole("link", { name: "LLM Provider Credentials", exact: true }).click();
```

Search `tests/e2e/ui` for `LLM Credentials` and update any other hit the same way.

- [ ] **Step 4: Run the tests to verify they pass**

Run from `ui/litellm-dashboard`: `npx vitest run src/components/leftnav.test.tsx "src/app/(dashboard)/models-and-endpoints/page.test.tsx" src/components/page_utils.test.ts`
Expected: PASS, except the one `page_utils.test.ts` test about descriptions of hidden pages, which already fails before this plan

- [ ] **Step 5: Lint and commit**

Run from `ui/litellm-dashboard`: `npx eslint src/components/leftnav.tsx src/components/leftnav.test.tsx src/utils/migratedPages.ts src/components/page_metadata.ts "src/app/(dashboard)/llm-provider-credentials/page.tsx" "src/app/(dashboard)/models-and-endpoints/page.tsx" "src/app/(dashboard)/models-and-endpoints/page.test.tsx"`
Expected: no errors on lines this task changed

```bash
git add -A ui/litellm-dashboard/src/components/leftnav.tsx ui/litellm-dashboard/src/components/leftnav.test.tsx ui/litellm-dashboard/src/utils/migratedPages.ts ui/litellm-dashboard/src/components/page_metadata.ts "ui/litellm-dashboard/src/app/(dashboard)/llm-provider-credentials" "ui/litellm-dashboard/src/app/(dashboard)/models-and-endpoints" tests/e2e/ui/tests/modelsPage/credentials.spec.ts
git commit -m "feat(ui): move llm credentials to a data sources page named llm provider credentials"
```

---

### Task 4: Purpose in the credential form, the table, and every credential picker

**Files:**
- Modify: `ui/litellm-dashboard/src/components/networking.tsx` (`CredentialItem`)
- Modify: `ui/litellm-dashboard/src/components/model_add/credential_form_helpers.ts`, `credential_form_helpers.test.ts`
- Create: `ui/litellm-dashboard/src/components/model_add/BillingCredentialFields.tsx`
- Modify: `ui/litellm-dashboard/src/components/model_add/CredentialModal.tsx`, `CredentialModal.test.tsx`
- Modify: `ui/litellm-dashboard/src/components/model_add/CredentialsPanel.tsx`, `CredentialsPanel.test.tsx`
- Modify: `ui/litellm-dashboard/src/components/model_add/CredentialsTableColumns.tsx`, `CredentialsTable.test.tsx`
- Modify: `ui/litellm-dashboard/src/components/add_model/AddModelForm.tsx`
- Modify: `ui/litellm-dashboard/src/app/(dashboard)/vector-stores/_components/VectorStoreForm.tsx`, `vector_store_info.tsx`

**Interfaces:**
- Consumes: the backend contract from Tasks 1-2: billing credentials are `credential_info: { purpose: "billing_ingestion", provider: "openai" | "anthropic" | "openrouter" | "bedrock" }`, are returned with `credential_values: {}`, and a wrong key type answers 400 with the reason
- Produces, in `credential_form_helpers.ts`:
  - `BILLING_PURPOSE = "billing_ingestion"`
  - `type BillingProvider = "openai" | "anthropic" | "openrouter" | "bedrock"`
  - `BILLING_PROVIDERS: ReadonlyArray<{ value: BillingProvider; label: string }>`
  - `isBillingCredential(credential: CredentialItem): boolean`
  - `modelAccessCredentials(credentials: readonly CredentialItem[]): CredentialItem[]`
  - `credentialPurposeLabel(credential: CredentialItem): string` returning `"Model access"` or `"Billing access (read-only)"`
  - `buildCredentialPayload(values: Record<string, unknown>): { credential_name: string; credential_values: Record<string, unknown>; credential_info: Record<string, unknown> }`

Form values contract: the form sends `purpose` as `"model_access"` or `"billing_access"`. For model access it sends `custom_llm_provider` and provider fields as today. For billing access it sends `billing_provider` plus `api_key`, or for Bedrock `aws_access_key_id`, `aws_secret_access_key`, `aws_session_token`, `service_name`.

- [ ] **Step 1: Write the failing helper tests**

Append to `credential_form_helpers.test.ts` (keep its existing imports and tests; add the new names to its import from `./credential_form_helpers`, and import `CredentialItem` as a type from `../networking`):

```ts
describe("credential purpose", () => {
  const billing: CredentialItem = {
    credential_name: "anthropic-costs",
    credential_values: {},
    credential_info: { purpose: "billing_ingestion", provider: "anthropic" },
  };
  const modelAccess: CredentialItem = {
    credential_name: "openai-models",
    credential_values: { api_key: "sk-****" },
    credential_info: { custom_llm_provider: "OpenAI" },
  };

  it("tells billing credentials from model access credentials", () => {
    expect(isBillingCredential(billing)).toBe(true);
    expect(isBillingCredential(modelAccess)).toBe(false);
  });

  it("keeps billing credentials out of the lists used to serve models", () => {
    expect(modelAccessCredentials([billing, modelAccess]).map((c) => c.credential_name)).toEqual(["openai-models"]);
  });

  it("labels each purpose in plain words", () => {
    expect(credentialPurposeLabel(billing)).toBe("Billing access (read-only)");
    expect(credentialPurposeLabel(modelAccess)).toBe("Model access");
  });

  it("offers exactly the providers this build can read bills from", () => {
    expect(BILLING_PROVIDERS.map((p) => p.value)).toEqual(["openai", "anthropic", "openrouter", "bedrock"]);
  });

  it("builds a billing credential with the marker the ingestion job looks for", () => {
    expect(
      buildCredentialPayload({
        credential_name: "anthropic-costs",
        purpose: "billing_access",
        billing_provider: "anthropic",
        api_key: "sk-ant-admin01-test-not-real",
      }),
    ).toEqual({
      credential_name: "anthropic-costs",
      credential_values: { api_key: "sk-ant-admin01-test-not-real" },
      credential_info: { purpose: "billing_ingestion", provider: "anthropic" },
    });
  });

  it("keeps only the Bedrock values that were filled in", () => {
    expect(
      buildCredentialPayload({
        credential_name: "aws-costs",
        purpose: "billing_access",
        billing_provider: "bedrock",
        aws_access_key_id: "AKIATESTNOTREAL",
        aws_secret_access_key: "test-not-real",
        aws_session_token: "",
      }).credential_values,
    ).toEqual({ aws_access_key_id: "AKIATESTNOTREAL", aws_secret_access_key: "test-not-real" });
  });

  it("builds a model access credential exactly as before", () => {
    expect(
      buildCredentialPayload({
        credential_name: "openai-models",
        purpose: "model_access",
        custom_llm_provider: "OpenAI",
        api_key: "sk-test-not-real",
        api_base: "https://api.openai.com/v1",
      }),
    ).toEqual({
      credential_name: "openai-models",
      credential_values: { api_key: "sk-test-not-real", api_base: "https://api.openai.com/v1" },
      credential_info: { custom_llm_provider: "OpenAI" },
    });
  });

  it("treats a form with no purpose as model access, so existing callers keep working", () => {
    expect(
      buildCredentialPayload({ credential_name: "x", custom_llm_provider: "OpenAI", api_key: "k" }).credential_info,
    ).toEqual({ custom_llm_provider: "OpenAI" });
  });
});
```

- [ ] **Step 2: Run the helper tests to verify they fail**

Run from `ui/litellm-dashboard`: `npx vitest run src/components/model_add/credential_form_helpers.test.ts`
Expected: FAIL, the new exports do not exist

- [ ] **Step 3: Implement the helpers and widen the type**

In `components/networking.tsx`, change `CredentialItem.credential_info` to:

```ts
  credential_info: {
    custom_llm_provider?: string;
    description?: string;
    required?: boolean;
    purpose?: string;
    provider?: string;
  };
```

Append to `components/model_add/credential_form_helpers.ts` (add `import type { CredentialItem } from "../networking";` at the top):

```ts
export const BILLING_PURPOSE = "billing_ingestion";

export type BillingProvider = "openai" | "anthropic" | "openrouter" | "bedrock";

export const BILLING_PROVIDERS: ReadonlyArray<{ value: BillingProvider; label: string }> = [
  { value: "openai", label: "OpenAI" },
  { value: "anthropic", label: "Anthropic" },
  { value: "openrouter", label: "OpenRouter" },
  { value: "bedrock", label: "Amazon Bedrock" },
];

const BEDROCK_BILLING_FIELDS = ["aws_access_key_id", "aws_secret_access_key", "aws_session_token", "service_name"];

const FORM_ONLY_FIELDS = ["credential_name", "custom_llm_provider", "purpose", "billing_provider"];

export const isBillingCredential = (credential: CredentialItem): boolean =>
  credential.credential_info?.purpose === BILLING_PURPOSE;

export const modelAccessCredentials = (credentials: readonly CredentialItem[]): CredentialItem[] =>
  credentials.filter((credential) => !isBillingCredential(credential));

export const credentialPurposeLabel = (credential: CredentialItem): string =>
  isBillingCredential(credential) ? "Billing access (read-only)" : "Model access";

const filled = (value: unknown): boolean => value !== "" && value !== undefined && value !== null;

export const buildCredentialPayload = (
  values: Record<string, unknown>,
): {
  credential_name: string;
  credential_values: Record<string, unknown>;
  credential_info: Record<string, unknown>;
} => {
  const credentialName = values.credential_name as string;
  if (values.purpose === "billing_access") {
    const provider = values.billing_provider as BillingProvider;
    const keys = provider === "bedrock" ? BEDROCK_BILLING_FIELDS : ["api_key"];
    return {
      credential_name: credentialName,
      credential_values: Object.fromEntries(keys.filter((key) => filled(values[key])).map((key) => [key, values[key]])),
      credential_info: { purpose: BILLING_PURPOSE, provider },
    };
  }
  return {
    credential_name: credentialName,
    credential_values: Object.fromEntries(Object.entries(values).filter(([key]) => !FORM_ONLY_FIELDS.includes(key))),
    credential_info: { custom_llm_provider: values.custom_llm_provider as string },
  };
};
```

Run the helper tests again: they PASS.

- [ ] **Step 4: Write the failing component tests**

In `CredentialsPanel.test.tsx`, add to the top-level `describe("CredentialsPanel")`:

```tsx
  it("sends a billing credential with the billing marker and shows the server's reason when it is refused", async () => {
    const user = userEvent.setup();
    vi.mocked(credentialCreateCall).mockRejectedValueOnce(
      new Error("This is not a openai admin key. Cost reports need an organisation admin key, which starts with sk-admin-."),
    );
    mockCredentialModalValues({
      credential_name: "openai-costs",
      purpose: "billing_access",
      billing_provider: "openai",
      api_key: "sk-proj-test-not-real",
    });
    renderPanel();

    await user.click(screen.getByRole("button", { name: /add credential/i }));
    await user.click(await screen.findByTestId("credential-modal-add-submit"));

    await waitFor(() =>
      expect(credentialCreateCall).toHaveBeenCalledWith("sk-test", {
        credential_name: "openai-costs",
        credential_values: { api_key: "sk-proj-test-not-real" },
        credential_info: { purpose: "billing_ingestion", provider: "openai" },
      }),
    );
    expect(toast.error).toHaveBeenCalledWith(expect.stringContaining("sk-admin-"));
  });
```

The existing modal mock in that file hard-codes the add values. Change it so tests can override them: add near the top

```tsx
let addModalValues: Record<string, unknown> = { credential_name: "new-cred", custom_llm_provider: "openai" };
const mockCredentialModalValues = (values: Record<string, unknown>) => {
  addModalValues = values;
};
```

use `addModalValues` in place of the literal add values inside the mock, and reset it in the file's `beforeEach` to `{ credential_name: "new-cred", custom_llm_provider: "openai" }`. Match the file's existing names for the render helper and access token if they differ from `renderPanel` and `"sk-test"`. Check how `toast.error` is mocked there and follow that pattern.

In `CredentialsTable.test.tsx`, add:

```tsx
  it("should show each credential's purpose", () => {
    renderTable({
      credentials: [
        { credential_name: "openai-models", credential_values: {}, credential_info: { custom_llm_provider: "OpenAI" } },
        {
          credential_name: "anthropic-costs",
          credential_values: {},
          credential_info: { purpose: "billing_ingestion", provider: "anthropic" },
        },
      ],
    });

    expect(screen.getByRole("columnheader", { name: /Purpose/ })).toBeInTheDocument();
    expect(screen.getByText("Model access")).toBeInTheDocument();
    expect(screen.getByText("Billing access (read-only)")).toBeInTheDocument();
    expect(screen.getByText("Anthropic")).toBeInTheDocument();
  });
```

Match the file's existing render helper name and props.

In `CredentialModal.test.tsx` (create it if it does not exist, following `ui/litellm-dashboard/CLAUDE.md`; mock `../add_model/provider_specific_fields` to a stub so no network call happens), add:

```tsx
describe("CredentialModal purpose", () => {
  it("shows only the billing key field and the four billing providers when Billing access is chosen", async () => {
    const user = userEvent.setup();
    renderWithProviders(<CredentialModal open mode="add" onCancel={vi.fn()} onSubmit={vi.fn()} />);

    await user.click(screen.getByRole("radio", { name: /Billing access/ }));

    expect(screen.getByText(/Read-only/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Admin API key/)).toBeInTheDocument();
    expect(screen.queryByTestId("provider-specific-fields")).not.toBeInTheDocument();
  });

  it("sends the billing values in the shape the panel builds from", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    renderWithProviders(<CredentialModal open mode="add" onCancel={vi.fn()} onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText(/Credential Name/), { target: { value: "openai-costs" } });
    await user.click(screen.getByRole("radio", { name: /Billing access/ }));
    fireEvent.change(screen.getByLabelText(/Admin API key/), { target: { value: "sk-admin-test-not-real" } });
    await user.click(screen.getByRole("button", { name: /Add Credential/ }));

    await waitFor(() =>
      expect(onSubmit).toHaveBeenCalledWith({
        credential_name: "openai-costs",
        purpose: "billing_access",
        billing_provider: "openai",
        api_key: "sk-admin-test-not-real",
      }),
    );
  });

  it("asks for the two AWS keys when the billing provider is Amazon Bedrock", async () => {
    const user = userEvent.setup();
    renderWithProviders(<CredentialModal open mode="add" onCancel={vi.fn()} onSubmit={vi.fn()} />);

    await user.click(screen.getByRole("radio", { name: /Billing access/ }));
    await chooseSelectOption(user, screen.getByLabelText(/Billing provider/), /Amazon Bedrock/);

    expect(screen.getByLabelText(/AWS access key ID/)).toBeInTheDocument();
    expect(screen.getByLabelText(/AWS secret access key/)).toBeInTheDocument();
    expect(screen.queryByLabelText(/Admin API key/)).not.toBeInTheDocument();
  });

  it("opens an existing billing credential without offering to change its purpose or provider", () => {
    renderWithProviders(
      <CredentialModal
        open
        mode="edit"
        existingCredential={{
          credential_name: "openai-costs",
          credential_values: {},
          credential_info: { purpose: "billing_ingestion", provider: "openai" },
        }}
        onCancel={vi.fn()}
        onSubmit={vi.fn()}
      />,
    );

    expect(screen.queryByRole("radio", { name: /Model access/ })).not.toBeInTheDocument();
    expect(screen.getByText(/Leave the key empty to keep the stored one/)).toBeInTheDocument();
  });
});
```

Import `renderWithProviders` and `chooseSelectOption` from the test utils the other dashboard tests use (`tests/test-utils`), and the button, label and select names from what the component renders in Step 6. If the submit button is named differently in the existing modal (read it), use that name.

- [ ] **Step 5: Run the component tests to verify they fail**

Run from `ui/litellm-dashboard`: `npx vitest run src/components/model_add/CredentialsPanel.test.tsx src/components/model_add/CredentialsTable.test.tsx src/components/model_add/CredentialModal.test.tsx`
Expected: the new tests FAIL (no purpose choice, no Purpose column, the panel sends the old shape and a generic toast)

- [ ] **Step 6: Implement the form, panel, table and pickers**

Create `components/model_add/BillingCredentialFields.tsx`:

```tsx
"use client";

import { Input } from "@/components/ui/input";
import { SearchSelect } from "@/components/shared/SearchSelect";
import { MountedFormField } from "../common_components/MountedFormField";
import { requiredRule } from "../common_components/formRules";
import { BILLING_PROVIDERS, type BillingProvider } from "./credential_form_helpers";

interface BillingCredentialFieldsProps {
  provider: BillingProvider;
  onProviderChange: (provider: BillingProvider) => void;
  isEdit: boolean;
}

const secretRules = (isEdit: boolean, message: string) =>
  isEdit ? undefined : { validate: { required: requiredRule(message) } };

export default function BillingCredentialFields({ provider, onProviderChange, isEdit }: BillingCredentialFieldsProps) {
  return (
    <div className="flex flex-col gap-4">
      <p className="rounded-md border bg-muted/40 p-3 text-sm text-muted-foreground">
        Read-only. This key only reads costs, is stored encrypted, and is never shown again after saving.
        {isEdit ? " Leave the key empty to keep the stored one." : ""}
      </p>

      <MountedFormField label="Billing provider" name="billing_provider" required>
        {(control) => (
          <SearchSelect
            inputId={control.id}
            placeholder="Select a provider"
            options={BILLING_PROVIDERS.map((option) => ({ label: option.label, value: option.value }))}
            value={provider}
            disabled={isEdit}
            onValueChange={(value) => {
              control.onChange(value);
              onProviderChange(value as BillingProvider);
            }}
          />
        )}
      </MountedFormField>

      {provider === "bedrock" ? (
        <>
          <MountedFormField
            label="AWS access key ID"
            name="aws_access_key_id"
            required={!isEdit}
            rules={secretRules(isEdit, "AWS access key ID is required")}
          >
            {(control) => (
              <Input
                id={control.id}
                value={(control.value as string | undefined) ?? ""}
                onChange={control.onChange}
                onBlur={control.onBlur}
                autoComplete="off"
              />
            )}
          </MountedFormField>
          <MountedFormField
            label="AWS secret access key"
            name="aws_secret_access_key"
            required={!isEdit}
            rules={secretRules(isEdit, "AWS secret access key is required")}
          >
            {(control) => (
              <Input
                id={control.id}
                type="password"
                value={(control.value as string | undefined) ?? ""}
                onChange={control.onChange}
                onBlur={control.onBlur}
                autoComplete="off"
              />
            )}
          </MountedFormField>
          <MountedFormField label="AWS session token (optional)" name="aws_session_token">
            {(control) => (
              <Input
                id={control.id}
                type="password"
                value={(control.value as string | undefined) ?? ""}
                onChange={control.onChange}
                onBlur={control.onBlur}
                autoComplete="off"
              />
            )}
          </MountedFormField>
          <MountedFormField label="Cost Explorer service name (optional)" name="service_name">
            {(control) => (
              <Input
                id={control.id}
                placeholder="Amazon Bedrock"
                value={(control.value as string | undefined) ?? ""}
                onChange={control.onChange}
                onBlur={control.onBlur}
              />
            )}
          </MountedFormField>
        </>
      ) : (
        <MountedFormField
          label="Admin API key"
          name="api_key"
          required={!isEdit}
          rules={secretRules(isEdit, "Admin API key is required")}
        >
          {(control) => (
            <Input
              id={control.id}
              type="password"
              value={(control.value as string | undefined) ?? ""}
              onChange={control.onChange}
              onBlur={control.onBlur}
              autoComplete="off"
              placeholder={provider === "openai" ? "sk-admin-..." : provider === "anthropic" ? "sk-ant-admin..." : ""}
            />
          )}
        </MountedFormField>
      )}
    </div>
  );
}
```

Read `MountedFormField` and `SearchSelect` before using them: if `MountedFormField` does not accept `required` without `rules`, or `SearchSelect` has no `disabled` prop, adapt to what they accept and keep the tests' visible labels. The nested ternary in the placeholder may break the repo's `no-nested-ternary` lint rule; if so, replace it with a small lookup object `{ openai: "sk-admin-...", anthropic: "sk-ant-admin..." }[provider] ?? ""`.

In `components/model_add/CredentialModal.tsx`:
1. Import `BillingCredentialFields` and `{ BILLING_PROVIDERS, isBillingCredential, type BillingProvider }` from the helpers, and the radio group primitive the dashboard uses (look for `components/ui/radio-group.tsx`; if absent, use two `Button`s with `role="radio"` and `aria-checked`)
2. Add state: `const [purpose, setPurpose] = useState<"model_access" | "billing_access">(existingCredential && isBillingCredential(existingCredential) ? "billing_access" : "model_access");` and `const [billingProvider, setBillingProvider] = useState<BillingProvider>((existingCredential?.credential_info.provider as BillingProvider | undefined) ?? "openai");`
3. For an existing billing credential, set `initialValues` to `{ credential_name, purpose: "billing_access", billing_provider }` instead of spreading its (empty) values
4. In add mode only, render a radio group labelled "Purpose" with options "Model access" and "Billing access (read-only)", registered as the form field `purpose` with default `"model_access"`
5. Render the existing Provider select and `ProviderSpecificFields` only when `purpose === "model_access"`; otherwise render `<BillingCredentialFields provider={billingProvider} onProviderChange={setBillingProvider} isEdit={isEdit} />`, and make sure `billing_provider` defaults to `"openai"` in the form values
6. `handleSubmit` already drops empty values; keep it. When `purpose === "billing_access"`, make sure `purpose` and `billing_provider` are included in the submitted values (mounted fields are projected, so register both)

In `components/model_add/CredentialsPanel.tsx`:
1. Replace `buildCredential`, `restrictedFields` and `withoutRestrictedFields` with `buildCredentialPayload` from the helpers
2. `handleAddCredential`: `const newCredential = buildCredentialPayload(values);`
3. `handleUpdateCredential`: `const built = buildCredentialPayload(values); const newCredential = { ...built, credential_values: stripMaskedSecrets(built.credential_values) };`
4. In both `catch` blocks show the server's reason: `toast.error(error instanceof Error && error.message ? error.message : "Failed to add credential")` (and `"Failed to update credential"`). Check how `credentialCreateCall` surfaces a 400 body; if its thrown message is not the server's `error` text, use the existing `toast.fromError(error)` helper instead and adjust the test to assert what that helper shows

In `components/model_add/CredentialsTableColumns.tsx`:
1. Import `credentialPurposeLabel` and `isBillingCredential` from `./credential_form_helpers`
2. In the provider column cell, pass `isBillingCredential(row.original) ? row.original.credential_info?.provider : row.original.credential_info?.custom_llm_provider`
3. Add a column after `provider`:

```tsx
    {
      id: "purpose",
      meta: { title: "Purpose" },
      header: "Purpose",
      size: 190,
      enableSorting: false,
      cell: ({ row }) => <span className="text-sm">{credentialPurposeLabel(row.original)}</span>,
    },
```

In `components/add_model/AddModelForm.tsx`, change the `credentials.map(...)` inside `credentialOptions` to `modelAccessCredentials(credentials).map(...)` and import the helper. In `app/(dashboard)/vector-stores/_components/VectorStoreForm.tsx` and `vector_store_info.tsx`, do the same for their `credentials.map(...)` in `credentialOptions`.

- [ ] **Step 7: Run the tests to verify they pass**

Run from `ui/litellm-dashboard`: `npx vitest run src/components/model_add/credential_form_helpers.test.ts src/components/model_add/CredentialsPanel.test.tsx src/components/model_add/CredentialsTable.test.tsx src/components/model_add/CredentialModal.test.tsx src/components/add_model/AddModelForm.test.tsx`
Expected: PASS

Check `npx tsc --noEmit` output for errors in the files this task touched and fix those. Restore `ui/litellm-dashboard/tsconfig.tsbuildinfo` with `git checkout --` if it changed.

- [ ] **Step 8: Lint and commit**

Run from `ui/litellm-dashboard`: `npx eslint src/components/model_add src/components/add_model/AddModelForm.tsx src/components/networking.tsx "src/app/(dashboard)/vector-stores/_components/VectorStoreForm.tsx" "src/app/(dashboard)/vector-stores/_components/vector_store_info.tsx"`
Expected: no errors on lines this task changed

```bash
git add ui/litellm-dashboard/src/components/model_add ui/litellm-dashboard/src/components/add_model/AddModelForm.tsx ui/litellm-dashboard/src/components/networking.tsx "ui/litellm-dashboard/src/app/(dashboard)/vector-stores/_components"
git commit -m "feat(ui): label credentials by purpose and add read-only billing credentials"
```

---

### Task 5: Check it end to end, then push

**Files:** none changed unless a check fails

- [ ] **Step 1: Backend and dashboard checks**

Run: `.venv/Scripts/python -m pytest tests/test_litellm/provider_billing tests/test_litellm/proxy/credential_endpoints tests/test_litellm/proxy/management_endpoints/test_provider_reconciliation.py -q`
Expected: all PASS

Run from `ui/litellm-dashboard`: `npx tsc --noEmit` and compare the total with the branch's known count (about 1540). Expected: no errors in files this plan changed

- [ ] **Step 2: Live check against the proxy**

Restart the proxy with `bash ~/.claude/scripts/litellm-dev-up.sh` (port 4001, dev key `sk-1234` from `litellm/proxy/dev_config.yaml`). Then:

```bash
curl -s -X POST http://localhost:4001/credentials -H "Authorization: Bearer sk-1234" -H "Content-Type: application/json" \
  -d '{"credential_name":"plan-check-openai-costs","credential_values":{"api_key":"sk-proj-test-not-real"},"credential_info":{"purpose":"billing_ingestion","provider":"openai"}}'
curl -s -X POST http://localhost:4001/credentials -H "Authorization: Bearer sk-1234" -H "Content-Type: application/json" \
  -d '{"credential_name":"plan-check-openai-costs","credential_values":{"api_key":"sk-admin-test-not-real"},"credential_info":{"purpose":"billing_ingestion","provider":"openai"}}'
curl -s http://localhost:4001/credentials -H "Authorization: Bearer sk-1234" | grep -o '"credential_name":"plan-check-openai-costs","credential_values":{[^}]*}'
curl -s -X POST "http://localhost:4001/provider/billing/probe?provider=openai" -H "Authorization: Bearer sk-1234"
curl -s -X DELETE http://localhost:4001/credentials/plan-check-openai-costs -H "Authorization: Bearer sk-1234"
```

Expected, in order: a 400 naming `sk-admin-`; success; `"credential_values":{}`; a probe answer with outcome `failed` (the fake key is refused by OpenAI, which proves the credential was found and used); success

- [ ] **Step 3: Push**

```bash
git push origin litellm_token_iq
```

Then hand the user these click-through steps for the dashboard (dev server: `NEXT_PUBLIC_BASE_URL=http://localhost:4001 npx next dev -p 3001` from `ui/litellm-dashboard`):
1. The sidebar has a DATA SOURCES group with LLM Provider Credentials, and Models + Endpoints no longer has an LLM Credentials tab
2. Add Credential offers Purpose; Billing access shows the read-only note, four providers, and one Admin API key field (two AWS key fields for Bedrock)
3. Saving an ordinary OpenAI key as a billing credential shows the message about `sk-admin-`
4. The table shows a Purpose column, and a saved billing credential never shows its key when edited
5. Add Model's Existing Credentials list does not include billing credentials
