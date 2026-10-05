from __future__ import annotations

from datetime import datetime, timezone

from litellm.types.proxy.provider_billing import ProviderSyncRun

NOW = datetime(2026, 9, 16, 9, 0, tzinfo=timezone.utc)


def _run(outcome: str, detail: str | None = None, facts_written: int = 0) -> ProviderSyncRun:
    return ProviderSyncRun(
        provider="openai",
        credential_name="prod",
        started_at=NOW,
        finished_at=NOW,
        outcome=outcome,
        facts_written=facts_written,
        window_start=NOW,
        window_end=NOW,
        detail=detail,
    )


def test_an_account_that_has_never_synced_is_waiting_not_healthy():
    from token_iq.connectors.billing.connection_state import account_state

    assert account_state(last_run=None, facts_stored=0) == (
        "waiting_for_first_data",
        "No sync has run for this account yet.",
    )


def test_an_account_whose_last_run_failed_needs_attention_and_says_why():
    """The reason is the whole value of this state. A customer whose admin key was revoked
    should read the provider's own words, not open a ticket to find out."""
    from token_iq.connectors.billing.connection_state import account_state

    assert account_state(last_run=_run("failed", "openai refused credential prod"), facts_stored=12) == (
        "needs_attention",
        "openai refused credential prod",
    )


def test_a_credential_the_connector_cannot_use_needs_attention():
    from token_iq.connectors.billing.connection_state import account_state

    state, detail = account_state(last_run=_run("not_configured", "credential prod carries no api_key"), facts_stored=0)

    assert state == "needs_attention"
    assert detail == "credential prod carries no api_key"


def test_a_successful_run_that_has_produced_nothing_yet_is_still_waiting():
    """A provider that has answered but reported no spend is not proof the connection works
    end to end. Calling it healthy would hide a wrong account id until the first invoice."""
    from token_iq.connectors.billing.connection_state import account_state

    assert account_state(last_run=_run("fetched"), facts_stored=0)[0] == "waiting_for_first_data"


def test_a_successful_run_with_stored_facts_is_healthy():
    from token_iq.connectors.billing.connection_state import account_state

    assert account_state(last_run=_run("fetched", facts_written=3), facts_stored=3) == ("healthy", None)


def test_a_provider_with_no_accounts_is_not_connected():
    from token_iq.connectors.billing.connection_state import provider_state

    assert provider_state(()) == "not_connected"


def test_one_broken_account_puts_the_whole_provider_in_needs_attention():
    """Two OpenAI organisations where one key is dead is a half-reported bill. Showing the
    provider as healthy because the other account works is the failure this prevents."""
    from token_iq.connectors.billing.connection_state import provider_state

    assert provider_state(("healthy", "needs_attention")) == "needs_attention"


def test_a_provider_whose_accounts_are_all_healthy_is_healthy():
    from token_iq.connectors.billing.connection_state import provider_state

    assert provider_state(("healthy", "healthy")) == "healthy"


def test_a_provider_still_waiting_on_one_account_is_waiting():
    from token_iq.connectors.billing.connection_state import provider_state

    assert provider_state(("healthy", "waiting_for_first_data")) == "waiting_for_first_data"


def test_a_provider_that_has_never_stored_a_row_is_not_verified() -> None:
    from token_iq.connectors.billing.connection_state import verified_against_real_account

    assert verified_against_real_account(()) is False
    assert verified_against_real_account((0,)) is False
    assert verified_against_real_account((0, 0, 0)) is False


def test_one_account_with_real_rows_verifies_the_provider() -> None:
    """A customer with three accounts where only one has been connected has still proved that
    this connector reaches this vendor, which is the question being asked."""
    from token_iq.connectors.billing.connection_state import verified_against_real_account

    assert verified_against_real_account((0, 7, 0)) is True


def test_verification_does_not_depend_on_the_last_run_succeeding() -> None:
    """A provider that worked last month and is failing today has still met a real account.
    Tying this to the latest run would make the claim flip back and forth with an outage."""
    from token_iq.connectors.billing.connection_state import verified_against_real_account

    assert verified_against_real_account((42,)) is True
