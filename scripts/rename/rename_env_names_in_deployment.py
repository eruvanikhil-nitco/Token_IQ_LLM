"""Rename the engine's environment variables where a deployment sets them.

Phase 7 asks for the rename in `.env.example`, the compose files, the Terraform variables and the docs,
after the engine has been taught to read both names. The risk here is the opposite of the one inside the
engine: a deployment that sets a name nothing reads leaves a knob silently off, and the file looks right.

So a name is only renamed when the engine demonstrably asks for its new spelling, and the list of those
is read out of the engine's own source every run rather than written down here. `--audit` prints every
name left behind with where it was found, which is how a reader checks that each one was left on purpose.

    python scripts/rename/rename_env_names_in_deployment.py --audit
    python scripts/rename/rename_env_names_in_deployment.py --dry-run
    python scripts/rename/rename_env_names_in_deployment.py --apply

Names that stay, and why, as of the run that produced this:

- `LITELLM_LICENSE` is read by the enterprise package, which is not in this repository
- `LITELLM_LOCAL_MODEL_COST_MAP` is read by nothing: the price map is always the bundled one since the
  remote fetch was removed, so the variable is dead configuration that CI and the tests still set
- `LITELLM_MIGRATION_DIR` is read by `litellm-proxy-extras`, which installs as its own distribution and
  so cannot import the compatibility helper. Phase 8 renames that package and its variables together
- `LITELLM_IMAGE`, `LITELLM_VERSION`, `LITELLM_BUILD_IMAGE`, `LITELLM_RUNTIME_IMAGE`,
  `LITELLM_PROXY_EXTRAS_PATH`, `LITELLM_PKG_MIGRATIONS_PATH`, `LITELLM_PYTHON`,
  `LITELLM_MIGRATION_SCRIPT` and `LITELLM_MIGRATION_INTERPRETER` are build and CI plumbing read by
  shell and by Docker, not by the engine. Phase 9 covers the Docker and CI names
- `LITELLM_API_KEY` in CI is a test harness variable. The provider's key is `TOKEN_IQ_PROXY_API_KEY`
"""

from __future__ import annotations

import argparse
import ast
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
OLD_PREFIX: Final = "LITELLM_"
NEW_PREFIX: Final = "TOKEN_IQ_"
OLD_NAME: Final = re.compile(r"\bLITELLM_([A-Z0-9_]+)\b")

SCOPE: Final[tuple[str, ...]] = (
    ".env.example",
    "docker-compose.yml",
    "docker-compose.hardened.yml",
    "Dockerfile",
    "docker/",
    "terraform/",
    "docs/",
    ".github/",
    ".circleci/",
    "deploy/",
)

SKIP: Final[tuple[str, ...]] = (
    # Records that keep the name forever, per docs/decisions/0023-remove-litellm-names.md, and that `docs/`
    # would otherwise reach. `LICENSE`, `NOTICE` and `CHANGELOG.md` keep it too and need no entry here:
    # `SCOPE` is an allow-list and none of them sit under one of its paths.
    "docs/decisions/",
    "docs/plans/",
    "docs/specs/",
    "docs/status.md",
    # Installed as its own distribution, so it cannot import the compatibility helper.
    "litellm-proxy-extras/",
)

ITS_OWN_FILES: Final[frozenset[str]] = frozenset(
    {
        "scripts/rename/rename_env_names_in_deployment.py",
        "tests/gateway/test_rename_env_names_in_deployment.py",
    }
)
"""Both name the old prefix on purpose. A pass that rewrites itself matches nothing afterwards and
reports a clean run."""


class Options(BaseModel):
    """The command line, typed. `parse_args` hands back `Any` for every flag."""

    apply: bool = False
    dry_run: bool = False
    audit: bool = False


class Left(BaseModel):
    """A name this pass did not rename, for a person to check."""

    name: str
    where: str
    line: int


def tracked(scope: Iterable[str] = SCOPE) -> tuple[pathlib.Path, ...]:
    listed: Final = subprocess.run(
        ("git", "ls-files", *scope), cwd=REPO, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    return tuple(REPO / name for name in listed if name and not name.startswith(SKIP) and name not in ITS_OWN_FILES)


def named(path: pathlib.Path) -> str:
    try:
        return path.relative_to(REPO).as_posix()
    except ValueError:
        return path.name


def asked_for() -> frozenset[str]:
    """Every environment variable the engine reads under the new prefix.

    Read out of the engine rather than listed here, so this cannot claim a name the engine does not ask
    for. A name the engine only mentions in prose counts too: `compat.env` is what turns a mention into
    a read, and every mention left in the engine names a variable it reads.
    """
    found: set[str] = set()  # rebind-ok: the accumulator of a scan over files
    for name in subprocess.run(
        ("git", "ls-files", "token_iq/*.py"), cwd=REPO, capture_output=True, text=True, check=True
    ).stdout.splitlines():
        if not name:
            continue
        try:
            tree = ast.parse((REPO / name).read_text(encoding="utf-8"))
        except (SyntaxError, OSError):
            continue
        found.update(
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and node.value.startswith(NEW_PREFIX)
            and node.value.isupper()
        )
    return frozenset(found)


def rewrite(text: str, known: frozenset[str]) -> tuple[str, int]:
    """The text with every renamed variable moved on, and how many moved."""
    moved: Counter[str] = Counter()  # rebind-ok: a tally for the return value

    def swap(match: re.Match[str]) -> str:
        new = f"{NEW_PREFIX}{match.group(1)}"
        if new not in known:
            return match.group(0)
        moved[new] += 1
        return new

    return OLD_NAME.sub(swap, text), sum(moved.values())


def left_behind(text: str, path: str, known: frozenset[str]) -> tuple[Left, ...]:
    return tuple(
        Left(name=f"{OLD_PREFIX}{match.group(1)}", where=path, line=number)
        for number, line in enumerate(text.split("\n"), start=1)
        for match in OLD_NAME.finditer(line)
        if f"{NEW_PREFIX}{match.group(1)}" not in known
    )


def run(paths: Iterable[pathlib.Path], *, write: bool, known: frozenset[str]) -> tuple[Counter[str], tuple[Left, ...]]:
    """Every file rewritten, with a tally per file and everything left for a person."""
    totals: Counter[str] = Counter()  # rebind-ok: a tally across files
    remaining: list[Left] = []  # rebind-ok: what the audit reports

    for path in paths:
        name = named(path)
        try:
            before = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        after, moved = rewrite(before, known)
        remaining.extend(left_behind(after, name, known))
        if not moved:
            continue
        totals[name] = moved
        if write:
            _ = path.write_text(after, encoding="utf-8")

    return totals, tuple(remaining)


def main(argv: Sequence[str] | None = None, out: io.TextIOBase | None = None) -> int:
    parser: Final = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--apply", action="store_true", help="write the changes")
    _ = parser.add_argument("--dry-run", action="store_true", help="say what would change")
    _ = parser.add_argument("--audit", action="store_true", help="list the names left behind")
    options: Final = Options.model_validate(vars(parser.parse_args(argv)))
    say: Final = out or sys.stdout

    if sum((options.apply, options.dry_run, options.audit)) != 1:
        print("pass exactly one of --apply, --dry-run and --audit", file=say)
        return 2

    known: Final = asked_for()
    totals, remaining = run(tracked(), write=options.apply, known=known)

    if options.audit:
        counts: Final = Counter(item.name for item in remaining)
        for name, count in counts.most_common():
            first = next(item for item in remaining if item.name == name)
            print(f"{count:>4}  {name}\n      first at {first.where}:{first.line}", file=say)
        print(f"\nnames the engine does not ask for, left alone: {len(counts)}", file=say)
        return 0

    for name, count in sorted(totals.items()):
        print(f"{count:>4}  {name}", file=say)
    print(f"\n{sum(totals.values())} name(s) moved in {len(totals)} file(s)", file=say)
    print(f"{len(known)} name(s) the engine asks for under the new prefix", file=say)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
