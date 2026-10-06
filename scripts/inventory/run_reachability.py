"""Run the reachability analysis over this repository and write the artifact.

    python -m scripts.inventory.run_reachability
"""

from __future__ import annotations

import dataclasses
import json
import pathlib
import subprocess
import tomllib
from collections.abc import Sequence
from typing import Final

from scripts.inventory.reachability import Graph, analyse

REPO: Final = pathlib.Path(__file__).resolve().parents[2]
ARTIFACT: Final = REPO / "docs" / "plans" / "2026-10-04-phase-0-reachability.json"

# Build output, vendored code and test trees. Tests import product code, so including them
# would mark a module "used" because something tests it, which is not the question being
# asked: phase 5 deletes a feature and its tests together.
SKIP: Final[tuple[str, ...]] = (
    "token_iq/gateway/proxy/_experimental/out/",
    "tests/",
    "ui/",
    "docs/",
    "cookbook/",
    "scripts/",
    ".venv/",
)

# Registries that hold module paths as string literals while a different module performs the
# import. Found by reading every unresolved dynamic import in the first run, which is the step
# the plan requires precisely so holes like this are closed rather than quietly tolerated.
# `_lazy_imports_registry` alone holds 269 paths, most of them provider transformations, which
# are exactly what phase 5 has to decide about.
LITERAL_SOURCES: Final[tuple[str, ...]] = (
    "token_iq.gateway._lazy_imports_registry",
    "token_iq.gateway.llms",
    "token_iq.gateway.proxy._lazy_openapi_snapshot",
    "token_iq.gateway.proxy.guardrails.guardrail_registry",
    "token_iq.gateway.proxy.prompts.prompt_registry",
)

# The process entry points that nothing imports. Hardcoding these was a mistake once already:
# `litellm.proxy.client.cli` is a declared console script, and leaving it out made 7,356 lines
# of CLI look dead. The console scripts are now read from pyproject rather than listed here.
SEED_MODULES: Final[tuple[str, ...]] = (
    "litellm",
    "token_iq.gateway.proxy.proxy_server",
    "token_iq.gateway.proxy.proxy_cli",
    # Run as a script by the container entrypoint, never imported.
    "token_iq.gateway.proxy.prisma_migration",
)


def console_script_modules(repo: pathlib.Path) -> tuple[str, ...]:
    """Modules named by `[project.scripts]`, which are entry points by definition."""
    config: Final = tomllib.loads((repo / "pyproject.toml").read_text(encoding="utf-8"))
    targets: Final = config.get("project", {}).get("scripts", {})
    return tuple(sorted({str(target).split(":", 1)[0] for target in targets.values()}))


def token_iq_modules(repo: pathlib.Path) -> tuple[str, ...]:
    """The files authored for Token IQ, which are entry points in their own right.

    They are the product. Nothing upstream imports them, so without seeding them the whole
    product would read as unreachable.
    """
    finished: Final = subprocess.run(  # noqa: S603  # fixed argument vector
        ("git", "log", "--author=Nikhil", "--diff-filter=A", "--name-only", "--format="),
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    paths: Final = {
        line.strip()
        for line in finished.stdout.splitlines()
        if line.strip().endswith(".py") and not line.startswith("token_iq/gateway/proxy/_experimental/out")
    }
    return tuple(
        sorted(
            p[: -len(".py")].replace("/", ".").removesuffix(".__init__")
            for p in paths
            if (repo / p).exists() and not p.startswith(("tests/", "scripts/"))
        )
    )


def summarise(graph: Graph) -> dict[str, object]:
    counts: Final[dict[str, int]] = {}  # mutable-ok: a tally over the verdicts
    for verdict in graph.verdicts.values():
        counts[verdict.verdict] = counts.get(verdict.verdict, 0) + 1
    return {
        "modules": len(graph.verdicts),
        "counts": counts,
        "entry_points": len(graph.entry_points),
        "unresolved_dynamic_imports": len(graph.unresolved),
        "unparsed_files": len(graph.unparsed),
        "literal_sources": len(LITERAL_SOURCES),
    }


def main(argv: Sequence[str] | None = None) -> int:
    del argv
    entries: Final = (*SEED_MODULES, *console_script_modules(REPO), *token_iq_modules(REPO))
    graph: Final = analyse(REPO, entry_points=entries, skip=SKIP, literal_sources=LITERAL_SOURCES)

    payload: Final = {
        "summary": summarise(graph),
        "entry_points": list(graph.entry_points),
        "unresolved_dynamic_imports": [dataclasses.asdict(u) for u in graph.unresolved],
        "unparsed_files": list(graph.unparsed),
        "verdicts": {name: dataclasses.asdict(v) for name, v in graph.verdicts.items()},
    }
    ARTIFACT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary: Final = payload["summary"]
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
