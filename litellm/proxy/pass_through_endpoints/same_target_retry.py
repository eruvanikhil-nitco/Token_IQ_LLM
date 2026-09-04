"""Retry a pass-through request against the exact endpoint the client named.

The gateway forwards a request and returns what the provider returned. When the
provider cannot be reached, or answers that it did not process the request, the
gateway re-sends the identical bytes to the same endpoint. It never changes the
URL, the body, the headers, the model or the provider, so a retry is invisible in
the response except for having taken longer.

See project_usage/13-same-target-passthrough-retry.md
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Final

import httpx

from litellm._logging import verbose_proxy_logger

# Statuses where the provider is telling us it did not do the work: a rate limit,
# or a gateway that never reached the origin. A 500 is deliberately absent, since
# the provider may have processed the request before failing to answer, and a
# retry would bill the caller twice for one logical call.
RETRYABLE_STATUS_CODES: Final = frozenset({429, 502, 503, 504})

# Connect and pool errors mean the request never reached the provider. Read and
# write timeouts are excluded for the same reason 500 is: the request may already
# be in flight, so re-sending can duplicate it.
RETRYABLE_TRANSPORT_ERRORS: Final = (
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.PoolTimeout,
)

MAX_RETRY_AFTER_SECONDS: Final = 30.0


@dataclass(frozen=True, slots=True)
class SameTargetRetryPolicy:
    """How many times to re-send, and how long to wait between attempts."""

    max_attempts: int = 3
    initial_backoff_seconds: float = 0.5
    max_backoff_seconds: float = 8.0

    @property
    def enabled(self) -> bool:
        return self.max_attempts > 1


def _retry_after_seconds(response: httpx.Response) -> float | None:
    """Seconds the provider asked us to wait, when it said so in a form we trust."""
    raw: Final = response.headers.get("retry-after")
    if raw is None:
        return None
    try:
        seconds = float(raw.strip())
    except ValueError:
        # The HTTP-date form is legal but rare from LLM providers; fall back to
        # our own backoff rather than pulling in a date parser for it.
        return None
    if seconds < 0:
        return None
    return min(seconds, MAX_RETRY_AFTER_SECONDS)


def _backoff_seconds(policy: SameTargetRetryPolicy, attempt: int) -> float:
    """Exponential backoff for the attempt just failed, capped by the policy."""
    return min(policy.initial_backoff_seconds * (2**attempt), policy.max_backoff_seconds)


async def send_with_same_target_retry(
    *,
    send: Callable[[], Awaitable[httpx.Response]],
    policy: SameTargetRetryPolicy,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> httpx.Response:
    """Send, and re-send the identical request to the same endpoint on a retryable failure.

    `send` must build and dispatch the request afresh on every call, so nothing is
    carried over between attempts.

    A response that is returned to the caller is never read here, so a streaming
    body stays intact. A response that is retried is closed first, which releases
    its connection back to the pool.

    The last attempt's outcome is what the caller gets: a retryable status is
    returned like any other response, and a transport error is re-raised, so the
    client sees the provider's own failure rather than one this gateway invented.
    """
    last_error: BaseException | None = None

    for attempt in range(policy.max_attempts):
        is_last: Final = attempt == policy.max_attempts - 1
        try:
            response = await send()
        except RETRYABLE_TRANSPORT_ERRORS as exc:
            last_error = exc
            if is_last:
                raise
            wait: Final = _backoff_seconds(policy, attempt)
            verbose_proxy_logger.warning(
                "pass-through: %s reaching the provider, re-sending the same request in %.2fs (attempt %d/%d)",
                type(exc).__name__,
                wait,
                attempt + 1,
                policy.max_attempts,
            )
            await sleep(wait)
            continue

        if is_last or response.status_code not in RETRYABLE_STATUS_CODES:
            return response

        await response.aclose()
        wait = _retry_after_seconds(response) or _backoff_seconds(policy, attempt)
        verbose_proxy_logger.warning(
            "pass-through: provider returned %d, re-sending the same request in %.2fs (attempt %d/%d)",
            response.status_code,
            wait,
            attempt + 1,
            policy.max_attempts,
        )
        await sleep(wait)

    # Unreachable: the final attempt either returns or raises above. Kept so a
    # future edit to the loop cannot silently fall through to None.
    raise last_error or RuntimeError("same-target retry exhausted without a result")


DEFAULT_PASSTHROUGH_NUM_RETRIES: Final = 2


def passthrough_retry_policy() -> SameTargetRetryPolicy:
    """Resolve the policy from `general_settings.passthrough_num_retries`.

    The setting counts retries, so 2 means up to three attempts. Setting it to 0
    turns retrying off and makes the gateway a single-shot forwarder.
    """
    from litellm.proxy.proxy_server import general_settings

    configured: Final = general_settings.get("passthrough_num_retries", DEFAULT_PASSTHROUGH_NUM_RETRIES)
    try:
        num_retries: Final = max(0, int(configured))
    except (TypeError, ValueError):
        verbose_proxy_logger.warning(
            "pass-through: passthrough_num_retries=%r is not an integer, using %d",
            configured,
            DEFAULT_PASSTHROUGH_NUM_RETRIES,
        )
        return SameTargetRetryPolicy(max_attempts=DEFAULT_PASSTHROUGH_NUM_RETRIES + 1)
    return SameTargetRetryPolicy(max_attempts=num_retries + 1)
