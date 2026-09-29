"""Register the user tool connectors once, at proxy start.

Separate from `litellm/provider_billing/startup.py` because the two are configured
independently: a customer can have provider accounts with no tool accounts, which is the
common case today, and the reverse is equally possible.
"""

from __future__ import annotations

from typing import Any, Final

from litellm._logging import verbose_proxy_logger


def register_tool_connectors_once() -> None:
    """Add every tool connector that is not already registered.

    Idempotent, because the proxy can import this more than once under a reloader and
    registering twice is an error rather than a no-op.
    """
    from litellm.llms.custom_httpx.http_handler import get_async_httpx_client
    from litellm.tool_usage.claude_code import ClaudeCodeConnector
    from litellm.tool_usage.connector import register_tool_connector, registered_tool_connectors
    from litellm.tool_usage.cursor import CursorConnector
    from litellm.types.llms.custom_http import httpxSpecialProvider

    def http() -> Any:  # any-ok: the proxy's httpx wrapper is untyped
        return get_async_httpx_client(llm_provider=httpxSpecialProvider.LoggingCallback)

    already: Final = frozenset(connector.tool for connector in registered_tool_connectors())
    # Copilot is absent on purpose: it reports who holds a licence rather than what anyone
    # spent, so it satisfies the seat protocol and is driven separately from usage ingestion.
    candidates: Final = (ClaudeCodeConnector(http_client_factory=http), CursorConnector(http_client_factory=http))

    for connector in candidates:
        if connector.tool not in already:
            register_tool_connector(connector)
            verbose_proxy_logger.debug("registered tool connector %s", connector.tool)
