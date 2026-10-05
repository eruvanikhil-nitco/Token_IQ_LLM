"""Repoint every reference to the modules phase 3 moved into `token_iq/`.

The map below is the record of what moved. It is applied to code and configuration only:
`docs/decisions/` and `docs/plans/` hold what was true when they were written, and the
phase 0 baseline is keyed on paths that must not move under it.

An import that is missed raises `ModuleNotFoundError` on the first run, which is the safe
failure. A module path written inside a string does not fail: `mock.patch` resolves it
lazily, so a test whose patch stops applying goes green having patched nothing. That is why
the dotted and the slashed forms are both rewritten here, and why the search that found them
looked for the text rather than running the suite.
"""

from __future__ import annotations

import functools
import pathlib
import re
import sys
from collections.abc import Iterator, Mapping
from types import MappingProxyType
from typing import Final

REPO: Final = pathlib.Path(__file__).resolve().parents[1]

SCOPE: Final[tuple[str, ...]] = ("litellm", "token_iq", "tests", "scripts", ".github")
LOOSE_FILES: Final[tuple[str, ...]] = ("pyproject.toml", "Makefile", "pyrightconfig.json")
SUFFIXES: Final[frozenset[str]] = frozenset({".py", ".pyi", ".toml", ".cfg", ".yml", ".yaml", ".json", ".md", ".txt"})

# Split so the map survives the script being run over its own directory: spelled whole, the
# keys match the very rules they define and the first run turns the record into an identity
# map, which then reports a clean no-op having rewritten nothing.
_OLD: Final = "litellm" + "."

# Old dotted module path -> new dotted module path.
MOVES: Final[Mapping[str, str]] = MappingProxyType(
    {
        _OLD + "provider_billing": "token_iq.connectors.billing",
        _OLD + "tool_usage": "token_iq.connectors.tools",
        _OLD + "ledger": "token_iq.ledger",
        _OLD + "attribution": "token_iq.attribution",
        _OLD + "overview": "token_iq.overview",
        _OLD + "seats": "token_iq.seats",
        _OLD + "recommendations": "token_iq.recommendations",
        _OLD + "pricing": "token_iq.pricing",
        **{
            _OLD + f"repositories.{name}_repository": f"token_iq.repositories.{name}_repository"
            for name in (
                "attribution_rule",
                "gap",
                "gateway_spend",
                "invoice",
                "ledger",
                "overview",
                "provider_sync_run",
                "provider_usage_fact",
                "recommendation_state",
                "seat",
                "tool_usage_fact",
            )
        },
    }
)

# Longest first, so `token_iq.repositories.ledger_repository` is never half-matched by a
# shorter key, and `\b` so `token_iq.overview` never swallows `litellm.overviewer`.
RULES: Final[tuple[tuple[re.Pattern[str], str], ...]] = tuple(
    rule
    for old, new in sorted(MOVES.items(), key=lambda pair: -len(pair[0]))
    for rule in (
        (re.compile(rf"\b{re.escape(old)}\b"), new),
        (re.compile(rf"\b{re.escape(old.replace('.', '/'))}\b"), new.replace(".", "/")),
    )
)


def candidates() -> Iterator[pathlib.Path]:
    """Every file in scope, skipping the historical records and anything vendored."""
    roots: Final = (*(REPO / name for name in SCOPE), *(REPO / name for name in LOOSE_FILES))
    for root in roots:
        paths = root.rglob("*") if root.is_dir() else (root,)
        for path in paths:
            if not path.is_file() or (path.suffix and path.suffix not in SUFFIXES):
                continue
            if "node_modules" in path.parts or "__pycache__" in path.parts:
                continue
            if path == pathlib.Path(__file__).resolve():
                continue
            yield path


def rewrite(text: str) -> str:
    return functools.reduce(lambda carried, rule: rule[0].sub(rule[1], carried), RULES, text)


def main() -> int:
    """Rewrite in place, reading and writing with newline translation off.

    Translating line endings would rewrite every line of every file it touched, which is how
    a codemod earlier in this programme changed 16,140 lines when 320 were intended.
    """
    changed: Final = tuple(
        path
        for path in candidates()
        if _rewrite_file(path)
    )
    for path in changed:
        print(path.relative_to(REPO).as_posix())
    print(f"{len(changed)} files rewritten")
    return 0


def _rewrite_file(path: pathlib.Path) -> bool:
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            original: Final = handle.read()
    except UnicodeDecodeError:
        # Two pickled `data_map.txt` caches carry a .txt suffix. Reported rather than
        # skipped quietly, because a file this cannot read is a file it cannot vouch for.
        print(f"not text, left alone: {path.relative_to(REPO).as_posix()}", file=sys.stderr)
        return False
    updated: Final = rewrite(original)
    if updated == original:
        return False
    with path.open("w", encoding="utf-8", newline="") as handle:
        _ = handle.write(updated)
    return True


if __name__ == "__main__":
    sys.exit(main())
