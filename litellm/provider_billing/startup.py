"""Registering the connectors this build ships with.

Separate from the connectors themselves so importing one does not register it, which would
make the registry depend on import order and break the duplicate-registration guard.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any, Final

from litellm._logging import verbose_proxy_logger


def register_billing_connectors(*, prisma_client: Any) -> None:  # any-ok: untyped runtime wrapper
    """Idempotent: a worker that restarts its scheduler must not fail on a second call."""
    from litellm.llms.custom_httpx.http_handler import get_async_httpx_client
    from litellm.provider_billing.anthropic import AnthropicBillingConnector
    from litellm.provider_billing.azure import AzureBillingConnector
    from litellm.provider_billing.bedrock import BedrockBillingConnector, build_cost_explorer
    from litellm.provider_billing.connector import register_connector, registered_connectors
    from litellm.provider_billing.openai import OpenAIBillingConnector
    from litellm.provider_billing.openrouter import (
        OpenRouterBillingConnector,
        build_unpriced_openrouter_lookup,
    )
    from litellm.provider_billing.vertex import VertexBillingConnector
    from litellm.types.llms.custom_http import httpxSpecialProvider

    def http() -> Any:  # any-ok: the proxy's httpx wrapper is untyped
        return get_async_httpx_client(llm_provider=httpxSpecialProvider.LoggingCallback)

    async def azure_token(credential_values: Mapping[str, str]) -> str | None:
        """The credential only carries the subscription to read; the identity that reads it is
        the proxy's own, discovered the same way `DefaultAzureCredential` always does (managed
        identity, workload identity, or the `AZURE_CLIENT_ID`/`AZURE_CLIENT_SECRET`/`AZURE_TENANT_ID`
        environment variables), never from per-credential fields the dashboard never collects."""
        try:
            from azure.identity.aio import DefaultAzureCredential
        except ImportError:
            return None
        try:
            async with DefaultAzureCredential() as credential:
                token = await credential.get_token("https://management.azure.com/.default")
                return token.token
        except Exception:
            return None

    async def vertex_token(credential_values: Mapping[str, str]) -> str | None:
        try:
            import google.auth
            import google.auth.transport.requests
        except ImportError:
            return None

        def fetch_token() -> str | None:
            credentials: Any = google.auth.default(  # any-ok: google-auth ships no typed Credentials return
                scopes=("https://www.googleapis.com/auth/bigquery.readonly",)
            )[0]
            credentials.refresh(google.auth.transport.requests.Request())
            token: Any = credentials.token  # any-ok: google-auth ships no typed Credentials return
            return token if isinstance(token, str) else None

        try:
            return await asyncio.to_thread(fetch_token)
        except Exception:
            return None

    already: Final = {connector.provider for connector in registered_connectors()}
    candidates: Final = (
        OpenRouterBillingConnector(
            unpriced_request_ids=build_unpriced_openrouter_lookup(prisma_client),
            http_client_factory=http,
        ),
        AnthropicBillingConnector(http_client_factory=http),
        OpenAIBillingConnector(http_client_factory=http),
        BedrockBillingConnector(cost_explorer_factory=build_cost_explorer),
        AzureBillingConnector(http_client_factory=http, token_factory=azure_token),
        VertexBillingConnector(http_client_factory=http, token_factory=vertex_token),
    )

    for connector in candidates:
        if connector.provider not in already:
            register_connector(connector)
            verbose_proxy_logger.debug("registered the %s billing connector", connector.provider)
