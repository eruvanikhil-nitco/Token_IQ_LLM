# Feature usage inventory

Phase 0 item 3 of `docs/plans/2026-10-04-independent-codebase.md`. One row per top-level folder in
`litellm/` and `litellm/proxy/`, plus the loose Python files at those two levels, which a
folder-only inventory would have missed.

**This table drives phase 5, and phase 5 does not start until the owner has approved it.**

## What this can and cannot tell you

The reachability column is evidence. A module reached from an entry point is definitely loaded, and
nothing in that column is a guess.

`unproven` is not evidence of anything. Python loads modules by string, by `getattr`, by config and
by plugin registry, and a parser sees none of it. **Reachability proves keep. It never proves
delete.** So no row below is proposed for deletion because nothing reached it; every `delete` is
either named by section 9 of the plan or was read and decided.

Two false negatives were found and fixed while producing this table:

- `litellm/_lazy_imports_registry.py` holds 269 module paths as plain strings, handed to
  `import_module` by a different file. Reading only the call site left 162 live modules looking dead
- `litellm.proxy.client.cli` is a declared console script. Leaving it out of the entry points made
  7,356 lines of CLI look dead

There are 13 dynamic imports the analyser still cannot follow, listed in
`2026-10-04-phase-0-reachability.json`. That is the remaining hole. It is small enough that the
table is usable, and it is not zero.

## Where each proposal comes from

| Source | Rows | Meaning |
|---|---:|---|
| `read` | 26 | The file was opened and read, and the verdict is a person's |
| `rule` | 117 | Section 9 of the plan names the feature, or it is reachable and section 9 names neither |

A row section 9 names is decided by section 9, and the reason quotes the phrase. A row it names
neither way is `keep` when something reaches it, because deleting code in use needs a reason the
plan does not give. No row is `delete` on reachability alone.

## Summary

| Proposal | Rows | Files | Lines |
|---|---:|---:|---:|
| **delete** | 49 | 345 | 112,192 |
| **unsure** | 0 | 0 | 0 |
| **keep** | 94 | 2,601 | 941,255 |
| total | 143 | 2,946 | 1,053,447 |

Section 9 also sets three rules that bound what the `delete` rows above actually mean:

- **one feature per commit**, each followed by an import check and the remaining tests
- **if something still imports a deleted module, keep the feature and record why.** Several
  `delete` rows below are reachable today, so the importers come out first or the row becomes a keep
- **never delete a Prisma model or migration in this phase.** Unused tables are phase 8

## Every row, with its proposal

| Path | Files | Lines | Reachability | Proposal | Why | What it is |
|---|---:|---:|---|---|---|---|
| `litellm/proxy/guardrails/` | 131 | 50194 | 25/131 used | **delete** | Section 9 names "guardrails and the policy engine (unless used)". 25 of 131 modules are reached, so phase 5 must unpick the importers first | The guardrail engine and its per-vendor integrations |
| `litellm/router_strategy/` | 26 | 10095 | 21/26 used | **delete** | Section 9 names "routing, switched off by decision 0001". 21 of 26 modules are reached, so phase 5 must unpick the importers first | Complexity-based Auto Router A rule-based routing strategy that uses weighted scoring across multipl |
| `litellm/router_utils/` | 25 | 6448 | 23/25 used | **delete** | Section 9 names "routing helpers, switched off by decision 0001". 23 of 25 modules are reached, so phase 5 must unpick the importers first | Helpers for the routing layer |
| `litellm/a2a_protocol/` | 29 | 4785 | 1/29 used | **delete** | Section 9 names "agents and A2A". 1 of 29 modules are reached, so phase 5 must unpick the importers first | LiteLLM A2A - Wrapper for invoking A2A protocol agents. This module provides a thin wrapper around t |
| `litellm/proxy/policy_engine/` | 11 | 4555 | 8/11 used | **delete** | Section 9 names "guardrails and the policy engine (unless used)". 8 of 11 modules are reached, so phase 5 must unpick the importers first | LiteLLM Policy Engine The Policy Engine allows administrators to define policies that combine guardr |
| `litellm/proxy/agent_endpoints/` | 10 | 4061 | 5/10 used | **delete** | Section 9 names "agents and A2A". 5 of 10 modules are reached, so phase 5 must unpick the importers first | Agent endpoints for registering + discovering agents via LiteLLM. Follows the A2A Spec. 1. Register |
| `litellm/rag/` | 15 | 3585 | **unproven** | **delete** | RAG document ingestion. Out of scope for an observer-only gateway | LiteLLM RAG (Retrieval Augmented Generation) Module. Provides an all-in-one API for document ingesti |
| `litellm/evals/` | 2 | 1974 | 1/2 used | **delete** | Section 9 names "skills, prompts management and evals". 1 of 2 modules are reached, so phase 5 must unpick the importers first | Evals API operations |
| `litellm/proxy/vector_store_endpoints/` | 3 | 1816 | used | **delete** | Section 9 names "RAG and vector stores". 1 of 1 modules are reached, so phase 5 must unpick the importers first | VECTOR STORE MANAGEMENT All /vector_store management endpoints /vector_store/new /vector_store/delet |
| `litellm/videos/` | 3 | 1752 | 1/3 used | **delete** | Section 9 names "realtime, video, image, OCR, search and rerank APIs". 1 of 3 modules are reached, so phase 5 must unpick the importers first | Video generation and management functions for LiteLLM. |
| `litellm/vector_stores/` | 4 | 1645 | used | **delete** | Section 9 names "RAG and vector stores". 1 of 1 modules are reached, so phase 5 must unpick the importers first | LiteLLM SDK Functions for Creating and Searching Vector Stores |
| `litellm/assistants/` | 2 | 1499 | **unproven** | **delete** | Assistants API. Not a cost surface Token IQ reads | OpenAI Assistants API passthrough: threads, messages and runs |
| `litellm/rust_bridge/` | 11 | 1403 | 9/11 used | **delete** | Section 9 names "the Rust bridge, optional via native_bridge_available()". 9 of 11 modules are reached, so phase 5 must unpick the importers first | LiteLLM Rust bridge package. |
| `litellm/proxy/search_endpoints/` | 4 | 1295 | 2/4 used | **delete** | Section 9 names "realtime, video, image, OCR, search and rerank APIs". 2 of 4 modules are reached, so phase 5 must unpick the importers first | CRUD ENDPOINTS FOR SEARCH TOOLS |
| `litellm/images/` | 3 | 1202 | 1/3 used | **delete** | Section 9 names "realtime, video, image, OCR, search and rerank APIs". 1 of 3 modules are reached, so phase 5 must unpick the importers first | Image generation and edit APIs |
| `litellm/experimental_mcp_client/` | 3 | 1166 | 2/3 used | **delete** | Section 9 names "MCP". 2 of 3 modules are reached, so phase 5 must unpick the importers first | LiteLLM Proxy uses this MCP Client to connnect to other MCP servers. |
| `litellm/proxy/vector_store_files_endpoints/` | 2 | 1113 | **unproven** | **delete** | Vector stores. Named for deletion in the spec | File endpoints for the vector store feature |
| `litellm/proxy/rag_endpoints/` | 3 | 1098 | 2/3 used | **delete** | Section 9 names "RAG and vector stores". 2 of 3 modules are reached, so phase 5 must unpick the importers first | RAG Endpoints for LiteLLM Proxy. |
| `litellm/proxy/openai_evals_endpoints/` | 2 | 1039 | **unproven** | **delete** | Evals API. Named for deletion in the spec | OpenAI Evals API endpoints |
| `litellm/proxy/video_endpoints/` | 3 | 978 | 2/3 used | **delete** | Section 9 names "realtime, video, image, OCR, search and rerank APIs". 2 of 3 modules are reached, so phase 5 must unpick the importers first | Video endpoints module. |
| `litellm/proxy/a2a/` | 5 | 960 | **unproven** | **delete** | Agent-to-agent protocol. Named for deletion in the spec | A2A registration helpers for the LiteLLM proxy. - ``discovery``: fetches the upstream agent's well-k |
| `litellm/compression/` | 8 | 899 | 7/8 used | **delete** | Section 9 names "fine-tuning, sandbox, compression". 7 of 8 modules are reached, so phase 5 must unpick the importers first | Main compress() function — normalizes input messages, orchestrates BM25/embedding scoring, message s |
| `litellm/vector_store_files/` | 3 | 813 | 2/3 used | **delete** | Section 9 names "RAG and vector stores". 2 of 3 modules are reached, so phase 5 must unpick the importers first | LiteLLM SDK functions for managing vector store files. |
| `litellm/skills/` | 2 | 791 | **unproven** | **delete** | Skills API. Named for deletion in the spec | Skills API integration for LiteLLM |
| `litellm/fine_tuning/` | 1 | 778 | **unproven** | **delete** | Fine-tuning API. Named for deletion in the spec | Main File for Fine Tuning API implementation https://platform.openai.com/docs/api-reference/fine-tun |
| `litellm/ocr/` | 2 | 743 | used | **delete** | Section 9 names "realtime, video, image, OCR, search and rerank APIs". 1 of 1 modules are reached, so phase 5 must unpick the importers first | OCR module for LiteLLM. |
| `litellm/realtime_api/` | 1 | 693 | used | **delete** | Section 9 names "realtime, video, image, OCR, search and rerank APIs". 1 of 1 modules are reached, so phase 5 must unpick the importers first | Abstraction function for OpenAI's realtime API |
| `litellm/proxy/realtime_endpoints/` | 2 | 650 | **unproven** | **delete** | Realtime API. Named for deletion in the spec | The realtime websocket API passthrough |
| `litellm/proxy/fine_tuning_endpoints/` | 1 | 638 | used | **delete** | Section 9 names "fine-tuning, sandbox, compression". 1 of 1 modules are reached, so phase 5 must unpick the importers first | Fine-tuning API passthrough endpoints |
| `litellm/rerank_api/` | 2 | 616 | **unproven** | **delete** | Rerank API. Named for deletion in the spec | The /rerank endpoint and its provider dispatch |
| `litellm/search/` | 3 | 413 | used | **delete** | Section 9 names "realtime, video, image, OCR, search and rerank APIs". 1 of 1 modules are reached, so phase 5 must unpick the importers first | LiteLLM Search API module. |
| `litellm/proxy/ocr_endpoints/` | 2 | 351 | 1/2 used | **delete** | Section 9 names "realtime, video, image, OCR, search and rerank APIs". 1 of 2 modules are reached, so phase 5 must unpick the importers first | OCR API passthrough endpoints |
| `litellm/proxy/image_endpoints/` | 2 | 340 | 1/2 used | **delete** | Section 9 names "realtime, video, image, OCR, search and rerank APIs". 1 of 2 modules are reached, so phase 5 must unpick the importers first | Image API passthrough endpoints |
| `litellm/proxy_auth/` | 2 | 269 | **unproven** | **delete** | A client-side SDK helper for authenticating *to* a proxy, which an observer-only gateway does not offer. Nothing in the product imports the package, only its own test. The `litellm.proxy_auth` reads in `main.py` are a same-named module-level setting declared at `__init__.py:345`, which shadows this package and is a separate thing | Proxy Authentication module for LiteLLM SDK. This module provides OAuth2/JWT token management for au |
| `litellm/batch_completion/` | 1 | 256 | **unproven** | **delete** | A routing convenience; routing is already switched off by decision 0001 | Helper that fans one prompt out over a model list and returns the best |
| `litellm/proxy/caching_routes.py` | 1 | 249 | used | **delete** | Section 9 names "response caching, removed by decision 0005". 1 of 1 modules are reached, so phase 5 must unpick the importers first | Endpoints to inspect and flush the response cache |
| `litellm/proxy/compliance_checks.py` | 1 | 243 | **unproven** | **delete** | EU AI Act and GDPR validation built on guardrail modes, reached only from `management_endpoints/compliance_endpoints.py`. It goes with guardrails, so it is part of that chain rather than a separate decision | Compliance checker for EU AI Act and GDPR regulations. Provides guardrail-agnostic compliance valida |
| `litellm/budget_manager.py` | 1 | 216 | **unproven** | **delete** | SDK-side budgets. The proxy's own budget tables are what Token IQ uses | SDK-side budget tracker that writes spend to a local file or a hosted endpoint |
| `litellm/sandbox/` | 3 | 205 | 1/3 used | **delete** | Section 9 names "fine-tuning, sandbox, compression". 1 of 3 modules are reached, so phase 5 must unpick the importers first | Public entrypoints for running model-generated code in a sandbox. Low-level lifecycle: acreate_conta |
| `litellm/proxy/rerank_endpoints/` | 1 | 126 | used | **delete** | Section 9 names "realtime, video, image, OCR, search and rerank APIs". 1 of 1 modules are reached, so phase 5 must unpick the importers first | Rerank API passthrough endpoints |
| `litellm/proxy/custom_sso.py` | 1 | 46 | **unproven** | **delete** | An example handler, shipped as documentation | Example Custom SSO Handler Use this if you want to run custom code after litellm has retrieved infor |
| `litellm/proxy/custom_prompt_management.py` | 1 | 45 | **unproven** | **delete** | An example, shipped as documentation | Example showing how to plug in prompt management |
| `litellm/proxy/custom_hooks/` | 1 | 38 | **unproven** | **delete** | Examples, shipped as documentation | Example custom hook implementations shipped as documentation |
| `litellm/proxy/mcp_tools.py` | 1 | 35 | **unproven** | **delete** | MCP examples. MCP is named for deletion in the spec | Example MCP tool definitions |
| `litellm/proxy/read_model_list.py` | 1 | 29 | **unproven** | **delete** | Its docstring says the Rust gateway calls it at load time through an embedded interpreter, and nothing else does. Section 9 names the Rust bridge for deletion | Resolve a proxy config's ``model_list`` for the Rust AI gateway. The Rust gateway calls this once at |
| `litellm/proxy/custom_auth_auto.py` | 1 | 27 | **unproven** | **delete** | An example auth function, shipped as documentation | Example custom auth function. This will allow all keys starting with "my-custom-key" to pass through |
| `litellm/proxy/post_call_rules.py` | 1 | 8 | **unproven** | **delete** | An example, shipped as documentation | Example post-call rule function |
| `litellm/proxy/lambda.py` | 1 | 7 | **unproven** | **delete** | An AWS Lambda entrypoint via Mangum. Nothing references it and the deployment is ECS. Deleting it also drops the `mangum>=0.17.0` dependency from pyproject.toml | AWS Lambda handler wrapper around the proxy app |
| `litellm/proxy/custom_validate.py` | 1 | 5 | **unproven** | **delete** | An example, shipped as documentation | Example custom key-validation function |
| `litellm/proxy/` | 622 | 314654 | 395/622 used | **keep** | Neither list names it and 395 of 622 modules are reached. Deleting something in use needs a reason the document does not give | The proxy server package |
| `litellm/llms/` | 916 | 197105 | 631/916 used | **keep** | Neither list names it and 631 of 916 modules are reached. Deleting something in use needs a reason the document does not give | Per-provider request and response translation. One folder per provider |
| `litellm/integrations/` | 205 | 58410 | 171/205 used | **keep** | Neither list names it and 171 of 205 modules are reached. Deleting something in use needs a reason the document does not give | Logging and observability integrations, one module per destination |
| `litellm/proxy/management_endpoints/` | 64 | 54140 | 54/64 used | **keep** | Section 9's keep list: teams, users, organizations, budgets, rate limits | KEY MANAGEMENT All /key management endpoints /key/generate /key/info /key/update /key/delete |
| `litellm/litellm_core_utils/` | 81 | 39095 | 78/81 used | **keep** | Section 9's keep list: shared internals including the price map loader | Shared internals: token counting, streaming, prompt templates, the price map loader |
| `litellm/types/` | 212 | 31683 | 167/212 used | **keep** | Section 9's keep list: shared type definitions | Shared type definitions for the SDK and the proxy |
| `litellm/proxy/proxy_server.py` | 1 | 18504 | used | **keep** | Section 9's keep list: the FastAPI application | The FastAPI application. Registers every router and owns start-up and shutdown |
| `litellm/proxy/auth/` | 27 | 17817 | used | **keep** | Section 9's keep list: auth and virtual keys | Got Valid Token from Cache, DB Run checks for: 1. If user can call model 2. If user is in budget 3. |
| `litellm/proxy/pass_through_endpoints/` | 23 | 14766 | used | **keep** | Section 9's keep list: pass-through endpoints | Pass-through mode: forwards a request to a provider unchanged and records the cost |
| `litellm/responses/` | 15 | 14172 | 14/15 used | **keep** | Neither list names it and 14 of 15 modules are reached. Deleting something in use needs a reason the document does not give | Handles transforming from Responses API -> LiteLLM completion (Chat Completion API) |
| `litellm/proxy/hooks/` | 25 | 13734 | 20/25 used | **keep** | Neither list names it and 20 of 25 modules are reached. Deleting something in use needs a reason the document does not give | This is a rate limiter implementation based on a similar one by Envoy proxy. This is currently in de |
| `litellm/router.py` | 1 | 13715 | used | **keep** | Neither list names it and 1 of 1 modules are reached. Deleting something in use needs a reason the document does not give | The routing layer: deployment selection, fallbacks and cooldowns. Switched off by decision 0001 |
| `litellm/proxy/db/` | 33 | 11185 | 31/33 used | **keep** | Section 9's keep list: the Prisma client and migrations | Module responsible for 1. Writing spend increments to either in memory list of transactions or to re |
| `litellm/proxy/spend_tracking/` | 12 | 10261 | used | **keep** | Section 9's keep list: spend tracking | Writes spend rows and daily rollups. The gateway half of every Token IQ figure |
| `litellm/proxy/common_utils/` | 43 | 9939 | 42/43 used | **keep** | Neither list names it and 42 of 43 modules are reached. Deleting something in use needs a reason the document does not give | Helpers shared across proxy endpoints |
| `litellm/utils.py` | 1 | 9855 | used | **keep** | Neither list names it and 1 of 1 modules are reached. Deleting something in use needs a reason the document does not give | Utility helpers for LiteLLM core request handling and provider support. |
| `litellm/main.py` | 1 | 9087 | used | **keep** | Neither list names it and 1 of 1 modules are reached. Deleting something in use needs a reason the document does not give | The SDK entry points: completion, embedding and their async forms |
| `litellm/caching/` | 20 | 7790 | 19/20 used | **keep** | Section 9's keep list: DualCache, used for cooldowns and usage, not response caching | Redis Cache implementation Has 4 primary methods: - set_cache - get_cache - async_set_cache - async_ |
| `litellm/proxy/utils.py` | 1 | 7640 | used | **keep** | Section 9's keep list: the Prisma wrapper and the spend queue | Proxy-wide helpers, including the Prisma client wrapper and the spend queue |
| `litellm/proxy/client/` | 39 | 7356 | 2/39 used | **keep** | Neither list names it and 2 of 39 modules are reached. Deleting something in use needs a reason the document does not give | The command line client behind the `lite` and `litellm-proxy` commands |
| `litellm/proxy/_types.py` | 1 | 5105 | used | **keep** | Section 9's keep list: the auth and key types the whole proxy shares | Pydantic models shared across the proxy, including the auth and key types |
| `litellm/repositories/` | 27 | 4687 | 26/27 used | **keep** | Section 9's keep list: the data layer every Token IQ figure reads | Repository classes for database operations. |
| `litellm/proxy/openai_files_endpoints/` | 7 | 4414 | used | **keep** | Neither list names it and 1 of 1 modules are reached. Deleting something in use needs a reason the document does not give | OpenAI Files API passthrough endpoints |
| `litellm/proxy/common_request_processing.py` | 1 | 3943 | used | **keep** | Neither list names it and 1 of 1 modules are reached. Deleting something in use needs a reason the document does not give | Shared request handling: provider selection, withholding and error shaping |
| `litellm/interactions/` | 14 | 3904 | 13/14 used | **keep** | Neither list names it and 13 of 14 modules are reached. Deleting something in use needs a reason the document does not give | LiteLLM Interactions API This module provides SDK methods for Google's Interactions API. Usage: impo |
| `litellm/proxy/litellm_pre_call_utils.py` | 1 | 3239 | used | **keep** | Neither list names it and 1 of 1 modules are reached. Deleting something in use needs a reason the document does not give | Builds the request that is sent upstream, applying key and team settings |
| `litellm/secret_managers/` | 11 | 2927 | used | **keep** | Section 9's keep list: secret managers in use (AWS) | Reads secrets from AWS, Azure, Google and Hashicorp backends |
| `litellm/proxy/management_helpers/` | 9 | 2716 | used | **keep** | Neither list names it and 1 of 1 modules are reached. Deleting something in use needs a reason the document does not give | Shared helpers for the management endpoints |
| `litellm/cost_calculator.py` | 1 | 2597 | used | **keep** | Section 9's keep list: turns a response into a cost, core to every figure | Turns a response plus the price map into a cost. Core to every figure Token IQ reports |
| `litellm/provider_billing/` | 16 | 2116 | used | **keep** | Neither list names it and 1 of 1 modules are reached. Deleting something in use needs a reason the document does not give | Reading what providers say our usage cost, as opposed to what this gateway measured. |
| `litellm/proxy/health_endpoints/` | 1 | 2026 | used | **keep** | Section 9's keep list: liveness, which every phase check calls | The /health and liveness endpoints |
| `litellm/completion_extras/` | 4 | 1990 | 3/4 used | **keep** | Neither list names it and 3 of 4 modules are reached. Deleting something in use needs a reason the document does not give | Handler for transforming /chat/completions api requests to litellm.responses requests |
| `litellm/constants.py` | 1 | 1984 | used | **keep** | Neither list names it and 1 of 1 modules are reached. Deleting something in use needs a reason the document does not give | Shared constants: defaults, limits and provider lists |
| `litellm/batches/` | 2 | 1841 | used | **keep** | Neither list names it and 1 of 1 modules are reached. Deleting something in use needs a reason the document does not give | Main File for Batches API implementation https://platform.openai.com/docs/api-reference/batch - crea |
| `litellm/proxy/ui_crud_endpoints/` | 3 | 1830 | 2/3 used | **keep** | Neither list names it and 2 of 3 modules are reached. Deleting something in use needs a reason the document does not give | Admin UI settings and banner CRUD |
| `litellm/containers/` | 4 | 1814 | 3/4 used | **keep** | Neither list names it and 3 of 4 modules are reached. Deleting something in use needs a reason the document does not give | Container management functions for LiteLLM. |
| `litellm/google_genai/` | 6 | 1777 | 4/6 used | **keep** | Neither list names it and 4 of 6 modules are reached. Deleting something in use needs a reason the document does not give | This allows using Google GenAI model in their native interface. This module provides generate_conten |
| `litellm/proxy/anthropic_endpoints/` | 5 | 1658 | 1/5 used | **keep** | Neither list names it and 1 of 5 modules are reached. Deleting something in use needs a reason the document does not give | CLAUDE CODE MARKETPLACE Provides a registry/discovery layer for Claude Code plugins. Plugins are sto |
| `litellm/proxy/prompts/` | 4 | 1631 | 3/4 used | **keep** | Neither list names it and 3 of 4 modules are reached. Deleting something in use needs a reason the document does not give | CRUD ENDPOINTS FOR PROMPTS |
| `litellm/proxy/response_api_endpoints/` | 1 | 1549 | used | **keep** | Neither list names it and 1 of 1 modules are reached. Deleting something in use needs a reason the document does not give | Responses API passthrough endpoints |
| `litellm/_lazy_imports_registry.py` | 1 | 1510 | used | **keep** | Neither list names it and 1 of 1 modules are reached. Deleting something in use needs a reason the document does not give | Registry data for lazy imports. This module contains all the name tuples and import maps used by the |
| `litellm/proxy/proxy_cli.py` | 1 | 1454 | used | **keep** | Neither list names it and 1 of 1 modules are reached. Deleting something in use needs a reason the document does not give | The `litellm` command: argument parsing and server start-up |
| `litellm/proxy/container_endpoints/` | 4 | 1383 | 3/4 used | **keep** | Neither list names it and 3 of 4 modules are reached. Deleting something in use needs a reason the document does not give | Container API passthrough endpoints |
| `litellm/files/` | 4 | 1373 | used | **keep** | Neither list names it and 1 of 1 modules are reached. Deleting something in use needs a reason the document does not give | Main File for Files API implementation https://platform.openai.com/docs/api-reference/files |
| `litellm/exceptions.py` | 1 | 1226 | used | **keep** | Neither list names it and 1 of 1 modules are reached. Deleting something in use needs a reason the document does not give | The public exception types the SDK and proxy raise |
| `litellm/proxy/batches_endpoints/` | 2 | 1105 | used | **keep** | Neither list names it and 1 of 1 modules are reached. Deleting something in use needs a reason the document does not give | Batch API passthrough endpoints |
| `litellm/models/` | 21 | 1083 | 19/21 used | **keep** | Neither list names it and 19 of 21 modules are reached. Deleting something in use needs a reason the document does not give | Domain models for LiteLLM backend. |
| `litellm/tool_usage/` | 10 | 977 | used | **keep** | Neither list names it and 1 of 1 modules are reached. Deleting something in use needs a reason the document does not give | What each person spent inside Claude Code, per day. Anthropic publishes this per actor per day with |
| `litellm/_redis.py` | 1 | 967 | used | **keep** | Neither list names it and 1 of 1 modules are reached. Deleting something in use needs a reason the document does not give | Redis client construction from config or environment |
| `litellm/proxy/google_endpoints/` | 2 | 949 | 1/2 used | **keep** | Neither list names it and 1 of 2 modules are reached. Deleting something in use needs a reason the document does not give | Google AI Studio Managed Agents API Proxy Endpoints. Exposes Gemini's /v1beta/agents surface through |
| `litellm/proxy/health_check.py` | 1 | 929 | used | **keep** | Neither list names it and 1 of 1 modules are reached. Deleting something in use needs a reason the document does not give | Runs the configured health checks against each model |
| `litellm/proxy/public_endpoints/` | 4 | 875 | 3/4 used | **keep** | Neither list names it and 3 of 4 modules are reached. Deleting something in use needs a reason the document does not give | Endpoints served without authentication, such as the provider support matrix |
| `litellm/passthrough/` | 4 | 834 | 3/4 used | **keep** | Neither list names it and 3 of 4 modules are reached. Deleting something in use needs a reason the document does not give | This module is used to pass through requests to the LLM APIs. |
| `litellm/_logging.py` | 1 | 823 | used | **keep** | Neither list names it and 1 of 1 modules are reached. Deleting something in use needs a reason the document does not give | Logger setup and verbosity switches for the SDK |
| `litellm/proxy/list_api/` | 4 | 810 | 3/4 used | **keep** | Neither list names it and 3 of 4 modules are reached. Deleting something in use needs a reason the document does not give | Surface-neutral machinery for LiteLLM's own paginated list endpoints. |
| `litellm/proxy/response_polling/` | 3 | 745 | 2/3 used | **keep** | Neither list names it and 2 of 3 modules are reached. Deleting something in use needs a reason the document does not give | Response Polling Module for Background Responses with Cache |
| `litellm/proxy/route_llm_request.py` | 1 | 717 | used | **keep** | Neither list names it and 1 of 1 modules are reached. Deleting something in use needs a reason the document does not give | Chooses which deployment or user config handles a request |
| `litellm/proxy/middleware/` | 5 | 646 | used | **keep** | Neither list names it and 1 of 1 modules are reached. Deleting something in use needs a reason the document does not give | Counts HTTP requests to LLM inference, MCP, and A2A endpoints. Feeds two independent sinks off one c |
| `litellm/setup_wizard.py` | 1 | 630 | used | **keep** | Neither list names it and 1 of 1 modules are reached. Deleting something in use needs a reason the document does not give | LiteLLM Interactive Setup Wizard Guides users through selecting LLM providers, entering API keys, an |
| `litellm/proxy/credential_endpoints/` | 2 | 578 | used | **keep** | Section 9's keep list: stored credentials, including the billing split | CRUD endpoints for storing reusable credentials. |
| `litellm/proxy/example_config_yaml/` | 9 | 568 | **unproven** | **keep** | Fixtures the e2e suites load by path. Deleting them breaks those suites | Dispatching team metadata validator for the store_model_in_db e2e suite. The suite runs one proxy wi |
| `litellm/proxy/memory/` | 2 | 544 | 1/2 used | **keep** | Neither list names it and 1 of 2 modules are reached. Deleting something in use needs a reason the document does not give | MEMORY MANAGEMENT CRUD endpoints for user/team-scoped memory entries. POST /v1/memory - Create a mem |
| `litellm/_lazy_imports.py` | 1 | 469 | used | **keep** | Neither list names it and 1 of 1 modules are reached. Deleting something in use needs a reason the document does not give | Lazy Import System This module implements lazy loading for LiteLLM attributes. Instead of importing |
| `litellm/proxy/_lazy_features.py` | 1 | 464 | used | **keep** | Neither list names it and 1 of 1 modules are reached. Deleting something in use needs a reason the document does not give | Lazy registration for optional feature routers. Each LAZY_FEATURES entry imports its module only on |
| `litellm/anthropic_beta_headers_manager.py` | 1 | 410 | used | **keep** | Neither list names it and 1 of 1 modules are reached. Deleting something in use needs a reason the document does not give | Centralized manager for Anthropic beta headers across different providers. This module provides util |
| `litellm/anthropic_interface/` | 5 | 382 | 2/5 used | **keep** | Neither list names it and 2 of 5 modules are reached. Deleting something in use needs a reason the document does not give | Anthropic module for LiteLLM |
| `litellm/proxy/health_check_utils/` | 2 | 372 | 1/2 used | **keep** | Neither list names it and 1 of 2 modules are reached. Deleting something in use needs a reason the document does not give | Helpers for the health checks |
| `litellm/_service_logger.py` | 1 | 358 | used | **keep** | Neither list names it and 1 of 1 modules are reached. Deleting something in use needs a reason the document does not give | Emits service-health events to the configured logging integrations |
| `litellm/recommendations/` | 8 | 328 | used | **keep** | Neither list names it and 1 of 1 modules are reached. Deleting something in use needs a reason the document does not give | Turning the data the product holds into a short list of things worth doing. |
| `litellm/proxy/plugin_routes.py` | 1 | 327 | used | **keep** | Neither list names it and 1 of 1 modules are reached. Deleting something in use needs a reason the document does not give | Plugin proxy routes for litellm. Enables external services to register as plugins and be proxied thr |
| `litellm/endpoints/` | 2 | 310 | used | **keep** | Neither list names it and 1 of 1 modules are reached. Deleting something in use needs a reason the document does not give | Endpoint helpers shared by the SDK's API surfaces |
| `litellm/proxy/analytics_endpoints/` | 2 | 230 | used | **keep** | Neither list names it and 1 of 1 modules are reached. Deleting something in use needs a reason the document does not give | Analytics and cache-activity endpoints the admin UI reads |
| `litellm/proxy/vertex_ai_endpoints/` | 1 | 226 | **unproven** | **keep** | Misleadingly named: it holds Langfuse logging pass-through endpoints, registered lazily by `_lazy_features.py`. Pass-through is kept. The folder name wants fixing in phase 9 | What is this? Logging Pass-Through Endpoints |
| `litellm/proxy/config_resolvers/` | 4 | 212 | used | **keep** | Neither list names it and 1 of 1 modules are reached. Deleting something in use needs a reason the document does not give | Typed, provenance-aware resolution of proxy settings from DB then env. |
| `litellm/proxy/types_utils/` | 1 | 212 | used | **keep** | Neither list names it and 1 of 1 modules are reached. Deleting something in use needs a reason the document does not give | Runtime loading of user-supplied callable config values |
| `litellm/proxy/logging_endpoints/` | 2 | 200 | 1/2 used | **keep** | Neither list names it and 1 of 2 modules are reached. Deleting something in use needs a reason the document does not give | Ingest pre-built logging payloads from external producers and replay them through LiteLLM's standard |
| `litellm/proxy/shutdown/` | 2 | 175 | 1/2 used | **keep** | Neither list names it and 1 of 2 modules are reached. Deleting something in use needs a reason the document does not give | Application-level graceful shutdown coordination for the LiteLLM proxy. Kubernetes terminates a pod |
| `litellm/proxy/_lazy_openapi_snapshot.py` | 1 | 174 | used | **keep** | Neither list names it and 1 of 1 modules are reached. Deleting something in use needs a reason the document does not give | Per-feature OpenAPI snapshot for lazy-loaded routers. The committed JSON is generated by `python -m |
| `litellm/scheduler.py` | 1 | 137 | used | **keep** | Neither list names it and 1 of 1 modules are reached. Deleting something in use needs a reason the document does not give | Priority queue that holds requests when a deployment is at capacity |
| `litellm/_redis_credential_provider.py` | 1 | 132 | used | **keep** | Neither list names it and 1 of 1 modules are reached. Deleting something in use needs a reason the document does not give | Resolves Redis credentials, including from a secret manager |
| `litellm/timeout.py` | 1 | 117 | used | **keep** | Neither list names it and 1 of 1 modules are reached. Deleting something in use needs a reason the document does not give | Module containing "timeout" decorator for sync and async callables. |
| `litellm/overview/` | 2 | 97 | used | **keep** | Neither list names it and 1 of 1 modules are reached. Deleting something in use needs a reason the document does not give | The headline figures for the Overview page. Pure, so the one rule this product cannot get wrong can |
| `litellm/attribution/` | 2 | 96 | used | **keep** | Neither list names it and 1 of 1 modules are reached. Deleting something in use needs a reason the document does not give | Deciding who owns spend that bypassed the gateway. |
| `litellm/ledger/` | 2 | 79 | used | **keep** | Neither list names it and 1 of 1 modules are reached. Deleting something in use needs a reason the document does not give | Setting a provider's bill against what the product recorded. |
| `litellm/seats/` | 2 | 70 | used | **keep** | Neither list names it and 1 of 1 modules are reached. Deleting something in use needs a reason the document does not give | What one person costs the company. |
| `litellm/proxy/dd_span_tagger.py` | 1 | 58 | used | **keep** | Neither list names it and 1 of 1 modules are reached. Deleting something in use needs a reason the document does not give | Adds Datadog span tags to proxy traces |
| `litellm/proxy/discovery_endpoints/` | 2 | 49 | 1/2 used | **keep** | Neither list names it and 1 of 2 modules are reached. Deleting something in use needs a reason the document does not give | Serves the well-known UI config document the dashboard fetches at startup |
| `litellm/proxy/prisma_migration.py` | 1 | 45 | used | **keep** | Neither list names it and 1 of 1 modules are reached. Deleting something in use needs a reason the document does not give | Standalone entrypoint for applying database migrations and generating the Prisma client. Migration f |
| `litellm/proxy/_logging.py` | 1 | 41 | **unproven** | **keep** | Process logging setup. Unproven only because it is configured, not imported | JSON logging setup for the proxy process |
| `litellm/proxy/prometheus_cleanup.py` | 1 | 40 | used | **keep** | Neither list names it and 1 of 1 modules are reached. Deleting something in use needs a reason the document does not give | Prometheus multiprocess directory cleanup utilities. Wipes all .db files on startup so workers start |
| `litellm/proxy/config_management_endpoints/` | 1 | 28 | **unproven** | **keep** | CRUD for pass-through endpoints, which section 9's keep list names | What is this? CRUD endpoints for managing pass-through endpoints |
| `litellm/_uuid.py` | 1 | 15 | used | **keep** | Neither list names it and 1 of 1 modules are reached. Deleting something in use needs a reason the document does not give | Internal unified UUID helper. Always uses fastuuid for performance. |
| `litellm/_internal_context.py` | 1 | 14 | used | **keep** | Neither list names it and 1 of 1 modules are reached. Deleting something in use needs a reason the document does not give | Internal request context for LiteLLM. Provides a ContextVar-based mechanism for internal signals tha |
| `litellm/_version.py` | 1 | 6 | used | **keep** | Neither list names it and 1 of 1 modules are reached. Deleting something in use needs a reason the document does not give | The package version string |

## How to re-run this

```
python scripts/inventory/run_reachability.py
python scripts/inventory/write_inventory.py
```

The reachability pass writes `2026-10-04-phase-0-reachability.json`. The proposals in this table are
not regenerated by either script: they are decisions, and a script that recomputed them would turn a
judgement back into a guess.
