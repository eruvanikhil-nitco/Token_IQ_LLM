"""Decide which of the rename map's identifiers phase 6 may rename, and write it down.

Phase 6's rule is "identifiers containing the name become Gateway/gateway". Applied literally to all
2,217 rows that would rename things a running installation reads, so this works out which rows are
Python's own names and which are a calling convention wearing an identifier's clothes, and commits the
answer to `docs/plans/phase-6-identifier-scope.csv` for review before anything is renamed.

    python scripts/rename/scope_identifiers.py

A row is deferred when any of these is true of it, because each one means something outside this
repository knows the name:

- **It is written as a whole string literal somewhere.** `kwargs.get("litellm_logging_obj")` is how a
  caller passes that argument, so the name is the calling convention. 410 rows, and together they are
  72% of all the uses, which is why applying the rule literally would have been so damaging
- **It is a field of a Pydantic model or a TypedDict.** Those serialise, so the field name is in a
  response body. `litellm_credential_name` is declared in five of them
- **It is a key in a committed JSON or YAML file.** `litellm_provider` is a key in 3,559 entries of the
  2.1MB price file, so renaming the Python name alone breaks every price lookup and renaming both is a
  data-format change
- **It is the name of a module or package.** Renaming one means moving a file and rewriting its imports,
  which is a different operation from renaming a name inside a file

A CapWords name is exempt from the string-literal test, and only that test. A class written as a string
is a forward reference, not a key: `"LiteLLMLoggingObj"` appears 172 times that way and every one is an
annotation. The convention is what makes this safe to tell apart, and Python's own conventions are the
only thing that can.
"""

from __future__ import annotations

import ast
import csv
import pathlib
import re
import subprocess
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Final

from pydantic import TypeAdapter

REPO: Final = pathlib.Path(__file__).resolve().parents[2]
MAP: Final = REPO / "docs" / "plans" / "rename-map.csv"
OUT: Final = REPO / "docs" / "plans" / "phase-6-identifier-scope.csv"

SERIALISED_BASES: Final[frozenset[str]] = frozenset(
    {"BaseModel", "TypedDict", "LiteLLMPydanticObjectBase", "GatewayPydanticObjectBase"}
)
"""Base classes whose attributes become field names in a payload."""

DATA_KEY: Final = re.compile(r'"(\w*[Ll]ite[Ll][Ll][Mm]\w*)"\s*:')
YAML_KEY: Final = re.compile(r"^\s*-?\s*(\w*[Ll]ite[Ll][Ll][Mm]\w*)\s*:", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class Decision:
    old: str
    new: str
    files: str
    verdict: str
    because: str


def tracked(*patterns: str) -> tuple[pathlib.Path, ...]:
    out: Final = subprocess.run(
        ["git", "ls-files", *patterns], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout
    return tuple(REPO / line for line in out.splitlines() if line and "node_modules" not in line)


def read(path: pathlib.Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def capwords(name: str) -> bool:
    stripped: Final = name.lstrip("_")
    return bool(stripped) and stripped[0].isupper()


def identifier_rows() -> tuple[Mapping[str, str], ...]:
    with MAP.open(encoding="utf-8") as handle:
        return tuple(row for row in csv.DictReader(handle) if row["kind"] == "identifier")


def written_as_strings(paths: Iterable[pathlib.Path], wanted: frozenset[str]) -> frozenset[str]:
    """Names that appear as a whole string literal, which means something passes them by name."""
    found: set[str] = set()  # rebind-ok: a tally built by scanning
    for path in paths:
        try:
            tree = ast.parse(read(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in wanted:
                found.add(node.value)
    return frozenset(found)


def python_names(paths: Iterable[pathlib.Path], wanted: frozenset[str]) -> frozenset[str]:
    """Names that are written as a Python identifier somewhere, in any of the positions one can take.

    A row that never appears here is not Python's to rename. 746 rows are that, and they are not all the
    dashboard's: 292 are in the Go of the Terraform provider, 97 in documentation, 78 in JSON, 34 in CI
    config, and 97 in TypeScript, while 383 do appear in a `.py` file and only ever inside a string, a
    docstring or a comment. `getGlobalLitellmHeaderName` has 108 uses and not one of them is Python.
    Saying so is better than listing them as this phase's and renaming nothing.
    """
    found: set[str] = set()  # rebind-ok: a tally built by scanning

    def take(name: str | None) -> None:
        if name is not None and name in wanted:
            found.add(name)

    for path in paths:
        try:
            tree = ast.parse(read(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                take(node.id)
            elif isinstance(node, ast.Attribute):
                take(node.attr)
            elif isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                take(node.name)
            elif isinstance(node, (ast.arg, ast.keyword)):
                take(node.arg)
            elif isinstance(node, ast.alias):
                take(node.asname)
                for part in node.name.split("."):
                    take(part)
    return frozenset(found)


def serialised_fields(paths: Iterable[pathlib.Path], wanted: frozenset[str]) -> frozenset[str]:
    """Names declared as an attribute of something that serialises, which puts them in a payload."""
    found: set[str] = set()  # rebind-ok: a tally built by scanning

    def base_names(node: ast.ClassDef) -> set[str]:
        return {
            base.id if isinstance(base, ast.Name) else base.attr
            for base in node.bases
            if isinstance(base, (ast.Name, ast.Attribute))
        }

    for path in paths:
        try:
            tree = ast.parse(read(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            names = base_names(node)
            if not (names & SERIALISED_BASES or any("Base" in n or "Model" in n or "Dict" in n for n in names)):
                continue
            for statement in node.body:
                declared = (
                    statement.target.id
                    if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name)
                    else statement.targets[0].id
                    if isinstance(statement, ast.Assign)
                    and len(statement.targets) == 1
                    and isinstance(statement.targets[0], ast.Name)
                    else None
                )
                if declared is not None and declared in wanted:
                    found.add(declared)
    return frozenset(found)


def data_keys(paths: Iterable[pathlib.Path], wanted: frozenset[str]) -> frozenset[str]:
    """Names used as a key in a committed JSON or YAML file, which makes them a data format."""
    return frozenset(
        name
        for path in paths
        for text in (read(path),)
        if "itellm" in text or "iteLLM" in text
        for name in _found_keys(text)
        if name in wanted
    )


_KEY_NAMES: Final = TypeAdapter(tuple[str, ...])


def _found_keys(text: str) -> tuple[str, ...]:
    """Validated, because `findall` hands back `list[Any]` and these are key names."""
    return _KEY_NAMES.validate_python(
        [found.group(1) for found in DATA_KEY.finditer(text)] + [found.group(1) for found in YAML_KEY.finditer(text)]
    )


def module_names(paths: Iterable[pathlib.Path]) -> frozenset[str]:
    """Every module and package name in the tree. Renaming one of these moves a file."""
    collected: Final = tuple(paths)
    return frozenset(path.stem for path in collected) | frozenset(
        parent.name for path in collected for parent in path.parents if parent.name
    )


def decide(
    rows: Iterable[Mapping[str, str]],
    *,
    strings: frozenset[str],
    fields: frozenset[str],
    keys: frozenset[str],
    modules: frozenset[str],
    in_python: frozenset[str],
) -> tuple[Decision, ...]:
    """One verdict per row, from the five things the scans found.

    The five sets are parameters rather than looked up here, so each clause below can be exercised on
    its own. Asking the repository instead would make every test a test of this checkout, and dropping
    a clause would not fail any of them.
    """

    def verdict(name: str) -> tuple[str, str]:
        if name not in in_python:
            return "deferred", "not a Python identifier here, so a pass over Python cannot rename it"
        if name in modules:
            return "deferred", "a module or package name, so renaming it moves a file"
        if name in fields:
            return "deferred", "a field of something that serialises, so it is in a payload"
        if name in keys:
            return "deferred", "a key in a committed data file, so it is a data format"
        if name in strings and not capwords(name):
            return "deferred", "written as a string somewhere, so something passes it by name"
        return "phase 6", "a name Python uses and nothing outside this repository reads"

    return tuple(
        Decision(old=row["old"], new=row["new"], files=row["files"], verdict=call, because=why)
        for row in rows
        for call, why in (verdict(row["old"]),)
    )


def scan(rows: Iterable[Mapping[str, str]]) -> tuple[Decision, ...]:
    """Every scan the repository needs, then the verdicts."""
    listed: Final = tuple(rows)
    wanted: Final = frozenset(row["old"] for row in listed)
    python: Final = tracked("*.py")
    return decide(
        listed,
        strings=written_as_strings(python, wanted),
        fields=serialised_fields(python, wanted),
        keys=data_keys(tracked("*.json", "*.yaml", "*.yml"), wanted),
        modules=module_names(python),
        in_python=python_names(python, wanted),
    )


def main() -> int:
    decisions: Final = scan(identifier_rows())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(("old", "new", "files", "verdict", "because"))
        writer.writerows(
            (d.old, d.new, d.files, d.verdict, d.because)
            for d in sorted(decisions, key=lambda d: (d.verdict, -int(d.files), d.old))
        )

    mine: Final = tuple(d for d in decisions if d.verdict == "phase 6")
    waiting: Final = tuple(d for d in decisions if d.verdict != "phase 6")
    report: Final = (
        f"{len(decisions)} identifier rows -> {OUT.relative_to(REPO)}",
        f"  phase 6 : {len(mine):>5} rows, {sum(int(d.files) for d in mine):>6} file-hits",
        f"  deferred: {len(waiting):>5} rows, {sum(int(d.files) for d in waiting):>6} file-hits",
        *(
            f"      {reason}: {sum(1 for d in waiting if d.because == reason)}"
            for reason in sorted({d.because for d in waiting})
        ),
    )
    sys.stdout.write("\n".join(report) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
