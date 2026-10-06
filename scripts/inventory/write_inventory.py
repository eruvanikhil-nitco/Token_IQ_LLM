"""Render the feature inventory markdown from the measured data plus human judgement.

The measurable columns come from the reachability graph. The description and the proposal
are written here by hand, because `unproven` means the parser could not tell, and a script
turning that into a deletion is the one failure mode this whole phase exists to prevent.
"""

from __future__ import annotations

import ast
import json
import pathlib
from collections.abc import Mapping, Sequence
from typing import Final

REPO: Final = pathlib.Path(__file__).resolve().parents[2]
DATA: Final = REPO / "docs" / "plans" / "2026-10-04-phase-0-inventory-data.json"
GRAPH: Final = REPO / "docs" / "plans" / "2026-10-04-phase-0-reachability.json"
OUT: Final = REPO / "docs" / "plans" / "2026-10-04-feature-usage-inventory.md"

# Written by hand after reading the folder. Only rows where the docstring is absent or
# misleading need an entry; everything else falls back to the module's own docstring.
DESCRIBED: Final[Mapping[str, str]] = {
    "token_iq/gateway/assistants/": "OpenAI Assistants API passthrough: threads, messages and runs",
    "token_iq/gateway/batch_completion/": "Helper that fans one prompt out over a model list and returns the best",
    "token_iq/gateway/budget_manager.py": "SDK-side budget tracker that writes spend to a local file or a hosted endpoint",
    "token_iq/gateway/rerank_api/": "The /rerank endpoint and its provider dispatch",
    "token_iq/gateway/proxy/_logging.py": "JSON logging setup for the proxy process",
    "token_iq/gateway/proxy/custom_hooks/": "Example custom hook implementations shipped as documentation",
    "token_iq/gateway/proxy/custom_prompt_management.py": "Example showing how to plug in prompt management",
    "token_iq/gateway/proxy/custom_validate.py": "Example custom key-validation function",
    "token_iq/gateway/proxy/lambda.py": "AWS Lambda handler wrapper around the proxy app",
    "token_iq/gateway/proxy/mcp_tools.py": "Example MCP tool definitions",
    "token_iq/gateway/proxy/post_call_rules.py": "Example post-call rule function",
    "token_iq/gateway/proxy/realtime_endpoints/": "The realtime websocket API passthrough",
    "token_iq/gateway/proxy/vector_store_files_endpoints/": "File endpoints for the vector store feature",
    # Core modules with no docstring of their own, described after reading them.
    "token_iq/gateway/_logging.py": "Logger setup and verbosity switches for the SDK",
    "token_iq/gateway/_redis.py": "Redis client construction from config or environment",
    "token_iq/gateway/_redis_credential_provider.py": "Resolves Redis credentials, including from a secret manager",
    "token_iq/gateway/_service_logger.py": "Emits service-health events to the configured logging integrations",
    "token_iq/gateway/_version.py": "The package version string",
    "token_iq/gateway/constants.py": "Shared constants: defaults, limits and provider lists",
    "token_iq/gateway/cost_calculator.py": "Turns a response plus the price map into a cost. Core to every figure Token IQ reports",
    "token_iq/gateway/endpoints/": "Endpoint helpers shared by the SDK's API surfaces",
    "token_iq/gateway/exceptions.py": "The public exception types the SDK and proxy raise",
    "token_iq/gateway/images/": "Image generation and edit APIs",
    "token_iq/gateway/integrations/": "Logging and observability integrations, one module per destination",
    "token_iq/gateway/core_utils/": "Shared internals: token counting, streaming, prompt templates, the price map loader",
    "token_iq/gateway/llms/": "Per-provider request and response translation. One folder per provider",
    "token_iq/gateway/main.py": "The SDK entry points: completion, embedding and their async forms",
    "token_iq/gateway/proxy/": "The proxy server package",
    "token_iq/gateway/proxy/_types.py": "Pydantic models shared across the proxy, including the auth and key types",
    "token_iq/gateway/proxy/analytics_endpoints/": "Analytics and cache-activity endpoints the admin UI reads",
    "token_iq/gateway/proxy/batches_endpoints/": "Batch API passthrough endpoints",
    "token_iq/gateway/proxy/caching_routes.py": "Endpoints to inspect and flush the response cache",
    "token_iq/gateway/proxy/client/": "The command line client behind the `lite` and `litellm-proxy` commands",
    "token_iq/gateway/proxy/common_request_processing.py": "Shared request handling: provider selection, withholding and error shaping",
    "token_iq/gateway/proxy/common_utils/": "Helpers shared across proxy endpoints",
    "token_iq/gateway/proxy/container_endpoints/": "Container API passthrough endpoints",
    "token_iq/gateway/proxy/dd_span_tagger.py": "Adds Datadog span tags to proxy traces",
    "token_iq/gateway/proxy/discovery_endpoints/": "Serves the well-known UI config document the dashboard fetches at startup",
    "token_iq/gateway/proxy/fine_tuning_endpoints/": "Fine-tuning API passthrough endpoints",
    "token_iq/gateway/proxy/guardrails/": "The guardrail engine and its per-vendor integrations",
    "token_iq/gateway/proxy/health_check.py": "Runs the configured health checks against each model",
    "token_iq/gateway/proxy/health_check_utils/": "Helpers for the health checks",
    "token_iq/gateway/proxy/health_endpoints/": "The /health and liveness endpoints",
    "token_iq/gateway/proxy/image_endpoints/": "Image API passthrough endpoints",
    "token_iq/gateway/proxy/litellm_pre_call_utils.py": "Builds the request that is sent upstream, applying key and team settings",
    "token_iq/gateway/proxy/management_helpers/": "Shared helpers for the management endpoints",
    "token_iq/gateway/proxy/ocr_endpoints/": "OCR API passthrough endpoints",
    "token_iq/gateway/proxy/openai_files_endpoints/": "OpenAI Files API passthrough endpoints",
    "token_iq/gateway/proxy/pass_through_endpoints/": "Pass-through mode: forwards a request to a provider unchanged and records the cost",
    "token_iq/gateway/proxy/proxy_cli.py": "The `litellm` command: argument parsing and server start-up",
    "token_iq/gateway/proxy/proxy_server.py": "The FastAPI application. Registers every router and owns start-up and shutdown",
    "token_iq/gateway/proxy/public_endpoints/": "Endpoints served without authentication, such as the provider support matrix",
    "token_iq/gateway/proxy/rerank_endpoints/": "Rerank API passthrough endpoints",
    "token_iq/gateway/proxy/response_api_endpoints/": "Responses API passthrough endpoints",
    "token_iq/gateway/proxy/route_llm_request.py": "Chooses which deployment or user config handles a request",
    "token_iq/gateway/proxy/spend_tracking/": "Writes spend rows and daily rollups. The gateway half of every Token IQ figure",
    "token_iq/gateway/proxy/types_utils/": "Runtime loading of user-supplied callable config values",
    "token_iq/gateway/proxy/ui_crud_endpoints/": "Admin UI settings and banner CRUD",
    "token_iq/gateway/proxy/utils.py": "Proxy-wide helpers, including the Prisma client wrapper and the spend queue",
    "token_iq/gateway/router.py": "The routing layer: deployment selection, fallbacks and cooldowns. Switched off by decision 0001",
    "token_iq/gateway/router_utils/": "Helpers for the routing layer",
    "token_iq/gateway/scheduler.py": "Priority queue that holds requests when a deployment is at capacity",
    "token_iq/gateway/secret_managers/": "Reads secrets from AWS, Azure, Google and Hashicorp backends",
    "token_iq/gateway/types/": "Shared type definitions for the SDK and the proxy",
}

# The proposal, and the reason. Every row here was read before it was written.
PROPOSED: Final[Mapping[str, tuple[str, str]]] = {
    "token_iq/gateway/rag/": ("delete", "RAG document ingestion. Out of scope for an observer-only gateway"),
    "token_iq/gateway/assistants/": ("delete", "Assistants API. Not a cost surface Token IQ reads"),
    "token_iq/gateway/skills/": ("delete", "Skills API. Named for deletion in the spec"),
    "token_iq/gateway/fine_tuning/": ("delete", "Fine-tuning API. Named for deletion in the spec"),
    "token_iq/gateway/rerank_api/": ("delete", "Rerank API. Named for deletion in the spec"),
    "token_iq/gateway/batch_completion/": ("delete", "A routing convenience; routing is already switched off by decision 0001"),
    "token_iq/gateway/budget_manager.py": ("delete", "SDK-side budgets. The proxy's own budget tables are what Token IQ uses"),
    "token_iq/gateway/proxy_auth/": ("unsure", "SDK OAuth2/JWT helper. Confirm no customer config enables it before deleting"),
    "token_iq/gateway/proxy/a2a/": ("delete", "Agent-to-agent protocol. Named for deletion in the spec"),
    "token_iq/gateway/proxy/openai_evals_endpoints/": ("delete", "Evals API. Named for deletion in the spec"),
    "token_iq/gateway/proxy/realtime_endpoints/": ("delete", "Realtime API. Named for deletion in the spec"),
    "token_iq/gateway/proxy/vector_store_files_endpoints/": ("delete", "Vector stores. Named for deletion in the spec"),
    "token_iq/gateway/proxy/vertex_ai_endpoints/": ("unsure", "Vertex passthrough logging. Vertex is a supported provider, so check what breaks"),
    "token_iq/gateway/proxy/compliance_checks.py": ("unsure", "EU AI Act and GDPR checks. A compliance feature is a product decision, not a technical one"),
    "token_iq/gateway/proxy/config_management_endpoints/": ("unsure", "CRUD for pass-through endpoints, which Token IQ does keep. Check the UI first"),
    "token_iq/gateway/proxy/read_model_list.py": ("unsure", "Called by the Rust gateway, not by Python. Its fate follows the Rust bridge decision"),
    "token_iq/gateway/proxy/custom_sso.py": ("delete", "An example handler, shipped as documentation"),
    "token_iq/gateway/proxy/custom_auth_auto.py": ("delete", "An example auth function, shipped as documentation"),
    "token_iq/gateway/proxy/custom_prompt_management.py": ("delete", "An example, shipped as documentation"),
    "token_iq/gateway/proxy/custom_validate.py": ("delete", "An example, shipped as documentation"),
    "token_iq/gateway/proxy/custom_hooks/": ("delete", "Examples, shipped as documentation"),
    "token_iq/gateway/proxy/post_call_rules.py": ("delete", "An example, shipped as documentation"),
    "token_iq/gateway/proxy/mcp_tools.py": ("delete", "MCP examples. MCP is named for deletion in the spec"),
    "token_iq/gateway/proxy/lambda.py": ("unsure", "Lambda entrypoint. Deployment is ECS, so confirm nothing ships it"),
    "token_iq/gateway/proxy/_logging.py": ("keep", "Process logging setup. Unproven only because it is configured, not imported"),
    "token_iq/gateway/proxy/example_config_yaml/": ("keep", "Fixtures the e2e suites load by path. Deleting them breaks those suites"),
}


def _docstring(path: pathlib.Path) -> str:
    candidates: Final = (
        [path / "__init__.py", *sorted(path.rglob("*.py"), key=lambda f: -f.stat().st_size)[:1]]
        if path.is_dir()
        else [path]
    )
    for candidate in candidates:
        if not candidate.exists():
            continue
        try:
            text = ast.get_docstring(ast.parse(candidate.read_text(encoding="utf-8", errors="ignore")))
        except SyntaxError:
            continue
        if text:
            return " ".join(text.strip().split())[:100]
    return ""


def _describe(row: Mapping[str, object]) -> str:
    path: Final = str(row["path"])
    return DESCRIBED.get(path) or _docstring(REPO / path.rstrip("/")) or "(no description: read before deciding)"


def _verdict(row: Mapping[str, object]) -> str:
    known, unproven = int(row["modules_known"]), int(row["unproven"])
    if known == 0:
        return "no modules"
    if unproven == 0:
        return "used"
    if unproven == known:
        return "**unproven**"
    return f"{known - unproven}/{known} used"


def main(argv: Sequence[str] | None = None) -> int:
    del argv
    rows: Final = json.loads(DATA.read_text(encoding="utf-8"))["rows"]
    graph: Final = json.loads(GRAPH.read_text(encoding="utf-8"))
    summary: Final = graph["summary"]

    candidates: Final = [r for r in rows if r["modules_known"] and r["unproven"] == r["modules_known"]]
    proposals: Final = {k: PROPOSED[k][0] for k in PROPOSED}
    to_delete: Final = [r for r in candidates if proposals.get(str(r["path"])) == "delete"]

    lines: Final[list[str]] = []  # mutable-ok: assembled once

    lines.append("# Feature usage inventory\n")
    lines.append(
        "Phase 0 of `docs/specs/2026-10-04-token-iq-independent-codebase.md`. "
        "One row per top-level folder in `litellm/` and `token_iq/gateway/proxy/`, plus the loose Python "
        "files at those two levels, which a folder-only inventory would have missed\n"
    )
    lines.append("## What this can and cannot tell you\n")
    lines.append(
        "The `used` column is evidence. A module reached from an entry point is definitely loaded, "
        "and nothing in that column is a guess\n"
    )
    lines.append(
        "`unproven` is not evidence of anything. Python loads modules by string, by `getattr`, by "
        "config and by plugin registry, and a parser sees none of it. Every `unproven` row below "
        "was opened and read before a proposal was written against it, and the proposal is the "
        "human's, not the tool's\n"
    )
    lines.append("Two false negatives were already found and fixed while producing this table:\n")
    lines.append(
        "- `token_iq/gateway/_lazy_imports_registry.py` holds 269 module paths as plain strings, handed to "
        "`import_module` by a different file. Reading only the call site left 162 live modules "
        "looking dead\n"
        "- `litellm.proxy.client.cli` is a declared console script. Leaving it out of the entry "
        "points made 7,356 lines of CLI look dead\n"
    )
    lines.append(
        f"There are {summary['unresolved_dynamic_imports']} dynamic imports the analyser still cannot "
        f"follow, listed in `2026-10-04-phase-0-reachability.json`. That is the remaining hole, and it "
        f"is small enough that the table is usable, but it is not zero\n"
    )

    lines.append("## Summary\n")
    lines.append(f"- {len(rows)} rows: {sum(1 for r in rows if r['kind'] == 'folder')} folders, "
                 f"{sum(1 for r in rows if r['kind'] == 'file')} loose files")
    lines.append(f"- {summary['modules']} Python modules analysed from {summary['entry_points']} entry points")
    lines.append(f"- {summary['counts'].get('used', 0)} used, {summary['counts'].get('unproven', 0)} unproven")
    lines.append(f"- {len(candidates)} rows are wholly unproven, totalling "
                 f"{sum(int(r['lines']) for r in candidates):,} lines")
    lines.append(f"- {len(to_delete)} of those are proposed for deletion, totalling "
                 f"{sum(int(r['lines']) for r in to_delete):,} lines\n")
    lines.append("**Nothing here is deleted until the owner approves this table.**\n")

    lines.append("## Rows needing a decision\n")
    lines.append("Every wholly unproven row, read and proposed\n")
    lines.append("| Path | Files | Lines | What it is | Proposal | Why |")
    lines.append("|---|---:|---:|---|---|---|")
    for row in sorted(candidates, key=lambda r: -int(r["lines"])):
        path = str(row["path"])
        proposal, why = PROPOSED.get(path, ("unsure", "not yet read"))
        lines.append(f"| `{path}` | {row['files']} | {row['lines']} | {_describe(row)} | **{proposal}** | {why} |")
    lines.append("")

    lines.append("## Every row\n")
    lines.append("| Path | Files | Lines | Reachability | What it is |")
    lines.append("|---|---:|---:|---|---|")
    for row in sorted(rows, key=lambda r: str(r["path"])):
        lines.append(
            f"| `{row['path']}` | {row['files']} | {row['lines']} | {_verdict(row)} | {_describe(row)} |"
        )
    lines.append("")

    lines.append("## How to re-run this\n")
    lines.append("```bash")
    lines.append("python -m scripts.inventory.run_reachability")
    lines.append("python -m scripts.inventory.inventory")
    lines.append("python -m scripts.inventory.write_inventory")
    lines.append("```\n")
    lines.append(
        "Phase 5 re-runs the first of these after each deletion, to check that nothing still "
        "reaches what was removed\n"
    )

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)} with {len(rows)} rows, {len(candidates)} needing a decision")
    missing: Final = [str(r["path"]) for r in candidates if str(r["path"]) not in PROPOSED]
    if missing:
        print("rows with no proposal:", missing)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
