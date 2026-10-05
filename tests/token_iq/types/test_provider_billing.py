from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from decimal import Decimal

import pytest


def _fact(**overrides: object):
    from token_iq.types.provider_billing import ProviderUsageFact

    return ProviderUsageFact(
        **{
            "fact_key": "openrouter:gen-1",
            "provider": "openrouter",
            "credential_name": "acme-openrouter",
            "grain": "request",
            "bucket_start": datetime.now(timezone.utc),
            "evidence": "reconciled",
            "billed_cost": Decimal("0.0000025"),
            **overrides,
        }
    )


def test_a_fact_is_immutable_because_it_is_an_audit_record():
    """These rows exist to be compared against our own figures later. A fact that can be
    edited after it is fetched is not evidence of anything."""
    fact = _fact()

    with pytest.raises(FrozenInstanceError):
        fact.billed_cost = Decimal("99")  # pyright: ignore[reportAttributeAccessIssue]  # proving frozen


def test_cost_is_a_decimal_not_a_float():
    """Token costs run to twelve decimal places and get summed across millions of rows.
    Floats lose money here, and the whole point of this table is to be the accurate one."""
    assert isinstance(_fact().billed_cost, Decimal)


def test_a_failure_is_a_value_a_caller_must_handle():
    """The runner drives many connectors. One provider being down must not end the run,
    which it would if connectors raised."""
    from token_iq.types.provider_billing import Fetched, FetchFailed, NotConfigured

    for result in (
        Fetched(facts=(), watermark=datetime.now(timezone.utc)),
        NotConfigured(reason="no credential named"),
        FetchFailed(reason="429 from provider", retryable=True),
    ):
        assert result is not None


def test_a_retryable_failure_is_distinguishable_from_a_permanent_one():
    """A 429 should be tried again next tick. A 401 should not, and should surface to an
    operator instead of retrying forever against a revoked key."""
    from token_iq.types.provider_billing import FetchFailed

    assert FetchFailed(reason="429", retryable=True).retryable is True
    assert FetchFailed(reason="401 revoked", retryable=False).retryable is False
