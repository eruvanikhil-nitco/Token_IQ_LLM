"""What a provider billing connector is, and which ones exist.

A connector never raises. The runner drives every provider in one pass, and one provider
being down or unconfigured must not stop the others, which is what an exception would do.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Final, Protocol, runtime_checkable

from litellm.types.proxy.provider_billing import FetchResult


@runtime_checkable
class BillingConnector(Protocol):
    @property
    def provider(self) -> str: ...

    async def fetch(
        self,
        *,
        since: datetime,
        until: datetime,
        credential_name: str,
        credential_values: Mapping[str, str],
    ) -> FetchResult: ...


_REGISTRY: Final[dict[str, BillingConnector]] = {}  # mutable-ok: a process-wide registry populated once at startup


def register_connector(connector: BillingConnector) -> None:
    if connector.provider in _REGISTRY:
        raise ValueError(f"a billing connector for {connector.provider} is already registered")
    _REGISTRY[connector.provider] = connector


def registered_connectors() -> tuple[BillingConnector, ...]:
    return tuple(_REGISTRY.values())


def clear_registry_for_tests() -> None:
    _REGISTRY.clear()
