"""Registering the connectors this build ships with.

Separate from the connectors themselves so importing one does not register it, which would
make the registry depend on import order and break the duplicate-registration guard.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from logging import Logger
from typing import Any, Final

from litellm._logging import verbose_proxy_logger
from litellm.types.proxy.provider_billing import BillingTokenFactory

AZURE_MANAGEMENT_SCOPE: Final = "https://management.azure.com/.default"

BIGQUERY_SCOPE: Final = "https://www.googleapis.com/auth/bigquery"
"""`jobs.query` creates a query job, and BigQuery's discovery document accepts only
`bigquery`, `cloud-platform` and `cloud-platform.read-only` for that method. The narrower
`bigquery.readonly` scope is not one of them, so a token minted with it is refused."""


async def _acquire_azure_token() -> str | None:
    """The credential only carries the subscription to read; the identity that reads it is
    the proxy's own, discovered the same way `DefaultAzureCredential` always does (managed
    identity, workload identity, or the `AZURE_CLIENT_ID`/`AZURE_CLIENT_SECRET`/`AZURE_TENANT_ID`
    environment variables), never from per-credential fields the dashboard never collects."""
    from azure.identity.aio import DefaultAzureCredential

    async with DefaultAzureCredential() as credential:
        token: Final = await credential.get_token(AZURE_MANAGEMENT_SCOPE)
        return token.token


def _fetch_google_token() -> str | None:
    import google.auth
    import google.auth.transport.requests

    credentials: Final = google.auth.default(scopes=(BIGQUERY_SCOPE,))[0]
    credentials.refresh(google.auth.transport.requests.Request())
    token: Final[object] = credentials.token
    return token if isinstance(token, str) else None


async def _acquire_vertex_token() -> str | None:
    return await asyncio.to_thread(_fetch_google_token)


def build_token_factory(
    *,
    provider: str,
    acquire: Callable[[], Awaitable[str | None]],
    logger: Logger = verbose_proxy_logger,
) -> BillingTokenFactory:
    """A token factory the connectors can call without guarding it.

    Returning None rather than raising is the contract: the connector maps it to
    `NotConfigured`, and an ingestion run must not die because one cloud SDK is missing or
    one host has no ambient identity. The cause is logged, since the SDK's own exception is
    the only thing that separates a missing install from an expired login from a role the
    identity does not hold.
    """

    async def token_factory(credential_name: str, credential_values: Mapping[str, str]) -> str | None:
        try:
            return await acquire()
        except Exception as exc:
            logger.warning("could not acquire a %s billing token for credential %s: %s", provider, credential_name, exc)
            return None

    return token_factory


def register_billing_connectors(*, prisma_client: Any) -> None:  # any-ok: untyped runtime wrapper
    """Idempotent: a worker that restarts its scheduler must not fail on a second call."""
    from litellm.llms.custom_httpx.http_handler import get_async_httpx_client
    from litellm.types.llms.custom_http import httpxSpecialProvider
    from token_iq.connectors.billing.anthropic import AnthropicBillingConnector
    from token_iq.connectors.billing.azure import AzureBillingConnector
    from token_iq.connectors.billing.bedrock import BedrockBillingConnector, build_cost_explorer
    from token_iq.connectors.billing.connector import register_connector, registered_connectors
    from token_iq.connectors.billing.openai import OpenAIBillingConnector
    from token_iq.connectors.billing.openrouter import (
        OpenRouterBillingConnector,
        build_unpriced_openrouter_lookup,
    )
    from token_iq.connectors.billing.vertex import VertexBillingConnector

    def http() -> Any:  # any-ok: the proxy's httpx wrapper is untyped
        return get_async_httpx_client(llm_provider=httpxSpecialProvider.LoggingCallback)

    already: Final = {connector.provider for connector in registered_connectors()}
    candidates: Final = (
        OpenRouterBillingConnector(
            unpriced_request_ids=build_unpriced_openrouter_lookup(prisma_client),
            http_client_factory=http,
        ),
        AnthropicBillingConnector(http_client_factory=http),
        OpenAIBillingConnector(http_client_factory=http),
        BedrockBillingConnector(cost_explorer_factory=build_cost_explorer),
        AzureBillingConnector(
            http_client_factory=http,
            token_factory=build_token_factory(provider="azure", acquire=_acquire_azure_token),
        ),
        VertexBillingConnector(
            http_client_factory=http,
            token_factory=build_token_factory(provider="vertex_ai", acquire=_acquire_vertex_token),
        ),
    )

    for connector in candidates:
        if connector.provider not in already:
            register_connector(connector)
            verbose_proxy_logger.debug("registered the %s billing connector", connector.provider)
