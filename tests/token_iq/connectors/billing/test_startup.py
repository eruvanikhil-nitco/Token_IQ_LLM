from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest


def test_every_shipped_connector_is_registered():
    """A connector that exists but is never registered is dead code that looks like a
    feature. The registry is what the runner iterates."""
    from token_iq.connectors.billing.connector import clear_registry_for_tests, registered_connectors
    from token_iq.connectors.billing.startup import register_billing_connectors

    clear_registry_for_tests()
    register_billing_connectors(prisma_client=MagicMock())

    assert {connector.provider for connector in registered_connectors()} == {
        "openrouter",
        "anthropic",
        "openai",
        "bedrock",
        "azure",
        "vertex_ai",
    }
    clear_registry_for_tests()


def test_registering_twice_is_harmless():
    """A worker that restarts its scheduler calls this again, and the registry refuses
    duplicates by design. Startup must not die on the second call."""
    from token_iq.connectors.billing.connector import clear_registry_for_tests, registered_connectors
    from token_iq.connectors.billing.startup import register_billing_connectors

    clear_registry_for_tests()
    register_billing_connectors(prisma_client=MagicMock())
    register_billing_connectors(prisma_client=MagicMock())

    assert len(registered_connectors()) == 6
    clear_registry_for_tests()


def test_every_billing_provider_has_a_registered_connector():
    """BILLING_PROVIDERS is what the endpoints and the dashboard enumerate. A provider in
    that set with no connector answers every probe with 'this build ships no connector',
    which reads as a broken deployment rather than a missing feature."""
    from token_iq.connectors.billing.connector import clear_registry_for_tests, registered_connectors
    from token_iq.connectors.billing.credential_purpose import BILLING_PROVIDERS
    from token_iq.connectors.billing.startup import register_billing_connectors

    clear_registry_for_tests()
    register_billing_connectors(prisma_client=MagicMock())

    assert {connector.provider for connector in registered_connectors()} == BILLING_PROVIDERS
    clear_registry_for_tests()


@pytest.mark.asyncio
async def test_a_token_factory_answers_the_token_the_sdk_minted():
    from token_iq.connectors.billing.startup import build_token_factory

    async def acquire():
        return "minted-token"

    factory = build_token_factory(provider="vertex_ai", acquire=acquire, logger=MagicMock(spec=logging.Logger))

    assert await factory("vertex-prod", {}) == "minted-token"


@pytest.mark.parametrize(
    "failure",
    [ImportError("no module named 'azure.identity'"), RuntimeError("DefaultAzureCredential got no token")],
)
@pytest.mark.asyncio
async def test_a_failed_acquisition_answers_none_instead_of_raising(failure):
    """The connectors turn None into NotConfigured. If this raised, one host without the
    cloud SDK installed or without an ambient identity would take down the whole run,
    including the providers that were answering."""
    from token_iq.connectors.billing.startup import build_token_factory

    async def acquire():
        raise failure

    factory = build_token_factory(provider="azure", acquire=acquire, logger=MagicMock(spec=logging.Logger))

    assert await factory("azure-prod", {"subscription_id": "sub-123"}) is None


@pytest.mark.asyncio
async def test_a_failed_acquisition_logs_the_cause_without_the_credential_values():
    """'has no microsoft entra id token' cannot tell a missing install from an expired login from a
    role the identity does not hold. The SDK's own exception is the only thing that can, so
    it has to reach the log, and nothing the admin typed may go with it."""
    from token_iq.connectors.billing.startup import build_token_factory

    failure = RuntimeError("ManagedIdentityCredential declined, AzureCliCredential declined")

    async def acquire():
        raise failure

    logger = MagicMock(spec=logging.Logger)
    factory = build_token_factory(provider="azure", acquire=acquire, logger=logger)

    await factory("azure-prod", {"subscription_id": "sub-secret-value"})

    logger.warning.assert_called_once()
    logged = logger.warning.call_args.args
    assert failure in logged
    assert "azure" in logged
    assert "azure-prod" in logged
    assert "sub-secret-value" not in str(logged)
