from __future__ import annotations

from unittest.mock import MagicMock


def test_every_shipped_connector_is_registered():
    """A connector that exists but is never registered is dead code that looks like a
    feature. The registry is what the runner iterates."""
    from litellm.provider_billing.connector import clear_registry_for_tests, registered_connectors
    from litellm.provider_billing.startup import register_billing_connectors

    clear_registry_for_tests()
    register_billing_connectors(prisma_client=MagicMock())

    assert {connector.provider for connector in registered_connectors()} == {
        "openrouter",
        "anthropic",
        "openai",
    }
    clear_registry_for_tests()


def test_registering_twice_is_harmless():
    """A worker that restarts its scheduler calls this again, and the registry refuses
    duplicates by design. Startup must not die on the second call."""
    from litellm.provider_billing.connector import clear_registry_for_tests, registered_connectors
    from litellm.provider_billing.startup import register_billing_connectors

    clear_registry_for_tests()
    register_billing_connectors(prisma_client=MagicMock())
    register_billing_connectors(prisma_client=MagicMock())

    assert len(registered_connectors()) == 3
    clear_registry_for_tests()
