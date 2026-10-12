"""The one place the product attaches itself to the engine.

Section 11 of the codebase plan asks for this package by name, and the failure it prevents is
specific: fourteen import-and-mount pairs sat inside an eighteen-thousand-line engine file, so a
new product endpoint meant editing that file twice, and forgetting the second half left an endpoint
that answers 404 while every one of its own tests passes.

So what is asserted here is coverage rather than wiring: every module the product means to serve is
served, with the registry read off the package rather than typed out a second time.
"""

from __future__ import annotations

import importlib
import pkgutil
from typing import Final

from fastapi import APIRouter, FastAPI

import token_iq.api
from token_iq.proxy.routers import UNMOUNTED, register, router_modules, token_iq_routers


def _modules_declaring_a_router() -> tuple[str, ...]:
    """Found by looking, so a module added tomorrow is in this list without anybody editing it."""
    return tuple(
        name
        for name in sorted(module.name for module in pkgutil.iter_modules(token_iq.api.__path__))
        if isinstance(getattr(importlib.import_module(f"token_iq.api.{name}"), "router", None), APIRouter)
    )


def _registered_app() -> FastAPI:
    app: Final = FastAPI()
    register(app)
    return app


class TestEveryEndpointTheProductMeansToServeIsServed:
    def test_every_module_with_a_router_reaches_the_app(self) -> None:
        """The regression. An endpoint that exists and is not mounted answers 404 while its own
        tests pass, because they call the router rather than the app."""
        paths: Final = frozenset(route.path for route in _registered_app().routes)

        for name in _modules_declaring_a_router():
            if name in UNMOUNTED:
                continue
            router: Final = importlib.import_module(f"token_iq.api.{name}").router
            for route in router.routes:
                assert route.path in paths, f"{name} declares {route.path} and nothing mounts it"

    def test_the_registry_covers_every_such_module(self) -> None:
        assert router_modules() == tuple(n for n in _modules_declaring_a_router() if n not in UNMOUNTED)

    def test_nothing_is_left_out_without_a_reason(self) -> None:
        # The set exists so a deliberate omission is visible. Anything in it needs a reason in the
        # module's own docstring, which is why the set is empty today.
        assert UNMOUNTED == frozenset()

    def test_a_route_is_mounted_once(self) -> None:
        # Keyed on the method as well as the path, because one path carrying a GET and a POST is
        # ordinary: /ledger/invoices lists bills and enters one. The same method twice is not, and
        # would answer from whichever copy FastAPI matched first.
        routes: Final = tuple(
            (method, route.path)
            for route in _registered_app().routes
            for method in sorted(getattr(route, "methods", ()) or ())
        )

        assert len(routes) == len(frozenset(routes))

    def test_the_product_brings_its_own_endpoints_rather_than_an_empty_list(self) -> None:
        """A registry that silently finds nothing would mount nothing, and the proxy would start
        clean with every Token IQ screen returning 404."""
        assert len(token_iq_routers()) >= 14
