"""The API documentation a customer reads must not name LiteLLM.

This reads the generated OpenAPI schema rather than the source, because the schema is what a
customer actually sees on the API Reference screen and on `/docs`. Prose reaches it from four
different places, an endpoint docstring, a Pydantic `description=`, a field example and a
schema title, and a source scan would have to know all four and would still miss the fifth.

Schema and field *names* are out of scope on purpose. Renaming a class such as `LiteLLMKeyType`
changes the public schema and breaks any client that generated types from it, which is a
different decision from rewriting a sentence. It is recorded as open in the product design doc.
"""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import Final

REPO: Final = Path(__file__).resolve().parents[2]

FORBIDDEN: Final = re.compile(r"LiteLLM|litellm\.ai|berri\.ai", re.IGNORECASE)

PROSE_KEYS: Final[frozenset[str]] = frozenset({"description", "summary", "title", "example"})
"""The keys whose values a reader sees as words. `$ref` and the schema names it points at are
deliberately absent: those are identifiers, and renaming them is a separate decision."""


def _is_generated_title(path: Sequence[str], text: str, owner: str | None = None) -> bool:
    """Whether this title is just an identifier that Pydantic echoed back.

    A request field named `litellm_call_id` produces the title "Litellm Call Id", and a model
    class named `LiteLLMKeyType` produces that same string as its schema title. Rewriting
    either means renaming the thing, which changes the request a client sends or the schema it
    generated types from. That is the naming decision this gate deliberately leaves alone, and
    it is recorded as open in the product design doc.
    """
    if len(path) < 2 or path[-1] != "title":
        return False
    names: Final = tuple(name for name in (path[-2], owner) if name)
    return any(text in (name, name.replace("_", " ").title()) for name in names)


MAX_SHOWN: Final = 40


def _prose(node: object, path: Sequence[str], owner: str | None = None) -> Iterator[tuple[str, str]]:
    """Every string a customer reads, with the path that produced it.

    `owner` carries the name of the thing being described, which for a query parameter lives in
    a sibling `name` field rather than in the path, so a generated title can still be spotted.
    """
    if isinstance(node, Mapping):
        named: Final = node.get("name")
        here: Final = named if isinstance(named, str) else owner
        for key, value in node.items():
            yield from _prose(value, (*path, str(key)), here)
    elif isinstance(node, (list, tuple)):
        for index, value in enumerate(node):
            yield from _prose(value, (*path, str(index)), owner)
    elif isinstance(node, str) and path and path[-1] in PROSE_KEYS and not _is_generated_title(path, node, owner):
        yield (".".join(path), node)


def offenders(schema: Mapping[str, object]) -> tuple[tuple[str, str], ...]:
    return tuple((where, text) for where, text in _prose(schema, ()) if FORBIDDEN.search(text))


def _schema_from_app() -> Mapping[str, object]:
    """Build the app and generate its schema, so this gate cannot read a stale file."""
    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    from litellm.proxy.proxy_server import app

    return app.openapi()


def main() -> int:
    schema: Final = _schema_from_app()
    found: Final = offenders(schema)
    if not found:
        print("No API documentation a customer reads names LiteLLM.")
        return 0

    print(f"{len(found)} pieces of customer-facing API documentation name LiteLLM:\n")
    for where, text in found[:MAX_SHOWN]:
        collapsed = " ".join(text.split())
        print(f"  {where}\n    {collapsed[:160]}")
    if len(found) > MAX_SHOWN:
        print(f"\n  ... and {len(found) - MAX_SHOWN} more")
    print(
        "\nRewrite the prose. Remove a link to another product's documentation rather than "
        "replacing it with an invented Token IQ URL: a dead link is worse than none."
    )
    return 1


if __name__ == "__main__":
    if "--dump" in sys.argv:
        json.dump(_schema_from_app(), sys.stdout)
        raise SystemExit(0)
    raise SystemExit(main())
