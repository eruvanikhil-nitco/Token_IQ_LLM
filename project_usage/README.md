# project_usage

Every deletion made to this checkout is recorded here: what came out, why, and how to put
it back. Nothing is removed without an entry.

Each document carries a status line at the top. **REMOVED** means the code is gone from the
working tree and the change was verified against a running proxy. **ANALYSED, NOT YET
REMOVED** means the document is a specification for work still to do, and the code is still
in place.

## The observer-only requirement

Items 01 to 06 come from one rule: this proxy observes traffic, it does not participate in
it. It forwards a request to the endpoint the client already named, returns what the
provider returned, and records what happened. Anything that changes which endpoint serves a
call, what the response contains, or whether the provider is reached at all is out of
bounds.

| # | Concern | Status |
|---|---------|--------|
| 01 | Weighted / latency-based / cost-based routing | REMOVED |
| 02 | Load balancing across deployments | Neutralised: one deployment per model_name |
| 03 | Automatic fallbacks between models and providers | Neutralised: configuring one is a startup error |
| 04 | Retries that reroute, cooldowns, circuit breakers | Neutralised. Same-provider retry kept on purpose |
| 05 | Semantic and exact-match response caching | Neutralised: reads always miss, config refused |
| 06 | Enterprise-licensed code | REMOVED (separate reason: licensing) |
| 07 | Enterprise upsell sections in the Admin UI | REMOVED (separate reason: licensing) |
| 08 | LiteLLM branding in the Admin UI shell | REPLACED with Token IQ |
| 09 | Pass-through body fidelity (managed-id rewriter) | Asserted at startup; nothing removed |
| 10 | Docs and Blog links in the header toolbar | REMOVED from both headers |

## The unified translation layer

The seventh item on the original list, LiteLLM's "call every provider the same way"
translation layer, has no entry of its own because it cannot be removed while keeping the
surface you want.

`litellm/llms/` is 914 files across 140 providers, and it holds two different things. One
is the request/response translation that does breach observer-only. The other is the
provider credential and endpoint plumbing that the pass-through endpoints themselves depend
on: `llm_passthrough_endpoints.py` imports `VertexBase` for Vertex auth, `BaseAWSLLM` and
`BedrockError` for SigV4, the gigachat authenticator, and `get_async_httpx_client`.

Deleting `litellm/llms/` deletes pass-through with it. The translation layer is instead
avoided by *not routing through it*, which is what pass-through endpoints already do.

## The honest way to guarantee observer-only

Removing strategies narrows what the proxy can be configured to do, but it does not by
itself make the proxy an observer. Even with every scored strategy gone, `simple-shuffle`
still picks between duplicate deployments, and a `model_list` entry still sends traffic
through the translation layer.

The property is enforced at the surface, not by deletion:

- expose only the pass-through routes, so no request reaches the routed endpoints
- keep `model_list` empty, which the proxy already supports (`proxy_server.py` guards on
  `llm_router is None` in 45 places)
- never set `litellm.cache` (now enforced: reads always miss and both enablement paths raise)

Deletion is still worth doing, because it means a later config change cannot quietly turn
these back on. The two are complementary: the surface gives the guarantee today, the
deletions stop it regressing.
