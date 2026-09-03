# Retries, cooldowns and circuit breakers

> **Status: ANALYSED, NOT YET REMOVED.** The code below is still in the working tree.
> This document records what has to come out and why, plus the entanglement that stopped
> a clean deletion in this pass. Nothing here is deleted, so nothing here needs restoring
> yet; treat it as the specification for the next pass.

## Why this must be removed

A retry changes timing and ordering, and it can change which deployment actually served
the request. A cooldown removes a deployment from the pool for a period, so a later request
that names it is served by something else. A circuit breaker is the same thing driven by an
error-rate threshold. In all three cases the proxy is making a delivery decision.

`cooldown_handlers` decides when a deployment goes into cooldown and for how long,
`cooldown_cache` stores that state, and `cooldown_callbacks` fires the alerting.
`get_retry_from_policy` resolves the per-exception-type retry counts from a
`RetryPolicy`.

Retries deserve a specific note for an observer. If the proxy retries an upstream call, the
provider may have processed the first attempt, so the client is billed twice for one
logical request while the proxy reports one. Retry belongs to the client, which is the only
party that knows whether its request is safe to repeat.

## Files to remove

- `litellm/router_utils/cooldown_handlers.py` (625 lines)
- `litellm/router_utils/cooldown_cache.py` (203 lines)
- `litellm/router_utils/cooldown_callbacks.py` (97 lines)
- `litellm/router_utils/get_retry_from_policy.py` (56 lines)

### Why it did not come out in this pass

Same shape as the fallback work: the cooldown modules are referenced from 7, 4 and 2 files
respectively, and the retry paths are woven through the same `router.py` methods as the
fallback chain. They should be removed in one pass with the fallbacks, since a retry that
cannot fall back and a fallback that cannot retry are the same code path.

## The code in question

### `litellm/router_utils/cooldown_handlers.py`

```python
"""
Router cooldown handlers
- _set_cooldown_deployments: puts a deployment in the cooldown list
- get_cooldown_deployments: returns the list of deployments in the cooldown list
- async_get_cooldown_deployments: ASYNC: returns the list of deployments in the cooldown list

"""

import asyncio
import math
from collections.abc import Mapping
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Final

import litellm
from litellm._logging import verbose_router_logger
from litellm.constants import (
    DEFAULT_COOLDOWN_TIME_SECONDS,
    DEFAULT_FAILURE_THRESHOLD_MINIMUM_REQUESTS,
    DEFAULT_FAILURE_THRESHOLD_PERCENT,
    SINGLE_DEPLOYMENT_TRAFFIC_FAILURE_THRESHOLD,
)
from litellm.router_utils.cooldown_callbacks import router_cooldown_event_callback

from .router_callbacks.track_deployment_metrics import (
    get_deployment_failures_for_current_minute,
    get_deployment_successes_for_current_minute,
)

if TYPE_CHECKING:
    from opentelemetry.trace import Span as _Span

    from litellm.router import Router as _Router

    LitellmRouter = _Router
    Span = _Span | Any
else:
    LitellmRouter = Any
    Span = Any

_ADVISOR_ORCHESTRATION_FAILURE_ATTR: Final = "_litellm_advisor_orchestration_failure"


def mark_advisor_orchestration_failure(exception: BaseException) -> None:
    """Tag an exception as originating from advisor orchestration rather than the
    health of the router-selected deployment.

    Advisor orchestration failures (an advisor sub-call that targets different
    provider/credentials, or the orchestration loop exceeding max_uses) are not
    caused by the selected deployment, so they must not be attributed to (and
    cool down) that otherwise-healthy deployment. The exception object is tagged
    rather than wrapped so its type is preserved and the router's retry/fallback
    classification and the client-facing error are unchanged.
    """
    setattr(exception, _ADVISOR_ORCHESTRATION_FAILURE_ATTR, True)


def is_advisor_orchestration_failure(exception: BaseException | None) -> bool:
    """Whether ``exception`` was tagged by ``mark_advisor_orchestration_failure``."""
    return bool(getattr(exception, _ADVISOR_ORCHESTRATION_FAILURE_ATTR, False))


_EXCEPTION_POLICY_FIELDS: Final[tuple[tuple[type, str], ...]] = (
    # ContentPolicyViolationError subclasses BadRequestError, so it must be checked first.
    (litellm.ContentPolicyViolationError, "ContentPolicyViolationErrorAllowedFails"),
    (litellm.BadRequestError, "BadRequestErrorAllowedFails"),
    (litellm.AuthenticationError, "AuthenticationErrorAllowedFails"),
    (litellm.Timeout, "TimeoutErrorAllowedFails"),
    (litellm.RateLimitError, "RateLimitErrorAllowedFails"),
    (litellm.InternalServerError, "InternalServerErrorAllowedFails"),
    (litellm.ServiceUnavailableError, "ServiceUnavailableErrorAllowedFails"),
    (litellm.BadGatewayError, "BadGatewayErrorAllowedFails"),
    (litellm.NotFoundError, "NotFoundErrorAllowedFails"),
)


def _first_present(*sources: Mapping[str, Any] | None, key: str) -> int | float | None:
    """Return *key* from the first source mapping where it's set, so callers can
    support a setting living in more than one deployment config location. Sources
    are checked in order from most to least specific to that setting."""
    for source in sources:
        if source is None:
            continue
        value = source.get(key)
        if value is not None:
            return value
    return None


def _get_deployment_cooldown_policy(
    litellm_router_instance: LitellmRouter,
    deployment: str,
) -> tuple[Mapping[str, int] | None, int | None]:
    """Return (allowed_fails_policy, allowed_fails) from deployment model_info, or (None, None).

    `model_info` is the only supported location for these two fields (unlike
    `cooldown_time`, they have no pre-existing `litellm_params` precedent): `litellm_params`
    gets copied wholesale into the actual provider call kwargs (see e.g.
    Router._image_generation's `data = deployment["litellm_params"].copy()`), so a new
    field placed there would leak into the outgoing LLM request instead of staying
    router-internal.
    """
    dep: Final = litellm_router_instance.get_model_info(id=deployment)
    if dep is None:
        return None, None
    mi: Final[Mapping[str, Any]] = dep.get("model_info") or MappingProxyType({})
    raw: Final = mi.get("allowed_fails_policy")
    policy: Final[Mapping[str, int] | None] = raw if isinstance(raw, dict) else None
    allowed: Final[int | None] = mi.get("allowed_fails")
    return policy, allowed


def _resolve_allowed_fails_from_policy(
    policy: Mapping[str, int] | None,
    exception: Exception,
) -> int | None:
    """Match *exception* against *policy* and return the configured allowed-fail count, or None."""
    if policy is None:
        return None
    for exc_type, field in _EXCEPTION_POLICY_FIELDS:
        if isinstance(exception, exc_type):
            value = policy.get(field)
            if value is not None:
                return value
    return None


def _should_cooldown_based_on_deployment_policy(
    litellm_router_instance: LitellmRouter,
    deployment: str,
    original_exception: Exception,
    dep_policy: Mapping[str, int] | None,
    dep_allowed_fails: int | None,
    is_single_deployment_model_group: bool,
) -> bool:
    """Resolve deployment-level allowed-fails and delegate to the shared counting logic.

    When the deployment's policy doesn't cover *original_exception*'s type and no
    deployment-wide `allowed_fails` is set either, defer to router-level behavior
    instead of forcing an immediate cooldown.

    A generic, deployment-wide `allowed_fails` predates this feature's per-exception-type
    policy and is a much less deliberate opt-in, so on a single-deployment model group it
    still defers to the "avoid cooldowns on single deployment model groups" safety net
    (see `_should_cooldown_deployment`'s BASE CASE) rather than silently disabling it. An
    explicit, named-exception-type `allowed_fails_policy` entry is unambiguous enough to
    override that safety net, matching `_has_explicit_allowed_fails_policy_for_exception`.
    """
    allowed_fails_from_policy: Final = _resolve_allowed_fails_from_policy(dep_policy, original_exception)
    if allowed_fails_from_policy is None and dep_allowed_fails is not None and is_single_deployment_model_group:
        return False

    allowed_fails_override: Final[int | None] = (
        allowed_fails_from_policy if allowed_fails_from_policy is not None else dep_allowed_fails
    )
    cache_key_suffix: Final[str | None] = (
        type(original_exception).__name__
        if allowed_fails_from_policy is not None
        else ("generic" if dep_allowed_fails is not None else None)
    )

    dep: Final = litellm_router_instance.get_model_info(id=deployment)
    cooldown_time_override: Final = (
        _first_present(dep.get("model_info"), dep.get("litellm_params"), key="cooldown_time")
        if dep is not None
        else None
    )

    return should_cooldown_based_on_allowed_fails_policy(
        litellm_router_instance=litellm_router_instance,
        deployment=deployment,
        original_exception=original_exception,
        allowed_fails_override=allowed_fails_override,
        cooldown_time_override=cooldown_time_override,
        cache_key_suffix=cache_key_suffix,
    )


def _has_explicit_allowed_fails_policy_for_exception(
    litellm_router_instance: LitellmRouter,
    deployment: str | None,
    original_exception: Exception,
) -> bool:
    """True if this deployment has an explicit, deployment-level allowed_fails_policy
    entry matching *original_exception*'s type.

    `_is_cooldown_required` skips cooldown evaluation for most 4XX errors (BadRequestError,
    ContentPolicyViolationError) by default, since a generic client error is usually not the
    deployment's fault. A deployment-level allowed_fails_policy entry naming that exact
    exception type is this PR's own per-deployment opt-in, so it overrides that default.

    Deliberately scoped to the deployment level only, and to the named-exception-type
    policy dict rather than a plain `allowed_fails` integer: a pre-existing router-wide
    `allowed_fails_policy` (or a deployment's generic `allowed_fails`) predates this
    feature and must keep its existing behavior for 4XX types `_is_cooldown_required`
    already excludes, rather than silently start cooling down deployments whose configs
    never opted into this specific override.
    """
    if deployment is None:
        return False
    dep_policy, _ = _get_deployment_cooldown_policy(litellm_router_instance, deployment)
    return _resolve_allowed_fails_from_policy(dep_policy, original_exception) is not None


def _is_cooldown_required(
    litellm_router_instance: LitellmRouter,
    model_id: str,
    exception_status: str | int,
    exception_str: str | None = None,
) -> bool:
    """
    A function to determine if a cooldown is required based on the exception status.

    Parameters:
        model_id (str) The id of the model in the model list
        exception_status (Union[str, int]): The status of the exception.

    Returns:
        bool: True if a cooldown is required, False otherwise.
    """
    try:
        ignored_strings: Final = ["APIConnectionError"]
        if exception_str is not None:  # don't cooldown on litellm api connection errors errors
            for ignored_string in ignored_strings:
                if ignored_string in exception_str:
                    return False

        if isinstance(exception_status, str):
            if len(exception_status) == 0:
                return False
            exception_status = int(exception_status)

        if exception_status >= 400 and exception_status < 500:
            if exception_status == 429:
                # Cool down 429 Rate Limit Errors
                return True

            elif exception_status == 401:
                # Cool down 401 Auth Errors
                return True

            elif exception_status == 408 or exception_status == 404:
                return True

            else:
                # Do NOT cool down all other 4XX Errors
                return False

        else:
            # should cool down for all other errors
            return True

    except Exception:
        # Catch all - if any exceptions default to cooling down
        return True


def _should_run_cooldown_logic(
    litellm_router_instance: LitellmRouter,
    deployment: str | None,
    exception_status: str | int,
    original_exception: Any,
    time_to_cooldown: float | None = None,
) -> bool:
    """
    Helper that decides if cooldown logic should be run
    Returns False if cooldown logic should not be run

    Does not run cooldown logic when:
    - router.disable_cooldowns is True
    - deployment is None
    - _is_cooldown_required() returns False
    - deployment is in litellm_router_instance.provider_default_deployment_ids
    - exception_status is not one that should be immediately retried (e.g. 401)
    """
    if deployment is None or litellm_router_instance.get_model_group(id=deployment) is None:
        verbose_router_logger.debug(
            "Should Not Run Cooldown Logic: deployment id is none or model group can't be found."
        )
        return False

    #########################################################
    # If time_to_cooldown is 0 or 0.0000000, don't run cooldown logic
    #########################################################
    if time_to_cooldown is not None and math.isclose(a=time_to_cooldown, b=0.0, abs_tol=1e-9):
        verbose_router_logger.debug("Should Not Run Cooldown Logic: time_to_cooldown is effectively 0")
        return False

    if litellm_router_instance.disable_cooldowns:
        verbose_router_logger.debug("Should Not Run Cooldown Logic: disable_cooldowns is True")
        return False

    if deployment is None:
        verbose_router_logger.debug("Should Not Run Cooldown Logic: deployment is None")
        return False

    if not _is_cooldown_required(
        litellm_router_instance=litellm_router_instance,
        model_id=deployment,
        exception_status=exception_status,
        exception_str=str(original_exception),
    ) and not _has_explicit_allowed_fails_policy_for_exception(
        litellm_router_instance=litellm_router_instance,
        deployment=deployment,
        original_exception=original_exception,
    ):
        verbose_router_logger.debug("Should Not Run Cooldown Logic: _is_cooldown_required returned False")
        return False

    if deployment in litellm_router_instance.provider_default_deployment_ids:
        verbose_router_logger.debug("Should Not Run Cooldown Logic: deployment is in provider_default_deployment_ids")
        return False

    return True


def _should_cooldown_deployment(
    litellm_router_instance: LitellmRouter,
    deployment: str,
    exception_status: str | int,
    original_exception: Any,
    requested_model_group: str | None = None,
) -> bool:
    """
    Helper that decides if a deployment should be put in cooldown

    Returns True if the deployment should be put in cooldown
    Returns False if the deployment should not be put in cooldown


    Deployment is put in cooldown when:
    - v2 logic (Current):
    cooldown if:
        - got a 429 error from LLM API
        - if %fails/%(successes + fails) > ALLOWED_FAILURE_RATE_PER_MINUTE
        - got 401 Auth error, 404 NotFounder - checked by litellm._should_retry()



    - v1 logic (Legacy): if allowed fails or allowed fail policy set, coolsdown if num fails in this minute > allowed fails
    """
    model_group: Final = litellm_router_instance.get_model_group(id=deployment)
    is_single_deployment_model_group = False
    if model_group is not None and len(model_group) == 1:
        is_single_deployment_model_group = not litellm_router_instance.routing_group_has_alternatives(
            requested_model_group
        )

    ## CHECK DEPLOYMENT-LEVEL POLICY FIRST (overrides router-level)
    dep_policy, dep_allowed_fails = _get_deployment_cooldown_policy(litellm_router_instance, deployment)
    if dep_policy is not None or dep_allowed_fails is not None:
        return _should_cooldown_based_on_deployment_policy(
            litellm_router_instance,
            deployment,
            original_exception,
            dep_policy,
            dep_allowed_fails,
            is_single_deployment_model_group,
        )

    ## BASE CASE - single deployment
    if (
        litellm_router_instance.allowed_fails_policy is None
        and _is_allowed_fails_set_on_router(litellm_router_instance=litellm_router_instance) is False
    ):
        num_successes_this_minute: Final = get_deployment_successes_for_current_minute(
            litellm_router_instance=litellm_router_instance, deployment_id=deployment
        )
        num_fails_this_minute: Final = get_deployment_failures_for_current_minute(
            litellm_router_instance=litellm_router_instance, deployment_id=deployment
        )

        total_requests_this_minute: Final = num_successes_this_minute + num_fails_this_minute
        percent_fails = 0.0
        if total_requests_this_minute > 0:
            percent_fails = num_fails_this_minute / (num_successes_this_minute + num_fails_this_minute)
        verbose_router_logger.debug(
            "percent fails for deployment = %s, percent fails = %s, num successes = %s, num fails = %s",
            deployment,
            percent_fails,
            num_successes_this_minute,
            num_fails_this_minute,
        )

        exception_status_int: Final = cast_exception_status_to_int(exception_status)
        if exception_status_int == 429 and not is_single_deployment_model_group:
            return True
        elif percent_fails == 1.0 and total_requests_this_minute >= SINGLE_DEPLOYMENT_TRAFFIC_FAILURE_THRESHOLD:
            # Cooldown if all requests failed and we have reasonable traffic
            return True
        elif (
            percent_fails > DEFAULT_FAILURE_THRESHOLD_PERCENT
            and total_requests_this_minute >= DEFAULT_FAILURE_THRESHOLD_MINIMUM_REQUESTS
            and not is_single_deployment_model_group  # by default we should avoid cooldowns on single deployment model groups
        ):
            # Only apply error rate cooldown when we have enough requests to make the percentage meaningful
            return True

        elif litellm._should_retry(status_code=cast_exception_status_to_int(exception_status)) is False:
            return True

        return False
    else:
        return should_cooldown_based_on_allowed_fails_policy(
            litellm_router_instance=litellm_router_instance,
            deployment=deployment,
            original_exception=original_exception,
        )

    return False


def _set_cooldown_deployments(
    litellm_router_instance: LitellmRouter,
    original_exception: Any,
    exception_status: str | int,
    deployment: str | None = None,
    time_to_cooldown: float | None = None,
    requested_model_group: str | None = None,
) -> bool:
    """
    Add a model to the list of models being cooled down for that minute, if it exceeds the allowed fails / minute

    or

    the exception is not one that should be immediately retried (e.g. 401)

    Returns:
    - True if the deployment should be put in cooldown
    - False if the deployment should not be put in cooldown
    """
    verbose_router_logger.debug("checks 'should_run_cooldown_logic'")

    if (
        _should_run_cooldown_logic(
            litellm_router_instance=litellm_router_instance,
            deployment=deployment,
            exception_status=exception_status,
            original_exception=original_exception,
            time_to_cooldown=time_to_cooldown,
        )
        is False
        or deployment is None
    ):
        verbose_router_logger.debug("should_run_cooldown_logic returned False")
        return False

    exception_status_int: Final = cast_exception_status_to_int(exception_status)
    verbose_router_logger.debug("Attempting to add %s to cooldown list", deployment)

    if _should_cooldown_deployment(
        litellm_router_instance=litellm_router_instance,
        deployment=deployment,
        exception_status=exception_status,
        original_exception=original_exception,
        requested_model_group=requested_model_group,
    ):
        litellm_router_instance.cooldown_cache.add_deployment_to_cooldown(
            model_id=deployment,
            original_exception=original_exception,
            exception_status=exception_status_int,
            cooldown_time=time_to_cooldown,
        )

        # Trigger cooldown callback handler
        asyncio.create_task(
            router_cooldown_event_callback(
                litellm_router_instance=litellm_router_instance,
                deployment_id=deployment,
                exception_status=exception_status,
                cooldown_time=time_to_cooldown,
            )
        )
        return True
    return False


async def _async_get_cooldown_deployments(
    litellm_router_instance: LitellmRouter,
    parent_otel_span: Span | None,
) -> list[str]:
    """
    Async implementation of '_get_cooldown_deployments'
    """
    model_ids: Final = litellm_router_instance.get_model_ids()
    cooldown_models: Final = await litellm_router_instance.cooldown_cache.async_get_active_cooldowns(
        model_ids=model_ids,
        parent_otel_span=parent_otel_span,
    )

    cached_value_deployment_ids = []
    if (
        cooldown_models is not None
        and isinstance(cooldown_models, list)
        and len(cooldown_models) > 0
        and isinstance(cooldown_models[0], tuple)
    ):
        cached_value_deployment_ids = [cv[0] for cv in cooldown_models]

    verbose_router_logger.debug("retrieve cooldown models: %s", cooldown_models)
    return cached_value_deployment_ids


async def _async_get_cooldown_deployments_with_debug_info(
    litellm_router_instance: LitellmRouter,
    parent_otel_span: Span | None,
) -> list[tuple]:
    """
    Async implementation of '_get_cooldown_deployments'
    """
    model_ids: Final = litellm_router_instance.get_model_ids()
    cooldown_models: Final = await litellm_router_instance.cooldown_cache.async_get_active_cooldowns(
        model_ids=model_ids, parent_otel_span=parent_otel_span
    )

    verbose_router_logger.debug("retrieve cooldown models: %s", cooldown_models)
    return cooldown_models


def _get_cooldown_deployments(litellm_router_instance: LitellmRouter, parent_otel_span: Span | None) -> list[str]:
    """
    Get the list of models being cooled down for this minute
    """
    # get the current cooldown list for that minute

    # ----------------------
    # Return cooldown models
    # ----------------------
    model_ids: Final = litellm_router_instance.get_model_ids()

    cooldown_models: Final = litellm_router_instance.cooldown_cache.get_active_cooldowns(
        model_ids=model_ids, parent_otel_span=parent_otel_span
    )

    cached_value_deployment_ids = []
    if (
        cooldown_models is not None
        and isinstance(cooldown_models, list)
        and len(cooldown_models) > 0
        and isinstance(cooldown_models[0], tuple)
    ):
        cached_value_deployment_ids = [cv[0] for cv in cooldown_models]

    return cached_value_deployment_ids


def should_cooldown_based_on_allowed_fails_policy(
    litellm_router_instance: LitellmRouter,
    deployment: str,
    original_exception: Any,
    allowed_fails_override: int | None = None,
    cooldown_time_override: float | None = None,
    cache_key_suffix: str | None = None,
) -> bool:
    """
    Check if fails are within the allowed limit and update the number of fails.

    When *allowed_fails_override* / *cooldown_time_override* are supplied they
    take precedence over the router-level values (used by deployment-level overrides).

    When *cache_key_suffix* is supplied the fail counter is keyed as
    ``{deployment}:{cache_key_suffix}`` so that different exception types are
    tracked independently per deployment.

    Returns:
    - True if fails exceed the allowed limit (should cooldown)
    - False if fails are within the allowed limit (should not cooldown)
    """
    allowed_fails_from_policy: Final = litellm_router_instance.get_allowed_fails_from_policy(
        exception=original_exception
    )
    allowed_fails: Final = (
        allowed_fails_override
        if allowed_fails_override is not None
        else (
            allowed_fails_from_policy
            if allowed_fails_from_policy is not None
            else litellm_router_instance.allowed_fails
        )
    )
    cooldown_time: Final = (
        cooldown_time_override
        if cooldown_time_override is not None
        else (litellm_router_instance.cooldown_time or DEFAULT_COOLDOWN_TIME_SECONDS)
    )

    cache_key: Final = f"{deployment}:{cache_key_suffix}" if cache_key_suffix else deployment
    current_fails: Final = litellm_router_instance.failed_calls.get_cache(key=cache_key) or 0
    updated_fails: Final = current_fails + 1

    if updated_fails > allowed_fails:
        return True
    else:
        litellm_router_instance.failed_calls.set_cache(key=cache_key, value=updated_fails, ttl=cooldown_time)

    return False


def _is_allowed_fails_set_on_router(
    litellm_router_instance: LitellmRouter,
) -> bool:
    """
    Check if Router.allowed_fails is set or is Non-default Value

    Returns:
    - True if Router.allowed_fails is set or is Non-default Value
    - False if Router.allowed_fails is None or is Default Value
    """
    if litellm_router_instance.allowed_fails is None:
        return False
    if litellm_router_instance.allowed_fails != litellm.allowed_fails:
        return True
    return False


def cast_exception_status_to_int(exception_status: str | int) -> int:
    if isinstance(exception_status, str):
        try:
            exception_status = int(exception_status)
        except Exception:
            verbose_router_logger.debug(
                "Unable to cast exception status to int %s. Defaulting to status=500.", exception_status
            )
            exception_status = 500
    return exception_status
```

### `litellm/router_utils/cooldown_cache.py`

```python
"""
Wrapper around router cache. Meant to handle model cooldown logic
"""

import functools
import time
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Final

from typing_extensions import TypedDict

from litellm import verbose_logger
from litellm.caching.caching import DualCache
from litellm.caching.in_memory_cache import InMemoryCache
from litellm.litellm_core_utils.sensitive_data_masker import SensitiveDataMasker

if TYPE_CHECKING:
    from opentelemetry.trace import Span as _Span

    Span = _Span | Any
else:
    Span = Any


class CooldownCacheValue(TypedDict):
    exception_received: str
    status_code: str
    timestamp: float
    cooldown_time: float


# Cap on the corrected in-memory TTL set in `_corrected_active_cooldown`: re-checks the
# real remaining cooldown against Redis at least this often, so an entry that later gets
# deleted or extended in Redis before its original deadline is still noticed promptly.
_MAX_CORRECTED_IN_MEMORY_TTL_SECONDS: Final = 60.0


class CooldownCache:
    def __init__(self, cache: DualCache, default_cooldown_time: float):
        self.cache = cache
        self.default_cooldown_time = default_cooldown_time
        self.in_memory_cache = InMemoryCache()
        # Initialize the masker with custom settings for exception strings
        self.exception_masker = SensitiveDataMasker(
            visible_prefix=50,  # Show first 50 characters
            visible_suffix=0,  # Show last 0 characters
            mask_char="*",  # Use * for masking
            mask_short_values=False,  # Truncate long messages only; keep short ones readable
        )

    def _common_add_cooldown_logic(
        self, model_id: str, original_exception, exception_status, cooldown_time: float
    ) -> tuple[str, CooldownCacheValue]:
        try:
            current_time: Final = time.time()
            cooldown_key: Final = CooldownCache.get_cooldown_cache_key(model_id)

            # Store the cooldown information for the deployment separately
            cooldown_data: Final = CooldownCacheValue(
                exception_received=self.exception_masker._mask_value(str(original_exception)),
                status_code=str(exception_status),
                timestamp=current_time,
                cooldown_time=cooldown_time,
            )

            return cooldown_key, cooldown_data
        except Exception as e:
            verbose_logger.error("CooldownCache::_common_add_cooldown_logic - Exception occurred - %s", e)
            raise e

    def add_deployment_to_cooldown(
        self,
        model_id: str,
        original_exception: Exception,
        exception_status: int,
        cooldown_time: float | None,
    ):
        try:
            #########################################################
            # get cooldown time
            # 1. If dynamic cooldown time is set for the model/deployment, use that
            # 2. If no dynamic cooldown time is set, use the default cooldown time set on CooldownCache
            _cooldown_time = cooldown_time
            if _cooldown_time is None:
                _cooldown_time = self.default_cooldown_time
            #########################################################

            cooldown_key, cooldown_data = self._common_add_cooldown_logic(
                model_id=model_id,
                original_exception=original_exception,
                exception_status=exception_status,
                cooldown_time=_cooldown_time,
            )

            # Set the cache with a TTL equal to the cooldown time
            self.cache.set_cache(
                value=cooldown_data,
                key=cooldown_key,
                ttl=_cooldown_time,
            )
        except Exception as e:
            verbose_logger.error("CooldownCache::add_deployment_to_cooldown - Exception occurred - %s", e)
            raise e

    @staticmethod
    @functools.lru_cache(maxsize=1024)
    def get_cooldown_cache_key(model_id: str) -> str:
        return "deployment:" + model_id + ":cooldown"

    def _corrected_active_cooldown(
        self,
        key: str,
        result: Mapping[str, Any],
        current_time: float,
    ) -> CooldownCacheValue | None:
        """
        Return a CooldownCacheValue if the cooldown is still active, or None if it has expired.

        Also corrects the in-memory TTL when DualCache promotes a Redis entry using the
        default 600s TTL instead of the true remaining cooldown time.
        """
        cooldown_cache_value: Final = CooldownCacheValue(**result)  # pyright: ignore[reportUnknownArgumentType] - result comes from an untyped cache read, not from our own code
        remaining: Final = (cooldown_cache_value["timestamp"] + cooldown_cache_value["cooldown_time"]) - current_time
        if remaining <= 0:
            self.cache.in_memory_cache.delete_cache(key)
            return None
        current_expiry: Final = self.cache.in_memory_cache.ttl_dict.get(key)
        if current_expiry is not None and current_expiry > current_time + remaining + 5:
            corrected_ttl: Final = min(remaining, _MAX_CORRECTED_IN_MEMORY_TTL_SECONDS)
            self.cache.in_memory_cache.delete_cache(key)
            self.cache.in_memory_cache.set_cache(key, result, ttl=corrected_ttl)
        return cooldown_cache_value

    async def async_get_active_cooldowns(
        self, model_ids: list[str], parent_otel_span: Span | None
    ) -> list[tuple[str, CooldownCacheValue]]:
        # Generate the keys for the deployments
        keys: Final = [CooldownCache.get_cooldown_cache_key(model_id) for model_id in model_ids]

        # Retrieve the values for the keys using mget
        ## more likely to be none if no models ratelimited. So just check redis every 1s
        ## each redis call adds ~100ms latency.

        ## check in memory cache first
        results: Final = await self.cache.async_batch_get_cache(keys=keys, parent_otel_span=parent_otel_span)
        active_cooldowns: Final[list[tuple[str, CooldownCacheValue]]] = []

        if results is None or all(v is None for v in results):
            return active_cooldowns

        current_time: Final = time.time()
        for model_id, result in zip(model_ids, results):
            if result and isinstance(result, dict):
                key = CooldownCache.get_cooldown_cache_key(model_id)
                cooldown_cache_value = self._corrected_active_cooldown(key, result, current_time)
                if cooldown_cache_value is not None:
                    active_cooldowns.append((model_id, cooldown_cache_value))

        return active_cooldowns

    def get_active_cooldowns(
        self, model_ids: list[str], parent_otel_span: Span | None
    ) -> list[tuple[str, CooldownCacheValue]]:
        # Generate the keys for the deployments
        keys: Final = [CooldownCache.get_cooldown_cache_key(model_id) for model_id in model_ids]
        # Retrieve the values for the keys using mget
        results: Final = self.cache.batch_get_cache(keys=keys, parent_otel_span=parent_otel_span) or []

        active_cooldowns: Final = []
        current_time: Final = time.time()
        for model_id, result in zip(model_ids, results):
            if result and isinstance(result, dict):
                key = CooldownCache.get_cooldown_cache_key(model_id)
                cooldown_cache_value = self._corrected_active_cooldown(key, result, current_time)
                if cooldown_cache_value is not None:
                    active_cooldowns.append((model_id, cooldown_cache_value))

        return active_cooldowns

    def get_min_cooldown(self, model_ids: list[str], parent_otel_span: Span | None) -> float:
        """Return min cooldown time required for a group of model id's."""

        # Generate the keys for the deployments
        keys: Final = [f"deployment:{model_id}:cooldown" for model_id in model_ids]

        # Retrieve the values for the keys using mget
        results: Final = self.cache.batch_get_cache(keys=keys, parent_otel_span=parent_otel_span) or []

        min_cooldown_time: float | None = None
        # Process the results
        for model_id, result in zip(model_ids, results):
            if result and isinstance(result, dict):
                cooldown_cache_value = CooldownCacheValue(**result)
                if min_cooldown_time is None or cooldown_cache_value["cooldown_time"] < min_cooldown_time:
                    min_cooldown_time = cooldown_cache_value["cooldown_time"]

        return min_cooldown_time or self.default_cooldown_time


# Usage example:
# cooldown_cache = CooldownCache(cache=your_cache_instance, cooldown_time=your_cooldown_time)
# cooldown_cache.add_deployment_to_cooldown(deployment, original_exception, exception_status)
# active_cooldowns = cooldown_cache.get_active_cooldowns()
```

### `litellm/router_utils/cooldown_callbacks.py`

```python
"""
Callbacks triggered on cooling down deployments
"""

import copy
from typing import TYPE_CHECKING, Any, Final

import litellm
from litellm._logging import verbose_logger

if TYPE_CHECKING:
    from litellm.router import Router as _Router

    LitellmRouter = _Router
    from litellm.integrations.prometheus import PrometheusLogger
else:
    LitellmRouter = Any
    PrometheusLogger = Any


async def router_cooldown_event_callback(
    litellm_router_instance: LitellmRouter,
    deployment_id: str,
    exception_status: str | int,
    cooldown_time: float | None,
):
    """
    Callback triggered when a deployment is put into cooldown by litellm

    - Updates deployment state on Prometheus
    - Increments cooldown metric for deployment on Prometheus
    """
    verbose_logger.debug("In router_cooldown_event_callback - updating prometheus")
    _deployment: Final = litellm_router_instance.get_deployment(model_id=deployment_id)
    if _deployment is None:
        verbose_logger.warning(
            "in router_cooldown_event_callback but _deployment is None for deployment_id=%s. Doing nothing",
            deployment_id,
        )
        return
    _litellm_params: Final = _deployment["litellm_params"]
    temp_litellm_params = copy.deepcopy(_litellm_params)
    temp_litellm_params = dict(temp_litellm_params)
    _model_name: Final = _deployment.get("model_name", None) or ""
    _api_base: Final = litellm.get_api_base(model=_model_name, optional_params=temp_litellm_params) or ""
    model_info: Final = _deployment["model_info"]
    model_id: Final = model_info.id

    litellm_model_name: Final = temp_litellm_params.get("model") or ""
    llm_provider = ""
    try:
        _, llm_provider, _, _ = litellm.get_llm_provider(
            model=litellm_model_name,
            custom_llm_provider=temp_litellm_params.get("custom_llm_provider"),
        )
    except Exception:
        pass

    # get the prometheus logger from in memory loggers
    prometheusLogger: Final[PrometheusLogger | None] = _get_prometheus_logger_from_callbacks()

    if prometheusLogger is not None:
        prometheusLogger.set_deployment_complete_outage(
            litellm_model_name=_model_name,
            model_id=model_id,
            api_base=_api_base,
            api_provider=llm_provider,
        )

        prometheusLogger.increment_deployment_cooled_down(
            litellm_model_name=_model_name,
            model_id=model_id,
            api_base=_api_base,
            api_provider=llm_provider,
            exception_status=str(exception_status),
        )

    return


def _get_prometheus_logger_from_callbacks() -> PrometheusLogger | None:
    """
    Checks if prometheus is a initalized callback, if yes returns it
    """
    from litellm.integrations.prometheus import PrometheusLogger

    if PrometheusLogger is None:
        return None

    for _callback in litellm._async_success_callback:
        if isinstance(_callback, PrometheusLogger):
            return _callback
    for global_callback in litellm.callbacks:
        if isinstance(global_callback, PrometheusLogger):
            return global_callback

    return None
```

### `litellm/router_utils/get_retry_from_policy.py`

```python
"""
Get num retries for an exception.

- Account for retry policy by exception type.
"""

from litellm.exceptions import (
    AuthenticationError,
    BadRequestError,
    ContentPolicyViolationError,
    RateLimitError,
    Timeout,
)
from litellm.types.router import RetryPolicy


def get_num_retries_from_retry_policy(
    exception: Exception,
    retry_policy: RetryPolicy | dict | None = None,
    model_group: str | None = None,
    model_group_retry_policy: dict[str, RetryPolicy] | None = None,
):
    """
    BadRequestErrorRetries: Optional[int] = None
    AuthenticationErrorRetries: Optional[int] = None
    TimeoutErrorRetries: Optional[int] = None
    RateLimitErrorRetries: Optional[int] = None
    ContentPolicyViolationErrorRetries: Optional[int] = None
    """
    # if we can find the exception then in the retry policy -> return the number of retries

    if model_group_retry_policy is not None and model_group is not None and model_group in model_group_retry_policy:
        retry_policy = model_group_retry_policy.get(model_group, None)

    if retry_policy is None:
        return None
    if isinstance(retry_policy, dict):
        retry_policy = RetryPolicy(**retry_policy)

    if isinstance(exception, AuthenticationError) and retry_policy.AuthenticationErrorRetries is not None:
        return retry_policy.AuthenticationErrorRetries
    if isinstance(exception, Timeout) and retry_policy.TimeoutErrorRetries is not None:
        return retry_policy.TimeoutErrorRetries
    if isinstance(exception, RateLimitError) and retry_policy.RateLimitErrorRetries is not None:
        return retry_policy.RateLimitErrorRetries
    if (
        isinstance(exception, ContentPolicyViolationError)
        and retry_policy.ContentPolicyViolationErrorRetries is not None
    ):
        return retry_policy.ContentPolicyViolationErrorRetries
    if isinstance(exception, BadRequestError) and retry_policy.BadRequestErrorRetries is not None:
        return retry_policy.BadRequestErrorRetries


def reset_retry_policy() -> RetryPolicy:
    return RetryPolicy()
```

## How to restore (once removed)

The full source of every file above is inlined in this document, so it can be pasted back.
The cleaner route is git, since these files were untouched on the base branch:

```bash
git checkout litellm_internal_staging -- litellm/router_utils/cooldown_handlers.py
git checkout litellm_internal_staging -- litellm/router_utils/cooldown_cache.py
git checkout litellm_internal_staging -- litellm/router_utils/cooldown_callbacks.py
git checkout litellm_internal_staging -- litellm/router_utils/get_retry_from_policy.py
```

After restoring the files, put back the imports and call sites in `litellm/router.py`
that were removed alongside them, which the diff for this branch shows in full:

```bash
git diff litellm_internal_staging -- litellm/router.py
```
