# Credential identity: which of a customer's accounts paid for this request

## Why this document exists

Three plans written this week each contain a different answer to one question: in courier
mode, whose provider credential should the gateway use? A permission flag on each model,
then matching the model named in the request body, then reading the key's model list. Each
was a patch on the one before, and each was written without understanding how the identity
chain works or how a mature product solves it.

This replaces the credential portions of all three.

## The actual problem

Every request has to answer two questions. Who is calling, and whose money pays.

The first is answered by the gateway's own key. The second is answered by a chain: the key
names the models it may use, a model entry carries or references a credential, and the
credential is what reaches the provider.

In translating mode that chain holds, because the caller names one of our model entries.
The lookup is exact.

In courier mode the caller never names our model entry. The body is the provider's own, so
it carries the provider's model name, and for Bedrock and Vertex it carries no model in the
body at all because the provider puts it in the URL. The chain breaks at the first link.

Everything that has gone wrong follows from that single fact:

- The gateway falls back to "find any credential for this provider", which is guarded by an
  opt-in flag on each model entry. Nobody knows the flag exists, so 39 of the 40 deployments
  on this machine would fail on credentials the moment a team switched, with an error saying
  the credential is missing while the dashboard plainly shows it present.
- When more than one credential exists for a provider, the gateway takes the first it finds.
  A customer with a production and a test account at one provider has production traffic
  billed to the test account, silently, with a correct answer returned.
- A team's permitted models are our names, so they stop matching the moment that team is
  switched, and every call is refused as not allowed for a model the admin can see granted.

Three symptoms, one cause.

## What we already have

More than the patches assumed.

Credentials are already first-class. `LiteLLM_CredentialsTable` stores them by name, there
is a full API under `/credentials`, and `CredentialAccessor` resolves them. A model entry
can either embed a key inline or reference a stored credential by name.

Keys already carry a list of what they may use, in `LiteLLM_VerificationToken.models`. On
this machine 14 of 31 keys name specific models and 17 name none.

What is missing is a direct link from a key to a credential, and any record of which
credential served a request.

## What Bifrost does

Worth stating plainly, because it turns out they solved this and their answer is the one
that was suggested here independently.

Their headline feature is courier mode. A customer keeps the provider's own SDK, changes
the base URL to a provider-specific address on the gateway, and authenticates with a
Bifrost key rather than the provider's. The request stays in the provider's format
throughout. That is not a side feature of theirs; it is how the product is sold.

Provider credentials are objects in their own right, created per provider with a name, the
models they cover, a weight, and an optional denylist. A customer-facing key then declares
which credentials it may use, by id, with `["*"]` meaning all and an empty list meaning
none.

So a courier request never needs inspecting to decide whose money pays. The key that
authenticated it already says.

They also record, on every request, which credential served it, and when they switch
credentials they record the ordered trail of what was tried and why.

## Decisions

### Adopt: resolve the credential from the key, not from the request

The key already knows what it is allowed to use. Start there.

This is correct for every provider including Bedrock and Vertex, where the model is not in
the body and any body-scanning approach fails. It removes the opt-in flag as a concept
rather than switching it off, because the gateway is no longer rummaging through credentials
looking for a match; it is looking one up. And it distinguishes two accounts at one provider,
which body-scanning never could, because two such requests are identical on the wire.

### Adopt: a key may bind to credentials directly

Today a key names model entries and the credential is reached through them. That indirection
is what breaks in courier mode. A key gains an explicit list of credentials it may use,
which is Bifrost's `key_ids` under a different name.

The existing model list stays and keeps its current meaning for translating mode. The two
answer different questions: which models may I call, and whose account pays.

### Diverge: one credential per request, never chosen by the gateway

Bifrost spreads traffic across a customer's credentials by weight and switches automatically
when one is rate-limited or rejected.

We will not. That is the gateway deciding where a request goes, which is the behaviour this
fork removed when it dropped scored routing, fallbacks and cooldowns. Applying it to
credentials rather than models does not make it different in kind.

There is a money argument as well as a principle. Silently moving a request from one of a
customer's accounts to another puts their spend somewhere they did not choose, and this
product's entire claim is that spend is attributed accurately.

So: a request resolves to exactly one credential, by binding. If that credential fails, the
customer is told, in the provider's own words. No second attempt on a different account.

### Add: record which credential paid

Neither product's spend row records this today on our side. `LiteLLM_SpendLogs` stores the
gateway's own key and the provider's address, and nothing that identifies the customer's
account.

For a customer with two accounts at one provider, our records cannot answer "which account
was this charged to". That is a gap in the product being sold, independent of courier mode,
and it is the one place Bifrost is unambiguously ahead: they record the serving credential
on every request.

Every spend row gains the credential identity that served it.

### Not now: unrestricted keys

Seventeen of the thirty-one keys here name no models, and therefore bind to no credentials.
For those the gateway still has to fall back to matching by provider, which keeps today's
ambiguity.

That is acceptable and explicitly out of scope. Customers issue a key per project with the
models that project may use, so the bound case is the normal one and the unrestricted key is
the exception. When it matters, the answer is to require a binding rather than to guess
better.

## How a courier request resolves under this design

The gateway's key identifies the caller, as now. The key's credential binding names exactly
one credential for the provider being addressed. That credential is attached to the outgoing
request. The spend row records it.

No flag to enable. No scanning of the body. No difference between providers that name the
model in the body and those that name it in the URL. And no possibility of the wrong account
being billed, because nothing was chosen.

## What this replaces

- The permission flag work in `2026-09-11-courier-mode-design.md`, which described the flag
  as a hurdle to surface in the UI rather than a symptom to remove.
- The credential-resolution assumptions in `2026-09-11-courier-mode-provider-coverage.md`.
- The deployment opt-in reporting in `2026-09-12-courier-mode-admin-control.md`. The
  coverage endpoint and admin screen stay; the section warning about un-opted-in deployments
  becomes unnecessary once the flag is gone, and should be replaced by a warning about keys
  with no credential binding.

The model-name mismatch stays a real problem and is not solved here. A team's permitted
models are our names and a courier request carries the provider's, so permissions still stop
matching on switch. That is a separate piece of work and the admin screen must keep warning
about it.

## Risks

The binding is a new required concept, and a key without one falls back to today's guessing.
Migration has to be deliberate: existing keys keep working exactly as they do now, and the
binding is additive.

Removing the opt-in flag widens what a stored credential may be used for. That flag exists
because courier forwards a body the gateway has not interpreted. The mitigation is that the
credential is no longer selected by scanning; it is named by the key its owner issued, which
is a stronger statement of intent than the flag ever was.

## Sequencing

1. Record the serving credential on every spend row. Independent of everything else, fixes a
   real gap in the product today, and gives us the evidence to verify the rest.
2. Add the credential binding to keys, additive, defaulting to today's behaviour.
3. Resolve courier requests from the binding, falling back to the current behaviour for
   unbound keys.
4. Remove the opt-in flag once nothing depends on it.
5. Update the admin screen: drop the opt-in warning, add a warning for keys with no binding.

Each step ends with a real request through a real provider and the spend row read back.
Every credential defect this week returned a correct answer and was invisible until someone
looked at what the database recorded.
