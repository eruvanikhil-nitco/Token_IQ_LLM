"""Count the name that is being removed, split by the phase that removes it.

One total going down tells nobody which phase is working. Phase 6 moves the Python package,
phase 7 the environment variables and headers, phase 8 the database models and phase 9 the
metrics and the UI, so each is counted on its own and each phase can show its own line
reaching zero.

Vendored dependencies and the committed UI bundle are excluded. Counting generated files is
how the source document arrived at 521,641 occurrences, roughly three and a half times the
real figure.
"""

from __future__ import annotations

import dataclasses
import json
import pathlib
import re
from collections.abc import Mapping
from typing import Final

EXCLUDED_PARTS: Final[frozenset[str]] = frozenset({"node_modules", ".git", "__pycache__", ".venv", ".next"})
EXCLUDED_PREFIXES: Final[tuple[str, ...]] = ("litellm/proxy/_experimental/out/",)

# Phase 10 of the rename permits the name to survive in legal text and in history. Counting
# those keeps the target above zero forever, and a measure that cannot be satisfied stops
# being read, so they are reported separately instead of being folded into the target.
ALLOWLISTED_PREFIXES: Final[tuple[str, ...]] = (
    "docs/decisions/",
    "docs/plans/",
    "docs/superpowers/plans/",
    "docs/superpowers/specs/",
    ".superpowers/",
)
ALLOWLISTED_FILES: Final[frozenset[str]] = frozenset({"LICENSE", "NOTICE", "CHANGELOG.md"})

TEXT_SUFFIXES: Final[frozenset[str]] = frozenset(
    {
        ".py", ".pyi", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".json", ".yml", ".yaml", ".toml",
        ".md", ".sh", ".ps1", ".prisma", ".tf", ".sql", ".txt", ".env", ".cfg", ".ini", ".html",
        ".css", ".Dockerfile", ".example",
    }
)

# Files that carry no extension but are still text we must count. LICENSE and NOTICE matter
# because they are the two the rename deliberately leaves alone.
EXTENSIONLESS_TEXT: Final[frozenset[str]] = frozenset(
    {"Dockerfile", "Makefile", "LICENSE", "NOTICE", ".env.example", ".env"}
)

PYTHON_SUFFIXES: Final[frozenset[str]] = frozenset({".py", ".pyi"})
UI_SUFFIXES: Final[frozenset[str]] = frozenset({".ts", ".tsx", ".js", ".jsx", ".mjs"})

CATEGORIES: Final[tuple[str, ...]] = (
    "occurrences",
    "python",
    "ui",
    "env_vars",
    "headers",
    "metrics",
    "config_keys",
    "prisma_models",
    "commands",
)

ANY_CASE: Final = re.compile(r"litellm", re.IGNORECASE)
ENV_VAR: Final = re.compile(r"\bLITELLM_[A-Z0-9_]+\b")
HEADER: Final = re.compile(r"x-litellm-[a-z0-9-]+", re.IGNORECASE)
# A metric is declared inside a collector, not merely mentioned, so `litellm_logging.foo()`
# must not count. Requiring the quote is what separates the two.
METRIC: Final = re.compile(r"[\"']litellm_[a-z0-9_]+[\"']")
CONFIG_KEY: Final = re.compile(r"\blitellm_(settings|params)\b")
PRISMA_MODEL: Final = re.compile(r"^model\s+LiteLLM_\w+", re.MULTILINE)
COMMAND: Final = re.compile(r"^\s*(litellm|litellm-proxy|lite)\s*=", re.MULTILINE)


@dataclasses.dataclass(frozen=True, slots=True)
class Census:
    files: int
    scanned: int
    categories: Mapping[str, int]
    allowlisted: int
    """Occurrences in history and legal text, which phase 10 permits to remain."""


def is_excluded(path: pathlib.PurePosixPath) -> bool:
    posix: Final = path.as_posix()
    if any(posix.startswith(prefix) for prefix in EXCLUDED_PREFIXES):
        return True
    return any(part in EXCLUDED_PARTS for part in path.parts)


def is_allowlisted(path: pathlib.PurePosixPath) -> bool:
    posix: Final = path.as_posix()
    return posix in ALLOWLISTED_FILES or any(posix.startswith(prefix) for prefix in ALLOWLISTED_PREFIXES)


def _is_text(path: pathlib.Path) -> bool:
    return path.suffix in TEXT_SUFFIXES or path.name in EXTENSIONLESS_TEXT


def _counts_for(path: pathlib.Path, body: str) -> Mapping[str, int]:
    total: Final = len(ANY_CASE.findall(body))
    return {
        "occurrences": total,
        "python": total if path.suffix in PYTHON_SUFFIXES else 0,
        "ui": total if path.suffix in UI_SUFFIXES else 0,
        "env_vars": len(ENV_VAR.findall(body)),
        "headers": len(HEADER.findall(body)),
        "metrics": len(METRIC.findall(body)),
        "config_keys": len(CONFIG_KEY.findall(body)),
        "prisma_models": len(PRISMA_MODEL.findall(body)),
        "commands": len(COMMAND.findall(body)),
    }


def count_tree(root: pathlib.Path) -> Census:
    totals: Final[dict[str, int]] = {name: 0 for name in CATEGORIES}  # mutable-ok: a running sum over a file walk
    holding: int = 0  # rebind-ok: counter over the walk
    scanned: int = 0  # rebind-ok: counter over the walk
    allowlisted: int = 0  # rebind-ok: counter over the walk

    for path in sorted(root.rglob("*")):
        if not path.is_file() or not _is_text(path):
            continue
        relative = pathlib.PurePosixPath(path.relative_to(root).as_posix())
        if is_excluded(relative):
            continue
        scanned += 1
        try:
            body = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if is_allowlisted(relative):
            allowlisted += len(ANY_CASE.findall(body))
            continue
        counts = _counts_for(path, body)
        if counts["occurrences"] > 0:
            holding += 1
        for name, value in counts.items():
            totals[name] += value

    return Census(files=holding, scanned=scanned, categories=dict(totals), allowlisted=allowlisted)


def main() -> int:
    repo: Final = pathlib.Path(__file__).resolve().parents[2]
    artifact: Final = repo / "docs" / "superpowers" / "plans" / "2026-10-04-phase-0-name-census.json"
    counted: Final = count_tree(repo)
    artifact.write_text(json.dumps(dataclasses.asdict(counted), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{counted.categories['occurrences']} occurrences in {counted.files} files ({counted.scanned} scanned)")
    print(f"  (plus {counted.allowlisted} in history and legal text, which phase 10 permits)")
    for name in CATEGORIES:
        print(f"  {name:<16} {counted.categories[name]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
