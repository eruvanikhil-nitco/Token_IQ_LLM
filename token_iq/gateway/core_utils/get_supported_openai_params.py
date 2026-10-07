from typing import Final, Literal

from token_iq import gateway
from token_iq.gateway.core_utils.get_llm_provider_logic import declared_authenticating_provider
from token_iq.gateway.exceptions import BadRequestError
from token_iq.gateway.types.utils import LlmProviders, LlmProvidersSet


def get_supported_openai_params(
    model: str,
    custom_llm_provider: str | None = None,
    request_type: Literal["chat_completion", "embeddings", "transcription"] = "chat_completion",
    base_model: str | None = None,
) -> list | None:
    """
    Returns the supported openai params for a given model + provider

    Example:
    ```
    get_supported_openai_params(model="anthropic.claude-3", custom_llm_provider="bedrock")
    ```

    Args:
        base_model: An optional capability hint for deployments whose ``model``
            label isn't recognized on its own (e.g. an Azure deployment name, or a
            friendly Bedrock alias). It is additive: the result is the union of the
            params supported by ``model`` and by ``base_model``, so a hint can only
            add capabilities, never strip ones the real model already supports.

    Returns:
    - List if custom_llm_provider is mapped
    - None if unmapped
    """
    if not custom_llm_provider:
        custom_llm_provider = declared_authenticating_provider(
            model
        )  # rebind-ok: resolving would run the provider's OAuth flow
    if not custom_llm_provider:
        try:
            custom_llm_provider = gateway.get_llm_provider(model=model)[1]
        except BadRequestError:
            return None

    if custom_llm_provider in LlmProvidersSet:
        provider_config = gateway.ProviderConfigManager.get_provider_chat_config(
            model=model,
            provider=LlmProviders(custom_llm_provider),
            base_model=base_model,
        )
    elif custom_llm_provider.split("/")[0] in LlmProvidersSet:
        provider_config = gateway.ProviderConfigManager.get_provider_chat_config(
            model=model,
            provider=LlmProviders(custom_llm_provider.split("/")[0]),
            base_model=base_model,
        )
    else:
        provider_config = None

    if provider_config and request_type == "chat_completion":
        supported_params = provider_config.get_supported_openai_params(model=model)
        if base_model and base_model != model:
            base_model_params: Final = provider_config.get_supported_openai_params(model=base_model)
            supported_params = list(dict.fromkeys([*supported_params, *base_model_params]))
        return supported_params

    if custom_llm_provider == "bedrock" or custom_llm_provider == "bedrock_converse":
        return gateway.AmazonConverseConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "meta_llama":
        provider_config = gateway.ProviderConfigManager.get_provider_chat_config(
            model=model, provider=LlmProviders.LLAMA
        )
        if provider_config:
            return provider_config.get_supported_openai_params(model=model)
    elif custom_llm_provider == "ollama":
        return gateway.OllamaConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "ollama_chat":
        return gateway.OllamaChatConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "anthropic":
        return gateway.AnthropicConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "anthropic_text":
        return gateway.AnthropicTextConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "fireworks_ai":
        if request_type == "embeddings":
            return gateway.FireworksAIEmbeddingConfig().get_supported_openai_params(model=model)
        elif request_type == "transcription":
            return None
        else:
            return gateway.FireworksAIConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "nvidia_nim":
        if request_type == "chat_completion":
            return gateway.nvidiaNimConfig.get_supported_openai_params(model=model)
        elif request_type == "embeddings":
            return gateway.nvidiaNimEmbeddingConfig.get_supported_openai_params()
    elif custom_llm_provider == "cerebras":
        return gateway.CerebrasConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "baseten":
        return gateway.BasetenConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "xai":
        return gateway.XAIChatConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "ai21_chat" or custom_llm_provider == "ai21":
        return gateway.AI21ChatConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "volcengine":
        return gateway.VolcEngineConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "groq":
        return gateway.GroqChatConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "bedrock_mantle":
        return gateway.BedrockMantleChatConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "hosted_vllm":
        return gateway.HostedVLLMChatConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "vllm":
        return gateway.VLLMConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "deepseek":
        return gateway.DeepSeekChatConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "tencent":
        return gateway.TencentChatConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "cohere_chat" or custom_llm_provider == "cohere":
        return gateway.CohereChatConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "maritalk":
        return gateway.MaritalkConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "openai":
        if request_type == "transcription":
            transcription_provider_config = gateway.ProviderConfigManager.get_provider_audio_transcription_config(
                model=model, provider=LlmProviders.OPENAI
            )
            if isinstance(transcription_provider_config, gateway.OpenAIGPTAudioTranscriptionConfig):
                return transcription_provider_config.get_supported_openai_params(model=model)
            else:
                raise ValueError(f"Unsupported provider config: {transcription_provider_config} for model: {model}")
        return gateway.OpenAIConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "sap":
        if request_type == "chat_completion":
            return gateway.GenAIHubOrchestrationConfig().get_supported_openai_params(model=model)
        elif request_type == "embeddings":
            return gateway.GenAIHubEmbeddingConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "azure":
        _azure_detection_model: Final = base_model or model
        if gateway.AzureOpenAIO1Config().is_o_series_model(model=_azure_detection_model):
            return gateway.AzureOpenAIO1Config().get_supported_openai_params(model=_azure_detection_model)
        elif gateway.AzureOpenAIGPT5Config.is_model_gpt_5_model(model=_azure_detection_model):
            return gateway.AzureOpenAIGPT5Config().get_supported_openai_params(model=_azure_detection_model)
        else:
            return gateway.AzureOpenAIConfig().get_supported_openai_params(model=_azure_detection_model)
    elif custom_llm_provider == "openrouter":
        return gateway.OpenrouterConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "vercel_ai_gateway":
        return gateway.VercelAIGatewayConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "mistral" or custom_llm_provider == "codestral":
        # mistal and codestral api have the exact same params
        if request_type == "chat_completion":
            return gateway.MistralConfig().get_supported_openai_params(model=model)
        elif request_type == "embeddings":
            return gateway.MistralEmbeddingConfig().get_supported_openai_params()
        elif request_type == "transcription":
            from token_iq.gateway.llms.mistral.audio_transcription.transformation import (
                MistralAudioTranscriptionConfig,
            )

            return MistralAudioTranscriptionConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "text-completion-codestral":
        return gateway.CodestralTextCompletionConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "sambanova":
        if request_type == "embeddings":
            return gateway.SambaNovaEmbeddingConfig().get_supported_openai_params(model=model)
        else:
            return gateway.SambanovaConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "nebius":
        if request_type == "chat_completion":
            return gateway.NebiusConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "wandb":
        if request_type == "chat_completion":
            return gateway.WandbConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "replicate":
        return gateway.ReplicateConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "huggingface":
        return gateway.HuggingFaceChatConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "jina_ai":
        if request_type == "embeddings":
            return gateway.JinaAIEmbeddingConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "together_ai":
        return gateway.TogetherAIChatConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "databricks":
        if request_type == "chat_completion":
            return gateway.DatabricksConfig().get_supported_openai_params(model=model)
        elif request_type == "embeddings":
            return gateway.DatabricksEmbeddingConfig().get_supported_openai_params()
    elif custom_llm_provider == "palm" or custom_llm_provider == "gemini":
        return gateway.GoogleAIStudioGeminiConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "novita":
        return gateway.NovitaConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "vertex_ai" or custom_llm_provider == "vertex_ai_beta":
        if request_type == "chat_completion":
            if model.startswith("mistral"):
                return gateway.MistralConfig().get_supported_openai_params(model=model)
            elif model.startswith("codestral"):
                return gateway.CodestralTextCompletionConfig().get_supported_openai_params(model=model)
            elif model.startswith("claude"):
                return gateway.VertexAIAnthropicConfig().get_supported_openai_params(model=model)
            elif model.startswith("gemini"):
                return gateway.VertexGeminiConfig().get_supported_openai_params(model=model)
            else:
                return gateway.VertexAILlama3Config().get_supported_openai_params(model=model)
        elif request_type == "embeddings":
            return gateway.VertexAITextEmbeddingConfig().get_supported_openai_params()
    elif custom_llm_provider == "sagemaker":
        return gateway.SagemakerConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "aleph_alpha":
        return [
            "max_tokens",
            "stream",
            "top_p",
            "temperature",
            "presence_penalty",
            "frequency_penalty",
            "n",
            "stop",
        ]
    elif custom_llm_provider == "cloudflare":
        return gateway.CloudflareChatConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "nlp_cloud":
        return gateway.NLPCloudConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "petals":
        return gateway.PetalsConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "deepinfra":
        return gateway.DeepInfraConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "perplexity":
        return gateway.PerplexityChatConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "nscale":
        return gateway.NscaleConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "anyscale":
        return [
            "temperature",
            "top_p",
            "stream",
            "max_tokens",
            "stop",
            "frequency_penalty",
            "presence_penalty",
        ]
    elif custom_llm_provider == "watsonx":
        return gateway.IBMWatsonXChatConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "watsonx_text":
        return gateway.IBMWatsonXAIConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "custom_openai" or custom_llm_provider == "text-completion-openai":
        return gateway.OpenAITextCompletionConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "predibase":
        return gateway.PredibaseConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "voyage":
        if request_type == "embeddings" and gateway.VoyageMultimodalEmbeddingConfig.is_multimodal_embeddings(model):
            return gateway.VoyageMultimodalEmbeddingConfig().get_supported_openai_params(model=model)
        return gateway.VoyageEmbeddingConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "infinity":
        return gateway.InfinityEmbeddingConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "triton":
        if request_type == "embeddings":
            return gateway.TritonEmbeddingConfig().get_supported_openai_params(model=model)
        else:
            return gateway.TritonConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "deepgram":
        if request_type == "transcription":
            return gateway.DeepgramAudioTranscriptionConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "ovhcloud":
        if request_type == "transcription":
            from token_iq.gateway.llms.ovhcloud.audio_transcription.transformation import (
                OVHCloudAudioTranscriptionConfig,
            )

            return OVHCloudAudioTranscriptionConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "scaleway":
        if request_type == "transcription":
            from token_iq.gateway.llms.scaleway.audio_transcription.transformation import (
                ScalewayAudioTranscriptionConfig,
            )

            return ScalewayAudioTranscriptionConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "elevenlabs":
        if request_type == "transcription":
            from token_iq.gateway.llms.elevenlabs.audio_transcription.transformation import (
                ElevenLabsAudioTranscriptionConfig,
            )

            return ElevenLabsAudioTranscriptionConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "soniox":
        if request_type == "transcription":
            return gateway.SonioxAudioTranscriptionConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider in gateway._custom_providers:
        if request_type == "chat_completion":
            provider_config = gateway.ProviderConfigManager.get_provider_chat_config(
                model=model, provider=LlmProviders.CUSTOM
            )
            if provider_config:
                return provider_config.get_supported_openai_params(model=model)
        elif request_type == "embeddings" or request_type == "transcription":
            return None

    return None
