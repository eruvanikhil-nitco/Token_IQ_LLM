# Courier Mode: Provider Coverage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the pass-through ("courier") path work, and bill correctly, for every provider Token IQ actually sells.

**Architecture:** Pass-through already exists and already enforces keys, budgets and limits, because the routes depend on the same `user_api_key_auth`. The gap is per-provider: a provider needs a `BasePassthroughConfig` registered in `ProviderConfigManager.get_provider_passthrough_config` for the generic route factory to accept it, and a usage reader so the spend row carries real cost. OpenAI, Anthropic, Azure and Vertex have both. OpenRouter has neither. Bedrock has the route but no usage reader.

**Tech Stack:** Python 3.12, FastAPI, pytest, the `tests/e2e` harness (shared transport, typed pydantic models, `Result` unions).

**Spec:** `docs/superpowers/specs/2026-09-11-courier-mode-design.md`

## Global Constraints

- Python max line length is 120.
- Fully typed. No `Any`, no bare `dict`. Annotate locals with `: Final` (LIT010). Never rebind or mutate parameters (LIT011) without `# rebind-ok: <reason>`.
- No mutable containers built by accumulation (LIT001/LIT002); prefer comprehensions wrapped in `tuple()` / `MappingProxyType()`. `# mutable-ok: <reason>` is a last resort.
- Every lint or type suppression names its exact rule and carries a reason. `# type: ignore` is banned (LIT009).
- No comments except genuinely non-obvious business logic, tool-directed markers, or TODO/FIXME with a reason.
- e2e tests: never import `requests`; all HTTP goes through the shared transport. Mark live tests `@pytest.mark.e2e`. Declare coverage with `@pytest.mark.covers("<registry id>")` and add the id to `tests/e2e/coverage_registry/`.
- e2e hard-fails, never skips. A missing proxy turns the run red.
- Conventional commits. No Claude attribution beyond the configured trailer.

**Scope of this plan:** the four already-covered providers (verification only) and OpenRouter (new support). Bedrock's usage reader and the admin control are separate plans; this plan must leave Bedrock's behaviour unchanged.

---

### Task 1: Pin courier behaviour for the already-covered providers

Establishes the test shape every later task reuses, and proves the four providers we believe are covered actually are. Uses Anthropic because it is the provider whose native format differs most from the compatible endpoint, so a byte-identical body is a meaningful assertion.

**Files:**
- Create: `tests/e2e/llm_translation/test_courier_passthrough_e2e.py`
- Modify: `tests/e2e/coverage_registry/llm_nonconversational.yaml`

**Interfaces:**
- Consumes: the session `client` fixture from `tests/e2e/llm_translation/conftest.py`, which yields `PassthroughClient` (defined in `tests/e2e/llm_translation/passthrough_client.py:215`), and `scoped_key` from `tests/e2e/conftest.py`.
- Produces: `courier_post(client, key, provider, endpoint, body, response_type) -> Result[R]`, used by Task 4.

**Harness API this task depends on.** `transport.post` is typed:

```python
def post[R: BaseModel](self, path, *, headers: BaseModel, json: BaseModel,
                       response_type: type[R], timeout: float | None = None) -> Result[R]: ...
```

It requires a pydantic response model and returns a `Result` tagged union, so there is no raw
`.status_code` / `.json()` to read. Model only the fields each test asserts on. The variants are
`Success(status_code, data)`, `NetworkError(message)`, `UnauthorizedError`, `RateLimitedError`,
`ValidationError(message)` and `UnknownApiError(status_code, body)`. Use `unwrap(...)` when a
non-success should fail the test, and `match` when a failure is the expected outcome.

- [ ] **Step 1: Add the coverage registry rows**

Append to `tests/e2e/coverage_registry/llm_nonconversational.yaml`:

```yaml
- {id: llm.passthrough.anthropic.basic.nonstream.works, module: non_core_llms, tier: P0, behavior: passthrough, variant: anthropic, assertions: [works], exercised_on: [messages], source: "proxy/pass_through_endpoints/llm_passthrough_endpoints.py", rationale: "A native-format body reaches Anthropic through the courier route and the provider's own reply shape comes back"}
- {id: llm.passthrough.anthropic.basic.nonstream.cost_logged, module: non_core_llms, tier: P0, behavior: passthrough, variant: anthropic, assertions: [cost_logged], exercised_on: [messages], source: "proxy/pass_through_endpoints/success_handler.py", rationale: "Courier traffic writes a spend row with nonzero cost, so billing survives the mode switch"}
- {id: llm.passthrough.anthropic.bad_body.nonstream.works, module: non_core_llms, tier: P1, behavior: passthrough, variant: anthropic, assertions: [works], exercised_on: [messages], source: "proxy/pass_through_endpoints/pass_through_endpoints.py", rationale: "A malformed body is forwarded as sent and the provider's own rejection is returned verbatim, not reworded by the gateway"}
```

- [ ] **Step 2: Write the failing tests**

Create `tests/e2e/llm_translation/test_courier_passthrough_e2e.py`:

```python
"""Courier mode: the pass-through routes forward the body as sent and still bill.

The compatible endpoint translates a request into the provider's format. These routes
do not: the body reaches the provider exactly as the caller wrote it, and the provider's
reply, including its rejections, comes back unread. What must survive that is the part
that is the gateway's own business, which is the key check, the budget, and the spend row.
"""

from __future__ import annotations

from typing import Final

import pytest
from e2e_http import Result, Success, UnknownApiError, unwrap
from passthrough_client import PassthroughClient
from pydantic import BaseModel
from spend_e2e_client import unique_marker

pytestmark = pytest.mark.e2e

ANTHROPIC_MODEL: Final = "claude-haiku-4-5"
MAX_TOKENS: Final = 16


class AnthropicNativeBody(BaseModel):
    """Anthropic's own request shape, not the OpenAI-compatible one."""

    model: str
    max_tokens: int
    messages: list[dict[str, str]]


class AnthropicUsage(BaseModel):
    input_tokens: int
    output_tokens: int


class AnthropicNativeResponse(BaseModel):
    """Only the fields that prove this is Anthropic's shape rather than a translated one."""

    type: str
    role: str
    usage: AnthropicUsage


def courier_post[R: BaseModel](
    client: PassthroughClient,
    key: str,
    provider: str,
    endpoint: str,
    body: BaseModel,
    response_type: type[R],
) -> Result[R]:
    return client.proxy.transport.post(
        f"/{provider}/{endpoint}",
        headers=client.proxy.transport.bearer(key),
        json=body,
        response_type=response_type,
    )


class TestCourierPassthrough:
    @pytest.mark.covers("llm.passthrough.anthropic.basic.nonstream.works")
    def test_native_body_reaches_the_provider_and_its_shape_comes_back(
        self, client: PassthroughClient, scoped_key: str
    ) -> None:
        marker: Final = unique_marker()
        body: Final = AnthropicNativeBody(
            model=ANTHROPIC_MODEL,
            max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": f"reply with the single word {marker}"}],
        )

        reply: Final = unwrap(
            courier_post(client, scoped_key, "anthropic", "v1/messages", body, AnthropicNativeResponse)
        )

        assert reply.type == "message", (
            f"the reply must be Anthropic's own shape, not the OpenAI-compatible one; type was {reply.type!r}"
        )
        assert reply.role == "assistant"
        assert reply.usage.input_tokens > 0

    @pytest.mark.covers("llm.passthrough.anthropic.basic.nonstream.cost_logged")
    def test_courier_traffic_still_writes_a_priced_spend_row(
        self, client: PassthroughClient, scoped_key: str
    ) -> None:
        marker: Final = unique_marker()
        body: Final = AnthropicNativeBody(
            model=ANTHROPIC_MODEL,
            max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": f"reply with the single word {marker}"}],
        )
        unwrap(courier_post(client, scoped_key, "anthropic", "v1/messages", body, AnthropicNativeResponse))

        rows: Final = client.proxy.poll_logs_for_key(scoped_key, min_rows=1)

        assert rows, "courier traffic must write a spend row, or billing silently stops in courier mode"
        assert any((row.spend or 0.0) > 0 for row in rows), (
            f"every courier spend row priced at zero: {[(r.model, r.spend) for r in rows]}"
        )

    @pytest.mark.covers("llm.passthrough.anthropic.bad_body.nonstream.works")
    def test_a_malformed_body_returns_the_providers_own_rejection(
        self, client: PassthroughClient, scoped_key: str
    ) -> None:
        class NoMaxTokensBody(BaseModel):
            model: str
            messages: list[dict[str, str]]

        body: Final = NoMaxTokensBody(
            model=ANTHROPIC_MODEL,
            messages=[{"role": "user", "content": "hi"}],
        )

        result: Final = courier_post(
            client, scoped_key, "anthropic", "v1/messages", body, AnthropicNativeResponse
        )

        match result:
            case Success():
                pytest.fail("Anthropic requires max_tokens; the call should not have succeeded")
            case UnknownApiError(status_code=status, body=raw):
                assert status == 400, f"expected Anthropic's own 400, got {status}: {raw[:400]}"
                assert '"type"' in raw and "error" in raw, (
                    "the gateway must return the provider's rejection verbatim rather than authoring "
                    f"its own; got {raw[:400]}"
                )
            case other:
                pytest.fail(f"expected the provider's 400 to surface as UnknownApiError, got {other}")
```

- [ ] **Step 3: Confirm `claude-haiku-4-5` is a registered deployment**

Run: `curl -s -H "Authorization: Bearer sk-1234" http://localhost:4001/v1/models | grep -o 'claude-haiku-4-5'`

Expected: a match. The courier route addresses the provider directly rather than a proxy model name, so what actually matters is that `ANTHROPIC_API_KEY` resolves on the proxy. If it is empty in `.env`, restore it before continuing. The harness hard-fails on a missing key rather than skipping, and that is intended.

- [ ] **Step 4: Run the tests to see them fail for the right reason**

Run: `cd tests/e2e && LITELLM_PROXY_URL=http://localhost:4001 LITELLM_MASTER_KEY=sk-1234 uv run pytest llm_translation/test_courier_passthrough_e2e.py -v`

Expected: the three tests run and fail on their assertions, not on imports. `PassthroughClient` and the `client` fixture already exist in this suite, so the imports resolve. A failure naming `AnthropicNativeResponse` validation means the reply did not carry `type`/`role`/`usage`, which is itself the finding: either the route is translating, or it never reached Anthropic.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd tests/e2e && LITELLM_PROXY_URL=http://localhost:4001 LITELLM_MASTER_KEY=sk-1234 uv run pytest llm_translation/test_courier_passthrough_e2e.py -v`

Expected: 3 passed. If `test_courier_traffic_still_writes_a_priced_spend_row` fails with rows present but zero spend, stop: that is the Bedrock-class bug appearing on Anthropic and it invalidates the design's coverage table. Report it rather than weakening the assertion.

- [ ] **Step 6: Verify the coverage registry accepts the new ids**

Run: `cd tests/e2e && uv run python -m coverage_registry.collector --strict`

Expected: exits 0 with no "unknown marker id" lines.

- [ ] **Step 7: Commit**

```bash
git add tests/e2e/llm_translation/test_courier_passthrough_e2e.py tests/e2e/coverage_registry/llm_nonconversational.yaml
git commit -m "test(e2e): pin courier pass-through behaviour for anthropic"
```

---

### Task 2: Give OpenRouter a pass-through config

The generic route factory calls `ProviderConfigManager.get_provider_passthrough_config` and needs a non-None `get_api_base()`. OpenRouter has no entry, which is the whole reason it has no courier route. OpenRouter speaks OpenAI's wire format, so this config is far smaller than GigaChat's: response reading delegates to the existing `OpenrouterConfig`.

**Files:**
- Create: `litellm/llms/openrouter/passthrough/__init__.py`
- Create: `litellm/llms/openrouter/passthrough/transformation.py`
- Modify: `litellm/utils.py` (the `get_provider_passthrough_config` elif chain)
- Test: `tests/test_litellm/llms/openrouter/passthrough/test_transformation.py`

**Interfaces:**
- Consumes: `BasePassthroughConfig` from `litellm.llms.base_llm.passthrough.transformation`.
- Produces: `OpenRouterPassthroughConfig`, with `get_api_base(api_base: str | None = None) -> str | None` and `get_complete_url(...) -> tuple[httpx.URL, str]`. Task 3 registers it; Task 4 exercises it.

- [ ] **Step 1: Write the failing test**

Create `tests/test_litellm/llms/openrouter/passthrough/test_transformation.py`:

```python
from __future__ import annotations

import httpx
import pytest

from litellm.llms.openrouter.passthrough.transformation import OpenRouterPassthroughConfig

DEFAULT_BASE = "https://openrouter.ai/api/v1"


def test_api_base_defaults_to_openrouter():
    """The generic pass-through factory 404s a provider whose api base is None,
    which is the only reason OpenRouter had no courier route."""
    assert OpenRouterPassthroughConfig.get_api_base() == DEFAULT_BASE


def test_explicit_api_base_wins():
    assert OpenRouterPassthroughConfig.get_api_base("https://proxy.internal/v1") == "https://proxy.internal/v1"


def test_env_api_base_overrides_the_default(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_BASE", "https://env.example/v1")
    assert OpenRouterPassthroughConfig.get_api_base() == "https://env.example/v1"


def test_complete_url_joins_the_endpoint_without_doubling_slashes():
    url, base = OpenRouterPassthroughConfig().get_complete_url(
        api_base=None,
        api_key="sk-or-test",
        model="openai/gpt-4o-mini",
        endpoint="/chat/completions",
        request_query_params=None,
        litellm_params={},
    )
    assert base == DEFAULT_BASE
    assert url == httpx.URL(f"{DEFAULT_BASE}/chat/completions")


@pytest.mark.parametrize(
    "request_data,expected",
    [({"stream": True}, True), ({"stream": False}, False), ({}, False)],
)
def test_streaming_is_read_from_the_body(request_data, expected):
    assert OpenRouterPassthroughConfig().is_streaming_request("/chat/completions", request_data) is expected
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_litellm/llms/openrouter/passthrough/test_transformation.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'litellm.llms.openrouter.passthrough'`

- [ ] **Step 3: Write the implementation**

Create `litellm/llms/openrouter/passthrough/__init__.py` as an empty file.

Create `litellm/llms/openrouter/passthrough/transformation.py`:

```python
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Final

import httpx

from litellm.llms.base_llm.passthrough.transformation import BasePassthroughConfig
from litellm.secret_managers.main import get_secret_str
from litellm.types.llms.openai import AllMessageValues

if TYPE_CHECKING:
    from httpx import URL, Response

    from litellm.litellm_core_utils.litellm_logging import Logging as LiteLLMLoggingObj
    from litellm.types.utils import CostResponseTypes

OPENROUTER_API_BASE: Final = "https://openrouter.ai/api/v1"


class OpenRouterPassthroughConfig(BasePassthroughConfig):
    """Courier support for OpenRouter.

    OpenRouter speaks OpenAI's wire format, so reading a response back is the existing
    chat config's job rather than a second parser written here. OpenRouter also prices
    its own requests and reports the figure in `usage.cost`, which the shared cost path
    treats as authoritative, so the gateway records what OpenRouter billed instead of
    re-deriving it from the price map.
    """

    def is_streaming_request(self, endpoint: str, request_data: Mapping[str, object]) -> bool:
        return bool(request_data.get("stream", False))

    def get_complete_url(
        self,
        api_base: str | None,
        api_key: str | None,
        model: str,
        endpoint: str,
        request_query_params: Mapping[str, object] | None,
        litellm_params: Mapping[str, object],
    ) -> tuple[URL, str]:
        base_target_url: Final = self.get_api_base(api_base)
        if base_target_url is None:
            raise ValueError("OpenRouter api base not found")
        return httpx.URL(f"{base_target_url}/{endpoint.lstrip('/')}"), base_target_url

    def validate_environment(
        self,
        headers: dict,  # mutable-ok: base class contract mutates in place for httpx
        model: str,
        messages: Sequence[AllMessageValues],
        optional_params: Mapping[str, object],
        litellm_params: Mapping[str, object],
        api_key: str | None = None,
        api_base: str | None = None,
    ) -> dict:  # mutable-ok: base class contract returns dict for httpx
        resolved_key: Final = self.get_api_key(api_key)
        if resolved_key is None:
            raise ValueError("OpenRouter api key not found")
        headers["Authorization"] = f"Bearer {resolved_key}"  # rebind-ok: base class mutates headers in place
        headers["Content-Type"] = "application/json"  # rebind-ok: base class mutates headers in place
        return headers

    def logging_non_streaming_response(
        self,
        model: str,
        custom_llm_provider: str,
        httpx_response: Response,
        request_data: Mapping[str, object],
        logging_obj: LiteLLMLoggingObj,
        endpoint: str,
    ) -> CostResponseTypes | None:
        from litellm import encoding
        from litellm.types.utils import LlmProviders, ModelResponse
        from litellm.utils import ProviderConfigManager

        if "completions" not in endpoint:
            return None

        chat_config: Final = ProviderConfigManager.get_provider_chat_config(
            provider=LlmProviders(custom_llm_provider),
            model=model,
        )
        if chat_config is None:
            raise ValueError(f"No OpenRouter chat config found for model: {model}")

        raw_messages: Final = request_data.get("messages")
        return chat_config.transform_response(
            model=model,
            messages=list(raw_messages) if isinstance(raw_messages, list) else [],  # mutable-ok: callee wants a list
            raw_response=httpx_response,
            model_response=ModelResponse(),
            logging_obj=logging_obj,
            optional_params={},  # mutable-ok: empty kwarg required by transform_response
            litellm_params={},  # mutable-ok: empty kwarg required by transform_response
            api_key="",
            request_data=dict(request_data),  # mutable-ok: callee wants a dict
            encoding=encoding,
        )

    @staticmethod
    def get_api_base(api_base: str | None = None) -> str | None:
        return api_base or get_secret_str("OPENROUTER_API_BASE") or OPENROUTER_API_BASE

    @staticmethod
    def get_api_key(api_key: str | None = None) -> str | None:
        return api_key or get_secret_str("OPENROUTER_API_KEY")

    @staticmethod
    def get_base_model(model: str) -> str | None:
        return model
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_litellm/llms/openrouter/passthrough/test_transformation.py -v`
Expected: 5 passed. If `test_complete_url_joins_the_endpoint_without_doubling_slashes` fails on a doubled slash, the bug is in `get_complete_url`, not the test.

- [ ] **Step 5: Check lint and formatting**

Run: `uv run ruff check litellm/llms/openrouter/passthrough/ tests/test_litellm/llms/openrouter/passthrough/ && uv run ruff format --check litellm/llms/openrouter/passthrough/`
Expected: "All checks passed!" and "already formatted". Fix any line over 120 characters rather than adding a suppression.

- [ ] **Step 6: Commit**

```bash
git add litellm/llms/openrouter/passthrough tests/test_litellm/llms/openrouter/passthrough
git commit -m "feat(openrouter): add a pass-through config so courier mode can reach it"
```

---

### Task 3: Register OpenRouter and expose its courier route

**Files:**
- Modify: `litellm/utils.py` (`ProviderConfigManager.get_provider_passthrough_config`)
- Modify: `litellm/proxy/pass_through_endpoints/llm_passthrough_endpoints.py`
- Test: `tests/test_litellm/proxy/pass_through_endpoints/test_openrouter_passthrough_route.py`

**Interfaces:**
- Consumes: `OpenRouterPassthroughConfig` from Task 2.
- Produces: the route `/openrouter/{endpoint}` and a registry entry resolving `LlmProviders.OPENROUTER`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_litellm/proxy/pass_through_endpoints/test_openrouter_passthrough_route.py`:

```python
from __future__ import annotations

from litellm.llms.openrouter.passthrough.transformation import OpenRouterPassthroughConfig
from litellm.types.utils import LlmProviders
from litellm.utils import ProviderConfigManager


def test_openrouter_resolves_to_its_passthrough_config():
    """The generic factory looks the provider up here; without an entry it 404s."""
    config = ProviderConfigManager.get_provider_passthrough_config(
        provider=LlmProviders.OPENROUTER,
        model="openai/gpt-4o-mini",
    )
    assert isinstance(config, OpenRouterPassthroughConfig)


def test_openrouter_reports_an_api_base_to_the_factory():
    """`llm_passthrough_factory_proxy_route` raises a 404 when this is None."""
    config = ProviderConfigManager.get_provider_passthrough_config(
        provider=LlmProviders.OPENROUTER,
        model="openai/gpt-4o-mini",
    )
    assert config is not None
    assert config.get_api_base() == "https://openrouter.ai/api/v1"


def test_the_courier_route_is_mounted():
    from litellm.proxy.proxy_server import app

    paths = {route.path for route in app.routes if hasattr(route, "path")}
    assert "/openrouter/{endpoint}" in paths
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_litellm/proxy/pass_through_endpoints/test_openrouter_passthrough_route.py -v`
Expected: the first two FAIL (config resolves to something that is not `OpenRouterPassthroughConfig`, or `get_api_base()` returns None), and the third FAILs on the missing path.

- [ ] **Step 3: Register the config**

In `litellm/utils.py`, inside `ProviderConfigManager.get_provider_passthrough_config`, add a branch alongside the existing ones (`BedrockPassthroughConfig`, `AzurePassthroughConfig`, `VLLMPassthroughConfig`, `GigaChatPassthroughConfig`, `WatsonxPassthroughConfig`). Match the surrounding style, which imports inside the branch:

```python
        elif LlmProviders.OPENROUTER == provider:
            from litellm.llms.openrouter.passthrough.transformation import (
                OpenRouterPassthroughConfig,
            )

            return OpenRouterPassthroughConfig()
```

- [ ] **Step 4: Add the route**

In `litellm/proxy/pass_through_endpoints/llm_passthrough_endpoints.py`, add a route next to the existing provider routes, delegating to the shared factory exactly as the vllm route at line ~433 does:

```python
@router.api_route(
    "/openrouter/{endpoint:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    tags=["OpenRouter Pass-through", "pass-through"],
)
async def openrouter_proxy_route(
    endpoint: str,
    request: Request,
    fastapi_response: Response,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    """Forward a request to OpenRouter with its body untouched.

    The key check, budgets and limits still run through `user_api_key_auth`; only the
    payload is left alone.
    """
    return await llm_passthrough_factory_proxy_route(
        endpoint=endpoint,
        request=request,
        fastapi_response=fastapi_response,
        user_api_key_dict=user_api_key_dict,
        custom_llm_provider="openrouter",
    )
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `uv run pytest tests/test_litellm/proxy/pass_through_endpoints/test_openrouter_passthrough_route.py -v`
Expected: 3 passed.

- [ ] **Step 6: Check nothing else regressed**

Run: `uv run pytest tests/test_litellm/proxy/pass_through_endpoints/ -q -p no:randomly`
Expected: all pass. The new elif sits in a chain other providers share, so a failure here means the branch was inserted in the wrong place.

- [ ] **Step 7: Commit**

```bash
git add litellm/utils.py litellm/proxy/pass_through_endpoints/llm_passthrough_endpoints.py tests/test_litellm/proxy/pass_through_endpoints/test_openrouter_passthrough_route.py
git commit -m "feat(proxy): expose an OpenRouter pass-through route"
```

---

### Task 4: Prove OpenRouter courier traffic is billed from OpenRouter's own figure

The design's claim is that OpenRouter prices its own requests and the gateway records that figure rather than re-deriving it. Three rows in the live database already match exactly on the compatible endpoint. This proves it on the courier route, which is the one that had no support.

**Files:**
- Modify: `tests/e2e/llm_translation/test_courier_passthrough_e2e.py`
- Modify: `tests/e2e/coverage_registry/llm_nonconversational.yaml`

**Interfaces:**
- Consumes: `courier_post` from Task 1, the route from Task 3.

- [ ] **Step 1: Add the coverage registry row**

Append to `tests/e2e/coverage_registry/llm_nonconversational.yaml`:

```yaml
- {id: llm.passthrough.openrouter.basic.nonstream.cost_logged, module: non_core_llms, tier: P0, behavior: passthrough, variant: openrouter, assertions: [cost_logged], exercised_on: [chat_completions], source: "llms/openrouter/passthrough/transformation.py", rationale: "Courier traffic to OpenRouter is billed at the figure OpenRouter itself reports, not re-derived from the price map"}
```

- [ ] **Step 2: Write the failing test**

Append to `tests/e2e/llm_translation/test_courier_passthrough_e2e.py`:

```python
OPENROUTER_MODEL: Final = "openai/gpt-4o-mini"
COST_TOLERANCE: Final = 1e-9


class OpenRouterNativeBody(BaseModel):
    model: str
    max_tokens: int
    messages: list[dict[str, str]]


class OpenRouterUsage(BaseModel):
    total_tokens: int
    cost: float | None = None


class OpenRouterResponse(BaseModel):
    id: str
    usage: OpenRouterUsage


class TestOpenRouterCourier:
    @pytest.mark.covers("llm.passthrough.openrouter.basic.nonstream.cost_logged")
    def test_spend_row_matches_the_cost_openrouter_reported(
        self, client: PassthroughClient, scoped_key: str
    ) -> None:
        marker: Final = unique_marker()
        body: Final = OpenRouterNativeBody(
            model=OPENROUTER_MODEL,
            max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": f"reply with the single word {marker}"}],
        )

        reply: Final = unwrap(
            courier_post(client, scoped_key, "openrouter", "chat/completions", body, OpenRouterResponse)
        )
        reported: Final = reply.usage.cost
        assert reported is not None, "OpenRouter should report its own cost in usage.cost"

        rows: Final = client.proxy.poll_logs_for_key(scoped_key, min_rows=1)
        assert rows, "courier traffic to OpenRouter wrote no spend row"
        assert any(abs((row.spend or 0.0) - reported) < COST_TOLERANCE for row in rows), (
            f"no spend row matches OpenRouter's reported cost {reported}; "
            f"rows were {[(r.model, r.spend) for r in rows]}"
        )
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `cd tests/e2e && LITELLM_PROXY_URL=http://localhost:4001 LITELLM_MASTER_KEY=sk-1234 uv run pytest llm_translation/test_courier_passthrough_e2e.py::TestOpenRouterCourier -v`

Expected before restarting the proxy: FAIL with 404, because the running proxy predates Task 3. Restart the proxy, then expect either PASS or a failure on the spend assertion.

- [ ] **Step 4: If the spend assertion fails, wire the cost source**

A 200 with a spend row that does not match `usage.cost` means the shared cost path did not treat OpenRouter as an upstream that prices itself. Read `_set_cost_per_request` in `litellm/proxy/pass_through_endpoints/success_handler.py`, whose docstring states an upstream that prices its own requests wins, and make the OpenRouter courier path reach it. Do not "fix" this by relaxing the assertion to a tolerance band; the whole claim is that the figure is OpenRouter's own.

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd tests/e2e && LITELLM_PROXY_URL=http://localhost:4001 LITELLM_MASTER_KEY=sk-1234 uv run pytest llm_translation/test_courier_passthrough_e2e.py -v`
Expected: 4 passed.

- [ ] **Step 6: Verify the registry**

Run: `cd tests/e2e && uv run python -m coverage_registry.collector --strict`
Expected: exits 0, no unknown ids.

- [ ] **Step 7: Commit**

```bash
git add tests/e2e/llm_translation/test_courier_passthrough_e2e.py tests/e2e/coverage_registry/llm_nonconversational.yaml
git commit -m "test(e2e): pin OpenRouter courier billing to OpenRouter's reported cost"
```

---

### Task 5: Record the coverage the code now has

The admin screen in the next plan must generate its coverage claims from the same source the runtime uses, so they cannot drift. This task writes that source down.

**Files:**
- Modify: `docs/superpowers/specs/2026-09-11-courier-mode-design.md`

- [ ] **Step 1: Update the coverage table**

Change the OpenRouter row's "Courier route" to yes and "Work needed" to none, and note beneath the table that Bedrock remains the sole uncovered provider and still gates the default flip.

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/specs/2026-09-11-courier-mode-design.md
git commit -m "docs: mark OpenRouter courier support as landed"
```

---

## Not in this plan

**Bedrock's usage reader.** Bedrock carries courier traffic today and records no computed cost. It needs a handler in the `success_handler` chain covering both invoke and converse response shapes. Until it lands, Bedrock must be reported as not fully covered, and courier must not become the default.

**The admin control and the default flip.** Team-level mode selection, the coverage display, and making courier the default. That is a UI and configuration subsystem and gets its own plan once Bedrock is done.
