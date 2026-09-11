# Courier mode: pass-through as a first-class product mode

## The problem

The README says Token IQ "forwards the request to the provider unchanged, and returns the
provider's answer unchanged". On the main route that is not what happens. A request arriving
at `/v1/chat/completions` is translated into the target provider's own format, and the reply
is translated back before the client sees it.

Verified by running a request through the Anthropic transform. A client sends:

    {"messages": [{"role": "system", ...}, {"role": "user", "content": "hi"}], "max_tokens": 50}

and the provider actually receives:

    {"messages": [{"role": "user", "content": [{"type": "text", "text": "hi"}]}],
     "system": [{"type": "text", "text": "Be brief"}], "max_tokens": 50}

The words survive; the envelope does not. That translation is a real feature, it is what lets
a client switch providers by changing one string. But it is not what the README promises, and
observer-only is the claim the whole fork is built on.

Pass-through routes already exist and do what the README describes: the body reaches the
provider untouched, and `user_api_key_auth` still runs, so virtual keys, budgets, model
allow-lists and rate limits are all enforced on that path.

So both behaviours exist. The gap is that the documented one is not the default, is not
selectable, and does not cover every provider we sell.

## Scope

The providers this covers, decided by what the business actually sells rather than what the
upstream catalogue contains:

| Provider | Courier route | Usage/cost read back | Work needed |
|---|---|---|---|
| OpenAI | yes | yes | none, verify only |
| Anthropic | yes | yes | none, verify only |
| Azure OpenAI | yes | yes, via the OpenAI handler | none, verify only |
| Google Vertex | yes | yes | none, verify only |
| Bedrock | yes | **no** | write the usage reader |
| OpenRouter | yes | yes | done, see below |

**What landing OpenRouter actually took.** The estimate above, "declare its api base", was
wrong, and the way it was wrong is the useful part. Three defects stacked, and every unit test
passed while all three were live. Only a real request found them.

1. The route factory resolves its provider through `get_provider_model_info`, not
   `get_provider_passthrough_config`. Registering in one of the two leaves the route returning
   404 "Provider not found" with a green test suite.
2. Pass-through paths are separately gated by `LiteLLMRoutes.mapped_pass_through_routes`, an
   allow-list of prefixes. A route absent from it matches, enters the factory, and is then
   rejected as an unregistered endpoint.
3. The success handler prices courier traffic by dispatching on the target hostname, and the
   OpenAI-compatible allow-list held only `api.openai.com` and the Azure hosts. OpenRouter
   serves the OpenAI wire format but was not listed, so a courier request succeeded, returned
   correctly, and wrote a spend row of zero tokens and zero cost against a charge OpenRouter
   had actually billed.

The third is the one that matters. It is the same failure this document describes on Bedrock,
it was live on the provider carrying all of this fork's traffic, and nothing short of sending a
real request and reading the spend row back would have surfaced it.

**A deployment must be opted in.** Courier mode reads a provider credential from a deployment
only when that deployment sets `use_in_pass_through: true`. This is a deliberate default: a
credential added for ordinary use is not automatically usable by routes that forward a body
unopened. Nobody would guess it, and an admin switching a team to courier would otherwise watch
every call fail on credentials with no indication why, so the admin screen has to surface it.

**Treat the remaining coverage claims as unproven.** The table above was built by reading code.
OpenRouter read as "one missing api base" and was three bugs. Every row still marked covered
needs a real request and a reconciled spend row before it is believed, Bedrock most of all.

Explicitly out of scope: the remaining ~134 providers. Adding them all would cost months and
rot faster than we could maintain it. The deliverable instead is that adding provider 7 is a
documented day of work rather than a project. Voyage has the same missing-api-base shape as
OpenRouter and can ride along if it is cheap, but it is embeddings-only and not a blocker.

## Design

### 1. OpenRouter courier support

`llm_passthrough_factory_proxy_route` is already generic over providers. It needs exactly one
thing from a provider config: a non-None `get_api_base()`. Measured today:

    openrouter   config OK, api_base = None      -> factory returns 404
    anthropic    config OK, api_base = https://api.anthropic.com

So OpenRouter fails on a missing base URL, not on anything structural. Declaring the base is
the fix.

Billing then has two possible sources, and OpenRouter is unusually well placed. It reports its
own cost in `usage.cost`, and `_set_cost_per_request` already treats an upstream that prices
its own requests as authoritative. Three rows in the live database confirm the logged spend
already matches OpenRouter's reported figure exactly (0.0000051, 0.00001155, 0.0003132). The
implementation must confirm this path is what fires on the courier route, and fall back to
treating OpenRouter as OpenAI-compatible only if it does not.

### 2. Bedrock usage reader

Bedrock's courier route works; requests reach AWS and clients get correct answers. What is
missing is any code that reads token counts back off the reply, so the request logs but
records no computed cost.

This is the only genuinely new component. It follows the shape of the existing per-provider
handlers (`anthropic_passthrough_logging_handler.py` is the closest model) and must handle
Bedrock's differing response shapes across invoke and converse. Until it lands, Bedrock must
be reported as not fully covered rather than quietly billing zero.

### 3. Admin control, opt-in per team

A team-level setting choosing courier or translator, defaulting to translator.

The control cannot be a silent switch, and the design must not pretend otherwise. Courier and
translator are different addresses expecting differently shaped bodies. Flipping a team to
courier does not make their existing requests pass through; it changes which address they must
call and what they must send.

When an admin switches a team, the screen states what that team's configured providers will
actually do: fully covered, or carries traffic without recording cost. An admin must never
discover a billing gap from a month-end invoice.

### 4. Error behaviour in courier mode

Decided with the product owner: the gateway never authors an opinion about content. A
malformed body is forwarded as received, the provider rejects it, and the provider's own
rejection is returned verbatim.

The gateway speaks for itself only about things that are its own business: invalid key,
exhausted budget, disallowed model, rate limit. This is already how pass-through behaves for a
bad body, so it is a property to preserve and test, not to build.

## What "done" means

- Each in-scope provider has a test proving a courier request reaches it with a byte-identical
  body, and that the spend row's cost matches the provider's own reported figure where the
  provider reports one.
- A team switched to courier is billed and rate-limited exactly as it was on the translator.
- The admin screen's coverage claims are generated from the same source the runtime uses, so
  they cannot drift apart from reality.
- Bedrock either reads usage correctly or is reported as uncovered. It is never silently free.

## Risks

The one that matters: shipping courier mode while a provider silently records zero cost would
undermine the exact trust the feature exists to create. That is why Bedrock gates the default
flip, and why the coverage display is part of the feature rather than documentation.

Secondary: making courier the default is a breaking change for every existing integration.
Hence opt-in per team first, default only once the in-scope providers are covered.

## Sequencing

1. Verify the four already-covered providers, with tests. Cheapest, and it establishes the
   test shape everything else reuses.
2. OpenRouter api base plus billing confirmation.
3. Bedrock usage reader.
4. Admin control and coverage display, shipped opt-in.
5. Flip the default to courier, and correct the README either way.

## Open question

Whether the README should be corrected now or at step 5. It currently describes behaviour the
main route does not have. Correcting it immediately is honest but advertises the gap;
correcting it at step 5 leaves an inaccurate claim standing for the duration of the work.
Recommendation is to correct it now and describe courier as the direction, because the claim
is checkable by any technical buyer today.
