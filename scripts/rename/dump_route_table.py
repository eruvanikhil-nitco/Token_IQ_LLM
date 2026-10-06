"""Dump what the proxy serves, so a rename can be proved not to have changed it.

Phase 6 moves the engine package and rewrites every import in it. The failure that matters is not
a syntax error, which any check catches, but a module that silently stops being imported: the route
it registers disappears and the proxy answers 404 on an endpoint a customer calls. Nothing in a lint
or type pass sees that, because the code is still there and still valid.

So this takes the route table off the live FastAPI app, before and after, and the two dumps are
compared byte for byte. It imports the proxy exactly as the proxy does and reads `app.routes`; it
needs no database and starts no server.

    python scripts/rename/dump_route_table.py --out docs/plans/phase-6-routes-before.txt
    python scripts/rename/dump_route_table.py --out /tmp/after.txt
    diff docs/plans/phase-6-routes-before.txt /tmp/after.txt

One line per route, sorted, holding the path, the methods and the handler's module and name. The
handler is in there on purpose: a route that keeps its path while its handler moves to a different
module is a real change and a path-only dump would call it identical.
"""

from __future__ import annotations

import argparse
import pathlib
import sys
from collections.abc import Collection, Iterable, Sequence
from typing import Final

from pydantic import BaseModel

REPO: Final = pathlib.Path(__file__).resolve().parents[2]


class Options(BaseModel):
    """What the command line was asked for, validated rather than read off a Namespace."""

    out: pathlib.Path


class UnknownRouteShape(Exception):
    """A route neither Starlette nor FastAPI declares. Raised rather than skipped.

    A dump that quietly leaves out the shapes it does not recognise is worse than no dump: the
    comparison comes back clean because both sides are missing the same thing.
    """


def describe(route: object) -> str:
    """One line for one route: its path, its methods, and what serves it.

    Typed by asking the real classes rather than by reaching through `getattr` on `object`, so each
    attribute has its actual type. The handler is in the line on purpose: a route that keeps its path
    while its handler moves to another module is a real change, and a path-only dump calls it
    identical.
    """
    from fastapi.routing import APIRoute, APIWebSocketRoute
    from starlette.routing import Mount, Route, WebSocketRoute

    def verbs(methods: Collection[str] | None) -> str:
        return ",".join(sorted(methods)) if methods else "-"

    def named(endpoint: object) -> str:
        module: Final = getattr(endpoint, "__module__", "?")
        qualname: Final = getattr(endpoint, "__qualname__", "?")
        return f"{module}.{qualname}" if isinstance(module, str) and isinstance(qualname, str) else "?"

    if isinstance(route, (APIRoute, Route)):
        return f"{route.path}	{verbs(route.methods)}	{named(route.endpoint)}"
    if isinstance(route, (APIWebSocketRoute, WebSocketRoute)):
        return f"{route.path}	-	{named(route.endpoint)}"
    if isinstance(route, Mount):
        return f"{route.path}	-	{route.name}"
    raise UnknownRouteShape(f"{type(route).__module__}.{type(route).__qualname__}")


def lines(routes: Iterable[object]) -> tuple[str, ...]:
    return tuple(sorted({describe(route) for route in routes}))


def main(argv: Sequence[str] | None = None) -> int:
    parser: Final = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--out", required=True, help="where to write the dump")
    options: Final = Options.model_validate(vars(parser.parse_args(argv)))

    sys.path.insert(0, str(REPO))
    # Imported here rather than at module scope: importing the proxy costs about 600 MB, and
    # --help should not pay for it.
    from token_iq.gateway.proxy.proxy_server import app  # noqa: PLC0415  # see above

    options.out.parent.mkdir(parents=True, exist_ok=True)
    found: Final = lines(app.routes)
    _ = options.out.write_text("\n".join(found) + "\n", encoding="utf-8")
    sys.stdout.write(f"{len(found)} routes -> {options.out}{chr(10)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
