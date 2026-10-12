"""Mounting Token IQ's own API on the gateway's app.

The one place the product attaches itself to the engine. Section 11 of
`docs/plans/2026-10-04-independent-codebase.md` asks for this package by name, and the reason is
the direction of the dependency: the engine is inherited code that serves requests, and it should
not know what this product is. Before this, fourteen import-and-mount pairs sat inside
`proxy_server.py`, so every new product endpoint meant editing an eighteen-thousand-line engine
file, and forgetting the second half of the pair left an endpoint that returns 404 while its tests
pass.

The registry is read off the package rather than typed out again. A module under `token_iq/api/`
that declares a `router` is an endpoint the product means to serve, so that is the rule, and a new
one is mounted by existing.
"""

from __future__ import annotations

import importlib
import pkgutil
from typing import Final, Protocol

from fastapi import APIRouter

import token_iq.api

UNMOUNTED: Final[frozenset[str]] = frozenset()
"""Modules that declare a router the product deliberately does not serve.

Empty, and a module belongs here only with a reason: an endpoint that exists but is not reachable
is worse than one that does not exist, because its tests pass either way.
"""


class MountsRouters(Protocol):
    """What this needs of the app, which is one method.

    A protocol rather than FastAPI's own type so this module says what it uses. Anything that can
    mount a router satisfies it, which is also what makes the registration testable without
    building the engine's app.
    """

    def include_router(self, router: APIRouter) -> None: ...


def _router_of(name: str) -> APIRouter | None:
    """The router one product module declares, if it declares one.

    `isinstance` is the validation, not the annotation: a module's attributes are untyped by
    nature, so what comes back is checked rather than trusted.
    """
    module: Final = importlib.import_module(f"token_iq.api.{name}")
    declared: Final = getattr(module, "router", None)  # pyright: ignore[reportAny]  # module attributes are untyped
    return declared if isinstance(declared, APIRouter) else None


def router_modules() -> tuple[str, ...]:
    """Every module under `token_iq/api/` that declares a router, in a stable order."""
    return tuple(
        name
        for name in sorted(module.name for module in pkgutil.iter_modules(token_iq.api.__path__))
        if name not in UNMOUNTED and _router_of(name) is not None
    )


def token_iq_routers() -> tuple[APIRouter, ...]:
    """The product's routers, as the app should mount them."""
    return tuple(router for name in router_modules() if (router := _router_of(name)) is not None)


def register(app: MountsRouters) -> None:
    """Mount every Token IQ endpoint on the gateway's app.

    Called once, where the engine assembles its own routes. The engine's only knowledge of the
    product is this call.
    """
    for router in token_iq_routers():
        app.include_router(router)
