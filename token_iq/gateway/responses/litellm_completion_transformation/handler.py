"""
Handler for transforming responses api requests to litellm.completion requests
"""

from collections.abc import Coroutine, Mapping
from typing import Final

from token_iq import gateway
from token_iq.gateway.responses.litellm_completion_transformation.streaming_iterator import (
    GatewayCompletionStreamingIterator,
)
from token_iq.gateway.responses.litellm_completion_transformation.transformation import (
    GatewayCompletionResponsesConfig,
)
from token_iq.gateway.responses.streaming_iterator import BaseResponsesAPIStreamingIterator
from token_iq.gateway.types.llms.openai import (
    ResponseInputParam,
    ResponsesAPIOptionalRequestParams,
    ResponsesAPIResponse,
)
from token_iq.gateway.types.utils import ModelResponse


class GatewayCompletionTransformationHandler:
    def response_api_handler(
        self,
        model: str,
        input: str | ResponseInputParam,
        responses_api_request: ResponsesAPIOptionalRequestParams,
        custom_llm_provider: str | None = None,
        _is_async: bool = False,
        stream: bool | None = None,
        extra_headers: Mapping[str, object] | None = None,
        **kwargs,
    ) -> (
        ResponsesAPIResponse
        | BaseResponsesAPIStreamingIterator
        | Coroutine[object, object, ResponsesAPIResponse | BaseResponsesAPIStreamingIterator]
    ):
        gateway_completion_request: Final[dict] = (
            GatewayCompletionResponsesConfig.transform_responses_api_request_to_chat_completion_request(
                model=model,
                input=input,
                responses_api_request=responses_api_request,
                custom_llm_provider=custom_llm_provider,
                stream=stream,
                extra_headers=extra_headers,
                **kwargs,
            )
        )

        if _is_async:
            return self.async_response_api_handler(
                gateway_completion_request=gateway_completion_request,
                request_input=input,
                responses_api_request=responses_api_request,
                **kwargs,
            )

        completion_args: Final = {}
        completion_args.update(kwargs)
        completion_args.update(gateway_completion_request)
        completion_args["_skip_responses_api_bridge"] = True

        gateway_completion_response: Final[ModelResponse | gateway.CustomStreamWrapper] = gateway.completion(
            **completion_args,
        )

        if isinstance(gateway_completion_response, ModelResponse):
            responses_api_response: Final[ResponsesAPIResponse] = (
                GatewayCompletionResponsesConfig.transform_chat_completion_response_to_responses_api_response(
                    chat_completion_response=gateway_completion_response,
                    request_input=input,
                    responses_api_request=responses_api_request,
                )
            )

            return responses_api_response

        elif isinstance(gateway_completion_response, gateway.CustomStreamWrapper):
            return GatewayCompletionStreamingIterator(
                model=model,
                gateway_custom_stream_wrapper=gateway_completion_response,
                request_input=input,
                responses_api_request=responses_api_request,
                custom_llm_provider=custom_llm_provider,
                litellm_metadata=kwargs.get("litellm_metadata", {}),
            )
        raise ValueError(f"Unexpected response type: {type(gateway_completion_response)}")

    async def async_response_api_handler(
        self,
        gateway_completion_request: dict,
        request_input: str | ResponseInputParam,
        responses_api_request: ResponsesAPIOptionalRequestParams,
        **kwargs,
    ) -> ResponsesAPIResponse | BaseResponsesAPIStreamingIterator:
        previous_response_id: Final[str | None] = responses_api_request.get("previous_response_id")
        if previous_response_id:
            gateway_completion_request = await GatewayCompletionResponsesConfig.async_responses_api_session_handler(
                previous_response_id=previous_response_id,
                gateway_completion_request=gateway_completion_request,
            )

        acompletion_args: Final = {}
        acompletion_args.update(kwargs)
        acompletion_args.update(gateway_completion_request)
        acompletion_args["_skip_responses_api_bridge"] = True

        gateway_completion_response: Final[ModelResponse | gateway.CustomStreamWrapper] = await gateway.acompletion(
            **acompletion_args,
        )

        if isinstance(gateway_completion_response, ModelResponse):
            responses_api_response: Final[ResponsesAPIResponse] = (
                GatewayCompletionResponsesConfig.transform_chat_completion_response_to_responses_api_response(
                    chat_completion_response=gateway_completion_response,
                    request_input=request_input,
                    responses_api_request=responses_api_request,
                )
            )

            return responses_api_response

        elif isinstance(gateway_completion_response, gateway.CustomStreamWrapper):
            return GatewayCompletionStreamingIterator(
                model=gateway_completion_request.get("model") or "",
                gateway_custom_stream_wrapper=gateway_completion_response,
                request_input=request_input,
                responses_api_request=responses_api_request,
                custom_llm_provider=gateway_completion_request.get("custom_llm_provider"),
                litellm_metadata=kwargs.get("litellm_metadata", {}),
            )
        raise ValueError(f"Unexpected response type: {type(gateway_completion_response)}")
