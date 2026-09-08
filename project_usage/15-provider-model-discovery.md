# Provider model discovery, and the third caching bypass

> **Status: ADDED (discovery endpoint) and REMOVED (Response Cache nav entry).** Two
> unrelated things landed together because investigating the second turned up the first.

## The caching bypass

`POST /cache/settings` writes a `cache_config` row directly. It touches neither
`litellm_settings` nor the Router, so it slipped past both guards added in
`05-response-caching.md` and returned **200** while having no effect.

Caching was never actually enabled by it: the unconditional early return in
`caching_handler.py` ignores that row, which is why the guard went on the read path rather
than only on config. Verified after saving Redis settings through that endpoint, two
identical requests at `temperature: 0` still produced distinct upstream ids.

But an endpoint that accepts configuration, reports success and does nothing is worse than
one that refuses, because an operator will point it at Redis and believe caching is on. It
now raises 400 with the same message as the config path.

This corrects a claim made in `05-response-caching.md`: caching was closed on *two*
enablement paths, not all of them. There were three.

The Response Cache entry was also removed from the Developer Tools nav, since it configures
a feature that cannot be enabled. The four remaining "Response Cache" strings in the built
bundle are the chat-metrics and log-drawer cache-hit labels, which are unrelated.

## Model discovery

`GET /model/discover?custom_llm_provider=...` asks a provider what its credentials can
reach, and reports which of those the local catalogue can price.

It wraps `get_valid_models(check_provider_endpoint=True, ...)`, which already existed and
already caches; nothing here re-implements the provider call. What is new is
`merge_with_local_pricing`, a pure function pairing each discovered model with its pricing
row, so the merge is testable without a network call.

Credentials are optional and never returned. Omit them and the provider's own environment
variables are used.

### Two states, not three

At discovery time we know only whether a **local** pricing row exists. Whether the provider
will report a cost of its own is unknowable until a request is made, so a model with no row
is reported as exactly that rather than as free. Recording what actually happened belongs on
the spend log.

## What the investigation actually found

The case for building this rested on three claims, and measuring killed two of them.

The dropdown does **not** read the shipped `model_prices_and_context_window.json`. It fetches
`/public/litellm_model_cost_map`, which serves the **runtime** map, refreshed from a remote
source at startup:

```
openrouter rows in the shipped FILE   : 100
openrouter rows in runtime model_cost : 260
openrouter rows the UI dropdown sees  : 260
```

So LiteLLM already does the "download fresh pricing" half of Bifrost's hybrid. An earlier
figure of "340 of 427 models missing" was wrong: it compared OpenRouter's raw API (which
includes `:batch` duplicates LiteLLM filters) against the stale on-disk file.

Discovery run live against OpenRouter returns `260 total, 260 priced, 0 unpriced`.

`openrouter/openai/gpt-4o-mini`, the one example of an unpriced model, is priced at runtime
(`in=1.5e-07, out=6e-07`). Every zero-cost row in the spend log is a `status=failure` request
with zero tokens, which is correct rather than a metering hole.

## Why it was kept anyway

It answers "what can *this key* reach" rather than "what does the catalogue list", and makes
the unpriced count explicit instead of something discovered from a zero in a spend report.
It is the first thing to run when adding a provider whose coverage is worse than
OpenRouter's.

It is **not** closing a gap today. The UI fetch button was deliberately not built, because
it would show the same names the dropdown already shows.

## The trigger for doing more

Run `/model/discover` against a newly added provider and read the `unpriced` count. Zero
means the catalogue covers you and nothing further is needed. Non-zero is a real number, and
the spend-log unpriced flag becomes worth building.

## Tests

7 for the merge: priced, unpriced, mixed counts, duplicate collapsing, empty input, a
catalogue row carrying metadata but no costs (must not count as priced), and one-sided
pricing such as an embedding model (must not be a false alarm).

6 tests covering the cache-settings save path were removed, since it now refuses, and
replaced with one asserting the refusal.

## How to restore

Delete the `raise HTTPException` block at the top of `update_cache_settings`, and re-add the
`caching` entry to the AI Gateway group in `leftnav.tsx`. Removing discovery is deleting
`model_discovery.py`, its test, the `/model/discover` route and its import.
