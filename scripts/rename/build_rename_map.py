"""Measure every place the LiteLLM name appears, and write `docs/plans/rename-map.csv`.

Phase 6 of `docs/plans/2026-10-04-independent-codebase.md` asks for this map before any rename,
and asks for it to be reviewed before the codemod runs. So this script measures and never edits.

Each row is one rename the codemod will have to make, with the number of tracked files it touches.
A row with `new` empty is one the map cannot decide on its own: those are the collisions and the
deliberate exclusions, and the `note` column says which. Rows are grouped by `kind` so a reviewer
can read one category at a time rather than ten thousand occurrences.

The counts come from the git index, not from a directory walk, so build artifacts, the virtualenv
and `node_modules` cannot inflate them.
"""

from __future__ import annotations

import csv
import dataclasses
import re
import subprocess
import sys
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Final

REPO: Final = Path(__file__).resolve().parents[2]
OUT: Final = REPO / "docs" / "plans" / "rename-map.csv"

LEGAL_OBLIGATION: Final[frozenset[str]] = frozenset({"LICENSE", "NOTICE", "CHANGELOG.md"})
"""Kept under the MIT licence the fork was granted. Deleting these is a licence violation rather
than a completed rename. See docs/decisions/0023-remove-litellm-names.md."""

HISTORICAL: Final[tuple[str, ...]] = ("docs/decisions/", "docs/plans/", "docs/specs/")

DEFERRED_TO_LATER_PHASES: Final[Mapping[str, str]] = MappingProxyType(
    {
        "census fixture": "not renamed: these are the spellings a gate greps for",
        "env var": "phase 7",
        "config key": "phase 7",
        "request header": "phase 7",
        "database model": "phase 8",
        "prisma accessor": "phase 8",
        "metric name": "phase 9",
        "cache key prefix": "phase 9",
    }
)
"""Phase 6 renames code. Anything a running installation's configuration or an existing dashboard
reads by name is a compatibility problem, and each has its own phase."""


@dataclasses.dataclass(frozen=True, slots=True)
class Rename:
    kind: str
    old: str
    new: str
    files: int
    note: str


def tracked() -> tuple[str, ...]:
    out: Final = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True).stdout
    return tuple(line for line in out.splitlines() if line)


def excluded(path: str) -> bool:
    return path in LEGAL_OBLIGATION or any(path.startswith(prefix) for prefix in HISTORICAL)


def read(path: str) -> str:
    try:
        return (REPO / path).read_text(encoding="utf-8", errors="replace")
    except (OSError, IsADirectoryError):
        return ""


NAME: Final = re.compile(r"[A-Za-z_]*[Ll][Ii][Tt][Ee][Ll][Ll][Mm][A-Za-z0-9_]*")


@dataclasses.dataclass(frozen=True, slots=True)
class Move:
    """A folder that moves whole. `path` is where it is today, because a package's name and its
    path are not the same thing here: `litellm_core_utils` lives inside `litellm/`."""

    kind: str
    old: str
    new: str
    path: str
    note: str


PACKAGE_MOVES: Final[tuple[Move, ...]] = (
    Move("package", "litellm", "token_iq.gateway", "litellm", "the engine folder moves to token_iq/gateway/"),
    Move(
        "package",
        "litellm_core_utils",
        "core_utils",
        "token_iq/gateway/litellm_core_utils",
        "the redundant prefix goes; it moves with the engine",
    ),
    Move(
        "package",
        "litellm_proxy_extras",
        "token_iq_migrations",
        "litellm-proxy-extras/litellm_proxy_extras",
        "phase 8 renames the migrations package",
    ),
    Move("test tree", "tests/test_litellm", "tests/gateway", "tests/test_litellm", "mirrors token_iq/gateway/"),
)

IDENTIFIER_SPECIAL_CASES: Final[Mapping[str, str]] = MappingProxyType(
    {
        "litellm_params": "model_params",
        "litellm_settings": "gateway_settings",
    }
)
"""Named in the plan. `litellm_params` is a model's own parameters and `litellm_settings` is the
gateway's, so neither reads correctly as `gateway_params`."""

CASE_RULES: Final[tuple[tuple[str, str], ...]] = (
    ("LiteLLM", "Gateway"),
    ("Litellm", "Gateway"),
    ("LITELLM", "GATEWAY"),
    ("litellm", "gateway"),
)


ANY_CASE: Final = re.compile(r"[Ll][Ii][Tt][Ee][Ll][Ll][Mm]")


def renamed_identifier(identifier: str) -> str:
    special: Final = IDENTIFIER_SPECIAL_CASES.get(identifier)
    if special is not None:
        return special
    for old, new in CASE_RULES:
        if old in identifier:
            return identifier.replace(old, new)
    # Spellings nobody intended, such as liteLLM and LiTeLlM. They are still the name, so they are
    # still renamed; the leading letter decides the case because nothing else about them is
    # consistent enough to read. An identifier the old name is not in at all is not this function's
    # to answer, and "" is how every other branch says so.
    renamed: Final = ANY_CASE.sub(lambda m: "Gateway" if m.group()[0].isupper() else "gateway", identifier)
    return "" if renamed == identifier else renamed


def classify(identifier: str, where: tuple[str, ...]) -> str:
    """Which phase owns this name, read from where it is written rather than from its spelling."""
    if identifier.startswith("LITELLM_") and identifier.isupper():
        return "env var"
    if identifier in ("litellm_settings", "litellm_params"):
        return "config key"
    if identifier.startswith("x-litellm") or identifier.startswith("x_litellm"):
        return "request header"
    if identifier.startswith("LiteLLM_"):
        return "database model"
    if "_" in identifier and all(p.endswith(".prisma") for p in where):
        return "database model"
    if where == ("tests/code_coverage_tests/test_inventory_census.py",):
        return "census fixture"
    if identifier.startswith("litellm_") and any("metrics" in p or "prometheus" in p for p in where):
        return "metric name"
    return "identifier"


def main() -> int:
    paths: Final = tuple(p for p in tracked() if not excluded(p))
    occurrences: Counter[str] = Counter()  # mutable-ok: a tally built by scanning, not state
    seen: dict[str, set[str]] = {}  # mutable-ok: same tally, carrying where each name was found
    for path in paths:
        for match in NAME.finditer(read(path)):
            found = match.group()  # rebind-ok: the loop variable of a scan, one match per iteration
            occurrences[found] += 1
            seen.setdefault(found, set()).add(path)

    # A package row counts the files that MOVE, which is a question about paths. Counting content
    # occurrences here reported 0 for the test tree, whose own name appears inside no file.
    moved: Final[Mapping[str, int]] = MappingProxyType(
        {
            move.old: sum(1 for path in paths if path == move.path or path.startswith(f"{move.path}/"))
            for move in PACKAGE_MOVES
        }
    )
    rows: Final = tuple(
        Rename(kind=move.kind, old=move.old, new=move.new, files=moved[move.old], note=move.note)
        for move in PACKAGE_MOVES
    ) + tuple(
        sorted(
            (
                Rename(
                    kind=kind,
                    old=identifier,
                    new="" if kind in DEFERRED_TO_LATER_PHASES else renamed_identifier(identifier),
                    files=len(where),
                    note=DEFERRED_TO_LATER_PHASES.get(kind, ""),
                )
                for identifier, where in ((identifier, tuple(sorted(found))) for identifier, found in seen.items())
                for kind in (classify(identifier, where),)
            ),
            key=lambda row: (row.kind, -row.files, row.old),
        )
    )

    # Two old names landing on one new name. Every pair found so far is the same concept spelled
    # two ways (LiteLLMLogging and LitellmLogging are both local aliases of one Logging class), or
    # two module-local names that never share a namespace. The note says so per row rather than in
    # prose somewhere else, because the codemod has to be read against this file.
    folded: Final[Mapping[str, tuple[str, ...]]] = MappingProxyType(
        {
            new: others
            for new, others in (
                (new, tuple(sorted(r.old for r in rows if r.new == new and r.kind == "identifier")))
                for new in {r.new for r in rows if r.kind == "identifier" and r.new != ""}
            )
            if len(others) > 1
        }
    )
    # An identifier row for a name that is also a package move is not a contradiction: the package
    # becomes token_iq.gateway while the name a module binds becomes gateway, which is both of the
    # plan's rules. It is said per row, because a reviewer reading only the identifier rows would
    # otherwise apply the wrong one of the two.
    also_a_package: Final[frozenset[str]] = frozenset(move.old for move in PACKAGE_MOVES)
    noted: Final = tuple(
        dataclasses.replace(
            row,
            note=row.note
            or (
                f"the package itself becomes "
                f"{next(m.new for m in PACKAGE_MOVES if m.old == row.old)}; this row is the bound name"
                if row.kind == "identifier" and row.old in also_a_package
                else ""
            )
            or (
                f"folded with {', '.join(o for o in folded[row.new] if o != row.old)}"
                if row.kind == "identifier" and row.new in folded
                else ""
            ),
        )
        for row in rows
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(("kind", "old", "new", "files", "note"))
        writer.writerows((row.kind, row.old, row.new, row.files, row.note) for row in noted)

    by_kind: Final = Counter(row.kind for row in noted)
    undecided: Final = tuple(row for row in noted if row.new == "" and row.note == "")
    report: Final = (
        (f"{len(noted)} rows over {len(paths)} tracked files -> {OUT.relative_to(REPO)}",)
        + tuple(f"  {count:>6}  {kind}" for kind, count in sorted(by_kind.items(), key=lambda i: -i[1]))
        + (f"{len(undecided)} rows the rules could not decide",)
        + tuple(f"  {row.old}  ({row.files} files)" for row in undecided)
        + (f"{len(folded)} new names that two or more old names fold onto",)
        + tuple(f"  {new}  <-  {', '.join(olds)}" for new, olds in sorted(folded.items()))
    )
    sys.stdout.write(chr(10).join(report) + chr(10))
    return 0


if __name__ == "__main__":
    sys.exit(main())
