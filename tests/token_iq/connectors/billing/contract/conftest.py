"""A server a connector can actually talk to.

Every other connector test replaces the HTTP client with a `MagicMock` returning a dictionary
we typed out ourselves. That proves the parser agrees with itself and nothing else: the URL we
build, the query we attach, the authentication scheme we use, the pagination link we follow and
what we do with a 401 are all untested, and all of them are wrong until something rejects them.

Here the connector gets a real `httpx.AsyncClient`, builds a real request and reads a real
response. Only the socket is replaced. Everything the connector decides is exercised.

A `MockTransport` rather than a listening socket, deliberately: a real port adds races and
flakes to CI and buys only TLS and the socket itself, neither of which is where these bugs live.
The request object the connector produces is identical either way.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Final

import httpx
import pytest


@dataclass(frozen=True, slots=True)
class Recorded:
    """One request the connector actually sent."""

    method: str
    url: str
    path: str
    params: Mapping[str, str]
    headers: Mapping[str, str]
    body: bytes

    @property
    def query(self) -> str:
        return httpx.URL(self.url).query.decode()


@dataclass(frozen=True, slots=True)
class Reply:
    """One response the vendor is standing in to give."""

    json: object = None
    status: int = 200
    text: str | None = None


@dataclass
class Vendor:
    """A stand-in for one provider, holding what it will say and what it was asked."""

    replies: Sequence[Reply]
    requests: list[Recorded] = field(default_factory=list)  # mutable-ok: a spy the test reads back

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(
            Recorded(
                method=request.method,
                url=str(request.url),
                path=request.url.path,
                params=dict(request.url.params),
                headers={k.lower(): v for k, v in request.headers.items()},
                body=request.content,
            )
        )
        reply: Final = (
            self.replies[len(self.requests) - 1] if len(self.requests) <= len(self.replies) else self.replies[-1]
        )
        if reply.text is not None:
            return httpx.Response(reply.status, text=reply.text)
        return httpx.Response(reply.status, json=reply.json)

    def client_factory(self) -> Callable[[], Any]:  # any-ok: connectors take an untyped client factory
        transport: Final = httpx.MockTransport(self._handle)
        client: Final = httpx.AsyncClient(transport=transport)
        return lambda: client

    @property
    def last(self) -> Recorded:
        assert self.requests, "the connector sent no request at all"
        return self.requests[-1]

    @property
    def first(self) -> Recorded:
        assert self.requests, "the connector sent no request at all"
        return self.requests[0]


@pytest.fixture
def vendor() -> Callable[..., Vendor]:
    """Build a stand-in provider that answers with the replies given, in order.

    Once the replies run out the last one repeats, so a test that only cares about the request
    does not have to spell out a reply per page.
    """

    def build(*replies: Reply) -> Vendor:
        return Vendor(replies=replies or (Reply(json={}),))

    return build
