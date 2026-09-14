# Token IQ Plan System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace LiteLLM's licence key with Token IQ's own per-installation plan, so team admins, SSO and the other gated MIT features work without a LiteLLM licence and nothing in the product contacts LiteLLM's licence server or metering collector

**Architecture:** A small module resolves the installation's plan from the `TOKEN_IQ_PLAN` environment variable at import, at startup and when the YAML config sets it. The existing `premium_user` global stays the single switch that roughly 200 gated call sites already read, now derived from the plan, so none of those call sites change. User and team caps move from LiteLLM licence data onto the plan, `/health/license` reports the plan in the shape the dashboard already reads, and the LiteLLM licence client and the OTLP metering package are deleted

**Tech Stack:** Python 3.12, FastAPI, pytest, Starlette middleware. The dashboard needs no change

**Spec:** `docs/superpowers/specs/2026-09-14-token-iq-product-design.md`, sections "Licensing rules" and "Phases" (Phase 0)

## Global Constraints

- All Python runs in the repository venv: every command uses `.venv/Scripts/python`, never a system Python
- Nothing is copied or adapted from LiteLLM enterprise code, including this repository's history before commit `728daee2d8`
- No text a customer can see mentions LiteLLM, `LITELLM_LICENSE`, `litellm.ai` or `berri.ai`
- Token IQ never sends data to LiteLLM or BerriAI: no licence verification call and no usage metering
- New code annotates variables `Final`, uses frozen slotted dataclasses and tagged unions with `match`, and carries no comments beyond genuinely complex logic
- Python line length is 120
- Tests check behaviour, not code structure
- Plan tiers are an open question in the spec. This plan ships exactly one plan, `standard`, which unlocks every gated feature whose code exists and caps neither users nor teams. Tiers are added later as entries in `PLANS`
- An installation with `TOKEN_IQ_PLAN` unset runs on `standard`. A misspelt plan name stops the proxy at startup rather than silently granting or refusing features
- Plan A runs before Plan B (`docs/superpowers/plans/2026-09-14-release-readiness.md`), because Plan B's customer message check expects the licence wording removed here

## File map

| File | Responsibility |
|---|---|
| `litellm/proxy/auth/token_iq_plan.py` (create) | The plan type, the known plans, and resolving the installation's plan |
| `tests/test_litellm/proxy/auth/test_token_iq_plan.py` (create) | Plan resolution and caps |
| `litellm/proxy/proxy_server.py` (modify) | Resolve the plan, derive `premium_user`, stop metering |
| `litellm/proxy/management_endpoints/internal_user_endpoints.py` (modify) | User cap from the plan |
| `litellm/proxy/management_endpoints/team_endpoints.py` (modify) | Team cap from the plan, team admin refusal wording |
| `litellm/proxy/hooks/dynamic_rate_limiter.py`, `dynamic_rate_limiter_v3.py` (modify) | Priority reservation gated on the plan instead of an environment variable |
| `litellm/proxy/health_endpoints/_health_endpoints.py` (modify) | `/health/license` reports the plan |
| `litellm/proxy/_types.py`, `litellm/proxy/utils.py`, `litellm/proxy/management_endpoints/ui_sso.py`, `key_management_endpoints.py` (modify) | Refusal wording |
| `litellm/proxy/enterprise_billing/` (delete) | LiteLLM's usage metering to its own collector |
| `litellm/proxy/auth/litellm_license.py`, `litellm/proxy/auth/public_key.pem` (delete) | LiteLLM's licence client and its public key |

---

### Task 1: The plan module

**Files:**
- Create: `litellm/proxy/auth/token_iq_plan.py`
- Test: `tests/test_litellm/proxy/auth/test_token_iq_plan.py`

**Interfaces:**
- Produces: `PLAN_ENV: Final = "TOKEN_IQ_PLAN"`, `TokenIqPlan(name: str, unlocks_gated_features: bool, max_users: int | None, max_teams: int | None)` with `is_over_user_limit(total_users: int) -> bool` and `is_over_team_limit(team_count: int) -> bool`, `PLANS: Mapping[str, TokenIqPlan]`, `KnownPlan(plan)`, `UnknownPlan(requested)`, `lookup_plan(environ: Mapping[str, str]) -> KnownPlan | UnknownPlan`, `require_plan(environ: Mapping[str, str]) -> TokenIqPlan`

- [ ] **Step 1: Write the failing tests**

```python
import pytest

from litellm.proxy.auth.token_iq_plan import (
    PLAN_ENV,
    PLANS,
    KnownPlan,
    TokenIqPlan,
    UnknownPlan,
    lookup_plan,
    require_plan,
)


def test_an_installation_with_no_plan_configured_runs_on_the_standard_plan():
    assert lookup_plan({}) == KnownPlan(PLANS["standard"])


def test_a_blank_plan_setting_is_treated_as_unset():
    assert lookup_plan({PLAN_ENV: "   "}) == KnownPlan(PLANS["standard"])


def test_a_configured_plan_name_is_honoured_despite_surrounding_whitespace():
    assert lookup_plan({PLAN_ENV: "  standard "}) == KnownPlan(PLANS["standard"])


def test_the_standard_plan_unlocks_gated_features_and_caps_nothing():
    standard = PLANS["standard"]
    assert standard.unlocks_gated_features is True
    assert standard.is_over_user_limit(total_users=1_000_000) is False
    assert standard.is_over_team_limit(team_count=1_000_000) is False


def test_an_unknown_plan_is_reported_rather_than_guessed():
    assert lookup_plan({PLAN_ENV: "enterprize"}) == UnknownPlan(requested="enterprize")


def test_a_misspelt_plan_stops_startup_and_names_the_real_plans():
    with pytest.raises(ValueError, match=r"enterprize.*standard"):
        require_plan({PLAN_ENV: "enterprize"})


@pytest.mark.parametrize(("total_users", "over"), [(2, False), (3, True)])
def test_a_user_cap_refuses_only_beyond_the_cap(total_users, over):
    capped = TokenIqPlan(name="capped", unlocks_gated_features=True, max_users=2, max_teams=None)
    assert capped.is_over_user_limit(total_users=total_users) is over


@pytest.mark.parametrize(("team_count", "over"), [(5, False), (6, True)])
def test_a_team_cap_refuses_only_beyond_the_cap(team_count, over):
    capped = TokenIqPlan(name="capped", unlocks_gated_features=True, max_users=None, max_teams=5)
    assert capped.is_over_team_limit(team_count=team_count) is over
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_litellm/proxy/auth/test_token_iq_plan.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'litellm.proxy.auth.token_iq_plan'`

- [ ] **Step 3: Write the module**

```python
"""Which gated features an installation may use, decided by its Token IQ plan."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

PLAN_ENV: Final = "TOKEN_IQ_PLAN"
DEFAULT_PLAN_NAME: Final = "standard"


@dataclass(frozen=True, slots=True)
class TokenIqPlan:
    name: str
    unlocks_gated_features: bool
    max_users: int | None
    max_teams: int | None

    def is_over_user_limit(self, total_users: int) -> bool:
        return self.max_users is not None and total_users > self.max_users

    def is_over_team_limit(self, team_count: int) -> bool:
        return self.max_teams is not None and team_count > self.max_teams


PLANS: Final[Mapping[str, TokenIqPlan]] = MappingProxyType(
    {
        "standard": TokenIqPlan(name="standard", unlocks_gated_features=True, max_users=None, max_teams=None),
    }
)


@dataclass(frozen=True, slots=True)
class KnownPlan:
    plan: TokenIqPlan


@dataclass(frozen=True, slots=True)
class UnknownPlan:
    requested: str


def lookup_plan(environ: Mapping[str, str]) -> KnownPlan | UnknownPlan:
    requested: Final = environ.get(PLAN_ENV, "").strip() or DEFAULT_PLAN_NAME
    plan: Final = PLANS.get(requested)
    return KnownPlan(plan) if plan is not None else UnknownPlan(requested)


def require_plan(environ: Mapping[str, str]) -> TokenIqPlan:
    """The installation's plan, or a startup failure naming the plans that exist."""
    match lookup_plan(environ):
        case KnownPlan(plan=plan):
            return plan
        case UnknownPlan(requested=requested):
            raise ValueError(f"{PLAN_ENV}={requested!r} is not a Token IQ plan. Known plans: {', '.join(sorted(PLANS))}")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_litellm/proxy/auth/test_token_iq_plan.py -v`

Expected: PASS, 10 tests

- [ ] **Step 5: Commit**

```bash
git add litellm/proxy/auth/token_iq_plan.py tests/test_litellm/proxy/auth/test_token_iq_plan.py
git commit -m "feat(plan): resolve an installation's Token IQ plan"
```

---

### Task 2: Stop metering usage to LiteLLM

`litellm/proxy/enterprise_billing/billing_metrics.py` pushes usage to LiteLLM's own OTLP collector over mutual TLS, and it is switched on by `premium_user`. Task 3 makes `premium_user` true on every installation, so this path is removed first. The `BillableRequestMetricsMiddleware` stays, because it also feeds the dashboard's gateway request counts

**Files:**
- Modify: `litellm/proxy/proxy_server.py` (the import block that begins `try:` above `from litellm.proxy.enterprise_billing.billing_metrics import (` near line 548, the `BillableRequestMetricsMiddleware` registration near line 2096, and the shutdown call near line 921)
- Modify: `litellm/proxy/middleware/billable_request_metrics_middleware.py` (module docstring line naming `litellm.proxy.enterprise_billing.billing_metrics`)
- Delete: `litellm/proxy/enterprise_billing/`, `tests/test_litellm/proxy/enterprise_billing/`
- Test: `tests/test_litellm/proxy/test_proxy_server.py`

**Interfaces:**
- Produces: `proxy_server.app` still registers `BillableRequestMetricsMiddleware`, now with a `recorder_factory` that always returns `None`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_litellm/proxy/test_proxy_server.py`:

```python
def test_the_gateway_has_no_path_that_meters_usage_to_litellm(monkeypatch):
    import importlib.util

    from litellm.proxy import proxy_server

    monkeypatch.setattr(proxy_server, "premium_user", True)
    monkeypatch.setenv("LITELLM_BILLING_METRICS_ENDPOINT", "https://collector.invalid")
    billable = next(m for m in proxy_server.app.user_middleware if m.cls.__name__ == "BillableRequestMetricsMiddleware")

    assert billable.kwargs["recorder_factory"]() is None
    assert importlib.util.find_spec("litellm.proxy.enterprise_billing") is None
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_litellm/proxy/test_proxy_server.py -k meters_usage_to_litellm -v`

Expected: FAIL on `find_spec(...) is None`, because the package still exists

- [ ] **Step 3: Remove the metering path**

In `litellm/proxy/proxy_server.py`, delete this whole block:

```python
try:
    from litellm.proxy.enterprise_billing.billing_metrics import (
        build_billing_metrics_recorder as _build_billing_metrics_recorder,
    )
    from litellm.proxy.enterprise_billing.billing_metrics import (
        shutdown_billing_metrics_recorder as _shutdown_billing_metrics_recorder,
    )

    build_billing_metrics_recorder: Callable[..., BillingRecorder | None] | None = _build_billing_metrics_recorder
    shutdown_billing_metrics_recorder: Callable[[], None] | None = _shutdown_billing_metrics_recorder
except ImportError:
    build_billing_metrics_recorder = None
    shutdown_billing_metrics_recorder = None
```

Delete the shutdown call:

```python
    if shutdown_billing_metrics_recorder is not None:
        shutdown_billing_metrics_recorder()
```

In the `app.add_middleware(BillableRequestMetricsMiddleware, ...)` call, replace the `recorder_factory=lambda: (...)` argument and the comment lines directly above it with:

```python
    recorder_factory=lambda: None,
```

In `litellm/proxy/middleware/billable_request_metrics_middleware.py`, delete the docstring line that says `enterprise metering (see litellm.proxy.enterprise_billing.billing_metrics).` and reword the sentence it ends so it still reads as a complete sentence

Delete the package and its tests:

```bash
git rm -r litellm/proxy/enterprise_billing tests/test_litellm/proxy/enterprise_billing
```

- [ ] **Step 4: Clear what the removal left unused**

Run: `.venv/Scripts/python -m ruff check litellm/proxy/proxy_server.py litellm/proxy/middleware/billable_request_metrics_middleware.py`

Remove each import it reports as unused (expected: `BillingRecorder`, and `Callable` only if nothing else in the file uses it), then run it again until it reports no errors

- [ ] **Step 5: Run the test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_litellm/proxy/test_proxy_server.py -k meters_usage_to_litellm -v`

Expected: PASS

- [ ] **Step 6: Run the middleware tests**

Run: `.venv/Scripts/python -m pytest tests/test_litellm/proxy/middleware -q`

Expected: PASS. If a test imported the deleted package only to build a recorder, delete that test, because the recorder no longer exists

- [ ] **Step 7: Commit**

```bash
git add -A litellm/proxy tests/test_litellm/proxy
git commit -m "fix(proxy): never meter usage to LiteLLM's collector"
```

---

### Task 3: Resolve the plan in the proxy

**Files:**
- Modify: `litellm/proxy/proxy_server.py`
- Modify: `litellm/proxy/management_endpoints/internal_user_endpoints.py:505,523-527`
- Modify: `litellm/proxy/management_endpoints/team_endpoints.py:1284,1345-1349`
- Modify: `litellm/proxy/hooks/dynamic_rate_limiter.py:115-117`, `litellm/proxy/hooks/dynamic_rate_limiter_v3.py:124-126`
- Test: `tests/test_litellm/proxy/test_proxy_server.py`, `tests/test_litellm/proxy/management_endpoints/test_internal_user_endpoints.py`, `tests/test_litellm/proxy/management_endpoints/test_team_endpoints.py`, `tests/test_litellm/proxy/management_helpers/test_team_metadata_validation.py`, `tests/test_litellm/proxy/hooks/test_dynamic_rate_limiter_v3.py`, `tests/test_litellm/proxy/hooks/test_rate_limiter_toctou.py`, `tests/proxy_behavior/management/conftest.py`, `tests/e2e/quota_management/ratelimit/test_dynamic_rate_limit_priority_e2e.py`

**Interfaces:**
- Consumes: `PLAN_ENV`, `TokenIqPlan`, `require_plan` from Task 1
- Produces: module globals `proxy_server.token_iq_plan: TokenIqPlan` and `proxy_server.premium_user: bool`, where `premium_user == token_iq_plan.unlocks_gated_features`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_litellm/proxy/test_proxy_server.py`:

```python
def test_gated_features_unlock_from_the_token_iq_plan_without_a_litellm_licence(monkeypatch):
    from litellm.proxy import proxy_server

    monkeypatch.delenv("LITELLM_LICENSE", raising=False)
    monkeypatch.setattr(proxy_server, "premium_user", False)

    proxy_server.ProxyConfig()._load_environment_variables({"environment_variables": {"TOKEN_IQ_PLAN": "standard"}})

    assert proxy_server.token_iq_plan.name == "standard"
    assert proxy_server.premium_user is True
```

In `tests/test_litellm/proxy/management_endpoints/test_internal_user_endpoints.py`, in the test that asserts `"License is over limit"` with `mock_license_check.is_over_limit.return_value = True`, replace this block:

```python
    # Mock the license check to return True (over limit)
    mock_license_check = mocker.MagicMock()
    mock_license_check.is_over_limit.return_value = True

    # Patch the imports in the endpoint
    mocker.patch("litellm.proxy.proxy_server.prisma_client", mock_prisma_client)
    mocker.patch("litellm.proxy.proxy_server._license_check", mock_license_check)
```

with:

```python
    from litellm.proxy.auth.token_iq_plan import TokenIqPlan

    mocker.patch("litellm.proxy.proxy_server.prisma_client", mock_prisma_client)
    mocker.patch(
        "litellm.proxy.proxy_server.token_iq_plan",
        TokenIqPlan(name="capped", unlocks_gated_features=True, max_users=999, max_teams=None),
    )
```

and replace its closing assertions:

```python
    assert "License is over limit" in str(exc_info.value.message)
    assert "support@berri.ai" in str(exc_info.value.message)

    # Verify that the license check was called with the correct user count
    mock_license_check.is_over_limit.assert_called_once_with(total_users=1000)
```

with:

```python
    assert "Token IQ plan allows 999 users" in str(exc_info.value.message)
    assert "berri.ai" not in str(exc_info.value.message)
```

In `test_new_user_license_gate_counts_only_billable_users` in the same file, replace:

```python
    from litellm.proxy.auth.litellm_license import LicenseCheck
```

with:

```python
    from litellm.proxy.auth.token_iq_plan import TokenIqPlan
```

replace:

```python
    license_check = LicenseCheck()
    license_check.airgapped_license_data = {"max_users": 2}  # type: ignore
    mocker.patch("litellm.proxy.proxy_server._license_check", license_check)
```

with:

```python
    mocker.patch(
        "litellm.proxy.proxy_server.token_iq_plan",
        TokenIqPlan(name="capped", unlocks_gated_features=True, max_users=2, max_teams=None),
    )
```

and replace both remaining occurrences of `"License is over limit"` in that test with `"Token IQ plan allows"`

In `tests/test_litellm/proxy/test_proxy_server.py`, in `test_load_environment_variables_litellm_license_and_edge_cases`, rename the test to `test_load_environment_variables_token_iq_plan_and_edge_cases` and replace its Test Case 1 (from `# Test Case 1: LITELLM_LICENSE in environment_variables` down to `mock_license_check.is_premium.assert_called_once()`) with:

```python
    # Test Case 1: TOKEN_IQ_PLAN in environment_variables
    from litellm.proxy import proxy_server

    test_config_with_plan = {
        "environment_variables": {
            "TOKEN_IQ_PLAN": "standard",
            "OTHER_VAR": "other_value",
        }
    }

    with patch.dict(os.environ, {}, clear=False), patch("litellm.proxy.proxy_server.premium_user", False):
        proxy_config._load_environment_variables(test_config_with_plan)

        assert os.environ["TOKEN_IQ_PLAN"] == "standard"
        assert proxy_server.premium_user is True
```

Remove the environment variable that the rate limiter tests set, which becomes the failing test for the limiters:

```bash
sed -i '/monkeypatch.setenv("LITELLM_LICENSE", "test-license-key")/d' tests/test_litellm/proxy/hooks/test_dynamic_rate_limiter_v3.py tests/test_litellm/proxy/hooks/test_rate_limiter_toctou.py
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_litellm/proxy/test_proxy_server.py -k "token_iq_plan or litellm_licence" tests/test_litellm/proxy/management_endpoints/test_internal_user_endpoints.py -k "over_limit or billable" tests/test_litellm/proxy/hooks/test_dynamic_rate_limiter_v3.py -q`

Expected: FAIL. `proxy_server` has no `token_iq_plan`, and the priority weight tests split capacity equally because the limiter still requires `LITELLM_LICENSE`

- [ ] **Step 3: Resolve the plan in `proxy_server.py`**

Replace the import:

```python
from litellm.proxy.auth.litellm_license import LicenseCheck
```

with:

```python
from litellm.proxy.auth.token_iq_plan import PLAN_ENV, TokenIqPlan, require_plan
```

Replace:

```python
_license_check = LicenseCheck()
premium_user: bool = _license_check.is_premium()
premium_user_data: Optional["EnterpriseLicenseData"] = _license_check.airgapped_license_data
```

with:

```python
token_iq_plan: TokenIqPlan = require_plan(os.environ)
premium_user: bool = token_iq_plan.unlocks_gated_features
```

In the `global \` statement of `proxy_startup_event`, replace the line `        _license_check, \` with `        token_iq_plan, \`

Replace the startup block:

```python
    ## CHECK PREMIUM USER
    verbose_proxy_logger.debug("litellm.proxy.proxy_server.py::startup() - CHECKING PREMIUM USER - %s", premium_user)
    if premium_user is False:
        premium_user = _license_check.is_premium()
```

with:

```python
    ## RESOLVE THE TOKEN IQ PLAN
    token_iq_plan = require_plan(os.environ)
    premium_user = token_iq_plan.unlocks_gated_features
```

In `_load_environment_variables`, replace `global premium_user` with `global premium_user, token_iq_plan`, and replace:

```python
            # check if litellm_license in general_settings
            if "LITELLM_LICENSE" in environment_variables:
                _license_check.license_str = os.getenv("LITELLM_LICENSE", None)
                premium_user = _license_check.is_premium()
```

with:

```python
            if PLAN_ENV in environment_variables:
                token_iq_plan = require_plan(os.environ)
                premium_user = token_iq_plan.unlocks_gated_features
```

Delete the general settings licence block:

```python
            # check if litellm_license in general_settings
            if "litellm_license" in general_settings:
                _license_check.license_str = general_settings["litellm_license"]
                premium_user = _license_check.is_premium()
```

- [ ] **Step 4: Take the user and team caps from the plan**

In `internal_user_endpoints.py`, change the import `from litellm.proxy.proxy_server import _license_check, general_settings, prisma_client` to `from litellm.proxy.proxy_server import general_settings, prisma_client, token_iq_plan`, and replace:

```python
        if billable_users and _license_check.is_over_limit(total_users=billable_users):
            raise HTTPException(
                status_code=403,
                detail="License is over limit. Please contact support@berri.ai to upgrade your license.",
            )
```

with:

```python
        if billable_users and token_iq_plan.is_over_user_limit(total_users=billable_users):
            raise HTTPException(
                status_code=403,
                detail=(
                    f"This installation's Token IQ plan allows {token_iq_plan.max_users} users. "
                    "Ask your Token IQ administrator to raise the limit."
                ),
            )
```

In `team_endpoints.py`, in the import list that contains `_license_check,` near line 1284, replace that entry with `token_iq_plan,`, and replace:

```python
        if total_teams and _license_check.is_team_count_over_limit(team_count=total_teams):
            raise HTTPException(
                status_code=403,
                detail="License is over limit. Please contact support@berri.ai to upgrade your license.",
            )
```

with:

```python
        if total_teams and token_iq_plan.is_over_team_limit(team_count=total_teams):
            raise HTTPException(
                status_code=403,
                detail=(
                    f"This installation's Token IQ plan allows {token_iq_plan.max_teams} teams. "
                    "Ask your Token IQ administrator to raise the limit."
                ),
            )
```

- [ ] **Step 5: Gate priority reservation on the plan**

In both `dynamic_rate_limiter.py` and `dynamic_rate_limiter_v3.py`, replace:

```python
if os.getenv("LITELLM_LICENSE", None) is None:
    verbose_proxy_logger.error(
        "PREMIUM FEATURE: Reserving tpm/rpm by priority is a premium feature. Please add a 'LITELLM_LICENSE' to your .env to enable this.\nGet a license: https://docs.litellm.ai/docs/proxy/enterprise."
    )
```

keeping each file's existing indentation, with:

```python
from litellm.proxy.proxy_server import premium_user

if premium_user is not True:
    verbose_proxy_logger.error("Reserving tpm/rpm by priority is not included in this installation's Token IQ plan")
```

Then run `.venv/Scripts/python -m ruff check litellm/proxy/hooks/dynamic_rate_limiter.py litellm/proxy/hooks/dynamic_rate_limiter_v3.py` and remove `import os` from any file where it reports the import as unused

- [ ] **Step 6: Drop test patches of the removed licence object**

These tests patched `_license_check` only to keep the caps out of the way, and `standard` has no caps:

```bash
sed -i -e '/patch("litellm.proxy.proxy_server._license_check") as mock_license,/d' -e '/mock_license.is_team_count_over_limit.return_value = False/d' tests/test_litellm/proxy/management_endpoints/test_team_endpoints.py
sed -i -e '/patch("litellm.proxy.proxy_server._license_check") as lic,/d' -e '/lic.is_team_count_over_limit.return_value = False/d' tests/test_litellm/proxy/management_helpers/test_team_metadata_validation.py
sed -i -e '/# Mock the license check to return False (under limit)/d' -e '/mock_license_check = mocker.MagicMock()/d' -e '/mock_license_check.is_over_limit.return_value = False/d' -e '/mocker.patch("litellm.proxy.proxy_server._license_check", mock_license_check)/d' tests/test_litellm/proxy/management_endpoints/test_internal_user_endpoints.py
sed -i 's/# lifespan re-runs _license_check/# lifespan re-resolves the Token IQ plan/' tests/proxy_behavior/management/conftest.py
```

In `tests/e2e/quota_management/ratelimit/test_dynamic_rate_limit_priority_e2e.py`, reword the module docstring lines that say the proxy must run with `LITELLM_LICENSE` set so they say priority reservation needs a Token IQ plan that unlocks gated features, which `standard` does

Confirm nothing still references the removed object:

Run: `grep -rnE "_license_check|premium_user_data" litellm tests --include=*.py`

Expected: no output

- [ ] **Step 7: Run the tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_litellm/proxy/test_proxy_server.py tests/test_litellm/proxy/management_endpoints/test_internal_user_endpoints.py tests/test_litellm/proxy/management_endpoints/test_team_endpoints.py tests/test_litellm/proxy/management_helpers/test_team_metadata_validation.py tests/test_litellm/proxy/hooks/test_dynamic_rate_limiter_v3.py tests/test_litellm/proxy/hooks/test_rate_limiter_toctou.py -q`

Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add -A litellm/proxy tests
git commit -m "feat(plan): unlock gated features from the Token IQ plan"
```

---

### Task 4: `/health/license` reports the plan

The dashboard's plan card (`SidebarUsageCard.tsx`) and expiry banner (`LicenseExpiryBanner.tsx`) read this endpoint through `getLicenseInfo`. Keeping the response shape means neither changes: the card shows the plan name, and the banner stays hidden because a plan has no expiry date

**Files:**
- Modify: `litellm/proxy/health_endpoints/_health_endpoints.py` (the functions `_read_license_data`, `_read_allowed_features` and `health_license_endpoint`, and `EnterpriseLicenseData` in the `from litellm.proxy._types import (` list)
- Modify: `litellm/proxy/proxy_server.py` (`EnterpriseLicenseData` in the `_types` import list)
- Test: `tests/test_litellm/proxy/health_endpoints/test_health_endpoints.py`

**Interfaces:**
- Consumes: `proxy_server.token_iq_plan` from Task 3, `PLANS` and `TokenIqPlan` from Task 1
- Produces: `GET /health/license` returns `{"has_license": True, "license_type": <plan name>, "expiration_date": None, "allowed_features": [], "limits": {"max_users": int | None, "max_teams": int | None}}`

- [ ] **Step 1: Write the failing tests**

In `tests/test_litellm/proxy/health_endpoints/test_health_endpoints.py`, delete `test_health_license_endpoint_with_active_license` and `test_health_license_endpoint_without_valid_license`, and add:

```python
@pytest.mark.asyncio
async def test_health_license_reports_the_installations_token_iq_plan():
    from litellm.proxy.auth.token_iq_plan import TokenIqPlan

    growth = TokenIqPlan(name="growth", unlocks_gated_features=True, max_users=50, max_teams=4)
    with patch("litellm.proxy.proxy_server.token_iq_plan", growth):
        response = await health_license_endpoint(user_api_key_dict=MagicMock())

    assert response == {
        "has_license": True,
        "license_type": "growth",
        "expiration_date": None,
        "allowed_features": [],
        "limits": {"max_users": 50, "max_teams": 4},
    }


@pytest.mark.asyncio
async def test_health_license_shows_no_caps_on_the_standard_plan():
    from litellm.proxy.auth.token_iq_plan import PLANS

    with patch("litellm.proxy.proxy_server.token_iq_plan", PLANS["standard"]):
        response = await health_license_endpoint(user_api_key_dict=MagicMock())

    assert response["license_type"] == "standard"
    assert response["limits"] == {"max_users": None, "max_teams": None}
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_litellm/proxy/health_endpoints/test_health_endpoints.py -k health_license -v`

Expected: FAIL, because the endpoint still imports `_license_check`, which Task 3 removed

- [ ] **Step 3: Rewrite the endpoint**

Delete `_read_license_data` and `_read_allowed_features`, and replace `health_license_endpoint` with:

```python
@router.get(
    "/health/license",
    tags=["health"],
    dependencies=[Depends(user_api_key_auth)],
)
async def health_license_endpoint(
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    """The installation's Token IQ plan, in the shape the dashboard's plan card reads."""
    from litellm.proxy.proxy_server import token_iq_plan

    return {
        "has_license": True,
        "license_type": token_iq_plan.name,
        "expiration_date": None,
        "allowed_features": [],
        "limits": {"max_users": token_iq_plan.max_users, "max_teams": token_iq_plan.max_teams},
    }
```

Remove `EnterpriseLicenseData` from the `_types` import lists in `_health_endpoints.py` and `proxy_server.py`, then run `.venv/Scripts/python -m ruff check litellm/proxy/health_endpoints/_health_endpoints.py litellm/proxy/proxy_server.py` and remove any other import it reports as unused

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_litellm/proxy/health_endpoints/test_health_endpoints.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add litellm/proxy/health_endpoints/_health_endpoints.py litellm/proxy/proxy_server.py tests/test_litellm/proxy/health_endpoints/test_health_endpoints.py
git commit -m "feat(plan): report the Token IQ plan on /health/license"
```

---

### Task 5: Refusals name the Token IQ plan, never LiteLLM

**Files:**
- Modify: `litellm/proxy/_types.py` (`CommonProxyErrors.not_premium_user` and `CommonProxyErrors.missing_enterprise_package`)
- Modify: `litellm/proxy/management_endpoints/team_endpoints.py` (`_check_team_member_admin_add` and the `data.role == "admin" and not premium_user` refusal in `team_member_update`)
- Modify: `litellm/proxy/utils.py` (`_premium_user_check`)
- Modify: `litellm/proxy/management_endpoints/ui_sso.py` (the two `You must be a LiteLLM Enterprise user to use SSO` messages)
- Modify: `litellm/proxy/management_endpoints/key_management_endpoints.py` (the wildcard model access group message)
- Test: `tests/test_litellm/proxy/test_team_member_update.py`, `tests/test_litellm/proxy/management_endpoints/test_ui_sso.py`

**Interfaces:**
- Consumes: nothing from earlier tasks
- Produces: `CommonProxyErrors.not_premium_user.value == "This feature is not included in this installation's Token IQ plan."`

- [ ] **Step 1: Write the failing tests**

In `tests/test_litellm/proxy/test_team_member_update.py`, rename `test_ateam_member_update_admin_requires_premium` to `test_assigning_a_team_admin_off_plan_names_the_token_iq_plan` and replace its `expected_msg` block and final assertion with:

```python
    assert exc_info.value.detail == "Assigning team admins: This feature is not included in this installation's Token IQ plan."
    assert "LiteLLM" not in exc_info.value.detail
```

Append to `tests/test_litellm/proxy/management_endpoints/test_ui_sso.py`, adding any of these imports the file does not already have at its top:

```python
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_sso_beyond_the_free_user_count_names_the_token_iq_plan():
    from litellm.proxy._types import ProxyException
    from litellm.proxy.management_endpoints.ui_sso import _raise_if_sso_exceeds_free_user_limit

    repository = MagicMock()
    repository.return_value.count_billable_users = AsyncMock(return_value=6)
    with patch("litellm.proxy.management_endpoints.ui_sso.UserRepository", repository):
        with pytest.raises(ProxyException) as refused:
            await _raise_if_sso_exceeds_free_user_limit(premium_user=False, prisma_client=MagicMock())

    assert "Token IQ plan" in refused.value.message
    assert "LiteLLM" not in refused.value.message
    assert "litellm.ai" not in refused.value.message


def test_plan_refusals_never_send_customers_to_litellm():
    from litellm.proxy._types import CommonProxyErrors

    for message in (CommonProxyErrors.not_premium_user.value, CommonProxyErrors.missing_enterprise_package.value):
        assert "LiteLLM" not in message
        assert "LITELLM_LICENSE" not in message
        assert "litellm.ai" not in message
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_litellm/proxy/test_team_member_update.py tests/test_litellm/proxy/management_endpoints/test_ui_sso.py -k "token_iq_plan or never_send" -v`

Expected: FAIL, because every message still names LiteLLM

- [ ] **Step 3: Rewrite the messages**

In `_types.py`:

```python
    not_premium_user = "This feature is not included in this installation's Token IQ plan."
```

```python
    missing_enterprise_package = "This feature is not available in Token IQ."
```

In `team_endpoints.py`, in `_check_team_member_admin_add`, replace both `raise ValueError(...)` messages with `f"Assigning team admins: {CommonProxyErrors.not_premium_user.value}"`. In `team_member_update`, replace the hard-coded `detail="Assigning team admins is a premium feature. ..."` with:

```python
            detail=f"Assigning team admins: {CommonProxyErrors.not_premium_user.value}",
```

In `utils.py`, replace the body of `_premium_user_check` up to the `if not premium_user:` line with:

```python
    from litellm.proxy.proxy_server import premium_user

    detail_msg: Final = (
        f"{feature}: {CommonProxyErrors.not_premium_user.value}" if feature else CommonProxyErrors.not_premium_user.value
    )
```

In `ui_sso.py`, replace the first SSO message with:

```python
            message=(
                "SSO for more than 5 users is not included in this installation's Token IQ plan. "
                "SSO is active because MICROSOFT_CLIENT_ID, GOOGLE_CLIENT_ID, GENERIC_CLIENT_ID or SAML is configured."
            ),
```

and the second with:

```python
                message=(
                    "SSO is not included in this installation's Token IQ plan. "
                    "SSO is active because MICROSOFT_CLIENT_ID, GOOGLE_CLIENT_ID or GENERIC_CLIENT_ID is set."
                ),
```

In `key_management_endpoints.py`, replace the wildcard message with:

```python
                        "error": f"Setting a model access group on a wildcard model: {CommonProxyErrors.not_premium_user.value}"
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_litellm/proxy/test_team_member_update.py tests/test_litellm/proxy/management_endpoints/test_ui_sso.py -q`

Expected: PASS

- [ ] **Step 5: Find any other test that asserted the old wording**

Run: `grep -rnE "LiteLLM Enterprise user|premium feature\. You must|enterprise\.litellm\.ai/demo|Missing litellm-enterprise package" tests --include=*.py`

Expected: no output. Update any test the command lists so it asserts the Token IQ wording, then run that test file

- [ ] **Step 6: Commit**

```bash
git add -A litellm/proxy tests
git commit -m "fix(plan): refusals name the Token IQ plan instead of LiteLLM"
```

---

### Task 6: Delete LiteLLM's licence client and prove it live

**Files:**
- Delete: `litellm/proxy/auth/litellm_license.py`, `litellm/proxy/auth/public_key.pem` (if present), `tests/test_litellm/proxy/auth/test_litellm_license.py`
- Modify: `litellm/proxy/_types.py` (delete `class EnterpriseLicenseData`)

- [ ] **Step 1: Delete the client, its key and its test**

```bash
git rm litellm/proxy/auth/litellm_license.py tests/test_litellm/proxy/auth/test_litellm_license.py
git rm --ignore-unmatch litellm/proxy/auth/public_key.pem
```

Delete `class EnterpriseLicenseData(TypedDict, total=False):` and its five fields from `litellm/proxy/_types.py`

- [ ] **Step 2: Verify nothing still depends on them**

Run: `grep -rnE "litellm_license|LicenseCheck|EnterpriseLicenseData|license\.litellm\.ai|LITELLM_LICENSE" litellm tests --include=*.py`

Expected: no output

Run: `.venv/Scripts/python -c "import litellm.proxy.proxy_server"`

Expected: exits cleanly

- [ ] **Step 3: Run every affected suite**

Run: `.venv/Scripts/python -m pytest tests/test_litellm/proxy/auth tests/test_litellm/proxy/health_endpoints tests/test_litellm/proxy/management_endpoints tests/test_litellm/proxy/management_helpers tests/test_litellm/proxy/hooks tests/test_litellm/proxy/test_proxy_server.py tests/test_litellm/proxy/test_team_member_update.py -q`

Expected: PASS apart from failures that also fail on the commit before Task 1. Check any failure against that commit with `git stash` before treating it as new

Run: `.venv/Scripts/python -m ruff check litellm tests/test_litellm/proxy`

Expected: no new errors

- [ ] **Step 4: Prove it against a running proxy**

Start the proxy with the dev script and no LiteLLM licence, then assign a team admin and read the plan. Run from the repository root:

```bash
bash ~/.claude/scripts/litellm-dev-up.sh
K=$(grep -E '^LITELLM_MASTER_KEY' .env | cut -d= -f2- | tr -d ' "')
TEAM=$(curl -s -X POST localhost:4001/team/new -H "Authorization: Bearer $K" -H 'Content-Type: application/json' -d '{"team_alias":"plan-proof"}' | .venv/Scripts/python -c "import sys,json;print(json.load(sys.stdin)['team_id'])")
curl -s -X POST localhost:4001/team/member_add -H "Authorization: Bearer $K" -H 'Content-Type: application/json' -d "{\"team_id\":\"$TEAM\",\"member\":{\"role\":\"admin\",\"user_email\":\"plan-proof@example.com\"}}"
curl -s localhost:4001/health/license -H "Authorization: Bearer $K"
curl -s -X POST localhost:4001/team/delete -H "Authorization: Bearer $K" -H 'Content-Type: application/json' -d "{\"team_ids\":[\"$TEAM\"]}"
```

Expected: `/team/member_add` returns the team with the new member's role `admin`, not a premium refusal, and `/health/license` returns `"license_type":"standard"`

- [ ] **Step 5: Commit**

```bash
git add -A litellm tests
git commit -m "chore(plan): delete LiteLLM's licence client"
```
