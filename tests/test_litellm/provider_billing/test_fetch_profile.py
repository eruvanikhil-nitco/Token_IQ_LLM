from __future__ import annotations

from litellm.provider_billing.bedrock import SETTLING_HOURS
from litellm.provider_billing.credential_purpose import BILLING_PROVIDERS
from litellm.provider_billing.fetch_profile import FETCH_PROFILES


def test_every_billing_provider_has_a_fetch_profile():
    """FETCH_PROFILES and BILLING_PROVIDERS are maintained by hand in two separate files.
    The connections endpoint does `FETCH_PROFILES[provider]` for every provider in
    BILLING_PROVIDERS with no fallback, so if someone adds a provider to one set and
    forgets the other, that lookup raises KeyError: the screen that exists to tell a
    customer their billing connection is healthy answers 500 instead."""
    assert set(FETCH_PROFILES.keys()) == BILLING_PROVIDERS


def test_every_profile_says_whether_its_figures_still_move():
    """A cost screen that does not say a number is still settling invites someone to
    treat it as final. Every provider must state something, even if that something is
    that we do not know."""
    for provider, profile in FETCH_PROFILES.items():
        assert profile.settling_note, f"{provider} has no settling_note"


def test_bedrocks_settling_note_matches_the_constant_that_drives_it():
    """The 48 hour cutoff is real code, not a claim. If someone changes the constant the
    text must move with it, or the screen starts lying."""
    assert str(SETTLING_HOURS) in FETCH_PROFILES["bedrock"].settling_note


def test_providers_without_a_verified_window_say_so_rather_than_inventing_one():
    """We have not verified a settling window for these providers, so any number in the
    text would be invented. A note that hedges with "not verified" while still naming a
    duration is worse than no note at all, because a customer reads that number as a fact
    about their own money. No digit may appear in these three notes."""
    for provider in ("openai", "anthropic", "openrouter"):
        note = FETCH_PROFILES[provider].settling_note.lower()
        assert "not" in note or "unknown" in note
        assert not any(char.isdigit() for char in note), f"{provider} settling_note contains a number: {note}"
