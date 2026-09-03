# Weighted / latency-based / cost-based routing

> **Status: REMOVED.** The files below are deleted from the working tree and the
> call sites in `litellm/router.py` are gutted. Verified: proxy boots, `db: connected`,
> and a live OpenRouter call returns normally.

## Why this is removed

The requirement is that the proxy forwards a request to the exact endpoint the client
already asked for. Every module below does the opposite: it scores the configured
deployments and picks one, so the endpoint that actually serves the call is chosen by
the proxy rather than by the caller.

`lowest_latency` keeps a rolling window of response times per deployment and selects the
fastest. `lowest_cost` selects on per-token price. `lowest_tpm_rpm` and its v2 select on
remaining token and request budget. `least_busy` selects on in-flight request count.

All five are unusable in an observer: to score a deployment you must first have several
interchangeable deployments, and choosing between them is the routing decision the
observer is not allowed to make. They also mutate shared state on every call, since the
latency and TPM handlers write counters back into the cache from success and failure
callbacks, which means even the act of observing changes future routing.

## Files removed

- `litellm/router_strategy/lowest_latency.py` (542 lines)
- `litellm/router_strategy/lowest_cost.py` (305 lines)
- `litellm/router_strategy/lowest_tpm_rpm.py` (231 lines)
- `litellm/router_strategy/lowest_tpm_rpm_v2.py` (624 lines)
- `litellm/router_strategy/least_busy.py` (214 lines)

## Removed code

### `litellm/router_strategy/lowest_latency.py`

```python
#### What this does ####
#   picks based on response time (for streaming, this is time to first token)
import random
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Final

import litellm
from litellm import ModelResponse, token_counter, verbose_logger
from litellm.caching.caching import DualCache
from litellm.integrations.custom_logger import CustomLogger
from litellm.litellm_core_utils.core_helpers import _get_parent_otel_span_from_kwargs, safe_divide_seconds
from litellm.types.utils import LiteLLMPydanticObjectBase

if TYPE_CHECKING:
    from opentelemetry.trace import Span as _Span

    Span = _Span | Any
else:
    Span = Any


class RoutingArgs(LiteLLMPydanticObjectBase):
    ttl: float = 1 * 60 * 60  # 1 hour
    lowest_latency_buffer: float = 0
    max_latency_list_size: int = 10


class LowestLatencyLoggingHandler(CustomLogger):
    test_flag: bool = False
    logged_success: int = 0
    logged_failure: int = 0

    def __init__(self, router_cache: DualCache, routing_args: dict = {}):
        self.router_cache = router_cache
        self.routing_args = RoutingArgs(**routing_args)

    def log_success_event(self, kwargs, response_obj, start_time, end_time):
        try:
            """
            Update latency usage on success
            """
            metadata_field: Final = self._select_metadata_field(kwargs)
            if kwargs["litellm_params"].get(metadata_field) is None:
                pass
            else:
                model_group: Final = kwargs["litellm_params"][metadata_field].get("model_group", None)

                id = (kwargs["litellm_params"].get("model_info") or {}).get("id", None)
                if model_group is None or id is None:
                    return
                elif isinstance(id, int):
                    id = str(id)

                # ------------
                # Setup values
                # ------------
                """
                {
                    {model_group}_map: {
                        id: {
                            "latency": [..]
                            f"{date:hour:minute}" : {"tpm": 34, "rpm": 3}
                        }
                    }
                }
                """
                latency_key: Final = f"{model_group}_map"

                current_date: Final = datetime.now().strftime("%Y-%m-%d")
                current_hour: Final = datetime.now().strftime("%H")
                current_minute: Final = datetime.now().strftime("%M")
                precise_minute: Final = f"{current_date}-{current_hour}-{current_minute}"

                response_ms = end_time - start_time
                if isinstance(response_ms, timedelta):
                    # normalize to float seconds up-front: non-chat responses
                    # (embeddings, speech, image) skip the ModelResponse branch
                    # below, and a raw timedelta appended to the latency list
                    # breaks JSON serialization when the router cache syncs to
                    # Redis (issue #33169)
                    response_ms = response_ms.total_seconds()
                time_to_first_token_response_time = None

                if kwargs.get("stream", None) is not None and kwargs["stream"] is True:
                    # only log ttft for streaming request
                    time_to_first_token_response_time = kwargs.get("completion_start_time", end_time) - start_time

                final_value: float = response_ms
                time_to_first_token: float | None = None
                total_tokens = 0

                if isinstance(response_obj, ModelResponse):
                    _usage: Final = getattr(response_obj, "usage", None)
                    if _usage is not None:
                        completion_tokens: Final = _usage.completion_tokens
                        total_tokens = _usage.total_tokens

                        # response_ms is already normalized to float seconds above
                        response_seconds: Final = response_ms

                        normalized_value: Final = safe_divide_seconds(response_seconds, completion_tokens)
                        if normalized_value is not None:
                            final_value = float(normalized_value)
                        else:
                            final_value = response_seconds

                        if time_to_first_token_response_time is not None:
                            if isinstance(time_to_first_token_response_time, timedelta):
                                ttft_seconds = time_to_first_token_response_time.total_seconds()
                            else:
                                ttft_seconds = time_to_first_token_response_time
                            time_to_first_token = safe_divide_seconds(ttft_seconds, completion_tokens)

                # ------------
                # Update usage
                # ------------
                parent_otel_span: Final = _get_parent_otel_span_from_kwargs(kwargs)
                request_count_dict: Final = (
                    self.router_cache.get_cache(key=latency_key, parent_otel_span=parent_otel_span) or {}
                )

                if id not in request_count_dict:
                    request_count_dict[id] = {}

                ## Latency
                if len(request_count_dict[id].get("latency", [])) < self.routing_args.max_latency_list_size:
                    request_count_dict[id].setdefault("latency", []).append(final_value)
                else:
                    request_count_dict[id]["latency"] = request_count_dict[id]["latency"][1:] + [final_value]

                ## Time to first token
                if time_to_first_token is not None:
                    if (
                        len(request_count_dict[id].get("time_to_first_token", []))
                        < self.routing_args.max_latency_list_size
                    ):
                        request_count_dict[id].setdefault("time_to_first_token", []).append(time_to_first_token)
                    else:
                        request_count_dict[id]["time_to_first_token"] = request_count_dict[id]["time_to_first_token"][
                            1:
                        ] + [time_to_first_token]

                if precise_minute not in request_count_dict[id]:
                    request_count_dict[id][precise_minute] = {}

                ## TPM
                request_count_dict[id][precise_minute]["tpm"] = (
                    request_count_dict[id][precise_minute].get("tpm", 0) + total_tokens
                )

                ## RPM
                request_count_dict[id][precise_minute]["rpm"] = request_count_dict[id][precise_minute].get("rpm", 0) + 1

                self.router_cache.set_cache(
                    key=latency_key, value=request_count_dict, ttl=self.routing_args.ttl
                )  # reset map within window

                ### TESTING ###
                if self.test_flag:
                    self.logged_success += 1
        except Exception as e:
            verbose_logger.exception(
                "litellm.proxy.hooks.prompt_injection_detection.py::async_pre_call_hook(): Exception occured - %s", e
            )

    async def async_log_failure_event(self, kwargs, response_obj, start_time, end_time):
        """
        Check if Timeout Error, if timeout set deployment latency -> 100
        """
        try:
            metadata_field: Final = self._select_metadata_field(kwargs)
            _exception: Final = kwargs.get("exception", None)
            if isinstance(_exception, litellm.Timeout):
                if kwargs["litellm_params"].get(metadata_field) is None:
                    pass
                else:
                    model_group: Final = kwargs["litellm_params"][metadata_field].get("model_group", None)

                    id = (kwargs["litellm_params"].get("model_info") or {}).get("id", None)
                    if model_group is None or id is None:
                        return
                    elif isinstance(id, int):
                        id = str(id)

                    # ------------
                    # Setup values
                    # ------------
                    """
                    {
                        {model_group}_map: {
                            id: {
                                "latency": [..]
                                f"{date:hour:minute}" : {"tpm": 34, "rpm": 3}
                            }
                        }
                    }
                    """
                    latency_key: Final = f"{model_group}_map"
                    request_count_dict: Final = await self.router_cache.async_get_cache(key=latency_key) or {}

                    if id not in request_count_dict:
                        request_count_dict[id] = {}

                    ## Latency - give 1000s penalty for failing
                    if len(request_count_dict[id].get("latency", [])) < self.routing_args.max_latency_list_size:
                        request_count_dict[id].setdefault("latency", []).append(1000.0)
                    else:
                        request_count_dict[id]["latency"] = request_count_dict[id]["latency"][1:] + [1000.0]

                    await self.router_cache.async_set_cache(
                        key=latency_key,
                        value=request_count_dict,
                        ttl=self.routing_args.ttl,
                    )  # reset map within window
            else:
                # do nothing if it's not a timeout error
                return
        except Exception as e:
            verbose_logger.exception(
                "litellm.proxy.hooks.prompt_injection_detection.py::async_pre_call_hook(): Exception occured - %s", e
            )

    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        try:
            """
            Update latency usage on success
            """
            metadata_field: Final = self._select_metadata_field(kwargs)
            if kwargs["litellm_params"].get(metadata_field) is None:
                pass
            else:
                model_group: Final = kwargs["litellm_params"][metadata_field].get("model_group", None)

                id = (kwargs["litellm_params"].get("model_info") or {}).get("id", None)
                if model_group is None or id is None:
                    return
                elif isinstance(id, int):
                    id = str(id)

                # ------------
                # Setup values
                # ------------
                """
                {
                    {model_group}_map: {
                        id: {
                            "latency": [..]
                            "time_to_first_token": [..]
                            f"{date:hour:minute}" : {"tpm": 34, "rpm": 3}
                        }
                    }
                }
                """
                latency_key: Final = f"{model_group}_map"

                current_date: Final = datetime.now().strftime("%Y-%m-%d")
                current_hour: Final = datetime.now().strftime("%H")
                current_minute: Final = datetime.now().strftime("%M")
                precise_minute: Final = f"{current_date}-{current_hour}-{current_minute}"

                response_ms = end_time - start_time
                if isinstance(response_ms, timedelta):
                    # normalize to float seconds up-front: non-chat responses
                    # (embeddings, speech, image) skip the ModelResponse branch
                    # below, and a raw timedelta appended to the latency list
                    # breaks JSON serialization when the router cache syncs to
                    # Redis (issue #33169)
                    response_ms = response_ms.total_seconds()
                time_to_first_token_response_time = None
                if kwargs.get("stream", None) is not None and kwargs["stream"] is True:
                    # only log ttft for streaming request
                    time_to_first_token_response_time = kwargs.get("completion_start_time", end_time) - start_time

                final_value: float = response_ms
                total_tokens = 0
                time_to_first_token: float | None = None

                if isinstance(response_obj, ModelResponse):
                    _usage: Final = getattr(response_obj, "usage", None)
                    if _usage is not None:
                        completion_tokens: Final = _usage.completion_tokens
                        total_tokens = _usage.total_tokens

                        # response_ms is already normalized to float seconds above
                        response_seconds: Final = response_ms

                        normalized_value: Final = safe_divide_seconds(response_seconds, completion_tokens)
                        if normalized_value is not None:
                            final_value = float(normalized_value)
                        else:
                            final_value = response_seconds

                        if time_to_first_token_response_time is not None:
                            if isinstance(time_to_first_token_response_time, timedelta):
                                ttft_seconds = time_to_first_token_response_time.total_seconds()
                            else:
                                ttft_seconds = time_to_first_token_response_time
                            time_to_first_token = safe_divide_seconds(ttft_seconds, completion_tokens)
                # ------------
                # Update usage
                # ------------
                parent_otel_span: Final = _get_parent_otel_span_from_kwargs(kwargs)
                request_count_dict: Final = (
                    await self.router_cache.async_get_cache(
                        key=latency_key,
                        parent_otel_span=parent_otel_span,
                        local_only=True,
                    )
                    or {}
                )

                if id not in request_count_dict:
                    request_count_dict[id] = {}

                ## Latency
                if len(request_count_dict[id].get("latency", [])) < self.routing_args.max_latency_list_size:
                    request_count_dict[id].setdefault("latency", []).append(final_value)
                else:
                    request_count_dict[id]["latency"] = request_count_dict[id]["latency"][1:] + [final_value]

                ## Time to first token
                if time_to_first_token is not None:
                    if (
                        len(request_count_dict[id].get("time_to_first_token", []))
                        < self.routing_args.max_latency_list_size
                    ):
                        request_count_dict[id].setdefault("time_to_first_token", []).append(time_to_first_token)
                    else:
                        request_count_dict[id]["time_to_first_token"] = request_count_dict[id]["time_to_first_token"][
                            1:
                        ] + [time_to_first_token]

                if precise_minute not in request_count_dict[id]:
                    request_count_dict[id][precise_minute] = {}

                ## TPM
                request_count_dict[id][precise_minute]["tpm"] = (
                    request_count_dict[id][precise_minute].get("tpm", 0) + total_tokens
                )

                ## RPM
                request_count_dict[id][precise_minute]["rpm"] = request_count_dict[id][precise_minute].get("rpm", 0) + 1

                await self.router_cache.async_set_cache(
                    key=latency_key, value=request_count_dict, ttl=self.routing_args.ttl
                )  # reset map within window

                ### TESTING ###
                if self.test_flag:
                    self.logged_success += 1
        except Exception as e:
            verbose_logger.exception(
                "litellm.router_strategy.lowest_latency.py::async_log_success_event(): Exception occured - %s", e
            )

    def _get_available_deployments(
        self,
        model_group: str,
        healthy_deployments: list,
        messages: list[dict[str, str]] | None = None,
        input: str | list | None = None,
        request_kwargs: dict | None = None,
        request_count_dict: dict | None = None,
    ):
        """Common logic for both sync and async get_available_deployments"""

        # -----------------------
        # Find lowest used model
        # ----------------------
        _latency_per_deployment: Final = {}
        lowest_latency = float("inf")

        current_date: Final = datetime.now().strftime("%Y-%m-%d")
        current_hour: Final = datetime.now().strftime("%H")
        current_minute: Final = datetime.now().strftime("%M")
        precise_minute: Final = f"{current_date}-{current_hour}-{current_minute}"

        deployment = None

        if request_count_dict is None:  # base case
            return

        all_deployments = request_count_dict
        for d in healthy_deployments:
            ## if healthy deployment not yet used
            if d["model_info"]["id"] not in all_deployments:
                all_deployments[d["model_info"]["id"]] = {
                    "latency": [0],
                    precise_minute: {"tpm": 0, "rpm": 0},
                }

        try:
            input_tokens = token_counter(messages=messages, text=input)
        except Exception:
            input_tokens = 0

        # randomly sample from all_deployments, incase all deployments have latency=0.0
        _items: Final = all_deployments.items()

        _all_deployments: Final = random.sample(list(_items), len(_items))
        all_deployments = dict(_all_deployments)
        ### GET AVAILABLE DEPLOYMENTS ### filter out any deployments > tpm/rpm limits

        potential_deployments: Final = []
        for item, item_map in all_deployments.items():
            ## get the item from model list
            _deployment = None
            for m in healthy_deployments:
                if item == m["model_info"]["id"]:
                    _deployment = m

            if _deployment is None:
                continue  # skip to next one

            _deployment_tpm = (
                _deployment.get("tpm", None)
                or _deployment.get("litellm_params", {}).get("tpm", None)
                or _deployment.get("model_info", {}).get("tpm", None)
                or float("inf")
            )

            _deployment_rpm = (
                _deployment.get("rpm", None)
                or _deployment.get("litellm_params", {}).get("rpm", None)
                or _deployment.get("model_info", {}).get("rpm", None)
                or float("inf")
            )
            item_latency = item_map.get("latency", [])
            item_ttft_latency = item_map.get("time_to_first_token", [])
            item_rpm = item_map.get(precise_minute, {}).get("rpm", 0)
            item_tpm = item_map.get(precise_minute, {}).get("tpm", 0)

            # get average latency or average ttft (depending on streaming/non-streaming)
            total: float = 0.0
            use_ttft = (
                request_kwargs is not None
                and request_kwargs.get("stream", None) is not None
                and request_kwargs["stream"] is True
                and len(item_ttft_latency) > 0
            )
            if use_ttft:
                for _call_latency in item_ttft_latency:
                    if isinstance(_call_latency, float):
                        total += _call_latency
                item_latency = total / len(item_ttft_latency)
            else:
                for _call_latency in item_latency:
                    if isinstance(_call_latency, float):
                        total += _call_latency
                item_latency = total / len(item_latency)

            # -------------- #
            # Debugging Logic
            # -------------- #
            # We use _latency_per_deployment to log to langfuse, slack - this is not used to make a decision on routing
            # this helps a user to debug why the router picked a specfic deployment      #
            _deployment_api_base = _deployment.get("litellm_params", {}).get("api_base", "")
            if _deployment_api_base is not None:
                _latency_per_deployment[_deployment_api_base] = item_latency
            # -------------- #
            # End of Debugging Logic
            # -------------- #

            if (
                item_tpm + input_tokens > _deployment_tpm or item_rpm + 1 > _deployment_rpm
            ):  # if user passed in tpm / rpm in the model_list
                continue
            else:
                potential_deployments.append((_deployment, item_latency))

        if len(potential_deployments) == 0:
            return None

        # Sort potential deployments by latency
        sorted_deployments: Final = sorted(potential_deployments, key=lambda x: x[1])

        # Find lowest latency deployment
        lowest_latency = sorted_deployments[0][1]

        # Find deployments within buffer of lowest latency
        buffer: Final = self.routing_args.lowest_latency_buffer * lowest_latency

        valid_deployments: Final = [x for x in sorted_deployments if x[1] <= lowest_latency + buffer]

        # Pick a random deployment from valid deployments
        random_valid_deployment: Final = random.choice(valid_deployments)
        deployment = random_valid_deployment[0]
        metadata_field: Final = self._select_metadata_field(request_kwargs)
        if request_kwargs is not None and metadata_field in request_kwargs:
            request_kwargs[metadata_field]["_latency_per_deployment"] = _latency_per_deployment
        return deployment

    async def async_get_available_deployments(
        self,
        model_group: str,
        healthy_deployments: list,
        messages: list[dict[str, str]] | None = None,
        input: str | list | None = None,
        request_kwargs: dict | None = None,
    ):
        # get list of potential deployments
        latency_key: Final = f"{model_group}_map"

        parent_otel_span: Final[Span | None] = _get_parent_otel_span_from_kwargs(request_kwargs)
        request_count_dict: Final = (
            await self.router_cache.async_get_cache(key=latency_key, parent_otel_span=parent_otel_span) or {}
        )

        return self._get_available_deployments(
            model_group,
            healthy_deployments,
            messages,
            input,
            request_kwargs,
            request_count_dict,
        )

    def get_available_deployments(
        self,
        model_group: str,
        healthy_deployments: list,
        messages: list[dict[str, str]] | None = None,
        input: str | list | None = None,
        request_kwargs: dict | None = None,
    ):
        """
        Returns a deployment with the lowest latency
        """
        # get list of potential deployments
        latency_key: Final = f"{model_group}_map"

        parent_otel_span: Final[Span | None] = _get_parent_otel_span_from_kwargs(request_kwargs)
        request_count_dict = self.router_cache.get_cache(key=latency_key, parent_otel_span=parent_otel_span) or {}

        return self._get_available_deployments(
            model_group,
            healthy_deployments,
            messages,
            input,
            request_kwargs,
            request_count_dict,
        )
```

### `litellm/router_strategy/lowest_cost.py`

```python
#### What this does ####
#   picks based on response time (for streaming, this is time to first token)
from datetime import datetime, timedelta
from typing import Final

import litellm
from litellm import ModelResponse, token_counter, verbose_logger
from litellm._logging import verbose_router_logger
from litellm.caching.caching import DualCache
from litellm.integrations.custom_logger import CustomLogger


class LowestCostLoggingHandler(CustomLogger):
    test_flag: bool = False
    logged_success: int = 0
    logged_failure: int = 0

    def __init__(self, router_cache: DualCache, routing_args: dict = {}):
        self.router_cache = router_cache

    def log_success_event(self, kwargs, response_obj, start_time, end_time):
        try:
            """
            Update usage on success
            """
            if kwargs["litellm_params"].get("metadata") is None:
                pass
            else:
                model_group: Final = kwargs["litellm_params"]["metadata"].get("model_group", None)

                id = kwargs["litellm_params"].get("model_info", {}).get("id", None)
                if model_group is None or id is None:
                    return
                elif isinstance(id, int):
                    id = str(id)

                # ------------
                # Setup values
                # ------------
                """
                {
                    {model_group}_map: {
                        id: {
                            f"{date:hour:minute}" : {"tpm": 34, "rpm": 3}
                        }
                    }
                }
                """
                current_date: Final = datetime.now().strftime("%Y-%m-%d")
                current_hour: Final = datetime.now().strftime("%H")
                current_minute: Final = datetime.now().strftime("%M")
                precise_minute: Final = f"{current_date}-{current_hour}-{current_minute}"
                cost_key: Final = f"{model_group}_map"

                response_ms: Final[timedelta] = end_time - start_time

                total_tokens = 0

                if isinstance(response_obj, ModelResponse):
                    _usage: Final = getattr(response_obj, "usage", None)
                    if _usage is not None and isinstance(_usage, litellm.Usage):
                        completion_tokens: Final = _usage.completion_tokens
                        total_tokens = _usage.total_tokens
                        float(response_ms.total_seconds() / completion_tokens)

                # ------------
                # Update usage
                # ------------

                request_count_dict: Final = self.router_cache.get_cache(key=cost_key) or {}

                # check local result first

                if id not in request_count_dict:
                    request_count_dict[id] = {}

                if precise_minute not in request_count_dict[id]:
                    request_count_dict[id][precise_minute] = {}

                ## TPM
                request_count_dict[id][precise_minute]["tpm"] = (
                    request_count_dict[id][precise_minute].get("tpm", 0) + total_tokens
                )

                ## RPM
                request_count_dict[id][precise_minute]["rpm"] = request_count_dict[id][precise_minute].get("rpm", 0) + 1

                self.router_cache.set_cache(key=cost_key, value=request_count_dict)

                ### TESTING ###
                if self.test_flag:
                    self.logged_success += 1
        except Exception as e:
            verbose_logger.exception(
                "litellm.router_strategy.lowest_cost.py::log_success_event(): Exception occured - %s", e
            )

    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        try:
            """
            Update cost usage on success
            """
            if kwargs["litellm_params"].get("metadata") is None:
                pass
            else:
                model_group: Final = kwargs["litellm_params"]["metadata"].get("model_group", None)

                id = kwargs["litellm_params"].get("model_info", {}).get("id", None)
                if model_group is None or id is None:
                    return
                elif isinstance(id, int):
                    id = str(id)

                # ------------
                # Setup values
                # ------------
                """
                {
                    {model_group}_map: {
                        id: {
                            "cost": [..]
                            f"{date:hour:minute}" : {"tpm": 34, "rpm": 3}
                        }
                    }
                }
                """
                cost_key: Final = f"{model_group}_map"

                current_date: Final = datetime.now().strftime("%Y-%m-%d")
                current_hour: Final = datetime.now().strftime("%H")
                current_minute: Final = datetime.now().strftime("%M")
                precise_minute: Final = f"{current_date}-{current_hour}-{current_minute}"

                response_ms: Final[timedelta] = end_time - start_time

                total_tokens = 0

                if isinstance(response_obj, ModelResponse):
                    _usage: Final = getattr(response_obj, "usage", None)
                    if _usage is not None and isinstance(_usage, litellm.Usage):
                        completion_tokens: Final = _usage.completion_tokens
                        total_tokens = _usage.total_tokens

                        float(response_ms.total_seconds() / completion_tokens)

                # ------------
                # Update usage
                # ------------

                request_count_dict: Final = await self.router_cache.async_get_cache(key=cost_key) or {}

                if id not in request_count_dict:
                    request_count_dict[id] = {}
                if precise_minute not in request_count_dict[id]:
                    request_count_dict[id][precise_minute] = {}

                ## TPM
                request_count_dict[id][precise_minute]["tpm"] = (
                    request_count_dict[id][precise_minute].get("tpm", 0) + total_tokens
                )

                ## RPM
                request_count_dict[id][precise_minute]["rpm"] = request_count_dict[id][precise_minute].get("rpm", 0) + 1

                await self.router_cache.async_set_cache(
                    key=cost_key, value=request_count_dict
                )  # reset map within window

                ### TESTING ###
                if self.test_flag:
                    self.logged_success += 1
        except Exception as e:
            verbose_logger.exception(
                "litellm.proxy.hooks.prompt_injection_detection.py::async_pre_call_hook(): Exception occured - %s", e
            )

    async def async_get_available_deployments(
        self,
        model_group: str,
        healthy_deployments: list,
        messages: list[dict[str, str]] | None = None,
        input: str | list | None = None,
        request_kwargs: dict | None = None,
    ):
        """
        Returns a deployment with the lowest cost
        """
        cost_key: Final = f"{model_group}_map"

        request_count_dict: Final = await self.router_cache.async_get_cache(key=cost_key) or {}

        # -----------------------
        # Find lowest used model
        # ----------------------
        float("inf")

        current_date: Final = datetime.now().strftime("%Y-%m-%d")
        current_hour: Final = datetime.now().strftime("%H")
        current_minute: Final = datetime.now().strftime("%M")
        precise_minute: Final = f"{current_date}-{current_hour}-{current_minute}"

        if request_count_dict is None:  # base case
            return

        all_deployments: Final = request_count_dict
        for d in healthy_deployments:
            ## if healthy deployment not yet used
            if d["model_info"]["id"] not in all_deployments:
                all_deployments[d["model_info"]["id"]] = {
                    precise_minute: {"tpm": 0, "rpm": 0},
                }

        try:
            input_tokens = token_counter(messages=messages, text=input)
        except Exception:
            input_tokens = 0

        # randomly sample from all_deployments, incase all deployments have latency=0.0
        _items: Final = all_deployments.items()

        ### GET AVAILABLE DEPLOYMENTS ### filter out any deployments > tpm/rpm limits
        potential_deployments = []
        _cost_per_deployment: Final = {}
        for item, item_map in all_deployments.items():
            ## get the item from model list
            _deployment = None
            for m in healthy_deployments:
                if item == m["model_info"]["id"]:
                    _deployment = m

            if _deployment is None:
                continue  # skip to next one

            _deployment_tpm = (
                _deployment.get("tpm", None)
                or _deployment.get("litellm_params", {}).get("tpm", None)
                or _deployment.get("model_info", {}).get("tpm", None)
                or float("inf")
            )

            _deployment_rpm = (
                _deployment.get("rpm", None)
                or _deployment.get("litellm_params", {}).get("rpm", None)
                or _deployment.get("model_info", {}).get("rpm", None)
                or float("inf")
            )
            item_litellm_model_name = _deployment.get("litellm_params", {}).get("model")
            item_litellm_model_cost_map = litellm.model_cost.get(item_litellm_model_name, {})

            # check if user provided input_cost_per_token and output_cost_per_token in litellm_params
            item_input_cost = None
            item_output_cost = None
            if _deployment.get("litellm_params", {}).get("input_cost_per_token", None):
                item_input_cost = _deployment.get("litellm_params", {}).get("input_cost_per_token")

            if _deployment.get("litellm_params", {}).get("output_cost_per_token", None):
                item_output_cost = _deployment.get("litellm_params", {}).get("output_cost_per_token")

            if item_input_cost is None:
                item_input_cost = item_litellm_model_cost_map.get("input_cost_per_token", 5.0)

            if item_output_cost is None:
                item_output_cost = item_litellm_model_cost_map.get("output_cost_per_token", 5.0)

            # if litellm["model"] is not in model_cost map -> use item_cost = $10

            item_cost = item_input_cost + item_output_cost

            item_rpm = item_map.get(precise_minute, {}).get("rpm", 0)
            item_tpm = item_map.get(precise_minute, {}).get("tpm", 0)

            verbose_router_logger.debug(
                "item_cost: %s, item_tpm: %s, item_rpm: %s, model_id: %s",
                item_cost,
                item_tpm,
                item_rpm,
                _deployment.get("model_info", {}).get("id"),
            )

            # -------------- #
            # Debugging Logic
            # -------------- #
            # We use _cost_per_deployment to log to langfuse, slack - this is not used to make a decision on routing
            # this helps a user to debug why the router picked a specfic deployment      #
            _deployment_api_base = _deployment.get("litellm_params", {}).get("api_base", "")
            if _deployment_api_base is not None:
                _cost_per_deployment[_deployment_api_base] = item_cost
            # -------------- #
            # End of Debugging Logic
            # -------------- #

            if (
                item_tpm + input_tokens > _deployment_tpm or item_rpm + 1 > _deployment_rpm
            ):  # if user passed in tpm / rpm in the model_list
                continue
            else:
                potential_deployments.append((_deployment, item_cost))

        if len(potential_deployments) == 0:
            return None

        potential_deployments = sorted(potential_deployments, key=lambda x: x[1])

        selected_deployment: Final = potential_deployments[0][0]
        return selected_deployment
```

### `litellm/router_strategy/lowest_tpm_rpm.py`

```python
#### What this does ####
#   identifies lowest tpm deployment
import traceback
from datetime import datetime
from typing import Final

from litellm import token_counter
from litellm._logging import verbose_router_logger
from litellm.caching.caching import DualCache
from litellm.integrations.custom_logger import CustomLogger
from litellm.types.utils import LiteLLMPydanticObjectBase
from litellm.utils import print_verbose


class RoutingArgs(LiteLLMPydanticObjectBase):
    ttl: int = 1 * 60  # 1min (RPM/TPM expire key)


class LowestTPMLoggingHandler(CustomLogger):
    test_flag: bool = False
    logged_success: int = 0
    logged_failure: int = 0
    default_cache_time_seconds: int = 1 * 60 * 60  # 1 hour

    def __init__(self, router_cache: DualCache, routing_args: dict = {}):
        self.router_cache = router_cache
        self.routing_args = RoutingArgs(**routing_args)

    def log_success_event(self, kwargs, response_obj, start_time, end_time):
        try:
            """
            Update TPM/RPM usage on success
            """
            if "litellm_params" not in kwargs or kwargs["litellm_params"] is None:
                return
            if kwargs["litellm_params"].get("metadata") is None:
                pass
            else:
                model_group: Final = kwargs["litellm_params"]["metadata"].get("model_group", None)

                id = kwargs["litellm_params"].get("model_info", {}).get("id", None)
                if model_group is None or id is None:
                    return
                elif isinstance(id, int):
                    id = str(id)

                total_tokens: Final = response_obj["usage"]["total_tokens"]

                # ------------
                # Setup values
                # ------------
                current_minute: Final = datetime.now().strftime("%H-%M")
                tpm_key: Final = f"{model_group}:tpm:{current_minute}"
                rpm_key: Final = f"{model_group}:rpm:{current_minute}"

                # ------------
                # Update usage
                # ------------

                ## TPM
                request_count_dict = self.router_cache.get_cache(key=tpm_key) or {}
                request_count_dict[id] = request_count_dict.get(id, 0) + total_tokens

                self.router_cache.set_cache(key=tpm_key, value=request_count_dict, ttl=self.routing_args.ttl)

                ## RPM
                request_count_dict = self.router_cache.get_cache(key=rpm_key) or {}
                request_count_dict[id] = request_count_dict.get(id, 0) + 1

                self.router_cache.set_cache(key=rpm_key, value=request_count_dict, ttl=self.routing_args.ttl)

                ### TESTING ###
                if self.test_flag:
                    self.logged_success += 1
        except Exception as e:
            verbose_router_logger.error(
                "litellm.router_strategy.lowest_tpm_rpm.py::async_log_success_event(): Exception occured - %s", e
            )
            verbose_router_logger.debug(traceback.format_exc())

    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        try:
            """
            Update TPM/RPM usage on success
            """
            if "litellm_params" not in kwargs or kwargs["litellm_params"] is None:
                return
            if kwargs["litellm_params"].get("metadata") is None:
                pass
            else:
                model_group: Final = kwargs["litellm_params"]["metadata"].get("model_group", None)

                model_info: Final = kwargs["litellm_params"].get("model_info")
                id = None
                if model_info is not None and isinstance(model_info, dict):
                    id = model_info.get("id", None)
                if model_group is None or id is None:
                    return
                elif isinstance(id, int):
                    id = str(id)

                if "usage" not in response_obj:
                    return
                total_tokens: Final = response_obj["usage"]["total_tokens"]

                # ------------
                # Setup values
                # ------------
                current_minute: Final = datetime.now().strftime("%H-%M")
                tpm_key: Final = f"{model_group}:tpm:{current_minute}"
                rpm_key: Final = f"{model_group}:rpm:{current_minute}"

                # ------------
                # Update usage
                # ------------
                # update cache

                ## TPM
                request_count_dict = await self.router_cache.async_get_cache(key=tpm_key) or {}
                request_count_dict[id] = request_count_dict.get(id, 0) + total_tokens

                await self.router_cache.async_set_cache(
                    key=tpm_key, value=request_count_dict, ttl=self.routing_args.ttl
                )

                ## RPM
                request_count_dict = await self.router_cache.async_get_cache(key=rpm_key) or {}
                request_count_dict[id] = request_count_dict.get(id, 0) + 1

                await self.router_cache.async_set_cache(
                    key=rpm_key, value=request_count_dict, ttl=self.routing_args.ttl
                )

                ### TESTING ###
                if self.test_flag:
                    self.logged_success += 1
        except Exception as e:
            verbose_router_logger.exception(
                "litellm.router_strategy.lowest_tpm_rpm.py::async_log_success_event(): Exception occured - %s", e
            )
            verbose_router_logger.debug(traceback.format_exc())

    def get_available_deployments(
        self,
        model_group: str,
        healthy_deployments: list,
        messages: list[dict[str, str]] | None = None,
        input: str | list | None = None,
    ):
        """
        Returns a deployment with the lowest TPM/RPM usage.
        """
        # get list of potential deployments
        verbose_router_logger.debug(
            "get_available_deployments - Usage Based. model_group: %s, healthy_deployments: %s",
            model_group,
            healthy_deployments,
        )
        current_minute: Final = datetime.now().strftime("%H-%M")
        tpm_key: Final = f"{model_group}:tpm:{current_minute}"
        rpm_key: Final = f"{model_group}:rpm:{current_minute}"

        tpm_dict = self.router_cache.get_cache(key=tpm_key)
        rpm_dict: Final = self.router_cache.get_cache(key=rpm_key)

        verbose_router_logger.debug("tpm_key=%s, tpm_dict: %s, rpm_dict: %s", tpm_key, tpm_dict, rpm_dict)
        try:
            input_tokens = token_counter(messages=messages, text=input)
        except Exception:
            input_tokens = 0
        verbose_router_logger.debug("input_tokens=%s", input_tokens)
        # -----------------------
        # Find lowest used model
        # ----------------------
        lowest_tpm = float("inf")

        if tpm_dict is None:  # base case - none of the deployments have been used
            # initialize a tpm dict with {model_id: 0}
            tpm_dict = {}
            for deployment in healthy_deployments:
                tpm_dict[deployment["model_info"]["id"]] = 0
        else:
            for d in healthy_deployments:
                ## if healthy deployment not yet used
                if d["model_info"]["id"] not in tpm_dict:
                    tpm_dict[d["model_info"]["id"]] = 0

        all_deployments: Final = tpm_dict

        deployment = None
        for item, item_tpm in all_deployments.items():
            ## get the item from model list
            _deployment = None
            for m in healthy_deployments:
                if item == m["model_info"]["id"]:
                    _deployment = m

            if _deployment is None:
                continue  # skip to next one

            _deployment_tpm = None
            if _deployment_tpm is None:
                _deployment_tpm = _deployment.get("tpm")
            if _deployment_tpm is None:
                _deployment_tpm = _deployment.get("litellm_params", {}).get("tpm")
            if _deployment_tpm is None:
                _deployment_tpm = _deployment.get("model_info", {}).get("tpm")
            if _deployment_tpm is None:
                _deployment_tpm = float("inf")

            _deployment_rpm = None
            if _deployment_rpm is None:
                _deployment_rpm = _deployment.get("rpm")
            if _deployment_rpm is None:
                _deployment_rpm = _deployment.get("litellm_params", {}).get("rpm")
            if _deployment_rpm is None:
                _deployment_rpm = _deployment.get("model_info", {}).get("rpm")
            if _deployment_rpm is None:
                _deployment_rpm = float("inf")

            if (
                item_tpm + input_tokens > _deployment_tpm
                or (rpm_dict is not None and item in rpm_dict)
                and (rpm_dict[item] + 1 >= _deployment_rpm)
            ):
                continue
            elif item_tpm < lowest_tpm:
                lowest_tpm = item_tpm
                deployment = _deployment
        print_verbose("returning picked lowest tpm/rpm deployment.")
        return deployment
```

### `litellm/router_strategy/lowest_tpm_rpm_v2.py`

```python
#### What this does ####
#   identifies lowest tpm deployment
import random
from typing import TYPE_CHECKING, Any, Final

import httpx

import litellm
from litellm import token_counter
from litellm._logging import verbose_logger, verbose_router_logger
from litellm.caching.caching import DualCache
from litellm.integrations.custom_logger import CustomLogger
from litellm.litellm_core_utils.core_helpers import _get_parent_otel_span_from_kwargs
from litellm.types.router import RouterErrors
from litellm.types.utils import LiteLLMPydanticObjectBase, StandardLoggingPayload
from litellm.utils import get_utc_datetime, print_verbose

from .base_routing_strategy import BaseRoutingStrategy

if TYPE_CHECKING:
    from opentelemetry.trace import Span as _Span

    Span = _Span | Any
else:
    Span = Any


class RoutingArgs(LiteLLMPydanticObjectBase):
    ttl: int = 1 * 60  # 1min (RPM/TPM expire key)


class LowestTPMLoggingHandler_v2(BaseRoutingStrategy, CustomLogger):
    """
    Updated version of TPM/RPM Logging.

    Meant to work across instances.

    Caches individual models, not model_groups

    Uses batch get (redis.mget)

    Increments tpm/rpm limit using redis.incr
    """

    test_flag: bool = False
    logged_success: int = 0
    logged_failure: int = 0
    default_cache_time_seconds: int = 1 * 60 * 60  # 1 hour

    def __init__(self, router_cache: DualCache, routing_args: dict = {}):
        self.router_cache = router_cache
        self.routing_args = RoutingArgs(**routing_args)
        BaseRoutingStrategy.__init__(
            self,
            dual_cache=router_cache,
            should_batch_redis_writes=True,
            default_sync_interval=0.1,
        )

    def pre_call_check(self, deployment: dict) -> dict | None:
        """
        Pre-call check + update model rpm

        Returns - deployment

        Raises - RateLimitError if deployment over defined RPM limit
        """
        try:
            # ------------
            # Setup values
            # ------------

            dt: Final = get_utc_datetime()
            current_minute: Final = dt.strftime("%H-%M")
            model_id: Final = deployment.get("model_info", {}).get("id")
            deployment_name: Final = deployment.get("litellm_params", {}).get("model")
            rpm_key: Final = f"{model_id}:{deployment_name}:rpm:{current_minute}"

            local_result: Final = self.router_cache.get_cache(key=rpm_key, local_only=True)  # check local result first

            deployment_rpm = None
            if deployment_rpm is None:
                deployment_rpm = deployment.get("rpm")
            if deployment_rpm is None:
                deployment_rpm = deployment.get("litellm_params", {}).get("rpm")
            if deployment_rpm is None:
                deployment_rpm = deployment.get("model_info", {}).get("rpm")
            if deployment_rpm is None:
                deployment_rpm = float("inf")

            if local_result is not None and local_result >= deployment_rpm:
                raise litellm.RateLimitError(
                    message=f"Deployment over defined rpm limit={deployment_rpm}. current usage={local_result}",
                    llm_provider="",
                    model=deployment.get("litellm_params", {}).get("model"),
                    response=httpx.Response(
                        status_code=429,
                        content="{} rpm limit={}. current usage={}. id={}, model_group={}. Get the model info by calling 'router.get_model_info(id)".format(
                            RouterErrors.user_defined_ratelimit_error.value,
                            deployment_rpm,
                            local_result,
                            model_id,
                            deployment.get("model_name", ""),
                        ),
                        request=httpx.Request(
                            method="tpm_rpm_limits",
                            url="https://github.com/BerriAI/litellm",
                        ),
                    ),
                )
            else:
                # if local result below limit, check redis ## prevent unnecessary redis checks

                result: Final = self.router_cache.increment_cache(key=rpm_key, value=1, ttl=self.routing_args.ttl)
                if result is not None and result > deployment_rpm:
                    raise litellm.RateLimitError(
                        message=f"Deployment over defined rpm limit={deployment_rpm}. current usage={result}",
                        llm_provider="",
                        model=deployment.get("litellm_params", {}).get("model"),
                        response=httpx.Response(
                            status_code=429,
                            content=f"{RouterErrors.user_defined_ratelimit_error.value} rpm limit={deployment_rpm}. current usage={result}",
                            request=httpx.Request(
                                method="tpm_rpm_limits",
                                url="https://github.com/BerriAI/litellm",
                            ),
                        ),
                    )
            return deployment
        except Exception as e:
            if isinstance(e, litellm.RateLimitError):
                raise e
            return deployment  # don't fail calls if eg. redis fails to connect

    async def async_pre_call_check(self, deployment: dict, parent_otel_span: Span | None) -> dict | None:
        """
        Pre-call check + update model rpm
        - Used inside semaphore
        - raise rate limit error if deployment over limit

        Why? solves concurrency issue - https://github.com/BerriAI/litellm/issues/2994

        Returns - deployment

        Raises - RateLimitError if deployment over defined RPM limit
        """
        try:
            # ------------
            # Setup values
            # ------------
            dt: Final = get_utc_datetime()
            current_minute: Final = dt.strftime("%H-%M")
            model_id: Final = deployment.get("model_info", {}).get("id")
            deployment_name: Final = deployment.get("litellm_params", {}).get("model")

            rpm_key: Final = f"{model_id}:{deployment_name}:rpm:{current_minute}"
            local_result: Final = await self.router_cache.async_get_cache(
                key=rpm_key, local_only=True
            )  # check local result first

            deployment_rpm = None
            if deployment_rpm is None:
                deployment_rpm = deployment.get("rpm")
            if deployment_rpm is None:
                deployment_rpm = deployment.get("litellm_params", {}).get("rpm")
            if deployment_rpm is None:
                deployment_rpm = deployment.get("model_info", {}).get("rpm")
            if deployment_rpm is None:
                deployment_rpm = float("inf")
            if local_result is not None and local_result >= deployment_rpm:
                raise litellm.RateLimitError(
                    message=f"Deployment over defined rpm limit={deployment_rpm}. current usage={local_result}",
                    llm_provider="",
                    model=deployment.get("litellm_params", {}).get("model"),
                    response=httpx.Response(
                        status_code=429,
                        content=f"{RouterErrors.user_defined_ratelimit_error.value} rpm limit={deployment_rpm}. current usage={local_result}",
                        headers={"retry-after": str(60)},
                        request=httpx.Request(
                            method="tpm_rpm_limits",
                            url="https://github.com/BerriAI/litellm",
                        ),
                    ),
                    num_retries=deployment.get("num_retries"),
                )
            else:
                # if local result below limit, check redis ## prevent unnecessary redis checks
                result = await self._increment_value_in_current_window(key=rpm_key, value=1, ttl=self.routing_args.ttl)
                if result is not None and result > deployment_rpm:
                    raise litellm.RateLimitError(
                        message=f"Deployment over defined rpm limit={deployment_rpm}. current usage={result}",
                        llm_provider="",
                        model=deployment.get("litellm_params", {}).get("model"),
                        response=httpx.Response(
                            status_code=429,
                            content=f"{RouterErrors.user_defined_ratelimit_error.value} rpm limit={deployment_rpm}. current usage={result}",
                            headers={"retry-after": str(60)},
                            request=httpx.Request(
                                method="tpm_rpm_limits",
                                url="https://github.com/BerriAI/litellm",
                            ),
                        ),
                        num_retries=deployment.get("num_retries"),
                    )
            return deployment
        except Exception as e:
            if isinstance(e, litellm.RateLimitError):
                raise e
            return deployment  # don't fail calls if eg. redis fails to connect

    def log_success_event(self, kwargs, response_obj, start_time, end_time):
        try:
            """
            Update TPM/RPM usage on success
            """
            standard_logging_object: Final[StandardLoggingPayload | None] = kwargs.get("standard_logging_object")
            if standard_logging_object is None:
                raise ValueError("standard_logging_object not passed in.")
            model_group: Final = standard_logging_object.get("model_group")
            model: Final = standard_logging_object["hidden_params"].get("litellm_model_name")
            id = standard_logging_object.get("model_id")
            if model_group is None or id is None or model is None:
                return
            elif isinstance(id, int):
                id = str(id)

            total_tokens: Final = standard_logging_object.get("total_tokens")

            # ------------
            # Setup values
            # ------------
            dt: Final = get_utc_datetime()
            current_minute: Final = dt.strftime("%H-%M")  # use the same timezone regardless of system clock

            tpm_key: Final = f"{id}:{model}:tpm:{current_minute}"
            # ------------
            # Update usage
            # ------------
            # update cache

            ## TPM
            self.router_cache.increment_cache(key=tpm_key, value=total_tokens, ttl=self.routing_args.ttl)
            ### TESTING ###
            if self.test_flag:
                self.logged_success += 1
        except Exception as e:
            verbose_logger.exception(
                "litellm.proxy.hooks.lowest_tpm_rpm_v2.py::log_success_event(): Exception occured - %s", e
            )

    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        try:
            """
            Update TPM usage on success
            """
            standard_logging_object: Final[StandardLoggingPayload | None] = kwargs.get("standard_logging_object")
            if standard_logging_object is None:
                raise ValueError("standard_logging_object not passed in.")
            model_group: Final = standard_logging_object.get("model_group")
            model: Final = standard_logging_object["hidden_params"]["litellm_model_name"]
            id = standard_logging_object.get("model_id")
            if model_group is None or id is None:
                return
            elif isinstance(id, int):
                id = str(id)
            total_tokens: Final = standard_logging_object.get("total_tokens")
            # ------------
            # Setup values
            # ------------
            dt: Final = get_utc_datetime()
            current_minute: Final = dt.strftime("%H-%M")  # use the same timezone regardless of system clock

            tpm_key: Final = f"{id}:{model}:tpm:{current_minute}"
            # ------------
            # Update usage
            # ------------
            # update cache
            parent_otel_span: Final = _get_parent_otel_span_from_kwargs(kwargs)
            ## TPM
            await self.router_cache.async_increment_cache(
                key=tpm_key,
                value=total_tokens,
                ttl=self.routing_args.ttl,
                parent_otel_span=parent_otel_span,
            )

            ### TESTING ###
            if self.test_flag:
                self.logged_success += 1
        except Exception as e:
            verbose_logger.exception(
                "litellm.proxy.hooks.lowest_tpm_rpm_v2.py::async_log_success_event(): Exception occured - %s", e
            )

    def _return_potential_deployments(
        self,
        healthy_deployments: list[dict],
        all_deployments: dict,
        input_tokens: int,
        rpm_dict: dict,
    ):
        lowest_tpm = float("inf")
        potential_deployments = []  # if multiple deployments have the same low value
        deployment_lookup: Final = {
            deployment.get("model_info", {}).get("id"): deployment for deployment in healthy_deployments
        }
        for item, item_tpm in all_deployments.items():
            ## get the item from model list
            item = item.split(":")[0]
            _deployment = deployment_lookup.get(item)
            if _deployment is None:
                continue  # skip to next one
            elif item_tpm is None:
                continue  # skip if unhealthy deployment

            _deployment_tpm = None
            if _deployment_tpm is None:
                _deployment_tpm = _deployment.get("tpm")
            if _deployment_tpm is None:
                _deployment_tpm = _deployment.get("litellm_params", {}).get("tpm")
            if _deployment_tpm is None:
                _deployment_tpm = _deployment.get("model_info", {}).get("tpm")
            if _deployment_tpm is None:
                _deployment_tpm = float("inf")

            _deployment_rpm = None
            if _deployment_rpm is None:
                _deployment_rpm = _deployment.get("rpm")
            if _deployment_rpm is None:
                _deployment_rpm = _deployment.get("litellm_params", {}).get("rpm")
            if _deployment_rpm is None:
                _deployment_rpm = _deployment.get("model_info", {}).get("rpm")
            if _deployment_rpm is None:
                _deployment_rpm = float("inf")
            if item_tpm + input_tokens > _deployment_tpm or (
                (rpm_dict is not None and item in rpm_dict)
                and rpm_dict[item] is not None
                and (rpm_dict[item] + 1 >= _deployment_rpm)
            ):
                continue
            elif item_tpm == lowest_tpm:
                potential_deployments.append(_deployment)
            elif item_tpm < lowest_tpm:
                lowest_tpm = item_tpm
                potential_deployments = [_deployment]
        return potential_deployments

    def _common_checks_available_deployment(
        self,
        model_group: str,
        healthy_deployments: list,
        tpm_keys: list,
        tpm_values: list | None,
        rpm_keys: list,
        rpm_values: list | None,
        messages: list[dict[str, str]] | None = None,
        input: str | list | None = None,
    ) -> dict | None:
        """
        Common checks for get available deployment, across sync + async implementations
        """

        if tpm_values is None or rpm_values is None:
            return None

        tpm_dict = {}  # {model_id: 1, ..}
        for idx, key in enumerate(tpm_keys):
            tpm_dict[tpm_keys[idx].split(":")[0]] = tpm_values[idx]

        rpm_dict: Final = {}  # {model_id: 1, ..}
        for idx, key in enumerate(rpm_keys):
            rpm_dict[rpm_keys[idx].split(":")[0]] = rpm_values[idx]

        try:
            input_tokens = token_counter(messages=messages, text=input)
        except Exception:
            input_tokens = 0
        verbose_router_logger.debug("input_tokens=%s", input_tokens)
        # -----------------------
        # Find lowest used model
        # ----------------------

        if tpm_dict is None:  # base case - none of the deployments have been used
            # initialize a tpm dict with {model_id: 0}
            tpm_dict = {}
            for deployment in healthy_deployments:
                tpm_dict[deployment["model_info"]["id"]] = 0
        else:
            for d in healthy_deployments:
                ## if healthy deployment not yet used
                tpm_key = d["model_info"]["id"]
                if tpm_key not in tpm_dict or tpm_dict[tpm_key] is None:
                    tpm_dict[tpm_key] = 0

        all_deployments: Final = tpm_dict
        potential_deployments: Final = self._return_potential_deployments(
            healthy_deployments=healthy_deployments,
            all_deployments=all_deployments,
            input_tokens=input_tokens,
            rpm_dict=rpm_dict,
        )
        print_verbose("returning picked lowest tpm/rpm deployment.")

        if len(potential_deployments) > 0:
            return random.choice(potential_deployments)
        else:
            return None

    async def async_get_available_deployments(
        self,
        model_group: str,
        healthy_deployments: list,
        messages: list[dict[str, str]] | None = None,
        input: str | list | None = None,
    ):
        """
        Async implementation of get deployments.

        Reduces time to retrieve the tpm/rpm values from cache
        """
        # get list of potential deployments
        verbose_router_logger.debug(
            "get_available_deployments - Usage Based. model_group: %s, healthy_deployments: %s",
            model_group,
            healthy_deployments,
        )

        dt: Final = get_utc_datetime()
        current_minute: Final = dt.strftime("%H-%M")

        tpm_keys: Final = []
        rpm_keys: Final = []
        for m in healthy_deployments:
            if isinstance(m, dict):
                id = m.get("model_info", {}).get(
                    "id"
                )  # a deployment should always have an 'id'. this is set in router.py
                deployment_name = m.get("litellm_params", {}).get("model")
                tpm_key = f"{id}:{deployment_name}:tpm:{current_minute}"
                rpm_key = f"{id}:{deployment_name}:rpm:{current_minute}"

                tpm_keys.append(tpm_key)
                rpm_keys.append(rpm_key)

        combined_tpm_rpm_keys: Final = tpm_keys + rpm_keys

        combined_tpm_rpm_values: Final = await self.router_cache.async_batch_get_cache(
            keys=combined_tpm_rpm_keys
        )  # [1, 2, None, ..]

        if combined_tpm_rpm_values is not None:
            tpm_values = combined_tpm_rpm_values[: len(tpm_keys)]
            rpm_values = combined_tpm_rpm_values[len(tpm_keys) :]
        else:
            tpm_values = None
            rpm_values = None

        deployment: Final = self._common_checks_available_deployment(
            model_group=model_group,
            healthy_deployments=healthy_deployments,
            tpm_keys=tpm_keys,
            tpm_values=tpm_values,
            rpm_keys=rpm_keys,
            rpm_values=rpm_values,
            messages=messages,
            input=input,
        )

        try:
            assert deployment is not None
            return deployment
        except Exception:
            ### GET THE DICT OF TPM / RPM + LIMITS PER DEPLOYMENT ###
            deployment_dict: Final = {}
            for index, _deployment in enumerate(healthy_deployments):
                if isinstance(_deployment, dict):
                    id = _deployment.get("model_info", {}).get("id")
                    ### GET DEPLOYMENT TPM LIMIT ###
                    _deployment_tpm = None
                    if _deployment_tpm is None:
                        _deployment_tpm = _deployment.get("tpm", None)
                    if _deployment_tpm is None:
                        _deployment_tpm = _deployment.get("litellm_params", {}).get("tpm", None)
                    if _deployment_tpm is None:
                        _deployment_tpm = _deployment.get("model_info", {}).get("tpm", None)
                    if _deployment_tpm is None:
                        _deployment_tpm = float("inf")

                    ### GET CURRENT TPM ###
                    current_tpm = tpm_values[index] if tpm_values else 0

                    ### GET DEPLOYMENT TPM LIMIT ###
                    _deployment_rpm = None
                    if _deployment_rpm is None:
                        _deployment_rpm = _deployment.get("rpm", None)
                    if _deployment_rpm is None:
                        _deployment_rpm = _deployment.get("litellm_params", {}).get("rpm", None)
                    if _deployment_rpm is None:
                        _deployment_rpm = _deployment.get("model_info", {}).get("rpm", None)
                    if _deployment_rpm is None:
                        _deployment_rpm = float("inf")

                    ### GET CURRENT RPM ###
                    current_rpm = rpm_values[index] if rpm_values else 0

                    deployment_dict[id] = {
                        "current_tpm": current_tpm,
                        "tpm_limit": _deployment_tpm,
                        "current_rpm": current_rpm,
                        "rpm_limit": _deployment_rpm,
                    }
            raise litellm.RateLimitError(
                message=f"{RouterErrors.no_deployments_available.value}. Passed model={model_group}. Deployments={deployment_dict}",
                llm_provider="",
                model=model_group,
                response=httpx.Response(
                    status_code=429,
                    content="",
                    headers={"retry-after": str(60)},
                    request=httpx.Request(
                        method="tpm_rpm_limits",
                        url="https://github.com/BerriAI/litellm",
                    ),
                ),
            )

    def get_available_deployments(
        self,
        model_group: str,
        healthy_deployments: list,
        messages: list[dict[str, str]] | None = None,
        input: str | list | None = None,
        parent_otel_span: Span | None = None,
    ):
        """
        Returns a deployment with the lowest TPM/RPM usage.
        """
        # get list of potential deployments
        verbose_router_logger.debug(
            "get_available_deployments - Usage Based. model_group: %s, healthy_deployments: %s",
            model_group,
            healthy_deployments,
        )

        dt: Final = get_utc_datetime()
        current_minute: Final = dt.strftime("%H-%M")
        tpm_keys: Final = []
        rpm_keys: Final = []
        for m in healthy_deployments:
            if isinstance(m, dict):
                id = m.get("model_info", {}).get(
                    "id"
                )  # a deployment should always have an 'id'. this is set in router.py
                deployment_name = m.get("litellm_params", {}).get("model")
                tpm_key = f"{id}:{deployment_name}:tpm:{current_minute}"
                rpm_key = f"{id}:{deployment_name}:rpm:{current_minute}"

                tpm_keys.append(tpm_key)
                rpm_keys.append(rpm_key)

        tpm_values: Final = self.router_cache.batch_get_cache(
            keys=tpm_keys, parent_otel_span=parent_otel_span
        )  # [1, 2, None, ..]
        rpm_values: Final = self.router_cache.batch_get_cache(
            keys=rpm_keys, parent_otel_span=parent_otel_span
        )  # [1, 2, None, ..]

        deployment: Final = self._common_checks_available_deployment(
            model_group=model_group,
            healthy_deployments=healthy_deployments,
            tpm_keys=tpm_keys,
            tpm_values=tpm_values,
            rpm_keys=rpm_keys,
            rpm_values=rpm_values,
            messages=messages,
            input=input,
        )

        try:
            assert deployment is not None
            return deployment
        except Exception:
            ### GET THE DICT OF TPM / RPM + LIMITS PER DEPLOYMENT ###
            deployment_dict: Final = {}
            for index, _deployment in enumerate(healthy_deployments):
                if isinstance(_deployment, dict):
                    id = _deployment.get("model_info", {}).get("id")
                    ### GET DEPLOYMENT TPM LIMIT ###
                    _deployment_tpm = None
                    if _deployment_tpm is None:
                        _deployment_tpm = _deployment.get("tpm", None)
                    if _deployment_tpm is None:
                        _deployment_tpm = _deployment.get("litellm_params", {}).get("tpm", None)
                    if _deployment_tpm is None:
                        _deployment_tpm = _deployment.get("model_info", {}).get("tpm", None)
                    if _deployment_tpm is None:
                        _deployment_tpm = float("inf")

                    ### GET CURRENT TPM ###
                    current_tpm = tpm_values[index] if tpm_values else 0

                    ### GET DEPLOYMENT TPM LIMIT ###
                    _deployment_rpm = None
                    if _deployment_rpm is None:
                        _deployment_rpm = _deployment.get("rpm", None)
                    if _deployment_rpm is None:
                        _deployment_rpm = _deployment.get("litellm_params", {}).get("rpm", None)
                    if _deployment_rpm is None:
                        _deployment_rpm = _deployment.get("model_info", {}).get("rpm", None)
                    if _deployment_rpm is None:
                        _deployment_rpm = float("inf")

                    ### GET CURRENT RPM ###
                    current_rpm = rpm_values[index] if rpm_values else 0

                    deployment_dict[id] = {
                        "current_tpm": current_tpm,
                        "tpm_limit": _deployment_tpm,
                        "current_rpm": current_rpm,
                        "rpm_limit": _deployment_rpm,
                    }
            raise ValueError(
                f"{RouterErrors.no_deployments_available.value}. Passed model={model_group}. Deployments={deployment_dict}"
            )
```

### `litellm/router_strategy/least_busy.py`

```python
#### What this does ####
#   identifies least busy deployment
#   How is this achieved?
#   - Before each call, have the router print the state of requests {"deployment": "requests_in_flight"}
#   - use litellm.input_callbacks to log when a request is just about to be made to a model - {"deployment-id": traffic}
#   - use litellm.success + failure callbacks to log when a request completed
#   - in get_available_deployment, for a given model group name -> pick based on traffic

import random
from typing import Final

from litellm.caching.caching import DualCache
from litellm.integrations.custom_logger import CustomLogger


class LeastBusyLoggingHandler(CustomLogger):
    test_flag: bool = False
    logged_success: int = 0
    logged_failure: int = 0

    def __init__(self, router_cache: DualCache):
        self.router_cache = router_cache

    def log_pre_api_call(self, model, messages, kwargs):
        """
        Log when a model is being used.

        Caching based on model group.
        """
        try:
            if kwargs["litellm_params"].get("metadata") is None:
                pass
            else:
                model_group: Final = kwargs["litellm_params"]["metadata"].get("model_group", None)
                id = kwargs["litellm_params"].get("model_info", {}).get("id", None)
                if model_group is None or id is None:
                    return
                elif isinstance(id, int):
                    id = str(id)

                request_count_api_key: Final = f"{model_group}_request_count"
                # update cache
                request_count_dict: Final = self.router_cache.get_cache(key=request_count_api_key) or {}
                request_count_dict[id] = request_count_dict.get(id, 0) + 1

                self.router_cache.set_cache(key=request_count_api_key, value=request_count_dict)
        except Exception:
            pass

    def log_success_event(self, kwargs, response_obj, start_time, end_time):
        try:
            if kwargs["litellm_params"].get("metadata") is None:
                pass
            else:
                model_group: Final = kwargs["litellm_params"]["metadata"].get("model_group", None)

                id = kwargs["litellm_params"].get("model_info", {}).get("id", None)
                if model_group is None or id is None:
                    return
                elif isinstance(id, int):
                    id = str(id)

                request_count_api_key: Final = f"{model_group}_request_count"
                # decrement count in cache
                request_count_dict: Final = self.router_cache.get_cache(key=request_count_api_key) or {}
                request_count_value: Final[int | None] = request_count_dict.get(id, 0)
                if request_count_value is None:
                    return
                request_count_dict[id] = request_count_value - 1
                self.router_cache.set_cache(key=request_count_api_key, value=request_count_dict)

                ### TESTING ###
                if self.test_flag:
                    self.logged_success += 1
        except Exception:
            pass

    def log_failure_event(self, kwargs, response_obj, start_time, end_time):
        try:
            if kwargs["litellm_params"].get("metadata") is None:
                pass
            else:
                model_group: Final = kwargs["litellm_params"]["metadata"].get("model_group", None)
                id = kwargs["litellm_params"].get("model_info", {}).get("id", None)
                if model_group is None or id is None:
                    return
                elif isinstance(id, int):
                    id = str(id)

                request_count_api_key: Final = f"{model_group}_request_count"
                # decrement count in cache
                request_count_dict: Final = self.router_cache.get_cache(key=request_count_api_key) or {}
                request_count_value: Final[int | None] = request_count_dict.get(id, 0)
                if request_count_value is None:
                    return
                request_count_dict[id] = request_count_value - 1
                self.router_cache.set_cache(key=request_count_api_key, value=request_count_dict)

                ### TESTING ###
                if self.test_flag:
                    self.logged_failure += 1
        except Exception:
            pass

    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        try:
            if kwargs["litellm_params"].get("metadata") is None:
                pass
            else:
                model_group: Final = kwargs["litellm_params"]["metadata"].get("model_group", None)

                id = kwargs["litellm_params"].get("model_info", {}).get("id", None)
                if model_group is None or id is None:
                    return
                elif isinstance(id, int):
                    id = str(id)

                request_count_api_key: Final = f"{model_group}_request_count"
                # decrement count in cache
                request_count_dict: Final = await self.router_cache.async_get_cache(key=request_count_api_key) or {}
                request_count_value: Final[int | None] = request_count_dict.get(id, 0)
                if request_count_value is None:
                    return
                request_count_dict[id] = request_count_value - 1
                await self.router_cache.async_set_cache(key=request_count_api_key, value=request_count_dict)

                ### TESTING ###
                if self.test_flag:
                    self.logged_success += 1
        except Exception:
            pass

    async def async_log_failure_event(self, kwargs, response_obj, start_time, end_time):
        try:
            if kwargs["litellm_params"].get("metadata") is None:
                pass
            else:
                model_group: Final = kwargs["litellm_params"]["metadata"].get("model_group", None)
                id = kwargs["litellm_params"].get("model_info", {}).get("id", None)
                if model_group is None or id is None:
                    return
                elif isinstance(id, int):
                    id = str(id)

                request_count_api_key: Final = f"{model_group}_request_count"
                # decrement count in cache
                request_count_dict: Final = await self.router_cache.async_get_cache(key=request_count_api_key) or {}
                request_count_value: Final[int | None] = request_count_dict.get(id, 0)
                if request_count_value is None:
                    return
                request_count_dict[id] = request_count_value - 1
                await self.router_cache.async_set_cache(key=request_count_api_key, value=request_count_dict)

                ### TESTING ###
                if self.test_flag:
                    self.logged_failure += 1
        except Exception:
            pass

    def _get_available_deployments(
        self,
        healthy_deployments: list,
        all_deployments: dict,
    ):
        """
        Helper to get deployments using least busy strategy
        """
        for d in healthy_deployments:
            ## if healthy deployment not yet used
            if d["model_info"]["id"] not in all_deployments:
                all_deployments[d["model_info"]["id"]] = 0
        # map deployment to id
        # pick least busy deployment
        min_traffic = float("inf")
        min_deployment = None
        for k, v in all_deployments.items():
            if v < min_traffic:
                min_traffic = v
                min_deployment = k
        if min_deployment is not None:
            ## check if min deployment is a string, if so, cast it to int
            for m in healthy_deployments:
                if m["model_info"]["id"] == min_deployment:
                    return m
            min_deployment = random.choice(healthy_deployments)
        else:
            min_deployment = random.choice(healthy_deployments)
        return min_deployment

    def get_available_deployments(
        self,
        model_group: str,
        healthy_deployments: list,
    ):
        """
        Sync helper to get deployments using least busy strategy
        """
        request_count_api_key: Final = f"{model_group}_request_count"
        all_deployments: Final = self.router_cache.get_cache(key=request_count_api_key) or {}
        return self._get_available_deployments(
            healthy_deployments=healthy_deployments,
            all_deployments=all_deployments,
        )

    async def async_get_available_deployments(self, model_group: str, healthy_deployments: list):
        """
        Async helper to get deployments using least busy strategy
        """
        request_count_api_key: Final = f"{model_group}_request_count"
        all_deployments: Final = await self.router_cache.async_get_cache(key=request_count_api_key) or {}
        return self._get_available_deployments(
            healthy_deployments=healthy_deployments,
            all_deployments=all_deployments,
        )
```

## How to restore

The full source of every file above is inlined in this document, so it can be pasted back.
The cleaner route is git, since these files were untouched on the base branch:

```bash
git checkout litellm_internal_staging -- litellm/router_strategy/lowest_latency.py
git checkout litellm_internal_staging -- litellm/router_strategy/lowest_cost.py
git checkout litellm_internal_staging -- litellm/router_strategy/lowest_tpm_rpm.py
git checkout litellm_internal_staging -- litellm/router_strategy/lowest_tpm_rpm_v2.py
git checkout litellm_internal_staging -- litellm/router_strategy/least_busy.py
```

After restoring the files, put back the imports and call sites in `litellm/router.py`
that were removed alongside them, which the diff for this branch shows in full:

```bash
git diff litellm_internal_staging -- litellm/router.py
```
