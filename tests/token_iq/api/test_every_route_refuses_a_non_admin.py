"""No Token IQ route answers a caller who is not an administrator with a success.

Measured on 13 Oct 2026: every endpoint under `token_iq/api/` is proxy-admin-only, through twelve
copies of the same three-line check. Twelve copies means a thirteenth endpoint can be written
without one, and nothing fails: its own tests pass, the page works, and the first person to notice
is whoever sees somebody else's spend.

So the rule is asserted over the registry rather than per endpoint. Every route the product mounts
is called with a caller who holds each non-administrator role, and none of them may come back with a
2xx. A new endpoint is swept in by existing, which is the same property that makes
`token_iq/proxy/routers.py` mount it.

The sweep sends no database. A route that refuses first never reaches one, so a 500 from a missing
database is itself a finding: it means the refusal came second.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict

from token_iq.gateway.proxy._types import GatewayUserRoles, UserAPIKeyAuth
from token_iq.gateway.proxy.auth.user_api_key_auth import user_api_key_auth
from token_iq.proxy.routers import token_iq_routers

NON_ADMIN_ROLES: Final = (
    GatewayUserRoles.INTERNAL_USER,
    GatewayUserRoles.INTERNAL_USER_VIEW_ONLY,
    GatewayUserRoles.TEAM,
    GatewayUserRoles.CUSTOMER,
)

PATH_PARAM: Final = re.compile(r"\{[^}]+\}")

EMPTY_BODY: Final = b"{}"
"""Nothing the route can accept, so what answers is its own rule rather than its body."""

JSON: Final[Mapping[str, str]] = MappingProxyType({"content-type": "application/json"})

ALLOWED_TO_ANSWER: Final[frozenset[str]] = frozenset(
    {
        # Projects and seats answer a person about their own team or themselves by design, and both
        # carry their own tests for what they then show. Everything else here covers every team.
        "/project/list",
        "/project/info",
        "/project/daily/activity",
        "/seats/mine",
    }
)
"""Routes whose own rule is narrower than administrator, each with its own scope test."""


def _app() -> FastAPI:
    # No docs routes: they answer everybody by design and are the harness rather than the product.
    app: Final = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    for router in token_iq_routers():
        app.include_router(router)
    return app


class _Probe(BaseModel):
    """One request this sweep makes, with every required query parameter filled.

    Filling them is what gives the sweep teeth. A route that requires `period_start` answers 422
    before its own code runs, so a route whose rule had been deleted still came back with a refusal
    of sorts and the deletion survived. With the parameters supplied the handler is reached, and the
    only thing left to answer is the rule.
    """

    model_config = ConfigDict(frozen=True)

    method: str
    path: str
    query: str


def _value_for(name: str) -> str:
    if any(word in name for word in ("start", "end", "day", "date", "month")):
        return "2026-09-01"
    if any(word in name for word in ("days", "limit", "page", "size")):
        return "1"
    return "probe"


def _is_required(field: object) -> bool:
    """Whether a query parameter has no default, which is what makes it answer 422 when absent.

    The flag sits on the `field_info` rather than on the field wrapper, where `required` reads as
    None. Getting this wrong is silent in the direction that matters: no parameter is filled, every
    route answers 422, and the sweep stops reaching the rule it exists to check.
    """
    info: Final = getattr(field, "field_info", None)
    required: Final = getattr(info, "is_required", None)
    return bool(required()) if callable(required) else False


def _required_query(route: object) -> str:
    """The query string a route needs to get past validation, read off its own dependant."""
    dependant: Final = getattr(route, "dependant", None)
    fields: Final = getattr(dependant, "query_params", ()) if dependant is not None else ()
    return "&".join(
        f"{name}={_value_for(name)}"
        for name in (str(getattr(field, "name", "")) for field in fields if _is_required(field))
        if name
    )


def _probes(app: FastAPI) -> tuple[_Probe, ...]:
    return tuple(
        _Probe(method=method, path=str(getattr(route, "path", "")), query=_required_query(route))
        for route in app.routes
        for method in sorted(getattr(route, "methods", frozenset()))
        if method != "HEAD" and str(getattr(route, "path", "")) not in ALLOWED_TO_ANSWER
    )


def _call(client: TestClient, probe: _Probe):
    # A path parameter is filled with something syntactically valid; the refusal must come before
    # anything looks it up.
    filled: Final = PATH_PARAM.sub("probe", probe.path) + (f"?{probe.query}" if probe.query else "")
    if probe.method == "GET":
        return client.get(filled)
    if probe.method == "DELETE":
        return client.delete(filled)
    if probe.method == "PUT":
        return client.put(filled, content=EMPTY_BODY, headers=JSON)
    if probe.method == "PATCH":
        return client.patch(filled, content=EMPTY_BODY, headers=JSON)
    return client.post(filled, content=EMPTY_BODY, headers=JSON)


@pytest.mark.parametrize("role", NON_ADMIN_ROLES)
def test_no_route_answers_a_non_admin_with_a_success(role: GatewayUserRoles) -> None:
    app: Final = _app()
    app.dependency_overrides[user_api_key_auth] = lambda: UserAPIKeyAuth(
        user_role=role, user_id="u-1", team_id="t-1", token="hashed"
    )
    client: Final = TestClient(app, raise_server_exceptions=False)

    answered: Final = tuple(
        f"{probe.method} {probe.path} -> {_call(client, probe).status_code}"
        for probe in _probes(app)
        if 200 <= _call(client, probe).status_code < 300
    )

    assert answered == (), f"{role} was answered by {len(answered)} route(s): {answered}"


def test_no_route_reaches_a_database_before_refusing() -> None:
    """A 5xx would mean the refusal came after the data was read, which is a filter rather than a
    rule. A refusal and a complaint about a missing parameter are the only two answers allowed: the
    parameter check runs first for routes that require one, and it tells the caller nothing the
    published schema does not."""
    app: Final = _app()
    app.dependency_overrides[user_api_key_auth] = lambda: UserAPIKeyAuth(
        user_role=GatewayUserRoles.INTERNAL_USER, user_id="u-1", team_id="t-1", token="hashed"
    )
    client: Final = TestClient(app, raise_server_exceptions=False)

    wrong: Final = tuple(
        f"{probe.method} {probe.path} -> {_call(client, probe).status_code}"
        for probe in _probes(app)
        if probe.method in ("GET", "DELETE") and _call(client, probe).status_code != 403
    )

    assert wrong == (), f"{len(wrong)} route(s) answered some other way: {wrong}"


def test_a_route_that_needs_nothing_from_the_caller_refuses_outright() -> None:
    """The routes where nothing can short-circuit ahead of the rule, so the rule is what answers."""
    app: Final = _app()
    app.dependency_overrides[user_api_key_auth] = lambda: UserAPIKeyAuth(
        user_role=GatewayUserRoles.INTERNAL_USER, user_id="u-1", team_id="t-1", token="hashed"
    )
    client: Final = TestClient(app, raise_server_exceptions=False)

    for path in ("/provider/connections", "/data-quality", "/ledger/uploads", "/pricing/rates"):
        assert client.get(path).status_code == 403, path


WRITES: Final = (
    (
        "/pricing/rates",
        '{"provider":"openai","basis":"discount","percent_off":"20","effective_from":"2026-09-01",'
        '"source":"a contract"}',
    ),
    (
        "/ledger/invoices",
        '{"provider":"openai","period_start":"2026-09-01","period_end":"2026-09-30","total":"100"}',
    ),
    (
        "/pricing/currency-rates",
        '{"source_currency":"EUR","target_currency":"USD","rate":"1.1","effective_from":"2026-09-01",'
        '"source":"the bank"}',
    ),
)
"""Writes sent with a body the server accepts, so what refuses them is the rule.

A body is validated before the handler runs, so an empty one answers 422 and the rule is never
reached. These three are the writes a non-administrator would most want: recording a rate, entering
a bill, and booking a currency rate.
"""


@pytest.mark.parametrize(("path", "body"), WRITES)
@pytest.mark.parametrize("role", NON_ADMIN_ROLES)
def test_a_write_with_a_valid_body_is_refused(role: GatewayUserRoles, path: str, body: str) -> None:
    app: Final = _app()
    app.dependency_overrides[user_api_key_auth] = lambda: UserAPIKeyAuth(
        user_role=role, user_id="u-1", team_id="t-1", token="hashed"
    )
    client: Final = TestClient(app, raise_server_exceptions=False)

    answer: Final = client.post(path, content=body.encode(), headers=JSON)

    assert answer.status_code == 403, f"{role} {path} -> {answer.status_code} {answer.text[:200]}"


def test_the_sweep_actually_reaches_the_routes() -> None:
    """The test that stops the two above passing by sweeping nothing, which is how an enumeration
    test dies quietly."""
    probes: Final = _probes(_app())
    addressed: Final = frozenset((probe.method, probe.path) for probe in probes)

    assert len(probes) > 40
    assert ("GET", "/overview") in addressed
    assert ("GET", "/ledger/lines") in addressed
    # And the parameters are really filled, which is what reaches the rule rather than validation.
    overview: Final = next(probe for probe in probes if probe.path == "/overview")
    assert "period_start=2026-09-01" in overview.query
    assert "period_end=2026-09-01" in overview.query
