# Bedrock Courier Cost Reader Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Bedrock traffic sent through the courier route record the tokens and cost it actually incurred, instead of silently billing nothing.

**Architecture:** The reader already exists. `BedrockPassthroughConfig.logging_non_streaming_response` handles both invoke and converse, and `handle_logging_collected_chunks` handles streaming. It is only reachable from the SDK path, because `litellm_logging.py:1994` calls it when `call_type` is `llm_passthrough_route`. The proxy's `/bedrock/{endpoint}` route goes through `create_pass_through_route` instead, whose success handler dispatches down an elif chain that has no Bedrock branch, so the reply falls through to an untyped default that extracts nothing. This wires the existing reader into that chain.

**Tech Stack:** Python 3.12, FastAPI, pytest, the `tests/e2e` harness.

**Spec:** `docs/superpowers/specs/2026-09-11-courier-mode-design.md`

## Global Constraints

- Python max line length is 120.
- Fully typed. No `Any`, no bare `dict`. Annotate locals with `: Final` (LIT010). Never rebind or mutate parameters (LIT011) without `# rebind-ok: <reason>`.
- No mutable containers built by accumulation (LIT001/LIT002). `# mutable-ok: <reason>` is a last resort.
- Every lint or type suppression names its exact rule and carries a reason. `# type: ignore` is banned (LIT009).
- No comments except genuinely non-obvious business logic, tool-directed markers, or TODO/FIXME with a reason.
- e2e tests: never import `requests`. Mark live tests `@pytest.mark.e2e`, declare `@pytest.mark.covers(...)`, add the id to `tests/e2e/coverage_registry/`.
- Conventional commits.

## The rule this plan exists to enforce

**A passing unit suite does not mean this works.** The OpenRouter work was estimated as one small change, passed every unit test, and was three separate defects, the worst of which returned correct answers while recording zero cost. Only a real request reconciled against a real spend row found it.

So Task 3 is not optional and not a formality. Until a real Bedrock request has been sent and its spend row reconciled against the tokens Bedrock reported, this feature is **not done**, regardless of what Tasks 1 and 2 report. Bedrock must continue to be described as uncovered in the design document until Task 3 passes.

**Task 3 is currently blocked.** This machine has no AWS credentials: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` and `AWS_PROFILE` are all empty and there is no `~/.aws`. Do Tasks 1 and 2, then stop and say so rather than declaring completion.

---

### Task 1: Route Bedrock replies to the reader that already exists

**Files:**
- Modify: `litellm/proxy/pass_through_endpoints/llm_passthrough_endpoints.py` (the `create_pass_through_route` call at ~1141)
- Modify: `litellm/proxy/pass_through_endpoints/success_handler.py`
- Test: `tests/test_litellm/proxy/pass_through_endpoints/test_bedrock_passthrough_cost.py`

**Interfaces:**
- Consumes: `BedrockPassthroughConfig.logging_non_streaming_response(model, custom_llm_provider, httpx_response, request_data, logging_obj, endpoint)` from `litellm/llms/bedrock/passthrough/transformation.py:119`, which returns a `ModelResponse` carrying usage, or `None` when the endpoint is neither invoke nor converse.
- Produces: `PassThroughEndpointLogging.is_bedrock_route(custom_llm_provider: str | None) -> bool`, and a Bedrock branch in `pass_through_async_success_handler`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_litellm/proxy/pass_through_endpoints/test_bedrock_passthrough_cost.py`:

```python
from __future__ import annotations

import json

import httpx
import pytest

from litellm.proxy.pass_through_endpoints.success_handler import PassThroughEndpointLogging

CONVERSE_BODY = {
    "output": {"message": {"role": "assistant", "content": [{"text": "hello"}]}},
    "stopReason": "end_turn",
    "usage": {"inputTokens": 11, "outputTokens": 4, "totalTokens": 15},
}

INVOKE_BODY = {
    "id": "msg_bdrk_01",
    "type": "message",
    "role": "assistant",
    "content": [{"type": "text", "text": "hello"}],
    "stop_reason": "end_turn",
    "usage": {"input_tokens": 11, "output_tokens": 4},
}


def test_bedrock_is_recognised_by_the_success_handler():
    """Without this the reply falls through to the untyped default, and a Bedrock
    request that succeeded and was billed by AWS records zero tokens and zero cost."""
    handler = PassThroughEndpointLogging()
    assert handler.is_bedrock_route("bedrock") is True
    assert handler.is_bedrock_route("openai") is False
    assert handler.is_bedrock_route(None) is False


@pytest.mark.parametrize(
    "endpoint,body,expected_prompt,expected_completion",
    [
        ("model/anthropic.claude-3-5-sonnet-20241022-v2:0/converse", CONVERSE_BODY, 11, 4),
        ("model/anthropic.claude-3-5-sonnet-20241022-v2:0/invoke", INVOKE_BODY, 11, 4),
    ],
)
def test_usage_is_read_from_both_bedrock_response_shapes(
    endpoint, body, expected_prompt, expected_completion
):
    """Bedrock answers in two different shapes depending on the API used, and the
    courier route must price both."""
    from litellm.llms.bedrock.passthrough.transformation import BedrockPassthroughConfig
    from litellm.litellm_core_utils.litellm_logging import Logging

    logging_obj = Logging(
        model="anthropic.claude-3-5-sonnet-20241022-v2:0",
        messages=[],
        stream=False,
        call_type="pass_through_endpoint",
        start_time=None,
        litellm_call_id="test-bedrock-cost",
        function_id="test",
    )

    result = BedrockPassthroughConfig().logging_non_streaming_response(
        model="anthropic.claude-3-5-sonnet-20241022-v2:0",
        custom_llm_provider="bedrock",
        httpx_response=httpx.Response(200, content=json.dumps(body).encode()),
        request_data={},
        logging_obj=logging_obj,
        endpoint=endpoint,
    )

    assert result is not None, f"no usage read from the {endpoint.rsplit('/', 1)[-1]} shape"
    assert result.usage.prompt_tokens == expected_prompt
    assert result.usage.completion_tokens == expected_completion
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_litellm/proxy/pass_through_endpoints/test_bedrock_passthrough_cost.py -v -p no:randomly`

Expected: `test_bedrock_is_recognised_by_the_success_handler` FAILS with `AttributeError: 'PassThroughEndpointLogging' object has no attribute 'is_bedrock_route'`.

The two shape tests exercise the existing reader directly and should PASS already. That is the point: it proves the reader works and that the only defect is that nothing calls it on this path. If either shape test fails, stop, because the reader is broken too and this plan's architecture section is wrong.

- [ ] **Step 3: Tell the success handler which provider it is talking to**

The Bedrock route never passes `custom_llm_provider`, so the handler cannot identify it. In `litellm/proxy/pass_through_endpoints/llm_passthrough_endpoints.py`, in `bedrock_proxy_route`, add it to the existing `create_pass_through_route` call (around line 1141):

```python
    endpoint_func: Final = create_pass_through_route(
        endpoint=endpoint,
        target=str(prepped.url),
        custom_headers=prepped.headers,
        is_streaming_request=is_streaming_request,
        _forward_headers=True,
        custom_llm_provider="bedrock",
    )
```

- [ ] **Step 4: Add the predicate**

In `litellm/proxy/pass_through_endpoints/success_handler.py`, add alongside the existing `is_cohere_route` / `is_cursor_route` predicates:

```python
    def is_bedrock_route(self, custom_llm_provider: str | None = None) -> bool:
        """Bedrock is identified by provider rather than hostname: its URL is regional
        (`bedrock-runtime.<region>.amazonaws.com`) and the route signs an exact host, so
        matching on the host would need a pattern per region."""
        return custom_llm_provider == "bedrock"
```

- [ ] **Step 5: Add the branch that calls the existing reader**

In `pass_through_async_success_handler`, add a branch in the same elif chain as the Cohere and Cursor branches, before the final `else`:

```python
        elif self.is_bedrock_route(custom_llm_provider):
            from litellm.llms.bedrock.passthrough.transformation import (
                BedrockPassthroughConfig,
            )

            standard_logging_response_object = BedrockPassthroughConfig().logging_non_streaming_response(
                model=logging_obj.model_call_details.get("model", ""),
                custom_llm_provider="bedrock",
                httpx_response=httpx_response,
                request_data=request_body if isinstance(request_body, dict) else {},
                logging_obj=logging_obj,
                endpoint=url_route,
            )
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `uv run pytest tests/test_litellm/proxy/pass_through_endpoints/test_bedrock_passthrough_cost.py -v -p no:randomly`
Expected: 3 passed.

- [ ] **Step 7: Check nothing else regressed**

Run: `uv run pytest tests/test_litellm/proxy/pass_through_endpoints/ -q -p no:randomly`
Expected: all pass. The baseline before this work is 712. The new branch sits in a chain every courier provider shares, so a failure here means it was inserted in the wrong place or shadows an earlier branch.

- [ ] **Step 8: Lint and format**

Run: `uv run ruff check litellm/proxy/pass_through_endpoints/ tests/test_litellm/proxy/pass_through_endpoints/test_bedrock_passthrough_cost.py && uv run ruff format --check litellm/proxy/pass_through_endpoints/`
Expected: "All checks passed!" and "already formatted". Fix any line over 120 characters rather than suppressing.

- [ ] **Step 9: Commit**

```bash
git add litellm/proxy/pass_through_endpoints tests/test_litellm/proxy/pass_through_endpoints/test_bedrock_passthrough_cost.py
git commit -m "fix(bedrock): price courier traffic with the reader that already existed"
```

---

### Task 2: Price streamed Bedrock replies

A streamed reply never reaches `logging_non_streaming_response`. The collected chunks go to `handle_logging_collected_chunks`, which `BedrockPassthroughConfig` also already implements, decoding Bedrock's binary event stream through botocore. Without this, streaming Bedrock traffic keeps billing nothing even after Task 1.

**Files:**
- Modify: `litellm/proxy/pass_through_endpoints/streaming_handler.py`
- Test: `tests/test_litellm/proxy/pass_through_endpoints/test_bedrock_passthrough_cost.py`

**Interfaces:**
- Consumes: `BedrockPassthroughConfig.handle_logging_collected_chunks(all_chunks, litellm_logging_obj, model, custom_llm_provider, endpoint)` from `litellm/llms/bedrock/passthrough/transformation.py:176`, and `is_bedrock_route` from Task 1.

- [ ] **Step 1: Read how the streaming handler currently dispatches**

Read `litellm/proxy/pass_through_endpoints/streaming_handler.py` and find where it decides which provider assembled the chunks. Note the exact name of that dispatch and whether it already receives `custom_llm_provider`. Do not guess: the non-streaming chain and the streaming chain are separate, and they do not necessarily identify providers the same way.

- [ ] **Step 2: Write the failing test**

Append to `tests/test_litellm/proxy/pass_through_endpoints/test_bedrock_passthrough_cost.py`. Build the chunk list using the same botocore event-stream encoding Bedrock emits, by round-tripping through the config's own `_convert_raw_bytes_to_str_lines`, so the fixture cannot drift from what the decoder expects:

```python
def test_streamed_bedrock_usage_is_read_from_the_collected_chunks():
    """A streamed reply never reaches logging_non_streaming_response. Without a
    streaming path, Bedrock streaming keeps billing nothing after Task 1."""
    from litellm.litellm_core_utils.litellm_logging import Logging
    from litellm.llms.bedrock.passthrough.transformation import BedrockPassthroughConfig

    chunks = [
        json.dumps({"role": "assistant"}),
        json.dumps({"contentBlockDelta": {"delta": {"text": "hello"}}}),
        json.dumps({"metadata": {"usage": {"inputTokens": 11, "outputTokens": 4, "totalTokens": 15}}}),
    ]
    logging_obj = Logging(
        model="anthropic.claude-3-5-sonnet-20241022-v2:0",
        messages=[],
        stream=True,
        call_type="pass_through_endpoint",
        start_time=None,
        litellm_call_id="test-bedrock-stream-cost",
        function_id="test",
    )

    result = BedrockPassthroughConfig().handle_logging_collected_chunks(
        all_chunks=chunks,
        litellm_logging_obj=logging_obj,
        model="anthropic.claude-3-5-sonnet-20241022-v2:0",
        custom_llm_provider="bedrock",
        endpoint="model/anthropic.claude-3-5-sonnet-20241022-v2:0/converse-stream",
    )

    assert result is not None, "streamed Bedrock chunks produced no usage"
    assert result.usage.prompt_tokens == 11
    assert result.usage.completion_tokens == 4
```

- [ ] **Step 3: Run it and record what actually happens**

Run: `uv run pytest tests/test_litellm/proxy/pass_through_endpoints/test_bedrock_passthrough_cost.py::test_streamed_bedrock_usage_is_read_from_the_collected_chunks -v -p no:randomly`

Two outcomes, and they lead different places. If it PASSES, the reader is fine and the work is purely wiring it into the streaming handler using what you learned in Step 1. If it FAILS on the chunk shape, the fixture is wrong rather than the code: correct the fixture against what `_parse_message_from_event` actually yields, and do not change the assertion on token counts.

- [ ] **Step 4: Wire the streaming handler**

Using the dispatch you identified in Step 1, add a Bedrock branch that calls `handle_logging_collected_chunks`, matching the shape of the surrounding provider branches. Reuse `is_bedrock_route` from Task 1 rather than writing a second predicate.

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/test_litellm/proxy/pass_through_endpoints/test_bedrock_passthrough_cost.py -v -p no:randomly`
Expected: 4 passed.

- [ ] **Step 6: Check nothing regressed**

Run: `uv run pytest tests/test_litellm/proxy/pass_through_endpoints/ -q -p no:randomly`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add litellm/proxy/pass_through_endpoints tests/test_litellm/proxy/pass_through_endpoints/test_bedrock_passthrough_cost.py
git commit -m "fix(bedrock): price streamed courier traffic from its collected chunks"
```

---

### Task 3: Prove it with a real Bedrock request

**Blocked on AWS credentials.** Do not start this until `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` (or `AWS_PROFILE`) resolve. Nothing in Tasks 1 and 2 constitutes evidence that this works.

**Files:**
- Modify: `tests/e2e/llm_translation/test_courier_passthrough_e2e.py`
- Modify: `tests/e2e/coverage_registry/llm_nonconversational.yaml`
- Modify: `docs/superpowers/specs/2026-09-11-courier-mode-design.md`

- [ ] **Step 1: Add the coverage registry row**

```yaml
- {id: llm.passthrough.bedrock.basic.nonstream.cost_logged, module: non_core_llms, tier: P0, behavior: passthrough, variant: bedrock, assertions: [cost_logged], exercised_on: [chat_completions], source: "proxy/pass_through_endpoints/success_handler.py", rationale: "Courier traffic to Bedrock writes a spend row carrying the tokens Bedrock reported, rather than succeeding at zero cost"}
```

- [ ] **Step 2: Send one real request by hand first**

Before writing the test, prove it manually, because this is the step that caught three defects on OpenRouter that every unit test missed:

```bash
curl -s -X POST "http://localhost:4001/bedrock/model/anthropic.claude-3-5-sonnet-20241022-v2:0/converse" \
  -H "Authorization: Bearer sk-1234" -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":[{"text":"reply with the single word bedrock"}]}],"inferenceConfig":{"maxTokens":16}}'
```

Note the `usage` block Bedrock returns. Then read the spend row back:

```bash
docker exec tokeniq_db psql -U llmproxy -d litellm -tAF'|' -c \
  "select call_type, total_tokens, round(spend::numeric,10) from \"LiteLLM_SpendLogs\" order by \"startTime\" desc limit 1;"
```

The row must carry Bedrock's token counts and a nonzero cost. A 200 response with a zero row is the exact failure this plan exists to fix, and means Tasks 1 and 2 did not reach the live path.

- [ ] **Step 3: Write the e2e test around what you just proved**

Add a `TestBedrockCourier` class to `tests/e2e/llm_translation/test_courier_passthrough_e2e.py`, following the shape of `TestOpenRouterCourier` in that file: a typed pydantic body and response model, `unwrap(...)` on the result, then `client.proxy.poll_logs_for_key` and an assertion that a row carries the tokens Bedrock reported. Model only the response fields you assert on.

- [ ] **Step 4: Run it**

Run: `cd tests/e2e && LITELLM_PROXY_URL=http://localhost:4001 LITELLM_MASTER_KEY=sk-1234 uv run pytest llm_translation/test_courier_passthrough_e2e.py -v`
Expected: all pass, including the pre-existing OpenRouter case.

- [ ] **Step 5: Update the design document**

Change the Bedrock row's "Usage/cost read back" from **no** to yes, and remove Bedrock from the sentence naming it as the provider that gates flipping the default. Leave the "treat the remaining coverage claims as unproven" paragraph in place for the providers still unverified.

- [ ] **Step 6: Commit**

```bash
git add tests/e2e docs/superpowers/specs/2026-09-11-courier-mode-design.md
git commit -m "test(e2e): prove Bedrock courier traffic is billed from its reported usage"
```

---

## Not in this plan

**The admin control and the default flip.** Once Bedrock is proven, every provider the business sells is covered and the default can move. That is a UI and configuration subsystem and gets its own plan, which must also surface the `use_in_pass_through` opt-in, since a deployment without it fails on credentials with nothing explaining why.

**Verifying OpenAI, Anthropic, Azure and Vertex.** Still marked covered on the strength of reading code, which got OpenRouter wrong by three defects. Each needs a real request and a reconciled spend row. Anthropic is Task 1 of the provider-coverage plan and is blocked on its key.
