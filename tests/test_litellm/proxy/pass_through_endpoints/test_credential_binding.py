from __future__ import annotations

import pytest


def test_a_key_can_name_the_credentials_it_may_use():
    """Courier requests never name one of our model entries, so the credential cannot be
    looked up from the request. The key that authenticated it is the only thing that
    already knows, which is why the binding lives here."""
    from litellm.models.verification_token import LiteLLM_VerificationToken

    key = LiteLLM_VerificationToken(token="hashed", provider_credentials=["acme-openai-production"])
    assert key.provider_credentials == ["acme-openai-production"]


def test_a_key_with_no_binding_keeps_todays_behaviour():
    from litellm.models.verification_token import LiteLLM_VerificationToken

    assert LiteLLM_VerificationToken(token="hashed").provider_credentials == []


def test_the_binding_survives_key_creation():
    """Regression shape borrowed from courier_mode, where the field was added to the read
    model only and /team/new silently dropped it while every unit test passed."""
    from litellm.proxy._types import GenerateKeyRequest

    request = GenerateKeyRequest(provider_credentials=["acme-openai-production"])
    assert request.provider_credentials == ["acme-openai-production"]


def test_the_binding_can_be_updated():
    from litellm.proxy._types import UpdateKeyRequest

    request = UpdateKeyRequest(key="sk-x", provider_credentials=["acme-openai-test"])
    assert request.provider_credentials == ["acme-openai-test"]


class TestCourierResolvesFromTheBinding:
    def test_a_bound_credential_is_preferred_over_scanning(self, monkeypatch):
        """The whole point: with a binding the gateway looks one up instead of taking the
        first deployment it finds for that provider, which is what billed a customer's
        production traffic to their test account."""
        from litellm.proxy.pass_through_endpoints.passthrough_endpoint_router import (
            PassthroughEndpointRouter,
        )

        router = PassthroughEndpointRouter()
        monkeypatch.setattr(
            "litellm.litellm_core_utils.credential_accessor.CredentialAccessor.get_credential_values",
            staticmethod(lambda name: {"api_key": f"secret-for-{name}"} if name == "bound-cred" else {}),
        )

        resolved = router.get_credentials(
            custom_llm_provider="openai",
            region_name=None,
            bound_credentials=("bound-cred",),
        )

        assert resolved == "secret-for-bound-cred"

    def test_an_unbound_key_falls_back_to_current_behaviour(self):
        """Seventeen of the thirty-one keys here name nothing. They must keep working."""
        from litellm.proxy.pass_through_endpoints.passthrough_endpoint_router import (
            PassthroughEndpointRouter,
        )

        router = PassthroughEndpointRouter()

        # No binding means the old path: scan deployments, then the environment. It must
        # not raise the way a broken binding does, and must not invent a credential.
        assert not router.get_credentials(custom_llm_provider="openai", region_name=None)

    def test_a_binding_naming_an_unknown_credential_does_not_silently_scan(self, monkeypatch):
        """If the operator named a credential, using a different one is worse than
        failing: it bills an account they did not choose."""
        from litellm.proxy.pass_through_endpoints.passthrough_endpoint_router import (
            PassthroughEndpointRouter,
        )

        router = PassthroughEndpointRouter()
        monkeypatch.setattr(
            "litellm.litellm_core_utils.credential_accessor.CredentialAccessor.get_credential_values",
            staticmethod(lambda name: {}),
        )

        with pytest.raises(Exception) as exc:
            router.get_credentials(
                custom_llm_provider="openai",
                region_name=None,
                bound_credentials=("missing-cred",),
            )

        assert "missing-cred" in str(exc.value)
