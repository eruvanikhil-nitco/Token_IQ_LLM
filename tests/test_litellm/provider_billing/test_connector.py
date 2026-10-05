from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

import pytest

from litellm.types.proxy.provider_billing import Fetched, FetchResult


class _Stub:
    provider = "stub"

    async def fetch(
        self,
        *,
        since: datetime,
        until: datetime,
        credential_name: str,
        credential_values: Mapping[str, str],
    ) -> FetchResult:
        return Fetched(facts=(), watermark=until)


def test_a_connector_satisfies_the_protocol_without_inheriting_from_it():
    """Composition over inheritance: a connector is anything with the right shape, so a
    test double is a plain object rather than a subclass of production code."""
    from token_iq.connectors.billing.connector import BillingConnector

    connector: BillingConnector = _Stub()
    assert connector.provider == "stub"


def test_registering_twice_under_one_provider_is_refused():
    """Two connectors for one provider would both write facts, and the second would
    overwrite the first on every tick. Better to fail at startup than to serve a number
    that flips."""
    from token_iq.connectors.billing.connector import clear_registry_for_tests, register_connector

    clear_registry_for_tests()
    register_connector(_Stub())
    with pytest.raises(ValueError, match="stub"):
        register_connector(_Stub())
    clear_registry_for_tests()


def test_the_registry_reports_what_was_registered():
    from token_iq.connectors.billing.connector import (
        clear_registry_for_tests,
        register_connector,
        registered_connectors,
    )

    clear_registry_for_tests()
    register_connector(_Stub())

    assert [c.provider for c in registered_connectors()] == ["stub"]
    clear_registry_for_tests()


def test_an_empty_registry_is_an_empty_tuple_not_a_failure():
    """A deployment with no billing credentials configured is normal, not broken."""
    from token_iq.connectors.billing.connector import clear_registry_for_tests, registered_connectors

    clear_registry_for_tests()
    assert registered_connectors() == ()
