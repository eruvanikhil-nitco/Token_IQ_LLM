"""Tests verifying Soniox is correctly registered as a litellm provider."""

import pytest

from token_iq import gateway


class TestProviderRegistration:
    def test_should_expose_soniox_in_llm_providers_enum(self):
        assert gateway.LlmProviders.SONIOX.value == "soniox"

    def test_should_list_soniox_in_provider_list(self):
        assert "soniox" in gateway.provider_list

    def test_should_list_soniox_in_models_by_provider(self):
        assert "soniox" in gateway.models_by_provider

    def test_should_lazy_import_soniox_audio_transcription_config(self):
        cls = gateway.SonioxAudioTranscriptionConfig
        assert cls.__name__ == "SonioxAudioTranscriptionConfig"
        # Calling again should return the same class (cached).
        assert gateway.SonioxAudioTranscriptionConfig is cls

    def test_should_resolve_soniox_via_get_llm_provider(self, monkeypatch):
        monkeypatch.setenv("SONIOX_API_KEY", "test-key")
        model, provider, api_key, api_base = gateway.get_llm_provider(
            model="soniox/stt-async-v4"
        )
        assert provider == "soniox"
        assert model == "stt-async-v4"
        assert api_key == "test-key"
        assert api_base == "https://api.soniox.com"

    def test_should_resolve_soniox_v5_via_get_llm_provider(self, monkeypatch):
        monkeypatch.setenv("SONIOX_API_KEY", "test-key")
        model, provider, api_key, api_base = gateway.get_llm_provider(
            model="soniox/stt-async-v5"
        )
        assert provider == "soniox"
        assert model == "stt-async-v5"
        assert api_key == "test-key"
        assert api_base == "https://api.soniox.com"

    def test_should_return_soniox_config_from_provider_config_manager(self):
        from token_iq.gateway.utils import ProviderConfigManager

        cfg = ProviderConfigManager.get_provider_audio_transcription_config(
            model="stt-async-v4",
            provider=gateway.LlmProviders.SONIOX,
        )
        assert cfg is not None
        assert cfg.__class__.__name__ == "SonioxAudioTranscriptionConfig"
