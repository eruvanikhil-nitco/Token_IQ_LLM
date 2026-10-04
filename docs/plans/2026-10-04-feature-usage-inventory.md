# Feature usage inventory

Phase 0 of `docs/superpowers/specs/2026-10-04-token-iq-independent-codebase.md`. One row per top-level folder in `litellm/` and `litellm/proxy/`, plus the loose Python files at those two levels, which a folder-only inventory would have missed

## What this can and cannot tell you

The `used` column is evidence. A module reached from an entry point is definitely loaded, and nothing in that column is a guess

`unproven` is not evidence of anything. Python loads modules by string, by `getattr`, by config and by plugin registry, and a parser sees none of it. Every `unproven` row below was opened and read before a proposal was written against it, and the proposal is the human's, not the tool's

Two false negatives were already found and fixed while producing this table:

- `litellm/_lazy_imports_registry.py` holds 269 module paths as plain strings, handed to `import_module` by a different file. Reading only the call site left 162 live modules looking dead
- `litellm.proxy.client.cli` is a declared console script. Leaving it out of the entry points made 7,356 lines of CLI look dead

There are 13 dynamic imports the analyser still cannot follow, listed in `2026-10-04-phase-0-reachability.json`. That is the remaining hole, and it is small enough that the table is usable, but it is not zero

## Summary

- 143 rows: 98 folders, 45 loose files
- 2431 Python modules analysed from 105 entry points
- 1714 used, 716 unproven
- 26 rows are wholly unproven, totalling 13,118 lines
- 18 of those are proposed for deletion, totalling 11,707 lines

**Nothing here is deleted until the owner approves this table.**

## Rows needing a decision

Every wholly unproven row, read and proposed

| Path | Files | Lines | What it is | Proposal | Why |
|---|---:|---:|---|---|---|
| `litellm/rag/` | 15 | 3585 | LiteLLM RAG (Retrieval Augmented Generation) Module. Provides an all-in-one API for document ingesti | **delete** | RAG document ingestion. Out of scope for an observer-only gateway |
| `litellm/assistants/` | 2 | 1499 | OpenAI Assistants API passthrough: threads, messages and runs | **delete** | Assistants API. Not a cost surface Token IQ reads |
| `litellm/proxy/vector_store_files_endpoints/` | 2 | 1113 | File endpoints for the vector store feature | **delete** | Vector stores. Named for deletion in the spec |
| `litellm/proxy/openai_evals_endpoints/` | 2 | 1039 | OpenAI Evals API endpoints | **delete** | Evals API. Named for deletion in the spec |
| `litellm/proxy/a2a/` | 5 | 960 | A2A registration helpers for the LiteLLM proxy. - ``discovery``: fetches the upstream agent's well-k | **delete** | Agent-to-agent protocol. Named for deletion in the spec |
| `litellm/skills/` | 2 | 791 | Skills API integration for LiteLLM | **delete** | Skills API. Named for deletion in the spec |
| `litellm/fine_tuning/` | 1 | 778 | Main File for Fine Tuning API implementation https://platform.openai.com/docs/api-reference/fine-tun | **delete** | Fine-tuning API. Named for deletion in the spec |
| `litellm/proxy/realtime_endpoints/` | 2 | 650 | The realtime websocket API passthrough | **delete** | Realtime API. Named for deletion in the spec |
| `litellm/rerank_api/` | 2 | 616 | The /rerank endpoint and its provider dispatch | **delete** | Rerank API. Named for deletion in the spec |
| `litellm/proxy/example_config_yaml/` | 9 | 568 | Dispatching team metadata validator for the store_model_in_db e2e suite. The suite runs one proxy wi | **keep** | Fixtures the e2e suites load by path. Deleting them breaks those suites |
| `litellm/proxy_auth/` | 2 | 269 | Proxy Authentication module for LiteLLM SDK. This module provides OAuth2/JWT token management for au | **unsure** | SDK OAuth2/JWT helper. Confirm no customer config enables it before deleting |
| `litellm/batch_completion/` | 1 | 256 | Helper that fans one prompt out over a model list and returns the best | **delete** | A routing convenience; routing is already switched off by decision 0001 |
| `litellm/proxy/compliance_checks.py` | 1 | 243 | Compliance checker for EU AI Act and GDPR regulations. Provides guardrail-agnostic compliance valida | **unsure** | EU AI Act and GDPR checks. A compliance feature is a product decision, not a technical one |
| `litellm/proxy/vertex_ai_endpoints/` | 1 | 226 | What is this? Logging Pass-Through Endpoints | **unsure** | Vertex passthrough logging. Vertex is a supported provider, so check what breaks |
| `litellm/budget_manager.py` | 1 | 216 | SDK-side budget tracker that writes spend to a local file or a hosted endpoint | **delete** | SDK-side budgets. The proxy's own budget tables are what Token IQ uses |
| `litellm/proxy/custom_sso.py` | 1 | 46 | Example Custom SSO Handler Use this if you want to run custom code after litellm has retrieved infor | **delete** | An example handler, shipped as documentation |
| `litellm/proxy/custom_prompt_management.py` | 1 | 45 | Example showing how to plug in prompt management | **delete** | An example, shipped as documentation |
| `litellm/proxy/_logging.py` | 1 | 41 | JSON logging setup for the proxy process | **keep** | Process logging setup. Unproven only because it is configured, not imported |
| `litellm/proxy/custom_hooks/` | 1 | 38 | Example custom hook implementations shipped as documentation | **delete** | Examples, shipped as documentation |
| `litellm/proxy/mcp_tools.py` | 1 | 35 | Example MCP tool definitions | **delete** | MCP examples. MCP is named for deletion in the spec |
| `litellm/proxy/read_model_list.py` | 1 | 29 | Resolve a proxy config's ``model_list`` for the Rust AI gateway. The Rust gateway calls this once at | **unsure** | Called by the Rust gateway, not by Python. Its fate follows the Rust bridge decision |
| `litellm/proxy/config_management_endpoints/` | 1 | 28 | What is this? CRUD endpoints for managing pass-through endpoints | **unsure** | CRUD for pass-through endpoints, which Token IQ does keep. Check the UI first |
| `litellm/proxy/custom_auth_auto.py` | 1 | 27 | Example custom auth function. This will allow all keys starting with "my-custom-key" to pass through | **delete** | An example auth function, shipped as documentation |
| `litellm/proxy/post_call_rules.py` | 1 | 8 | Example post-call rule function | **delete** | An example, shipped as documentation |
| `litellm/proxy/lambda.py` | 1 | 7 | AWS Lambda handler wrapper around the proxy app | **unsure** | Lambda entrypoint. Deployment is ECS, so confirm nothing ships it |
| `litellm/proxy/custom_validate.py` | 1 | 5 | Example custom key-validation function | **delete** | An example, shipped as documentation |

## Every row

| Path | Files | Lines | Reachability | What it is |
|---|---:|---:|---|---|
| `litellm/_internal_context.py` | 1 | 14 | used | Internal request context for LiteLLM. Provides a ContextVar-based mechanism for internal signals tha |
| `litellm/_lazy_imports.py` | 1 | 469 | used | Lazy Import System This module implements lazy loading for LiteLLM attributes. Instead of importing  |
| `litellm/_lazy_imports_registry.py` | 1 | 1510 | used | Registry data for lazy imports. This module contains all the name tuples and import maps used by the |
| `litellm/_logging.py` | 1 | 823 | used | Logger setup and verbosity switches for the SDK |
| `litellm/_redis.py` | 1 | 967 | used | Redis client construction from config or environment |
| `litellm/_redis_credential_provider.py` | 1 | 132 | used | Resolves Redis credentials, including from a secret manager |
| `litellm/_service_logger.py` | 1 | 358 | used | Emits service-health events to the configured logging integrations |
| `litellm/_uuid.py` | 1 | 15 | used | Internal unified UUID helper. Always uses fastuuid for performance. |
| `litellm/_version.py` | 1 | 6 | used | The package version string |
| `litellm/a2a_protocol/` | 29 | 4785 | 1/29 used | LiteLLM A2A - Wrapper for invoking A2A protocol agents. This module provides a thin wrapper around t |
| `litellm/anthropic_beta_headers_manager.py` | 1 | 410 | used | Centralized manager for Anthropic beta headers across different providers. This module provides util |
| `litellm/anthropic_interface/` | 5 | 382 | 2/5 used | Anthropic module for LiteLLM |
| `litellm/assistants/` | 2 | 1499 | **unproven** | OpenAI Assistants API passthrough: threads, messages and runs |
| `litellm/attribution/` | 2 | 96 | used | Deciding who owns spend that bypassed the gateway. |
| `litellm/batch_completion/` | 1 | 256 | **unproven** | Helper that fans one prompt out over a model list and returns the best |
| `litellm/batches/` | 2 | 1841 | used | Main File for Batches API implementation https://platform.openai.com/docs/api-reference/batch - crea |
| `litellm/budget_manager.py` | 1 | 216 | **unproven** | SDK-side budget tracker that writes spend to a local file or a hosted endpoint |
| `litellm/caching/` | 20 | 7790 | 19/20 used | Redis Cache implementation Has 4 primary methods: - set_cache - get_cache - async_set_cache - async_ |
| `litellm/completion_extras/` | 4 | 1990 | 3/4 used | Handler for transforming /chat/completions api requests to litellm.responses requests |
| `litellm/compression/` | 8 | 899 | 7/8 used | Main compress() function — normalizes input messages, orchestrates BM25/embedding scoring, message s |
| `litellm/constants.py` | 1 | 1984 | used | Shared constants: defaults, limits and provider lists |
| `litellm/containers/` | 4 | 1814 | 3/4 used | Container management functions for LiteLLM. |
| `litellm/cost_calculator.py` | 1 | 2597 | used | Turns a response plus the price map into a cost. Core to every figure Token IQ reports |
| `litellm/endpoints/` | 2 | 310 | used | Endpoint helpers shared by the SDK's API surfaces |
| `litellm/evals/` | 2 | 1974 | 1/2 used | Evals API operations |
| `litellm/exceptions.py` | 1 | 1226 | used | The public exception types the SDK and proxy raise |
| `litellm/experimental_mcp_client/` | 3 | 1166 | 2/3 used | LiteLLM Proxy uses this MCP Client to connnect to other MCP servers. |
| `litellm/files/` | 4 | 1373 | used | Main File for Files API implementation https://platform.openai.com/docs/api-reference/files |
| `litellm/fine_tuning/` | 1 | 778 | **unproven** | Main File for Fine Tuning API implementation https://platform.openai.com/docs/api-reference/fine-tun |
| `litellm/google_genai/` | 6 | 1777 | 4/6 used | This allows using Google GenAI model in their native interface. This module provides generate_conten |
| `litellm/images/` | 3 | 1202 | 1/3 used | Image generation and edit APIs |
| `litellm/integrations/` | 205 | 58410 | 171/205 used | Logging and observability integrations, one module per destination |
| `litellm/interactions/` | 14 | 3904 | 13/14 used | LiteLLM Interactions API This module provides SDK methods for Google's Interactions API. Usage: impo |
| `litellm/ledger/` | 2 | 79 | used | Setting a provider's bill against what the product recorded. |
| `litellm/litellm_core_utils/` | 81 | 39095 | 78/81 used | Shared internals: token counting, streaming, prompt templates, the price map loader |
| `litellm/llms/` | 916 | 197105 | 631/916 used | Per-provider request and response translation. One folder per provider |
| `litellm/main.py` | 1 | 9087 | used | The SDK entry points: completion, embedding and their async forms |
| `litellm/models/` | 21 | 1083 | 19/21 used | Domain models for LiteLLM backend. |
| `litellm/ocr/` | 2 | 743 | used | OCR module for LiteLLM. |
| `litellm/overview/` | 2 | 97 | used | The headline figures for the Overview page. Pure, so the one rule this product cannot get wrong can  |
| `litellm/passthrough/` | 4 | 834 | 3/4 used | This module is used to pass through requests to the LLM APIs. |
| `litellm/provider_billing/` | 16 | 2116 | used | Reading what providers say our usage cost, as opposed to what this gateway measured. |
| `litellm/proxy/` | 622 | 314654 | 395/622 used | The proxy server package |
| `litellm/proxy/_lazy_features.py` | 1 | 464 | used | Lazy registration for optional feature routers. Each LAZY_FEATURES entry imports its module only on  |
| `litellm/proxy/_lazy_openapi_snapshot.py` | 1 | 174 | used | Per-feature OpenAPI snapshot for lazy-loaded routers. The committed JSON is generated by `python -m  |
| `litellm/proxy/_logging.py` | 1 | 41 | **unproven** | JSON logging setup for the proxy process |
| `litellm/proxy/_types.py` | 1 | 5105 | used | Pydantic models shared across the proxy, including the auth and key types |
| `litellm/proxy/a2a/` | 5 | 960 | **unproven** | A2A registration helpers for the LiteLLM proxy. - ``discovery``: fetches the upstream agent's well-k |
| `litellm/proxy/agent_endpoints/` | 10 | 4061 | 5/10 used | Agent endpoints for registering + discovering agents via LiteLLM. Follows the A2A Spec. 1. Register  |
| `litellm/proxy/analytics_endpoints/` | 2 | 230 | used | Analytics and cache-activity endpoints the admin UI reads |
| `litellm/proxy/anthropic_endpoints/` | 5 | 1658 | 1/5 used | CLAUDE CODE MARKETPLACE Provides a registry/discovery layer for Claude Code plugins. Plugins are sto |
| `litellm/proxy/auth/` | 27 | 17817 | used | Got Valid Token from Cache, DB Run checks for: 1. If user can call model 2. If user is in budget 3.  |
| `litellm/proxy/batches_endpoints/` | 2 | 1105 | used | Batch API passthrough endpoints |
| `litellm/proxy/caching_routes.py` | 1 | 249 | used | Endpoints to inspect and flush the response cache |
| `litellm/proxy/client/` | 39 | 7356 | 2/39 used | The command line client behind the `lite` and `litellm-proxy` commands |
| `litellm/proxy/common_request_processing.py` | 1 | 3943 | used | Shared request handling: provider selection, withholding and error shaping |
| `litellm/proxy/common_utils/` | 43 | 9939 | 42/43 used | Helpers shared across proxy endpoints |
| `litellm/proxy/compliance_checks.py` | 1 | 243 | **unproven** | Compliance checker for EU AI Act and GDPR regulations. Provides guardrail-agnostic compliance valida |
| `litellm/proxy/config_management_endpoints/` | 1 | 28 | **unproven** | What is this? CRUD endpoints for managing pass-through endpoints |
| `litellm/proxy/config_resolvers/` | 4 | 212 | used | Typed, provenance-aware resolution of proxy settings from DB then env. |
| `litellm/proxy/container_endpoints/` | 4 | 1383 | 3/4 used | Container API passthrough endpoints |
| `litellm/proxy/credential_endpoints/` | 2 | 578 | used | CRUD endpoints for storing reusable credentials. |
| `litellm/proxy/custom_auth_auto.py` | 1 | 27 | **unproven** | Example custom auth function. This will allow all keys starting with "my-custom-key" to pass through |
| `litellm/proxy/custom_hooks/` | 1 | 38 | **unproven** | Example custom hook implementations shipped as documentation |
| `litellm/proxy/custom_prompt_management.py` | 1 | 45 | **unproven** | Example showing how to plug in prompt management |
| `litellm/proxy/custom_sso.py` | 1 | 46 | **unproven** | Example Custom SSO Handler Use this if you want to run custom code after litellm has retrieved infor |
| `litellm/proxy/custom_validate.py` | 1 | 5 | **unproven** | Example custom key-validation function |
| `litellm/proxy/db/` | 33 | 11185 | 31/33 used | Module responsible for 1. Writing spend increments to either in memory list of transactions or to re |
| `litellm/proxy/dd_span_tagger.py` | 1 | 58 | used | Adds Datadog span tags to proxy traces |
| `litellm/proxy/discovery_endpoints/` | 2 | 49 | 1/2 used | Serves the well-known UI config document the dashboard fetches at startup |
| `litellm/proxy/example_config_yaml/` | 9 | 568 | **unproven** | Dispatching team metadata validator for the store_model_in_db e2e suite. The suite runs one proxy wi |
| `litellm/proxy/fine_tuning_endpoints/` | 1 | 638 | used | Fine-tuning API passthrough endpoints |
| `litellm/proxy/google_endpoints/` | 2 | 949 | 1/2 used | Google AI Studio Managed Agents API Proxy Endpoints. Exposes Gemini's /v1beta/agents surface through |
| `litellm/proxy/guardrails/` | 131 | 50194 | 25/131 used | The guardrail engine and its per-vendor integrations |
| `litellm/proxy/health_check.py` | 1 | 929 | used | Runs the configured health checks against each model |
| `litellm/proxy/health_check_utils/` | 2 | 372 | 1/2 used | Helpers for the health checks |
| `litellm/proxy/health_endpoints/` | 1 | 2026 | used | The /health and liveness endpoints |
| `litellm/proxy/hooks/` | 25 | 13734 | 20/25 used | This is a rate limiter implementation based on a similar one by Envoy proxy. This is currently in de |
| `litellm/proxy/image_endpoints/` | 2 | 340 | 1/2 used | Image API passthrough endpoints |
| `litellm/proxy/lambda.py` | 1 | 7 | **unproven** | AWS Lambda handler wrapper around the proxy app |
| `litellm/proxy/list_api/` | 4 | 810 | 3/4 used | Surface-neutral machinery for LiteLLM's own paginated list endpoints. |
| `litellm/proxy/litellm_pre_call_utils.py` | 1 | 3239 | used | Builds the request that is sent upstream, applying key and team settings |
| `litellm/proxy/logging_endpoints/` | 2 | 200 | 1/2 used | Ingest pre-built logging payloads from external producers and replay them through LiteLLM's standard |
| `litellm/proxy/management_endpoints/` | 64 | 54140 | 54/64 used | KEY MANAGEMENT All /key management endpoints /key/generate /key/info /key/update /key/delete |
| `litellm/proxy/management_helpers/` | 9 | 2716 | used | Shared helpers for the management endpoints |
| `litellm/proxy/mcp_tools.py` | 1 | 35 | **unproven** | Example MCP tool definitions |
| `litellm/proxy/memory/` | 2 | 544 | 1/2 used | MEMORY MANAGEMENT CRUD endpoints for user/team-scoped memory entries. POST /v1/memory - Create a mem |
| `litellm/proxy/middleware/` | 5 | 646 | used | Counts HTTP requests to LLM inference, MCP, and A2A endpoints. Feeds two independent sinks off one c |
| `litellm/proxy/ocr_endpoints/` | 2 | 351 | 1/2 used | OCR API passthrough endpoints |
| `litellm/proxy/openai_evals_endpoints/` | 2 | 1039 | **unproven** | OpenAI Evals API endpoints |
| `litellm/proxy/openai_files_endpoints/` | 7 | 4414 | used | OpenAI Files API passthrough endpoints |
| `litellm/proxy/pass_through_endpoints/` | 23 | 14766 | used | Pass-through mode: forwards a request to a provider unchanged and records the cost |
| `litellm/proxy/plugin_routes.py` | 1 | 327 | used | Plugin proxy routes for litellm. Enables external services to register as plugins and be proxied thr |
| `litellm/proxy/policy_engine/` | 11 | 4555 | 8/11 used | LiteLLM Policy Engine The Policy Engine allows administrators to define policies that combine guardr |
| `litellm/proxy/post_call_rules.py` | 1 | 8 | **unproven** | Example post-call rule function |
| `litellm/proxy/prisma_migration.py` | 1 | 45 | used | Standalone entrypoint for applying database migrations and generating the Prisma client. Migration f |
| `litellm/proxy/prometheus_cleanup.py` | 1 | 40 | used | Prometheus multiprocess directory cleanup utilities. Wipes all .db files on startup so workers start |
| `litellm/proxy/prompts/` | 4 | 1631 | 3/4 used | CRUD ENDPOINTS FOR PROMPTS |
| `litellm/proxy/proxy_cli.py` | 1 | 1454 | used | The `litellm` command: argument parsing and server start-up |
| `litellm/proxy/proxy_server.py` | 1 | 18504 | used | The FastAPI application. Registers every router and owns start-up and shutdown |
| `litellm/proxy/public_endpoints/` | 4 | 875 | 3/4 used | Endpoints served without authentication, such as the provider support matrix |
| `litellm/proxy/rag_endpoints/` | 3 | 1098 | 2/3 used | RAG Endpoints for LiteLLM Proxy. |
| `litellm/proxy/read_model_list.py` | 1 | 29 | **unproven** | Resolve a proxy config's ``model_list`` for the Rust AI gateway. The Rust gateway calls this once at |
| `litellm/proxy/realtime_endpoints/` | 2 | 650 | **unproven** | The realtime websocket API passthrough |
| `litellm/proxy/rerank_endpoints/` | 1 | 126 | used | Rerank API passthrough endpoints |
| `litellm/proxy/response_api_endpoints/` | 1 | 1549 | used | Responses API passthrough endpoints |
| `litellm/proxy/response_polling/` | 3 | 745 | 2/3 used | Response Polling Module for Background Responses with Cache |
| `litellm/proxy/route_llm_request.py` | 1 | 717 | used | Chooses which deployment or user config handles a request |
| `litellm/proxy/search_endpoints/` | 4 | 1295 | 2/4 used | CRUD ENDPOINTS FOR SEARCH TOOLS |
| `litellm/proxy/shutdown/` | 2 | 175 | 1/2 used | Application-level graceful shutdown coordination for the LiteLLM proxy. Kubernetes terminates a pod  |
| `litellm/proxy/spend_tracking/` | 12 | 10261 | used | Writes spend rows and daily rollups. The gateway half of every Token IQ figure |
| `litellm/proxy/types_utils/` | 1 | 212 | used | Runtime loading of user-supplied callable config values |
| `litellm/proxy/ui_crud_endpoints/` | 3 | 1830 | 2/3 used | Admin UI settings and banner CRUD |
| `litellm/proxy/utils.py` | 1 | 7640 | used | Proxy-wide helpers, including the Prisma client wrapper and the spend queue |
| `litellm/proxy/vector_store_endpoints/` | 3 | 1816 | used | VECTOR STORE MANAGEMENT All /vector_store management endpoints /vector_store/new /vector_store/delet |
| `litellm/proxy/vector_store_files_endpoints/` | 2 | 1113 | **unproven** | File endpoints for the vector store feature |
| `litellm/proxy/vertex_ai_endpoints/` | 1 | 226 | **unproven** | What is this? Logging Pass-Through Endpoints |
| `litellm/proxy/video_endpoints/` | 3 | 978 | 2/3 used | Video endpoints module. |
| `litellm/proxy_auth/` | 2 | 269 | **unproven** | Proxy Authentication module for LiteLLM SDK. This module provides OAuth2/JWT token management for au |
| `litellm/rag/` | 15 | 3585 | **unproven** | LiteLLM RAG (Retrieval Augmented Generation) Module. Provides an all-in-one API for document ingesti |
| `litellm/realtime_api/` | 1 | 693 | used | Abstraction function for OpenAI's realtime API |
| `litellm/recommendations/` | 8 | 328 | used | Turning the data the product holds into a short list of things worth doing. |
| `litellm/repositories/` | 27 | 4687 | 26/27 used | Repository classes for database operations. |
| `litellm/rerank_api/` | 2 | 616 | **unproven** | The /rerank endpoint and its provider dispatch |
| `litellm/responses/` | 15 | 14172 | 14/15 used | Handles transforming from Responses API -> LiteLLM completion (Chat Completion API) |
| `litellm/router.py` | 1 | 13715 | used | The routing layer: deployment selection, fallbacks and cooldowns. Switched off by decision 0001 |
| `litellm/router_strategy/` | 26 | 10095 | 21/26 used | Complexity-based Auto Router A rule-based routing strategy that uses weighted scoring across multipl |
| `litellm/router_utils/` | 25 | 6448 | 23/25 used | Helpers for the routing layer |
| `litellm/rust_bridge/` | 11 | 1403 | 9/11 used | LiteLLM Rust bridge package. |
| `litellm/sandbox/` | 3 | 205 | 1/3 used | Public entrypoints for running model-generated code in a sandbox. Low-level lifecycle: acreate_conta |
| `litellm/scheduler.py` | 1 | 137 | used | Priority queue that holds requests when a deployment is at capacity |
| `litellm/search/` | 3 | 413 | used | LiteLLM Search API module. |
| `litellm/seats/` | 2 | 70 | used | What one person costs the company. |
| `litellm/secret_managers/` | 11 | 2927 | used | Reads secrets from AWS, Azure, Google and Hashicorp backends |
| `litellm/setup_wizard.py` | 1 | 630 | used | LiteLLM Interactive Setup Wizard Guides users through selecting LLM providers, entering API keys, an |
| `litellm/skills/` | 2 | 791 | **unproven** | Skills API integration for LiteLLM |
| `litellm/timeout.py` | 1 | 117 | used | Module containing "timeout" decorator for sync and async callables. |
| `litellm/tool_usage/` | 10 | 977 | used | What each person spent inside Claude Code, per day. Anthropic publishes this per actor per day with  |
| `litellm/types/` | 212 | 31683 | 167/212 used | Shared type definitions for the SDK and the proxy |
| `litellm/utils.py` | 1 | 9855 | used | Utility helpers for LiteLLM core request handling and provider support. |
| `litellm/vector_store_files/` | 3 | 813 | 2/3 used | LiteLLM SDK functions for managing vector store files. |
| `litellm/vector_stores/` | 4 | 1645 | used | LiteLLM SDK Functions for Creating and Searching Vector Stores |
| `litellm/videos/` | 3 | 1752 | 1/3 used | Video generation and management functions for LiteLLM. |

## How to re-run this

```bash
python -m scripts.inventory.run_reachability
python -m scripts.inventory.inventory
python -m scripts.inventory.write_inventory
```

Phase 5 re-runs the first of these after each deletion, to check that nothing still reaches what was removed
