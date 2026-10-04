# Courier Mode Admin Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let an admin put a team into courier mode, so that team's traffic only ever reaches a provider with its body untouched, and make the gateway honest about which of that team's providers actually bill correctly in that mode.

**Architecture:** Courier and translator are different addresses expecting differently shaped bodies, so a team setting cannot silently change how an existing request behaves. What it changes is which addresses that team may use. A team in courier mode is refused on the translating routes with a message naming the address to use instead, and unaffected on the pass-through routes. Enforcement rides the existing `common_checks` path in `auth_checks.py`, which is already where a team's blocked state, budget and model permissions are decided, so courier mode inherits the same caching and the same failure shape. The setting is a column on `LiteLLM_TeamTable` alongside `allow_team_guardrail_config`, which is the closest existing precedent.

**Tech Stack:** Python 3.12, FastAPI, Prisma, pytest, React/Next.js for the dashboard, the `tests/e2e` harness.

**Spec:** `docs/superpowers/specs/2026-09-11-courier-mode-design.md`

## Global Constraints

- Python max line length is 120.
- Fully typed. No `Any`, no bare `dict`. Annotate locals with `: Final` (LIT010). Never rebind or mutate parameters (LIT011) without `# rebind-ok: <reason>`.
- No mutable containers built by accumulation (LIT001/LIT002). `# mutable-ok: <reason>` is a last resort.
- Every lint or type suppression names its exact rule and carries a reason. `# type: ignore` is banned (LIT009).
- No comments except genuinely non-obvious business logic, tool-directed markers, or TODO/FIXME with a reason.
- **Migrations change schema only.** No `UPDATE`, `DELETE`, `MERGE` or `INSERT ... SELECT`. Adding a nullable column with a default is fine; backfilling rows is not. `tests/code_coverage_tests/check_migrations_no_data_rewrites.py` enforces this.
- e2e tests: never import `requests`. Mark live tests `@pytest.mark.e2e`, declare `@pytest.mark.covers(...)`, add the id to `tests/e2e/coverage_registry/`.
- The UI suite under `tests/e2e/ui/` is TypeScript Playwright and does not use the Python harness or its typing rules.
- Conventional commits.

## The rule carried over from the provider work

Courier mode was estimated as one small change for OpenRouter and turned out to be three defects, the worst of which returned correct answers while recording zero cost. Every one of them passed the unit suite. So no task here is complete on green tests alone: each one that touches the request path ends by driving a real request and reading back what the database recorded.

## Preconditions

**Do not flip the default in this plan.** Translator stays the default. Courier is opt-in per team until Bedrock is proven against real AWS traffic, which is Task 3 of `2026-09-11-bedrock-courier-cost-reader.md` and is blocked on credentials. Shipping a default that silently under-bills one provider is the exact failure this whole effort exists to prevent.

---

### Task 1: Store the setting

**Files:**
- Modify: `schema.prisma` (`LiteLLM_TeamTable`)
- Create: `litellm-proxy-extras/litellm_proxy_extras/migrations/20260912000000_team_courier_mode/migration.sql`
- Modify: `litellm/models/team.py`
- Modify: `litellm/repositories/team_repository.py`
- Test: `tests/test_litellm/proxy/management_endpoints/test_team_endpoints.py`

**Interfaces:**
- Produces: `LiteLLM_TeamTable.courier_mode: bool` defaulting to false, readable off the team object every later task consumes.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_litellm/proxy/management_endpoints/test_team_endpoints.py`:

```python
@pytest.mark.asyncio
async def test_courier_mode_round_trips_through_team_update():
    """A team's courier setting has to survive a write and read back, or an admin
    turns it on and the request path never sees it."""
    from litellm.models.team import LiteLLM_TeamTable

    team = LiteLLM_TeamTable(team_id="t-courier", team_alias="courier-team", courier_mode=True)
    assert team.courier_mode is True


def test_courier_mode_defaults_to_off():
    """Translator stays the default until every provider we sell is proven to bill
    correctly in courier mode."""
    from litellm.models.team import LiteLLM_TeamTable

    assert LiteLLM_TeamTable(team_id="t-default").courier_mode is False
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_litellm/proxy/management_endpoints/test_team_endpoints.py -k courier -v -p no:randomly`
Expected: FAIL, pydantic rejecting the unknown field `courier_mode` or returning None for it.

- [ ] **Step 3: Add the column to the schema**

In `schema.prisma`, in `model LiteLLM_TeamTable`, next to `allow_team_guardrail_config`:

```prisma
    courier_mode Boolean @default(false) // if true, this team may only use the pass-through routes, where the request body reaches the provider unread
```

- [ ] **Step 4: Write the migration**

Create `litellm-proxy-extras/litellm_proxy_extras/migrations/20260912000000_team_courier_mode/migration.sql`:

```sql
ALTER TABLE "LiteLLM_TeamTable" ADD COLUMN IF NOT EXISTS "courier_mode" BOOLEAN NOT NULL DEFAULT false;
```

Schema only. A column default applies to existing rows without rewriting them, so this stays within the migration rules and does not lock the table.

- [ ] **Step 5: Add the field to the model and the repository**

In `litellm/models/team.py`, alongside `allow_team_guardrail_config: bool | None = False`:

```python
    courier_mode: bool = False
```

In `litellm/repositories/team_repository.py`, in the same function that already does `data["allow_team_guardrail_config"] = team.allow_team_guardrail_config` (around line 308):

```python
        data["courier_mode"] = team.courier_mode
```

- [ ] **Step 6: Regenerate the Prisma client and run the tests**

Run: `.venv/Scripts/python.exe -m prisma generate --schema=schema.prisma`

This machine needs `.venv/Scripts` on PATH first, because the node CLI spawns `prisma-client-py` by bare name and otherwise fails with `spawn prisma-client-py ENOENT`.

Run: `uv run pytest tests/test_litellm/proxy/management_endpoints/test_team_endpoints.py -q -p no:randomly`
Expected: all pass.

- [ ] **Step 7: Confirm the migration gate is happy**

Run: `uv run python tests/code_coverage_tests/check_migrations_no_data_rewrites.py`
Expected: exits 0. If it complains, the migration is doing more than adding a column.

- [ ] **Step 8: Commit**

```bash
git add schema.prisma litellm-proxy-extras litellm/models/team.py litellm/repositories/team_repository.py tests/test_litellm/proxy/management_endpoints/test_team_endpoints.py
git commit -m "feat(teams): store a per-team courier mode setting"
```

---

### Task 2: Enforce it on the request path

**Files:**
- Modify: `litellm/proxy/auth/auth_checks.py` (`common_checks`)
- Test: `tests/test_litellm/proxy/auth/test_auth_checks.py`

**Interfaces:**
- Consumes: `team_object.courier_mode` from Task 1.
- Produces: a refusal on translating routes for a team in courier mode, carrying the courier address for the provider the caller named.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_litellm/proxy/auth/test_auth_checks.py`:

```python
@pytest.mark.asyncio
async def test_courier_team_is_refused_on_the_translating_route():
    """Courier mode means this team's bodies are never repackaged. The translating
    route repackages by definition, so it is closed for them, and the refusal has to
    say where to go instead or the caller is left guessing."""
    from litellm.proxy.auth.auth_checks import _courier_mode_route_check

    with pytest.raises(Exception) as exc:
        _courier_mode_route_check(courier_mode=True, route="/v1/chat/completions")

    message = str(exc.value)
    assert "courier" in message.lower()
    assert "/anthropic" in message or "pass-through" in message.lower()


@pytest.mark.asyncio
async def test_courier_team_is_allowed_on_the_pass_through_routes():
    from litellm.proxy.auth.auth_checks import _courier_mode_route_check

    _courier_mode_route_check(courier_mode=True, route="/anthropic/v1/messages")
    _courier_mode_route_check(courier_mode=True, route="/openrouter/chat/completions")


@pytest.mark.asyncio
async def test_a_normal_team_is_unaffected():
    from litellm.proxy.auth.auth_checks import _courier_mode_route_check

    _courier_mode_route_check(courier_mode=False, route="/v1/chat/completions")
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_litellm/proxy/auth/test_auth_checks.py -k courier -v -p no:randomly`
Expected: FAIL with `ImportError: cannot import name '_courier_mode_route_check'`.

- [ ] **Step 3: Write the check**

In `litellm/proxy/auth/auth_checks.py`, near the other team predicates:

```python
def _courier_mode_route_check(courier_mode: bool, route: str) -> None:
    """Close the translating routes for a team that has opted into courier mode.

    The gateway speaks for itself only about its own business: whose key this is, what
    they may spend, and which addresses they may use. It never authors an opinion about
    a request's content, so the message names the address to use and stops there.
    """
    if not courier_mode:
        return
    if any(route.startswith(prefix) for prefix in LiteLLMRoutes.mapped_pass_through_routes.value):
        return
    raise ProxyException(
        message=(
            f"This team is in courier mode, where request bodies reach the provider unread. "
            f"{route} translates the body into the provider's format, so it is closed for this "
            f"team. Send the provider's own request shape to its pass-through address instead, "
            f"for example /anthropic/v1/messages or /openrouter/chat/completions."
        ),
        type=ProxyErrorTypes.auth_error,
        param="route",
        code=status.HTTP_403_FORBIDDEN,
    )
```

Check the exact `ProxyException` constructor signature against a neighbouring raise in the same file before writing it; do not assume these argument names.

- [ ] **Step 4: Call it from common_checks**

In `common_checks`, where the team object's other policies are already applied, add:

```python
    _courier_mode_route_check(
        courier_mode=bool(getattr(team_object, "courier_mode", False)),
        route=route,
    )
```

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/test_litellm/proxy/auth/test_auth_checks.py -q -p no:randomly`
Expected: all pass.

- [ ] **Step 6: Check nothing regressed**

Run: `uv run pytest tests/test_litellm/proxy/auth/ tests/test_litellm/proxy/management_endpoints/test_team_endpoints.py -q -p no:randomly`
Expected: all pass. `common_checks` runs on every authenticated request, so a mistake here breaks the whole gateway rather than one feature.

- [ ] **Step 7: Prove it against the running proxy**

Restart the proxy, then with a key belonging to a courier-mode team:

```bash
curl -s -X POST http://localhost:4001/v1/chat/completions -H "Authorization: Bearer <team key>" \
  -H "Content-Type: application/json" -d '{"model":"openrouter/openai/gpt-4o-mini","messages":[{"role":"user","content":"hi"}]}'
```

Expected: a 403 naming courier mode and the address to use. Then the same team on the courier address must still succeed and still write a priced spend row:

```bash
curl -s -X POST http://localhost:4001/openrouter/chat/completions -H "Authorization: Bearer <team key>" \
  -H "Content-Type: application/json" \
  -d '{"model":"openai/gpt-4o-mini","max_tokens":16,"messages":[{"role":"user","content":"hi"}]}'

docker exec tokeniq_db psql -U llmproxy -d litellm -tAF'|' -c \
  "select call_type, total_tokens, round(spend::numeric,10) from \"LiteLLM_SpendLogs\" order by \"startTime\" desc limit 1;"
```

A 403 on the courier address means the route prefix check is wrong. A success with a zero-cost row means enforcement broke billing.

- [ ] **Step 8: Commit**

```bash
git add litellm/proxy/auth/auth_checks.py tests/test_litellm/proxy/auth/test_auth_checks.py
git commit -m "feat(auth): close the translating routes for a team in courier mode"
```

---

### Task 3: Report coverage honestly

The screen must not let an admin turn courier mode on and discover a billing gap from a month-end invoice. Coverage is computed from the same source the runtime uses so the two cannot drift.

**Files:**
- Create: `litellm/proxy/management_endpoints/courier_coverage.py`
- Modify: `litellm/proxy/management_endpoints/team_endpoints.py` (mount the route)
- Test: `tests/test_litellm/proxy/management_endpoints/test_courier_coverage.py`

**Interfaces:**
- Produces: `GET /team/{team_id}/courier_coverage` returning, per provider that team can reach, whether the courier route exists, whether usage is read back, and whether each deployment is opted in.

- [ ] **Step 1: Write the failing test**

Create `tests/test_litellm/proxy/management_endpoints/test_courier_coverage.py`:

```python
from __future__ import annotations

from litellm.proxy.management_endpoints.courier_coverage import provider_courier_coverage


def test_a_provider_with_a_route_and_a_usage_reader_reads_as_covered():
    coverage = provider_courier_coverage("openrouter")
    assert coverage.has_route is True
    assert coverage.reads_usage is True


def test_a_provider_with_no_courier_route_says_so():
    coverage = provider_courier_coverage("voyage")
    assert coverage.has_route is False


def test_coverage_is_derived_from_the_runtime_registries_not_a_hand_written_list():
    """A hand-maintained table drifts from the code and then lies to an admin. This
    asserts the function agrees with the registry the request path actually consults."""
    from litellm.proxy._types import LiteLLMRoutes

    for provider in ("openrouter", "anthropic", "bedrock"):
        expected = f"/{provider}" in LiteLLMRoutes.mapped_pass_through_routes.value
        assert provider_courier_coverage(provider).has_route is expected
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_litellm/proxy/management_endpoints/test_courier_coverage.py -v -p no:randomly`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the coverage module**

Create `litellm/proxy/management_endpoints/courier_coverage.py` exposing a frozen dataclass and `provider_courier_coverage(provider: str) -> ProviderCourierCoverage`.

`has_route` comes from `LiteLLMRoutes.mapped_pass_through_routes`, which is the list the request path itself gates on, so the two cannot disagree.

`reads_usage` must be derived, not hard-coded. Two mechanisms price courier traffic today and a provider is covered if either applies: a branch in `PassThroughEndpointLogging.normalize_llm_passthrough_logging_payload` keyed on provider or hostname, or a `BasePassthroughConfig` registered in `ProviderConfigManager.get_provider_passthrough_config` that overrides `logging_non_streaming_response`. Read both before implementing and derive from them. If deriving proves impossible without a hand-written map, stop and say so rather than shipping a list that will rot: an inaccurate coverage screen is worse than none, because it is believed.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_litellm/proxy/management_endpoints/test_courier_coverage.py -v -p no:randomly`
Expected: 3 passed.

- [ ] **Step 5: Add the deployment opt-in to the report**

Courier mode reads a provider credential from a deployment only when that deployment sets `use_in_pass_through: true`. This is invisible and an admin will not guess it: without it every call fails on credentials with nothing explaining why. It cost a live debugging session to find.

Extend the response with, per provider, how many of that team's deployments are opted in and how many are not, read from the router's model list via `litellm_params.get("use_in_pass_through")`. Add a test asserting a deployment without the flag is reported as not ready.

- [ ] **Step 6: Mount the route and commit**

Mount `GET /team/{team_id}/courier_coverage` in `team_endpoints.py`, admin-only, following the permission pattern of the neighbouring team routes.

```bash
git add litellm/proxy/management_endpoints tests/test_litellm/proxy/management_endpoints/test_courier_coverage.py
git commit -m "feat(teams): report courier coverage from the runtime registries"
```

---

### Model permissions are named differently in courier mode

Found while proving Task 2 live, and the admin screen has to say it.

A team's `models` allow-list is written against the proxy's deployment names, for
example `openrouter/openai/gpt-4o-mini`. On a courier route the caller names the
*provider's* model, `openai/gpt-4o-mini`, because the body is the provider's own. The
allow-list therefore stops matching the moment a team switches to courier, and every
call is refused with `team_model_access_denied` naming a model the admin believes they
granted.

This is correct behaviour, not a bug: courier mode means the provider's names, by
definition. But it is invisible, it looks like a permissions failure rather than a
naming mismatch, and it cost a debugging step to spot even knowing the feature
intimately. Task 4's panel must show, for a team being switched, which of its granted
models will no longer match, and Task 3's coverage endpoint is the natural place to
compute that.

### Task 4: The admin screen

**Files:**
- Modify: `ui/litellm-dashboard/src/components/team/` (the team settings panel)
- Create: `ui/litellm-dashboard/src/components/team/CourierModeSettings.tsx`
- Test: co-located `.test.tsx`, following the conventions of the neighbouring team components

- [ ] **Step 1: Read the neighbouring component first**

Read `ui/litellm-dashboard/src/components/team/LoggingSettings.tsx` and its test. It is the closest precedent: a team-scoped settings panel that reads current state, writes through a hook, and has co-located tests. Follow its structure rather than inventing one.

- [ ] **Step 2: Write the component test first**

The test must assert three things, because each corresponds to a way an admin gets hurt:

- the toggle reflects the team's stored setting
- turning it on shows the coverage report, and a provider whose usage is not read back is called out as billing incorrectly, not merely listed
- a provider whose deployments are not opted in shows that, with the fix named

- [ ] **Step 3: Build the component**

Wire it to `GET /team/{team_id}/courier_coverage` and to the team update endpoint. The copy must not describe courier mode as a switch that makes existing traffic pass through: it changes which addresses the team may use, and clients written against the translating route will be refused until they are changed. Say that plainly in the panel.

- [ ] **Step 4: Run the UI tests**

Run: `cd ui/litellm-dashboard && npm test -- CourierModeSettings`
Expected: all pass.

- [ ] **Step 5: Look at it**

Start the dashboard, open a team, turn courier mode on, and confirm the coverage report matches what the API returns for that team. A screen that disagrees with the API is worse than no screen.

- [ ] **Step 6: Commit**

```bash
git add ui/litellm-dashboard/src/components/team
git commit -m "feat(ui): let an admin put a team into courier mode"
```

---

### Task 5: Prove the whole thing end to end

**Files:**
- Modify: `tests/e2e/llm_translation/test_courier_passthrough_e2e.py`
- Modify: `tests/e2e/coverage_registry/llm_nonconversational.yaml`

- [ ] **Step 1: Add the coverage registry row**

```yaml
- {id: llm.passthrough.team_mode.enforced.nonstream.works, module: non_core_llms, tier: P0, behavior: passthrough, variant: team_mode, assertions: [works], exercised_on: [chat_completions], source: "proxy/auth/auth_checks.py", rationale: "A team in courier mode is refused on the translating route and served on the pass-through route, with billing intact on both sides of the switch"}
```

- [ ] **Step 2: Write the test**

Using the `resources` fixture, create a team with courier mode on and a key scoped to it. Assert the translating route returns 403 with a message naming courier mode, that the courier route succeeds, and that the spend row carries the provider's reported cost. Follow the shape of `TestOpenRouterCourier` in that file.

- [ ] **Step 3: Run it**

Run: `cd tests/e2e && LITELLM_PROXY_URL=http://localhost:4001 LITELLM_MASTER_KEY=sk-1234 uv run pytest llm_translation/test_courier_passthrough_e2e.py -v`
Expected: all pass, including the pre-existing OpenRouter cases.

- [ ] **Step 4: Commit**

```bash
git add tests/e2e
git commit -m "test(e2e): prove courier mode is enforced per team without losing billing"
```

---

## Not in this plan

**Flipping the default to courier.** Gated on Bedrock being proven against real AWS traffic. Once that lands, changing the default is a one-line change plus a migration default, and it deserves its own commit with the coverage evidence in the message.

**Verifying OpenAI, Anthropic, Azure and Vertex.** Still marked covered on the strength of reading code, which got OpenRouter wrong by three defects. Each needs a real request and a reconciled spend row before the coverage screen should report it as green.
