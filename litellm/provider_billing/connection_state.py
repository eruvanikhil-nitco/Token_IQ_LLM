"""What state a provider connection is in, decided only from evidence we hold.

Kept pure and separate from the endpoint so the rules can be read and tested on their own:
every branch here is something a customer will act on.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from litellm.types.proxy.provider_billing import ConnectionState, ProviderSyncRun

_NEVER_RUN: Final = "No sync has run for this account yet."

_SEVERITY: Final[tuple[ConnectionState, ...]] = (
    "needs_attention",
    "not_connected",
    "waiting_for_first_data",
    "healthy",
)
"""Worst first. A provider is only as good as its least healthy account."""


def account_state(*, last_run: ProviderSyncRun | None, facts_stored: int) -> tuple[ConnectionState, str | None]:
    """The state of one stored credential against one provider, and why."""
    if last_run is None:
        return ("waiting_for_first_data", _NEVER_RUN)
    if last_run.outcome in ("failed", "not_configured"):
        return ("needs_attention", last_run.detail)
    if facts_stored == 0:
        return (
            "waiting_for_first_data",
            "The provider answered but has reported no cost for this account yet.",
        )
    return ("healthy", None)


def provider_state(account_states: Sequence[ConnectionState]) -> ConnectionState:
    """One state for a provider that may have several accounts."""
    if not account_states:
        return "not_connected"
    return next(state for state in _SEVERITY if state in account_states)


def verified_against_real_account(facts_per_account: Sequence[int]) -> bool:
    """True once at least one of this provider's accounts has stored a real cost row.

    Stored facts are the only evidence here that a test cannot manufacture. A connector written
    from a vendor's documentation can pass every test we have and still be wrong about what the
    vendor actually sends, so the product should say which of the two it is looking at. Deriving
    it from stored rows rather than from a sentence in a design doc also means the answer stops
    being wrong the moment the first real account is connected.
    """
    return any(count > 0 for count in facts_per_account)
