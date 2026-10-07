"""Rename the Prometheus metrics: `litellm_*` becomes `token_iq_*`.

This one breaks something on purpose. A metric name is what a customer's dashboards and alert rules query,
so every one of them has to be edited on upgrade, and that is why the plan asks for the list in
`CHANGELOG.md` and for the dashboards in this repository to move with the code.

    python scripts/rename/rename_metric_names.py --audit
    python scripts/rename/rename_metric_names.py --dry-run
    python scripts/rename/rename_metric_names.py --apply

The set of names is read out of the code on every run, from the calls that construct a metric: the
`prometheus_client` classes and the three factories the Prometheus integration wraps them in. Written down
here it would drift, and a metric the code emits under a name the notes do not mention is a dashboard a
customer cannot fix.

It is a text pass rather than a syntax-tree one, because the same name appears in Python, in Grafana JSON
and in PromQL inside it, and because the 82 names are disjoint from everything else the engine calls
`litellm_…`: none of them is a Prisma accessor, a Prisma field, a config key or a metadata key, which is
checked before anything moves. Word boundaries and longest-first replacement keep a shorter name from
eating a longer one.

Each metric is also held in an attribute of the same name, `self.litellm_proxy_total_requests_metric`, so
the attribute moves with the metric: they are the same token.

`prometheus_services.py` builds a family of names at runtime from `f"litellm_{service}_{type_of_request}"`.
Those three templates are renamed too, which moves the whole family at once.
"""

from __future__ import annotations

import argparse
import ast
import functools
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
OLD_PREFIX: Final = "litellm_"
NEW_PREFIX: Final = "token_iq_"

FACTORIES: Final[frozenset[str]] = frozenset(
    {
        # prometheus_client's own classes
        "Counter",
        "Gauge",
        "Histogram",
        "Summary",
        "Info",
        "Enum",
        # the three the Prometheus integration wraps them in
        "_counter_factory",
        "_gauge_factory",
        "_histogram_factory",
    }
)

TEMPLATE: Final = re.compile(r'f"litellm_\{service\}_\{type_of_request\}"')

DERIVED: Final = ("_total", "_bucket", "_sum", "_count", "_created")
"""What Prometheus appends to a metric when it exposes it, which is the form a dashboard queries. Without
these a panel asking for `litellm_requests_metric_total` is left behind while the run reports every file
done, because a word boundary does not fall between `metric` and `_total`."""

GRAFANA: Final = re.compile(r"\blitellm_([a-z_]+)\b")
"""In a Grafana dashboard every `litellm_…` token is a metric reference, so the prefix moves on its own.
That reaches the forms Prometheus derived and the family `prometheus_services` builds at runtime, neither of
which is in the set read out of the constructor calls. Three names in these dashboards match no metric the
engine emits any more, which was true before this pass and stays true after it."""

SCOPE: Final[tuple[str, ...]] = (
    "token_iq/*.py",
    "tests/*.py",
    "enterprise/*.py",
    "cookbook/**/*.json",
    "token_iq/*.json",
    "*.yml",
    "*.yaml",
)

SKIP: Final[tuple[str, ...]] = (
    "docs/decisions/",
    "docs/plans/",
    "docs/specs/",
    "docs/status.md",
    "CHANGELOG.md",
    # Published artifacts, and the built dashboard, which is refreshed by a build rather than a rename.
    "token-iq-migrations/dist/",
    "token_iq/gateway/proxy/_experimental/out/",
)

ITS_OWN_FILES: Final[frozenset[str]] = frozenset(
    {
        "scripts/rename/rename_metric_names.py",
        "tests/gateway/test_rename_metric_names.py",
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
def every_metric() -> tuple[str, ...]:
    """Every metric the code constructs, under either prefix, longest first.

    Longest first so a shorter name cannot eat a longer one that starts with it. Read from the constructor
    calls rather than listed, because a name this does not know about is a dashboard a customer is never
    told to fix.
    """
    found: set[str] = set()  # rebind-ok: the accumulator of a scan over files
    for name in _listed(("token_iq/*.py", "enterprise/*.py")):
        if not name:
            continue
        try:
            tree = ast.parse((REPO / name).read_text(encoding="utf-8"))
        except (SyntaxError, OSError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            called = (
                node.func.id
                if isinstance(node.func, ast.Name)
                else node.func.attr
                if isinstance(node.func, ast.Attribute)
                else ""
            )
            if called not in FACTORIES:
                continue
            given = (*node.args[:1], *(word.value for word in node.keywords if word.arg == "name"))
            found.update(
                argument.value
                for argument in given
                if isinstance(argument, ast.Constant)
                and isinstance(argument.value, str)
                and argument.value.startswith((OLD_PREFIX, NEW_PREFIX))
            )
    return tuple(sorted(found, key=len, reverse=True))


def metric_names() -> tuple[str, ...]:
    """The ones still under the old prefix, which are the ones this pass moves."""
    return tuple(name for name in every_metric() if name.startswith(OLD_PREFIX))


def clashes() -> tuple[str, ...]:
    """Metric names that are also something else the engine calls `litellm_…`.

    A text pass is only safe while this is empty. A Prisma accessor, a field in the schema, a config key or
    a metadata key sharing a name with a metric would be renamed as the metric and break as the other.
    """
    schema: Final = (REPO / "schema.prisma").read_text(encoding="utf-8")
    tables: Final[list[str]] = re.findall(r'@@map\("LiteLLM_(\w+)"\)', schema)
    accessors: Final = {f"{OLD_PREFIX}{table.lower()}" for table in tables}
    fields: Final = set(re.findall(r"^\s+(litellm_\w+)\s", schema, re.MULTILINE))
    keys: Final = {
        "litellm_params",
        "litellm_settings",
        "litellm_metadata",
        "litellm_provider",
        "litellm_call_id",
        "litellm_trace_id",
        "litellm_session_id",
        "litellm_logging_obj",
        "litellm_credential_name",
        "litellm_model_name",
        "litellm_proxy",
    }
    return tuple(sorted(set(metric_names()) & (accessors | fields | keys)))


def tracked() -> tuple[pathlib.Path, ...]:
    return tuple(
        REPO / name for name in _listed(SCOPE) if name and not name.startswith(SKIP) and name not in ITS_OWN_FILES
    )


def named(path: pathlib.Path) -> str:
    try:
        return path.relative_to(REPO).as_posix()
    except ValueError:
        return path.name


def rewrite(text: str, names: Sequence[str], *, grafana: bool = False) -> tuple[str, int]:
    """The text with every metric renamed and the runtime template with it, and how many moved."""
    if grafana:
        return GRAFANA.sub(rf"{NEW_PREFIX}\1", text), len(GRAFANA.findall(text))

    if not names:
        # An alternation of nothing matches the empty string at every position, so a second run after the
        # rename would otherwise report fifteen million mentions and, with --apply, rewrite every file.
        return text, 0

    pattern: Final = _one_pattern(tuple(names))
    found: Final = pattern.findall(text)
    rewritten: Final = pattern.sub(lambda m: f"{NEW_PREFIX}{m.group(1).removeprefix(OLD_PREFIX)}", text)
    return (
        TEMPLATE.sub('f"token_iq_{service}_{type_of_request}"', rewritten),
        len(found) + len(TEMPLATE.findall(rewritten)),
    )


@functools.cache
def _one_pattern(names: tuple[str, ...]) -> re.Pattern[str]:
    """All 82 names in one alternation, longest first, so each file is read once rather than 82 times.

    A name may be followed by what Prometheus appends when it exposes the metric, and that suffix is left
    where it is: a word boundary does not fall between `metric` and `_total`, because an underscore is a word
    character, so without the lookahead a dashboard querying the derived form is quietly left behind.
    """
    alternation: Final = "|".join(re.escape(name) for name in names)
    derived: Final = "|".join(DERIVED)
    return re.compile(rf"\b({alternation})(?=(?:{derived})\b|\b)")


def run(paths: Iterable[pathlib.Path], *, write: bool, names: Sequence[str]) -> Counter[str]:
    totals: Counter[str] = Counter()  # rebind-ok: a tally across files
    for path in paths:
        try:
            before = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        after, moved = rewrite(before, names, grafana="grafana_dashboard.json" in named(path))
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
    _ = parser.add_argument("--audit", action="store_true", help="list the metrics and any clash")
    options: Final = Options.model_validate(vars(parser.parse_args(argv)))
    say: Final = out or sys.stdout

    if sum((options.apply, options.dry_run, options.audit)) != 1:
        print("pass exactly one of --apply, --dry-run and --audit", file=say)
        return 2

    names: Final = metric_names()
    sharing: Final = clashes()

    if options.audit:
        for old in sorted(names):
            print(f"{old:<56} {NEW_PREFIX}{old.removeprefix(OLD_PREFIX)}", file=say)
        print(f"\n{len(names)} metric(s)", file=say)
        print(f"names shared with something else: {sharing or 'none'}", file=say)
        return 0

    if sharing:
        print(f"refusing to run: these are a metric and something else as well: {sharing}", file=say)
        return 1

    totals: Final = run(tracked(), write=options.apply, names=names)
    for name, count in sorted(totals.items()):
        print(f"{count:>5}  {name}", file=say)
    print(f"\n{sum(totals.values())} mention(s) in {len(totals)} file(s), {len(names)} metric(s)", file=say)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
