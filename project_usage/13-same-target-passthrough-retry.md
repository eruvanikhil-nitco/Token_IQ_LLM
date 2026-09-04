# Same-target retry on the pass-through path

> **Status: ADDED.** This is the one entry in this folder that adds behaviour rather than
> removing it. It exists because the observer-only work took retrying away from the routed
> path, and the pass-through path never had any.

## Why this was needed

The requirement is that the gateway re-sends on a provider failure without changing the
provider or the model. The routed path had retries, but they re-entered deployment
selection, which is why `02-load-balancing.md` pins one deployment per `model_name`.

The pass-through path, which is the surface a forwarding gateway actually uses, had no
retry at all: `pass_through_endpoints.py` built one request, sent it once, and returned
whatever came back. So the requirement was not weakened there, it was simply absent.

## What was added

`litellm/proxy/pass_through_endpoints/same_target_retry.py`.

`send_with_same_target_retry` takes a `send` callable and re-invokes it on a retryable
failure. The forwarder passes a closure that rebuilds the request from scratch each time,
so every attempt sends identical bytes to the identical URL with identical headers. Nothing
about the target can drift between attempts.

## What is retried, and what is deliberately not

Retried:

- `429`, `502`, `503`, `504`. The provider is saying it did not do the work.
- `httpx.ConnectError`, `ConnectTimeout`, `PoolTimeout`. The request never reached the
  provider.

Not retried:

- Any `4xx` other than 429. That is the provider's actual answer, and re-sending it would
  be pointless at best.
- `500`. The provider may have processed the request before failing to answer, so a retry
  can bill the caller twice for one logical call.
- `ReadTimeout` / `WriteTimeout`. Same reason: the request is already in flight and may
  well be completing.

That distinction is the whole design. "Retry on failure" is easy; retrying only where the
work provably did not happen is what keeps a retry from turning into a duplicate paid call.

## Streaming safety

The forwarder sends with `stream=True`, so `httpx.send` returns once the response head
arrives and before any body byte has been handed to the client. The status is therefore
known while a retry is still safe. A response that is retried is `aclose()`d first, which
returns its connection to the pool. A response that is returned to the caller is never read
here, so the streaming body reaches the client intact.

## Backoff

Exponential from `initial_backoff_seconds`, doubling per attempt, capped at
`max_backoff_seconds`. A numeric `Retry-After` from the provider wins over our own backoff,
clamped to `MAX_RETRY_AFTER_SECONDS` (30s) so a hostile or mistaken header cannot park a
request indefinitely. The HTTP-date form of `Retry-After` is not parsed; it falls back to
our backoff rather than pulling in a date parser for a form LLM providers rarely send.

## The final attempt is the caller's answer

Once attempts are exhausted, a retryable status is returned like any other response and a
transport error is re-raised. The client sees the provider's own 503, not an error the
gateway invented. That keeps the observer property: the gateway reports what happened
rather than substituting its own verdict.

## Configuration

`general_settings.passthrough_num_retries`, counting retries rather than attempts, so the
default of 2 means up to three sends. Setting it to `0` makes the gateway a single-shot
forwarder again. A non-integer value logs a warning and falls back to the default rather
than failing startup.

## Verification

20 unit tests in
`tests/test_litellm/proxy/pass_through_endpoints/test_same_target_retry.py`, covering each
retryable status, each status that must pass straight through, connect-error retry and
re-raise, read-timeout non-retry, `Retry-After` precedence, unparseable `Retry-After`,
backoff growth and cap, retries disabled, and the config resolver including a nonsense
value. `send` is injected and `sleep` is recorded rather than performed, so the suite is
deterministic and runs in seconds.

The wiring was checked live: with a deliberately invalid `OPENAI_API_KEY`, a real request
through `POST /openai/v1/chat/completions` reached `api.openai.com` and returned `401` in
2 seconds, confirming the forwarder runs through the helper and that a status the provider
meant is passed back without retrying.

Not yet exercised: a live retry against a real provider outage. The retry semantics are
covered by unit tests only.

## How to restore the previous behaviour

Set `passthrough_num_retries: 0`, which makes the helper a pass-through wrapper around a
single send. To remove it entirely, revert this commit; the forwarder's original
single-shot `build_request` / `send` pair is in the diff.
