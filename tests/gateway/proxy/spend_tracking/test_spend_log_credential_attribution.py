from __future__ import annotations

from datetime import datetime

from token_iq.gateway.proxy.spend_tracking.spend_tracking_utils import get_logging_payload


def _kwargs(litellm_params: dict) -> dict:
    return {
        "call_type": "acompletion",
        "model": "gpt-4o-mini",
        "litellm_params": litellm_params,
        "response_cost": 0.0001,
    }


def _payload(litellm_params: dict):
    now = datetime.now()
    return get_logging_payload(
        kwargs=_kwargs(litellm_params),
        response_obj={},
        start_time=now,
        end_time=now,
    )


def test_the_stored_credential_that_paid_is_recorded():
    """Without this a spend row names our own key and the provider's address and
    nothing identifying the customer's account, so a customer with two accounts at one
    provider cannot be told which was charged."""
    payload = _payload({"litellm_credential_name": "acme-openai-production"})

    assert payload["provider_credential"] == "acme-openai-production"


def test_a_deployment_with_an_inline_key_falls_back_to_its_own_identity():
    """Not every deployment references a stored credential; some embed the key. The
    deployment is then the finest-grained answer available, and an answer beats a blank."""
    payload = _payload({"metadata": {"model_info": {"id": "deployment-abc"}}})

    assert payload["provider_credential"] == "deployment-abc"


def test_a_stored_credential_wins_over_the_deployment_identity():
    payload = _payload(
        {
            "litellm_credential_name": "acme-openai-production",
            "metadata": {"model_info": {"id": "deployment-abc"}},
        }
    )

    assert payload["provider_credential"] == "acme-openai-production"


def test_nothing_identifiable_records_empty_rather_than_guessing():
    payload = _payload({})

    assert payload["provider_credential"] == ""


def test_a_courier_request_records_the_credential_its_key_named():
    """Courier requests carry no deployment, so the deployment identity that answers this
    for translating mode is absent. The key's binding is what is known, and recording it
    is what makes a wrong-account charge visible in the data rather than only on an
    invoice."""
    payload = _payload({"metadata": {"provider_credential": "acme-openai-production"}})

    assert payload["provider_credential"] == "acme-openai-production"


def test_a_stored_credential_on_the_deployment_still_wins_for_translating_mode():
    payload = _payload(
        {
            "litellm_credential_name": "from-deployment",
            "metadata": {"provider_credential": "from-key-binding"},
        }
    )

    assert payload["provider_credential"] == "from-deployment"
