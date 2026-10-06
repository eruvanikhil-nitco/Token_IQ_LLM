"""Tests for the two tools that verify phase 6's rename.

These are the only evidence that the move did not change what the proxy serves or what it discovers,
so a defect in them is worse than a defect in the thing they measure: the comparison comes back clean
and the breakage ships. What matters is that neither tool can quietly leave something out.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _load(name: str):
    path = _REPO_ROOT / "scripts" / "rename" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


dump_route_table = _load("dump_route_table")
dump_dynamic_discovery = _load("dump_dynamic_discovery")


def test_a_route_shape_the_tool_does_not_know_is_refused_not_skipped() -> None:
    """The failure this prevents: a dump that leaves out what it does not recognise compares clean
    against another dump missing the same thing, so the rename looks verified when nothing was."""

    class NotARoute:
        path = "/somewhere"

    with pytest.raises(dump_route_table.UnknownRouteShape):
        dump_route_table.describe(NotARoute())


def test_a_plain_route_is_described_by_path_methods_and_handler() -> None:
    from starlette.routing import Route

    async def handler() -> None:  # pragma: no cover - never called, only described
        return None

    line = dump_route_table.describe(Route("/health", handler, methods=["GET", "HEAD"]))
    assert line.split("\t")[0] == "/health"
    assert line.split("\t")[1] == "GET,HEAD"
    # The handler, not the route's name: a route that keeps its path while its handler moves to
    # another module is a real change, and a path-only line would call it identical.
    assert line.split("\t")[2].endswith("handler")


def test_a_websocket_route_is_described_by_its_handler_not_its_name() -> None:
    """Websocket routes have no methods, so a dump keyed on methods alone would collapse them all
    onto one line and a handler that moved would not show."""
    from starlette.routing import WebSocketRoute

    async def socket() -> None:  # pragma: no cover - never called, only described
        return None

    line = dump_route_table.describe(WebSocketRoute("/v1/realtime", socket))
    assert line.split("\t")[0] == "/v1/realtime"
    assert line.split("\t")[2].endswith(".socket")


def test_a_mount_is_in_the_dump_because_losing_one_stops_a_page_being_served() -> None:
    from starlette.routing import Mount, Route

    async def handler() -> None:  # pragma: no cover - never called, only described
        return None

    line = dump_route_table.describe(Mount("/ui", routes=[Route("/", handler)], name="ui"))
    assert line.startswith("/ui\t")
    assert line.endswith("\tui")


def test_the_dump_is_sorted_and_holds_each_route_once() -> None:
    from starlette.routing import Route

    async def handler() -> None:  # pragma: no cover - never called, only described
        return None

    routes = [
        Route("/b", handler, methods=["GET"]),
        Route("/a", handler, methods=["GET"]),
        Route("/a", handler, methods=["GET"]),
    ]
    found = dump_route_table.lines(routes)
    assert [line.split("\t")[0] for line in found] == ["/a", "/b"]


@pytest.mark.parametrize(
    ("found", "expected"),
    [
        ({"aim": object(), "akto": object()}, ("aim", "akto")),
        (["one", "two"], ("one", "two")),
        (frozenset({"b", "a"}), ("a", "b")),
    ],
)
def test_a_registry_is_reduced_to_its_names_in_a_stable_order(found: object, expected: tuple[str, ...]) -> None:
    assert dump_dynamic_discovery.names_of(found) == expected


def test_a_registry_keyed_by_something_other_than_a_string_still_yields_names() -> None:
    """One of the four registries is keyed by a CallTypes enum, so the dump cannot assume strings."""
    import enum

    class CallTypes(enum.Enum):
        completion = "completion"
        embedding = "embedding"

    names = dump_dynamic_discovery.names_of({CallTypes.embedding: object(), CallTypes.completion: object()})
    assert names == ("CallTypes.completion", "CallTypes.embedding")


def test_an_empty_registry_is_reported_rather_than_omitted() -> None:
    """The real failure mode: a module path written as a string is not rewritten by the codemod, the
    import fails, and the registry comes back empty with only a debug log. A group that printed
    nothing would read as a gap in the dump instead of as a change."""
    report = dump_dynamic_discovery.report((("guardrail initializers", dict),))
    assert report == ("# guardrail initializers: 0",)


def test_each_group_counts_what_it_found() -> None:
    report = dump_dynamic_discovery.report((("prompt initializers", lambda: {"a": 1, "b": 2}),))
    assert report[0] == "# prompt initializers: 2"
    assert report[1:] == ("prompt initializers\ta", "prompt initializers\tb")
