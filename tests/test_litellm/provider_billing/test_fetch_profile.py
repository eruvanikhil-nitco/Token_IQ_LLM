from __future__ import annotations

from litellm.provider_billing.credential_purpose import BILLING_PROVIDERS
from litellm.provider_billing.fetch_profile import FETCH_PROFILES


def test_every_billing_provider_has_a_fetch_profile():
    """FETCH_PROFILES and BILLING_PROVIDERS are maintained by hand in two separate files.
    The connections endpoint does `FETCH_PROFILES[provider]` for every provider in
    BILLING_PROVIDERS with no fallback, so if someone adds a provider to one set and
    forgets the other, that lookup raises KeyError: the screen that exists to tell a
    customer their billing connection is healthy answers 500 instead."""
    assert set(FETCH_PROFILES.keys()) == BILLING_PROVIDERS
