"""Rename what the engine calls itself in traces, logs and metrics it sends elsewhere.

Phase 9's logs bullet. 84 dotted names appear as OpenTelemetry span attributes, Datadog span names and
Datadog metrics, and a customer's trace queries and dashboards reference them, so this breaks those the same
way the Prometheus rename does and belongs in the upgrade notes beside it.

    python scripts/rename/rename_observability_names.py --audit
    python scripts/rename/rename_observability_names.py --dry-run
    python scripts/rename/rename_observability_names.py --apply

The set is read out of the engine, not listed here, and then those exact names are renamed wherever they
appear including in tests. That matters because the same pattern over the test tree would also match 42
strings that are not observability names at all: module paths like `litellm.caching.caching`, engine
attributes like `litellm.drop_params`, and two hostnames. None of the 84 is any of those, and none is an
importable module path, which the audit checks before anything moves.

`gen_ai.*` attributes keep their names, as the plan asks. They are a standard, not ours. The *value* under
`gen_ai.framework` does move, because it names the framework and the framework is Token IQ now; that is
handled beside the logger and tracer defaults rather than by the pattern, since each is the bare string
`litellm` and renaming that everywhere would reach a great deal more than observability.
"""

from __future__ import annotations

import argparse
import ast
import functools
import importlib
import io
import pathlib
import re
import subprocess
import sys
from collections import Counter
from collections.abc import Iterable, Sequence
from typing import Final

from pydantic import BaseModel

REPO: Final = pathlib.Path(__file__).resolve().parents[2]
OLD_PREFIX: Final = "litellm."
NEW_PREFIX: Final = "token_iq."

DOTTED: Final = re.compile(r"^(?:litellm|token_iq)\.[a-z_][a-z_0-9]*(\.[a-z_][a-z_0-9]*)*$")
"""A lowercase dotted name under either prefix, which is the shape every one of these has. Both, so the
scan keeps finding them after the rename and `observability_names` can be empty rather than meaningless."""

SCOPE: Final[tuple[str, ...]] = ("token_iq/*.py", "tests/*.py", "enterprise/*.py")

SKIP: Final[tuple[str, ...]] = (
    "docs/decisions/",
    "docs/plans/",
    "docs/specs/",
    "docs/status.md",
    "CHANGELOG.md",
    "token_iq/gateway/proxy/_experimental/out/",
)

ITS_OWN_FILES: Final[frozenset[str]] = frozenset(
    {
        "scripts/rename/rename_observability_names.py",
        "tests/gateway/test_rename_observability_names.py",
    }
)


class Options(BaseModel):
    """The command line, typed. `parse_args` hands back `Any` for every flag."""

    apply: bool = False
    dry_run: bool = False
    audit: bool = False


def _listed(patterns: Iterable[str]) -> tuple[str, ...]:
    return tuple(
        subprocess.run(
            ("git", "ls-files", *patterns), cwd=REPO, capture_output=True, text=True, check=True
        ).stdout.splitlines()
    )


@functools.cache
def every_name() -> tuple[str, ...]:
    """Every dotted observability name the engine uses, under either prefix, longest first."""
    found: set[str] = set()  # rebind-ok: the accumulator of a scan over files
    for name in _listed(("token_iq/*.py",)):
        if not name:
            continue
        try:
            tree = ast.parse((REPO / name).read_text(encoding="utf-8"))
        except (SyntaxError, OSError):
            continue
        found.update(
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and DOTTED.match(node.value)
        )
    return tuple(sorted(found, key=len, reverse=True))


def observability_names() -> tuple[str, ...]:
    """The ones still under the old prefix, which are the ones this pass moves."""
    return tuple(name for name in every_name() if name.startswith(OLD_PREFIX))


def module_paths() -> tuple[str, ...]:
    """Names that would also resolve as a module under the new prefix.

    A text pass is only safe while this is empty. One of these would be renamed as an attribute name and
    break as an import, and the pass refuses to run rather than guess which it is.
    """
    return tuple(name for name in observability_names() if _imports(name.replace(OLD_PREFIX, "token_iq.gateway.", 1)))


def _imports(candidate: str) -> bool:
    try:
        _ = importlib.import_module(candidate)
    except Exception:  # noqa: BLE001  # any failure means it is not an importable module, which is the answer
        return False
    return True


def tracked() -> tuple[pathlib.Path, ...]:
    return tuple(
        REPO / name for name in _listed(SCOPE) if name and not name.startswith(SKIP) and name not in ITS_OWN_FILES
    )


def named(path: pathlib.Path) -> str:
    try:
        return path.relative_to(REPO).as_posix()
    except ValueError:
        return path.name


@functools.cache
def _one_pattern(names: tuple[str, ...]) -> re.Pattern[str]:
    """All the names in one alternation, longest first, so each file is read once rather than 84 times."""
    return re.compile(rf"\b({'|'.join(re.escape(name) for name in names)})\b")


def rewrite(text: str, names: Sequence[str]) -> tuple[str, int]:
    """The text with every observability name renamed, and how many moved."""
    if not names:
        # An alternation of nothing matches the empty string everywhere, so a second run after the rename
        # would otherwise rewrite every file it is given.
        return text, 0
    pattern: Final = _one_pattern(tuple(names))
    return (
        pattern.sub(lambda m: f"{NEW_PREFIX}{m.group(1).removeprefix(OLD_PREFIX)}", text),
        len(pattern.findall(text)),
    )


def run(paths: Iterable[pathlib.Path], *, write: bool, names: Sequence[str]) -> Counter[str]:
    totals: Counter[str] = Counter()  # rebind-ok: a tally across files
    for path in paths:
        try:
            before = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        after, moved = rewrite(before, names)
        if not moved:
            continue
        totals[named(path)] = moved
        if write:
            _ = path.write_text(after, encoding="utf-8")
    return totals


def main(argv: Sequence[str] | None = None, out: io.TextIOBase | None = None) -> int:
    parser: Final = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--apply", action="store_true", help="write the changes")
    _ = parser.add_argument("--dry-run", action="store_true", help="say what would change")
    _ = parser.add_argument("--audit", action="store_true", help="list the names and any that is a module")
    options: Final = Options.model_validate(vars(parser.parse_args(argv)))
    say: Final = out or sys.stdout

    if sum((options.apply, options.dry_run, options.audit)) != 1:
        print("pass exactly one of --apply, --dry-run and --audit", file=say)
        return 2

    names: Final = observability_names()

    if options.audit:
        for old in sorted(names):
            print(f"{old:<62} {NEW_PREFIX}{old.removeprefix(OLD_PREFIX)}", file=say)
        print(f"\n{len(names)} name(s)", file=say)
        print(f"names that are also a module path: {module_paths() or 'none'}", file=say)
        return 0

    shared: Final = module_paths()
    if shared:
        print(f"refusing to run: these are also module paths: {shared}", file=say)
        return 1

    totals: Final = run(tracked(), write=options.apply, names=names)
    for name, count in sorted(totals.items()):
        print(f"{count:>5}  {name}", file=say)
    print(f"\n{sum(totals.values())} mention(s) in {len(totals)} file(s), {len(names)} name(s)", file=say)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
