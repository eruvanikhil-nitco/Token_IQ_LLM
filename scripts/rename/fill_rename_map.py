"""Fill in the `new` column of the rename map for the three things phase 7 renamed.

The map was built in phase 2 as an inventory of old names, with the new ones left for the phase that
decides them. Phase 7 decided the environment variables, the two config keys and the request headers, so
this writes those answers back into the map, and `write_upgrading_notes.py` generates the changelog from
it. Nothing is hand-typed: each answer is read out of the engine, so a name the engine does not actually
ask for cannot end up in a customer's upgrade notes.

    python scripts/rename/fill_rename_map.py --dry-run
    python scripts/rename/fill_rename_map.py --apply

An environment variable keeps an empty `new` when the engine does not ask for its new spelling. Those are
not renamed in this release and must not appear in the upgrade notes; the reasons, one per name, are in
`rename_env_names_in_deployment.py`, which is also where the evidence for each sits.

The request header rows the inventory found were the three that appear as Python identifiers, not the
header names themselves. They are replaced by the names the engine sends and reads.
"""

from __future__ import annotations

import argparse
import ast
import csv
import functools
import importlib.util
import io
import pathlib
import subprocess
import sys
from collections.abc import Iterable, Sequence
from typing import Final

from pydantic import BaseModel

_METRICS: Final = pathlib.Path(__file__).with_name("rename_metric_names.py")


def metric_names() -> tuple[str, ...]:
    """Every Prometheus metric the code constructs, read from the pass that renamed them.

    Borrowed rather than reimplemented, so the notes and the rename cannot disagree about what a metric is.
    """
    spec: Final = importlib.util.spec_from_file_location("rename_metric_names", _METRICS)
    assert spec is not None and spec.loader is not None
    module: Final = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("rename_metric_names", module)
    spec.loader.exec_module(module)
    names: Final[tuple[str, ...]] = module.every_metric()  # pyright: ignore[reportAny]  # loaded at runtime
    return names


REPO: Final = pathlib.Path(__file__).resolve().parents[2]
MAP: Final = REPO / "docs" / "plans" / "rename-map.csv"

OLD_ENV_PREFIX: Final = "LITELLM_"
NEW_ENV_PREFIX: Final = "TOKEN_IQ_"
OLD_HEADER_PREFIX: Final = "x-litellm-"
NEW_HEADER_PREFIX: Final = "x-token-iq-"

OLD_METRIC_PREFIX: Final = "litellm_"
NEW_METRIC_PREFIX: Final = "token_iq_"

CONFIG_KEYS: Final[dict[str, str]] = {
    "litellm_settings": "gateway_settings",
    "litellm_params": "model_params",
}

FIELDS: Final[tuple[str, ...]] = ("kind", "old", "new", "files", "note")


class Options(BaseModel):
    """The command line, typed. `parse_args` hands back `Any` for every flag."""

    apply: bool = False
    dry_run: bool = False


def engine_files() -> tuple[pathlib.Path, ...]:
    """The engine, and the migrations package beside it.

    That package installs as its own distribution and so cannot import the compatibility helper, but it
    reads both names itself, and a variable a customer sets belongs in the upgrade notes wherever the code
    that reads it happens to live.
    """
    listed: Final = subprocess.run(
        ("git", "ls-files", "token_iq/*.py", "token-iq-migrations/token_iq_migrations/*.py"),
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    return tuple(REPO / name for name in listed if name)


@functools.cache
def literals() -> tuple[str, ...]:
    """Every string literal in the engine, which is where both answers are read from.

    Cached: this parses every file in the engine, and the callers ask more than once.
    """
    found: list[str] = []  # rebind-ok: the accumulator of a scan over files
    for path in engine_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, OSError):
            continue
        found.extend(
            node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)
        )
    return tuple(found)


def env_names(found: Iterable[str]) -> frozenset[str]:
    """Environment variables the engine reads under the new prefix.

    The bare prefix is one of these literals and is not a variable, so it is excluded by length. Without
    that the inventory's own `LITELLM_` row answers as though the prefix itself had been renamed, and the
    upgrade notes open with a row telling a customer to rename nothing into nothing.
    """
    return frozenset(
        text for text in found if text.startswith(NEW_ENV_PREFIX) and text.isupper() and len(text) > len(NEW_ENV_PREFIX)
    )


def header_names(found: Iterable[str]) -> tuple[str, ...]:
    """Request and response headers the engine names, in a stable order.

    A literal counts when the whole of it is a header name; a sentence that mentions one does not. Two of
    them end in a hyphen because the engine completes them with a model group, and those are written with
    a `*` so the map reads as the name a customer sees rather than as the fragment in the source.
    """
    whole: Final = {
        f"{lowered}*" if lowered.endswith("-") else lowered
        for text in found
        for lowered in (text.lower(),)
        if lowered.startswith(NEW_HEADER_PREFIX)
        and len(lowered) > len(NEW_HEADER_PREFIX)
        and all(part.isalnum() for part in lowered.split("-") if part)
    }
    return tuple(sorted(whole))


def filled(rows: Sequence[dict[str, str]], found: Sequence[str]) -> tuple[dict[str, str], ...]:
    """The map with the answers phases 7 and 9 decided."""
    asked: Final = env_names(found)
    headers: Final = header_names(found)
    metrics: Final = metric_names()

    def answer(row: dict[str, str]) -> dict[str, str] | None:
        kind: Final = row["kind"]
        if kind == "env var":
            new = f"{NEW_ENV_PREFIX}{row['old'].removeprefix(OLD_ENV_PREFIX)}"
            if new not in asked:
                # Cleared rather than left as it was, so a name that stops being read stops being
                # advertised. Running this twice has to give the same map as running it once.
                return {**row, "new": ""}
            return {**row, "new": new, "note": "phase 7, old name still read"}
        if kind == "config key":
            return {**row, "new": CONFIG_KEYS[row["old"]], "note": "phase 7, old name still read"}
        if kind in ("request header", "metric name"):
            return None
        return row

    kept: Final = tuple(answered for row in rows for answered in (answer(row),) if answered is not None)
    replaced: Final = tuple(
        {
            "kind": "request header",
            "old": f"{OLD_HEADER_PREFIX}{name.removeprefix(NEW_HEADER_PREFIX)}",
            "new": name,
            "files": "",
            "note": "phase 7, old name still accepted, only the new one is sent",
        }
        for name in headers
    )
    # The inventory's 141 "metric name" rows were a loose match on any quoted `litellm_…` string, so they
    # are module names, config keys and metadata keys rather than metrics. Replaced by the 82 the code
    # actually constructs.
    measured: Final = tuple(
        {
            "kind": "metric name",
            "old": f"{OLD_METRIC_PREFIX}{name.removeprefix(NEW_METRIC_PREFIX)}",
            "new": name,
            "files": "",
            "note": "phase 9, the old name stops being emitted",
        }
        for name in sorted(metrics)
    )
    return kept + replaced + measured


def main(argv: Sequence[str] | None = None, out: io.TextIOBase | None = None) -> int:
    parser: Final = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--apply", action="store_true", help="write the map")
    _ = parser.add_argument("--dry-run", action="store_true", help="say what would change")
    options: Final = Options.model_validate(vars(parser.parse_args(argv)))
    say: Final = out or sys.stdout

    if options.apply == options.dry_run:
        print("pass exactly one of --apply and --dry-run", file=say)
        return 2

    with MAP.open(newline="", encoding="utf-8") as handle:
        rows: Final = tuple(dict(row) for row in csv.DictReader(handle))

    answered: Final = filled(rows, literals())
    named: Final = tuple(row for row in answered if row["new"])
    for kind in ("env var", "config key", "request header", "metric name"):
        before = sum(1 for row in rows if row["kind"] == kind)
        after = sum(1 for row in answered if row["kind"] == kind)
        with_new = sum(1 for row in named if row["kind"] == kind)
        print(f"{kind:<16} {before:>4} row(s) in, {after:>4} out, {with_new:>4} with a new name", file=say)

    if options.apply:
        with MAP.open("w", newline="", encoding="utf-8") as handle:
            writer: csv.DictWriter[str] = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(answered)
        print(f"\nwrote {len(answered)} row(s) to {MAP.relative_to(REPO).as_posix()}", file=say)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
