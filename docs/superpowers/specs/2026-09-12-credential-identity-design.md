# Credential identity: reaching a provider as a specific customer

## Why this document exists

Three plans this week each answered "whose provider credential should a courier request
use" differently: a permission flag per model, then matching the model in the request body,
then reading the key's model list. Each patched the one before, because none of them started
from how the system reaches a provider at all.

A first version of this document was also too shallow. It framed the problem as choosing a
secret. Reading Bifrost's data model rather than its documentation showed the real shape,
and re-reading our own courier routes turned up a multi-tenancy defect that none of the
plans mention.

This replaces the credential portions of all three plans and the first version of itself.

## What reaching a provider actually requires

A secret is not enough. To send one request as one customer you need:

- the secret itself
- where to send it, which for Bedrock means the region, for Vertex the project and location,
  for Azure the endpoint, for a self-hosted model the base URL
- which models that credential is entitled to use

Any design that only answers the first question is incomplete, and that is the mistake the
earlier version made.

## How the two systems hold that

**Bifrost.** A credential is one object holding all of it. From `core/schemas/account.go`,
their `Key` carries the value, a model allowlist, a model denylist, a weight, aliases, and
then a provider-specific configuration block: `AzureKeyConfig`, `VertexKeyConfig`,
`BedrockKeyConfig`, `VLLMKeyConfig` and others. One credential is self-sufficient: given it
alone, you can reach that provider as that customer.

A customer-facing key then names which credentials it may use, by id, with `["*"]` for all
and an empty list for none.

**Ours.** The pieces are split. `LiteLLM_CredentialsTable` holds a secret, and the
connection details live on the model entry: `aws_region_name`, `vertex_project`,
`vertex_location`, `api_base`. A customer key names model entries, and the model entry is
where secret and connection details finally meet.

Both work. The difference only bites in courier mode.

## Why courier mode breaks, precisely

In translating mode the caller names one of our model entries, so both halves are found
together. Exact lookup, no ambiguity.

In courier mode the caller never names our model entry. The body is the provider's own, so
it carries the provider's model name, and for Bedrock and Vertex it carries no model in the
body at all because the provider puts it in the URL.

So courier mode has to reassemble, from a request that does not identify the model entry,
both the secret and the connection details that the model entry was holding together.

Everything that has gone wrong is a consequence:

- Secret resolution falls back to "any credential for this provider", gated by an opt-in
  flag on each model entry. Nobody knows the flag exists, so 39 of 40 deployments here would
  fail on credentials the moment a team switched, reporting a missing credential while the
  dashboard shows it plainly present.
- With more than one credential for a provider, it takes the first. A customer with a
  production and a test account has production traffic billed to test, silently, with a
  correct answer returned.
- A team's permitted models are our names, so they stop matching on switch and every call is
  refused for a model the admin can see granted.

## Connection details, and a claim withdrawn

An earlier version of this document said every customer's Bedrock courier traffic used a
server-wide region. That was wrong, and reading the resolution chain rather than one call
site corrected it.

The model pass-through path resolves the region from the request's own parameters first,
then from the model ARN, and only then from the environment. That is correct multi-tenant
behaviour and nothing needs changing there.

Only `bedrock-agent-runtime` fell back to the environment, and it had no alternative: such
a request names an agent, not a model or a deployment, so nothing in it identifies a
customer's region. Two real defects were fixed there separately: it read only
`AWS_REGION_NAME` while every neighbouring path also accepts `AWS_REGION` and
`AWS_DEFAULT_REGION`, and an unresolved region was interpolated into the hostname producing
`bedrock-agent-runtime.None.amazonaws.com`, turning a configuration problem into a DNS
failure.

What remains true, and is what this document is for: agent-runtime still cannot serve two
customers in different regions, because there is nowhere for a per-customer region to come
from. That is the argument for a credential carrying its own connection details rather than
a bug to patch. Once a key binds to a credential, the region arrives with the credential and
the environment fallback stops being load-bearing.

Vertex already reads its project from the deployment, so the two courier paths differ in how
much of the customer's configuration they can see. Making the credential self-sufficient
removes that inconsistency rather than papering over it.

## Decisions

### Make a credential self-sufficient

A credential gains the connection details for its provider, alongside its secret. This is
Bifrost's `BedrockKeyConfig` and `VertexKeyConfig` under a different name.

The storage already allows it: `credential_values` is an open map, and the pass-through
router already reads `api_base` out of it. This is filling in a shape that exists rather
than adding one.

Model entries keep their current fields and behaviour. Translating mode is untouched. A
credential that carries its own connection details is simply usable without a model entry,
which is exactly what courier mode needs.

### Resolve from the key, not from the request

A customer key gains an explicit list of credentials it may use, which is Bifrost's
`key_ids`.

The key already knows what it is entitled to. Starting there works for Bedrock and Vertex,
where the model is absent from the body and any body-scanning approach fails outright, and
it distinguishes two accounts at one provider, which body-scanning could never do because
those requests are identical on the wire.

The key's existing model list stays and keeps its meaning for translating mode. The two
answer different questions: which models may I call, and whose account pays.

### One credential per request, never chosen by the gateway

Bifrost spreads traffic across a customer's credentials by weight and switches automatically
when one is rate-limited or rejected. We will not.

That is the gateway deciding where a request goes, which this fork removed when it dropped
scored routing, fallbacks and cooldowns. Applying it to credentials rather than to models
does not make it different in kind. It also puts a customer's spend on an account they did
not choose, and accurate attribution is the product.

A request resolves to exactly one credential. If that credential fails, the customer is
told, in the provider's own words. No second attempt on another account.

We therefore do not need their weight or their denylist. Both exist to serve selection, and
we are not selecting.

### Record which credential paid

`LiteLLM_SpendLogs` stores the gateway's own key and the provider's address, and nothing
identifying the customer's account. For a customer with two accounts at one provider, the
records cannot say which was charged.

That is a gap in the product being sold, independent of courier mode, and it is the one
place Bifrost is plainly ahead: they record the serving credential on every request, and the
full trail when they switch.

Every spend row gains the credential that served it.

### Out of scope: unbound keys

Seventeen of the thirty-one keys here name no models, so they would bind to no credentials
and fall back to today's provider match. That is acceptable and stays. Customers issue a key
per project with the models that project may use, so the bound case is normal and the
unrestricted key is the exception. When it matters, the answer is to require a binding, not
to guess better.

### Out of scope: the model-name mismatch

A team's permitted models are our names and a courier request carries the provider's, so
permissions stop matching on switch. Separate problem, not solved here, and the admin screen
must keep warning about it.

## How a courier request resolves under this design

The gateway's key identifies the caller. The key's binding names one credential for the
provider being addressed. That credential carries both its secret and its connection
details, so the request can be sent without consulting a model entry at all. The spend row
records which credential paid.

No flag to enable. No scanning of the body. No difference between providers that name the
model in the body and those that name it in the URL. No possibility of the wrong account
being billed, because nothing was chosen. And no server-wide region standing in for a
customer's own.

## What this replaces

- The permission flag work in `2026-09-11-courier-mode-design.md`, which treated the flag as
  a hurdle to surface rather than a symptom to remove.
- The credential assumptions in `2026-09-11-courier-mode-provider-coverage.md`.
- The deployment opt-in reporting in `2026-09-12-courier-mode-admin-control.md`. The coverage
  endpoint and screen stay; the opt-in warning becomes unnecessary and should be replaced by
  a warning for keys with no credential binding.

## Risks

Widening what a stored credential may be used for is a real change. The flag exists because
courier forwards a body the gateway has not interpreted. The mitigation is that the
credential is no longer found by scanning; it is named by the key its owner issued, which is
a stronger statement of intent than the flag ever was.

Duplicating connection details onto credentials risks them drifting from the model entry
that also holds them. Mitigated by the credential being authoritative wherever it is bound,
and by never writing back to the model entry.

Existing keys have no binding and must keep working exactly as they do now. The binding is
additive.

## Sequencing

All of it is built and pushed.

1. ~~Bedrock agent-runtime region.~~ Done. Narrower than first claimed, see above.
2. ~~Record the serving credential on every spend row.~~ Done, both modes.
3. ~~A credential carries its provider connection details.~~ Not needed as a separate step:
   credentials created from an existing deployment already carry what they need, and the
   binding made the courier path work without duplicating connection fields. Revisit only
   if a customer needs a credential with no deployment behind it.
4. ~~Bind keys to credentials.~~ Done.
5. ~~Resolve courier requests from the binding.~~ Done, unbound keys unchanged.
6. ~~Remove the opt-in flag.~~ Done, proven with the flag switched off.
7. ~~Update the admin screen.~~ Done.

Also fixed along the way, found only by driving real requests: a team's permitted models
stopped matching in courier mode because they are named differently, which refused every
call for models the admin could see granted. `courier_model_names` translates between the
two schemes.

## What is still not proven

Bedrock's cost reader is wired and unit-tested and has never carried a real request,
because this machine has no AWS credentials. Anthropic, OpenAI, Azure and Vertex courier
routes are believed covered on the strength of reading code, which was wrong about
OpenRouter by three defects. Each needs one real request and a reconciled spend row.

The pattern worth carrying forward: every defect found this week returned a correct answer
to the caller and passed the unit suite. Only sending a real request and reading back what
the database recorded exposed them.

## The setting became three-way

`courier_mode` was a boolean, so it could say "only the provider addresses" or say nothing.
It could not say "either, while this team moves one application at a time", and a customer
migrating had to move everything on the day the switch flipped or not at all. It is now
`api_access_mode`, one of `courier`, `translator` or `both`, defaulting to `both`, which is
what every team behaved as before the setting existed.

`courier` is still worth having as an enforced mode rather than a label. A customer buying
the promise that their request bodies are never opened wants it refused at the door, not
intended.

Two defects came out of building it, both proven against a running proxy rather than
reasoned about:

The boolean refused every address that was not a provider address, so a courier team's own
keys got 403 on `/team/info`, `/key/info` and `/models`. Which way a team writes its model
requests says nothing about whether it may read its own key. Only the model-serving routes
are gated now, and the info routes are excluded before anything else is considered.

Deleting a key returned 500 for every key, because `provider_credentials` went onto the key
and not onto the record a deleted key is archived into. That is the same omission as
`courier_mode` and the team archive, one table over, found the same way: by deleting
something. The schema-reading guard now covers both archive tables, since covering only the
one that broke first is exactly what let the second one through.
