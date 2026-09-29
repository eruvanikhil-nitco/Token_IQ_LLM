from __future__ import annotations

from typing import Final

import pytest

from litellm.tool_usage.connector import (
    ToolConnector,
    clear_tool_registry_for_tests,
    registered_tool_connectors,
)
from litellm.tool_usage.startup import register_tool_connectors_once


@pytest.fixture(autouse=True)
def _empty_registry():
    clear_tool_registry_for_tests()
    yield
    clear_tool_registry_for_tests()


def test_it_registers_the_connectors_that_report_spend() -> None:
    register_tool_connectors_once()

    assert {connector.tool for connector in registered_tool_connectors()} == {"claude_code", "cursor"}


def test_registering_twice_is_harmless_because_a_reloader_will_do_it() -> None:
    """Registering the same tool twice raises, and the proxy imports this more than once
    under --reload, so the second call has to be a no-op rather than a crash at boot."""
    register_tool_connectors_once()
    register_tool_connectors_once()

    assert len(registered_tool_connectors()) == 2


def test_every_registered_connector_satisfies_the_protocol() -> None:
    register_tool_connectors_once()

    assert all(isinstance(connector, ToolConnector) for connector in registered_tool_connectors())


def test_copilot_is_not_registered_here_because_it_reports_no_spend() -> None:
    """Copilot says who holds a licence, not what it cost. Driving it through usage ingestion
    would mean inventing a figure, which is exactly what the separate protocol prevents."""
    register_tool_connectors_once()

    assert "copilot" not in {connector.tool for connector in registered_tool_connectors()}
