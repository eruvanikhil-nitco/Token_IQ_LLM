import httpx
import pytest

from token_iq.policy.same_target_retry import (
    SameTargetRetryPolicy,
    passthrough_retry_policy,
    send_with_same_target_retry,
)

NO_WAIT = SameTargetRetryPolicy(max_attempts=3, initial_backoff_seconds=0, max_backoff_seconds=0)


def _response(status_code: int, headers: dict[str, str] | None = None) -> httpx.Response:
    return httpx.Response(status_code, headers=headers or {}, request=httpx.Request("POST", "https://p/x"))


class _Recorder:
    """Collects the sleeps the helper asked for, so waiting is asserted not slept."""

    def __init__(self) -> None:
        self.waits: list[float] = []

    async def sleep(self, seconds: float) -> None:
        self.waits.append(seconds)


@pytest.mark.asyncio
async def test_a_successful_response_is_returned_without_retrying() -> None:
    calls = 0

    async def send() -> httpx.Response:
        nonlocal calls
        calls += 1
        return _response(200)

    recorder = _Recorder()
    result = await send_with_same_target_retry(send=send, policy=NO_WAIT, sleep=recorder.sleep)

    assert result.status_code == 200
    assert calls == 1
    assert recorder.waits == []


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [429, 502, 503, 504])
async def test_a_retryable_status_is_re_sent_to_the_same_endpoint(status: int) -> None:
    seen: list[int] = []

    async def send() -> httpx.Response:
        seen.append(status)
        return _response(status) if len(seen) == 1 else _response(200)

    recorder = _Recorder()
    result = await send_with_same_target_retry(send=send, policy=NO_WAIT, sleep=recorder.sleep)

    assert result.status_code == 200
    assert len(seen) == 2
    assert len(recorder.waits) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [400, 401, 403, 404, 422, 500])
async def test_a_status_the_provider_meant_is_returned_untouched(status: int) -> None:
    """A 4xx is the provider's answer, and a 500 may mean the work was already done.
    Re-sending either would change the response or bill the caller twice."""
    calls = 0

    async def send() -> httpx.Response:
        nonlocal calls
        calls += 1
        return _response(status)

    result = await send_with_same_target_retry(send=send, policy=NO_WAIT, sleep=_Recorder().sleep)

    assert result.status_code == status
    assert calls == 1


@pytest.mark.asyncio
async def test_the_provider_failure_survives_when_every_attempt_is_retryable() -> None:
    """The client must see the provider's own 503, not an error the gateway invented."""
    calls = 0

    async def send() -> httpx.Response:
        nonlocal calls
        calls += 1
        return _response(503)

    result = await send_with_same_target_retry(send=send, policy=NO_WAIT, sleep=_Recorder().sleep)

    assert result.status_code == 503
    assert calls == 3


@pytest.mark.asyncio
async def test_a_connect_error_is_re_sent_then_re_raised_when_it_never_succeeds() -> None:
    calls = 0

    async def send() -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ConnectError("no route to provider")

    with pytest.raises(httpx.ConnectError):
        await send_with_same_target_retry(send=send, policy=NO_WAIT, sleep=_Recorder().sleep)

    assert calls == 3


@pytest.mark.asyncio
async def test_a_read_timeout_is_not_re_sent() -> None:
    """The request may already be in flight, so re-sending could duplicate a paid call."""
    calls = 0

    async def send() -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("provider is slow")

    with pytest.raises(httpx.ReadTimeout):
        await send_with_same_target_retry(send=send, policy=NO_WAIT, sleep=_Recorder().sleep)

    assert calls == 1


@pytest.mark.asyncio
async def test_retry_after_from_the_provider_is_honoured_over_our_backoff() -> None:
    async def send() -> httpx.Response:
        return _response(429, {"retry-after": "7"})

    recorder = _Recorder()
    await send_with_same_target_retry(send=send, policy=NO_WAIT, sleep=recorder.sleep)

    assert recorder.waits == [7.0, 7.0]


@pytest.mark.asyncio
async def test_an_unparseable_retry_after_falls_back_to_our_backoff() -> None:
    policy = SameTargetRetryPolicy(max_attempts=2, initial_backoff_seconds=0.5, max_backoff_seconds=8)

    async def send() -> httpx.Response:
        return _response(503, {"retry-after": "Wed, 21 Oct 2026 07:28:00 GMT"})

    recorder = _Recorder()
    await send_with_same_target_retry(send=send, policy=policy, sleep=recorder.sleep)

    assert recorder.waits == [0.5]


@pytest.mark.asyncio
async def test_backoff_grows_and_is_capped_by_the_policy() -> None:
    policy = SameTargetRetryPolicy(max_attempts=5, initial_backoff_seconds=1, max_backoff_seconds=3)

    async def send() -> httpx.Response:
        return _response(503)

    recorder = _Recorder()
    await send_with_same_target_retry(send=send, policy=policy, sleep=recorder.sleep)

    assert recorder.waits == [1, 2, 3, 3]


@pytest.mark.asyncio
async def test_retrying_is_off_when_the_policy_allows_one_attempt() -> None:
    calls = 0

    async def send() -> httpx.Response:
        nonlocal calls
        calls += 1
        return _response(503)

    policy = SameTargetRetryPolicy(max_attempts=1)
    assert policy.enabled is False

    result = await send_with_same_target_retry(send=send, policy=policy, sleep=_Recorder().sleep)

    assert result.status_code == 503
    assert calls == 1


def test_the_policy_reads_passthrough_num_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    import litellm.proxy.proxy_server as proxy_server

    monkeypatch.setattr(proxy_server, "general_settings", {"passthrough_num_retries": 4}, raising=False)
    assert passthrough_retry_policy().max_attempts == 5

    monkeypatch.setattr(proxy_server, "general_settings", {"passthrough_num_retries": 0}, raising=False)
    assert passthrough_retry_policy().enabled is False

    monkeypatch.setattr(proxy_server, "general_settings", {}, raising=False)
    assert passthrough_retry_policy().max_attempts == 3


def test_a_nonsense_retry_setting_falls_back_to_the_default(monkeypatch: pytest.MonkeyPatch) -> None:
    import litellm.proxy.proxy_server as proxy_server

    monkeypatch.setattr(proxy_server, "general_settings", {"passthrough_num_retries": "lots"}, raising=False)
    assert passthrough_retry_policy().max_attempts == 3
