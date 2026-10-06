"""Dump what the engine discovers by importing module paths written as strings.

This is the one failure class that phase 6 can cause and nothing else can see. The codemod rewrites
`import` statements, which libcst understands. It does not understand
`f"litellm.proxy.guardrails.guardrail_hooks.{item}"`, and `litellm/llms/__init__.py` goes further
and builds its path from a filesystem walk prefixed with the literal `"litellm."`. A move that
leaves those strings alone still compiles, still lints, still type-checks, and the registry they
feed comes back empty: every guardrail silently stops being available.

The route table catches the subset of these that register routes, because the route disappears.
The registries here register no route, so they need their own before-and-after.

    python scripts/rename/dump_dynamic_discovery.py --out docs/plans/phase-6-discovery-before.txt

One line per discovered name, sorted, grouped by registry. An empty group is printed as such rather
than omitted, so a registry that stops discovering anything reads as a change instead of a gap.
"""

from __future__ import annotations

import argparse
import pathlib
import sys
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Final

from pydantic import BaseModel, TypeAdapter

REPO: Final = pathlib.Path(__file__).resolve().parents[2]


class Options(BaseModel):
    """What the command line was asked for, validated rather than read off a Namespace."""

    out: pathlib.Path


_NAMES: Final = TypeAdapter(tuple[str, ...])
"""The shape every discovery is reduced to before it is written out.

The four functions below are upstream and unannotated, so what they return is unknown to the type
checker. Rather than thread that through, each result is reduced to names here and validated into a
`tuple[str, ...]`, which is the only shape the rest of this file handles.
"""


def names_of(found: object) -> tuple[str, ...]:
    """The keys of whatever a discovery function returned, as readable strings, validated.

    Keys are enum members as often as strings, so `str()` rather than the key itself: the point is a
    stable line to compare, not the key's own type.
    """
    if isinstance(found, Mapping):
        keys = sorted(str(key) for key in found)  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]  # upstream registry is unannotated
        return _NAMES.validate_python(keys)
    if isinstance(found, (list, tuple, set, frozenset)):
        items = sorted(str(item) for item in found)  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]  # same
        return _NAMES.validate_python(items)
    return _NAMES.validate_python((str(found),))


def discoveries() -> tuple[tuple[str, Callable[[], object]], ...]:
    """Every registry the engine fills by importing a module path it built as a string."""
    from litellm.llms import discover_guardrail_translation_mappings
    from litellm.proxy.guardrails.guardrail_registry import (
        get_guardrail_class_from_hooks,
        get_guardrail_initializer_from_hooks,
    )
    from litellm.proxy.prompts.prompt_registry import get_prompt_initializer_from_integrations

    return (
        ("guardrail initializers", get_guardrail_initializer_from_hooks),
        ("guardrail classes", get_guardrail_class_from_hooks),
        ("prompt initializers", get_prompt_initializer_from_integrations),
        ("guardrail translations", discover_guardrail_translation_mappings),
    )


def report(groups: Iterable[tuple[str, Callable[[], object]]]) -> tuple[str, ...]:
    return tuple(
        line
        for label, discover in groups
        for found in (names_of(discover()),)
        for line in ((f"# {label}: {len(found)}",) + tuple(f"{label}\t{name}" for name in found))
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser: Final = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--out", required=True, help="where to write the dump")
    options: Final = Options.model_validate(vars(parser.parse_args(argv)))

    sys.path.insert(0, str(REPO))
    lines: Final = report(discoveries())

    out: Final = options.out
    out.parent.mkdir(parents=True, exist_ok=True)
    _ = out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    counted: Final = sum(1 for line in lines if not line.startswith("#"))
    sys.stdout.write(f"{counted} discovered names -> {out}{chr(10)}")
    sys.stdout.write("\n".join(line for line in lines if line.startswith("#")) + chr(10))
    return 0


if __name__ == "__main__":
    sys.exit(main())
