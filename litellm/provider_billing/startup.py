"""Registering the connectors this build ships with.

Separate from the connectors themselves so importing one does not register it, which would
make the registry depend on import order and break the duplicate-registration guard.
"""

from __future__ import annotations

from typing import Any, Final

from litellm._logging import verbose_proxy_logger


def register_openrouter_billing_connector(*, prisma_client: Any) -> None:  # any-ok: untyped runtime wrapper
    """Idempotent: a worker that restarts its scheduler must not fail on a second call."""
    from litellm.llms.custom_httpx.http_handler import get_async_httpx_client
    from litellm.provider_billing.connector import register_connector, registered_connectors
    from litellm.provider_billing.openrouter import (
        OpenRouterBillingConnector,
        build_unpriced_openrouter_lookup,
    )
    from litellm.types.llms.custom_http import httpxSpecialProvider

    if any(connector.provider == "openrouter" for connector in registered_connectors()):
        return

    register_connector(
        OpenRouterBillingConnector(
            unpriced_request_ids=build_unpriced_openrouter_lookup(prisma_client),
            http_client_factory=lambda: get_async_httpx_client(
                llm_provider=httpxSpecialProvider.LoggingCallback
            ),
        )
    )
    verbose_proxy_logger.debug("registered the openrouter billing connector")


_REGISTERED: Final = ("openrouter",)
