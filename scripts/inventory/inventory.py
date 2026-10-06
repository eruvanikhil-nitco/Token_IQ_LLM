"""Build the feature inventory skeleton from the reachability graph.

One row per top-level folder in `litellm/` and `token_iq/gateway/proxy/`, plus the loose Python files
at those two levels, which the source document's "one row per folder" would have missed.

This writes the measurable columns only. What each folder does, and the proposal, are added
by a person reading it, because the whole point of the `unproven` verdict is that a script
does not get to decide.
"""

from __future__ import annotations

import json
import pathlib
from collections.abc import Mapping, Sequence
from typing import Final

REPO: Final = pathlib.Path(__file__).resolve().parents[2]
GRAPH: Final = REPO / "docs" / "plans" / "2026-10-04-phase-0-reachability.json"
OUT: Final = REPO / "docs" / "plans" / "2026-10-04-phase-0-inventory-data.json"


def _module_of(path: pathlib.Path) -> str:
    relative: Final = path.relative_to(REPO).with_suffix("")
    parts: Final = tuple(relative.parts)
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def _lines(path: pathlib.Path) -> int:
    try:
        return len(path.read_text(encoding="utf-8", errors="ignore").splitlines())
    except OSError:
        return 0


def _rows_for(parent: pathlib.Path, verdicts: Mapping[str, Mapping[str, object]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []  # mutable-ok: built once over a directory listing

    for child in sorted(parent.iterdir()):
        if child.name in {"__pycache__", "_experimental"} or child.name.startswith("."):
            continue
        if child.is_dir():
            files = [p for p in child.rglob("*.py") if "__pycache__" not in p.parts]
            if not files:
                continue
            modules = [_module_of(p) for p in files]
            known = [verdicts[m] for m in modules if m in verdicts]
            used = sum(1 for v in known if v["verdict"] == "used")
            type_only = sum(1 for v in known if v["verdict"] == "used-type-only")
            reached = sorted({str(e) for v in known for e in (v["reached_from"] or ())})
            rows.append(
                {
                    "path": child.relative_to(REPO).as_posix() + "/",
                    "kind": "folder",
                    "files": len(files),
                    "lines": sum(_lines(p) for p in files),
                    "modules_known": len(known),
                    "used": used,
                    "used_type_only": type_only,
                    "unproven": len(known) - used - type_only,
                    "reached_from": reached[:4],
                }
            )
        elif child.suffix == ".py" and child.name != "__init__.py":
            module = _module_of(child)
            verdict = verdicts.get(module)
            rows.append(
                {
                    "path": child.relative_to(REPO).as_posix(),
                    "kind": "file",
                    "files": 1,
                    "lines": _lines(child),
                    "modules_known": 1 if verdict else 0,
                    "used": 1 if verdict and verdict["verdict"] == "used" else 0,
                    "used_type_only": 1 if verdict and verdict["verdict"] == "used-type-only" else 0,
                    "unproven": 1 if verdict and verdict["verdict"] == "unproven" else 0,
                    "reached_from": sorted({str(e) for e in (verdict["reached_from"] or ())})[:4] if verdict else [],
                }
            )
    return rows


def main(argv: Sequence[str] | None = None) -> int:
    del argv
    graph: Final = json.loads(GRAPH.read_text(encoding="utf-8"))
    verdicts: Final = graph["verdicts"]

    rows: Final = [*_rows_for(REPO / "litellm", verdicts), *_rows_for(REPO / "litellm" / "proxy", verdicts)]
    fully_unproven: Final = [r for r in rows if r["modules_known"] and r["unproven"] == r["modules_known"]]

    OUT.write_text(json.dumps({"rows": rows}, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"{len(rows)} rows")
    print(f"  folders: {sum(1 for r in rows if r['kind'] == 'folder')}")
    print(f"  loose files: {sum(1 for r in rows if r['kind'] == 'file')}")
    print(f"  wholly unproven: {len(fully_unproven)}")
    print(f"  lines in wholly unproven rows: {sum(int(r['lines']) for r in fully_unproven)}")
    print()
    for row in sorted(fully_unproven, key=lambda r: -int(r["lines"])):
        print(f"  {row['lines']:>7}  {row['files']:>4}f  {row['path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
