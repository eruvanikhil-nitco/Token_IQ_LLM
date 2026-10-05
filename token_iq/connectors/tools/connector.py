"""What a user tool connector is, and which ones exist.

Deliberately the same shape as `token_iq/connectors/billing/connector.py`: a connector never
raises, the runner drives every tool in one pass, and one tool being down or unconfigured must
not stop the others. Keeping the two protocols identical means the runner, the sync history and
the connection screens are written once rather than twice.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Final, Protocol, runtime_checkable

from token_iq.types.tool_usage import ToolFetchResult, ToolName, ToolSeatResult


@runtime_checkable
class ToolConnector(Protocol):
    @property
    def tool(self) -> ToolName: ...

    async def fetch(
        self,
        *,
        since: datetime,
        until: datetime,
        credential_name: str,
        credential_values: Mapping[str, str],
    ) -> ToolFetchResult: ...


_REGISTRY: Final[dict[str, ToolConnector]] = {}  # mutable-ok: a process-wide registry populated once at startup


def register_tool_connector(connector: ToolConnector) -> None:
    if connector.tool in _REGISTRY:
        raise ValueError(f"a tool connector for {connector.tool} is already registered")
    _REGISTRY[connector.tool] = connector


def registered_tool_connectors() -> tuple[ToolConnector, ...]:
    return tuple(_REGISTRY.values())


def clear_tool_registry_for_tests() -> None:
    _REGISTRY.clear()


@runtime_checkable
class ToolSeatConnector(Protocol):
    """A tool that can say who holds a licence but not what it costs.

    Separate from `ToolConnector` on purpose. A connector that cannot report money should not
    be able to satisfy a protocol whose whole return type is money, because the type is the
    only thing that stops a later change quietly reporting a guessed figure as a real one.
    """

    @property
    def tool(self) -> ToolName: ...

    async def fetch_seats(
        self,
        *,
        as_of: datetime,
        credential_name: str,
        credential_values: Mapping[str, str],
    ) -> ToolSeatResult: ...
