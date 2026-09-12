# Reading the provider's own meter

Token IQ measures what passes through it. Every provider separately meters what it charges
for. Today only the first number exists in this product, and it is an estimate: tokens
multiplied by a rate from a price table. This design covers reading the second number and
putting the two side by side.

Research behind it: <https://claude.ai/code/artifact/c6cd4b43-f14b-4745-984c-94ffe51faab3>

## Why bother

The two numbers disagree for nine knowable reasons: negotiated rates, batch discounts,
cache pricing, context tiering, reasoning tokens, service tier, provider-side retries,
stale price tables, and traffic that never came through the gateway at all.

Eight of those are accounting differences worth explaining to a customer. The ninth is a
discovery no gateway can make alone. A customer who bought a gateway for control does not
know how much of their spend is escaping it, and comparing the two sources is the only way
to find out.

For scale: LiteLLM's own troubleshooting guidance treats a gap under roughly 10% as normal,
and a FinOps practitioner reference puts enterprise inference bills 30 to 50% above
API-reported token costs. Nobody has published a measured distribution.

## The constraint that shapes the design

Providers fall into two families that behave so differently they need separate machinery.

**LLM-native meters** (OpenAI, Anthropic, OpenRouter) have purpose-built usage and cost
endpoints that understand tokens, models, cache hits and API keys. Anthropic documents ~5
minute freshness and supports polling once a minute. These can drive something that feels
live.

**Cloud bills** (Bedrock, Azure, Vertex) have no LLM-specific endpoint. Model spend is a
line on the cloud bill, reachable only through the general billing pipeline, arriving 24 to
48 hours later, with no user dimension at all.

A customer on Bedrock will never see today's spend from the provider side. The product must
say so rather than let them discover it.

## Decisions

These were taken rather than deferred. Each is cheap to reverse except where noted.

**Reconciliation is the product, not unified reporting.** Unified multi-provider reporting
is already sold well by CloudZero, Vantage, Finout and Amnic, none of which sit in the
request path. Reconciliation from inside the gateway is the position nobody occupies.

**The gateway number stays the operational number.** It is instant and attributable to a
team, so it keeps driving budgets, rate limits and live screens. The provider number
arrives later and is used to audit, correct history, and surface the delta. Neither
silently overwrites the other; both are always shown with their provenance.

**Every fact carries an evidence level.** Borrowed from Kenda, which sells the audit half
of this idea today and grades its own confidence rather than presenting one blended number:

- `reconciled` — the provider asserted dollars at this exact scope
- `priced` — the provider asserted tokens, and we applied rates
- `allocated` — only our own gateway events exist here

This is the honest way to present data of mixed provenance, and it is the design problem
that would otherwise have to be solved from scratch later.

**OpenRouter goes first.** It is the only provider that will price one individual request,
its generation id is already stored as `request_id` on every OpenRouter spend row, and its
history window is 30 days, so data is being lost every day this is not built.

**Poll and store, never query through.** OpenRouter's 30-day window and Anthropic's
per-request bucket caps both mean history has to be persisted locally. It also keeps the
product working when a provider's API is down.

**Column names follow FOCUS, because this codebase already speaks it.** See the prior
art below: `billed_cost` and `billing_currency` are FOCUS's `BilledCost` and
`BillingCurrency`, so facts drop into the existing export without a second mapping. This
one is not cheap to reverse.

**Ingestion credentials reuse the existing encrypted credential store.** They are different
in kind from serving credentials — read-only, organisation-wide, higher privilege — and are
marked as such in `credential_info`, but they do not justify a second encrypted store.

## Prior art already in this codebase

Three things exist here that change the shape of this work, and none of them were in the
external research.

`litellm/integrations/focus/` is a complete FOCUS pipeline: schema, transformer,
serializers and destinations. `litellm/integrations/cloudzero/` exports usage to CloudZero's
AnyCost API. `litellm/integrations/vantage/` exports through FOCUS to Vantage. So this
product already feeds two of the FinOps platforms named in the competitive survey.

All three push data out. None pull anything in, so the direction proposed here is still
new. But it means the FOCUS decision is not "adopt a standard early", it is "there is
already an export, and it currently overstates what it knows."

Read `litellm/integrations/focus/transformer.py`. `BilledCost`, `ContractedCost`,
`EffectiveCost`, `ListCost` and `PricingCurrencyEffectiveCost` are all mapped from the same
`spend` column, which is the gateway's own token-times-rate estimate. `InvoiceId` is null.
In FOCUS those columns mean different things, and `BilledCost` specifically means what the
provider billed.

So today this product tells CloudZero and Vantage that its estimate is the billed cost.
Ingesting provider data is what makes that true, and correcting those five columns is the
clearest downstream payoff of this work. It also means a customer already exporting to
Vantage gets more accurate data without changing anything on their side.

## Shape

One provider-agnostic fact table holds what providers report, at whatever grain that
provider offers. Each connector translates one provider into that shape and computes a
deterministic `fact_key` so re-running a fetch overwrites rather than duplicates.

```
LiteLLM_SpendLogs                    LiteLLM_ProviderUsageFact
  request_id  ──────────────────────►  provider_request_id     (grain = request)
  provider_credential ──────────────►  credential_name
  model, startTime ─────────────────►  model, bucket_start     (grain = day)
```

The join key differs per provider and that is unavoidable:

| Provider | Finest join available |
|---|---|
| OpenRouter | the individual request, via its generation id |
| Anthropic | provider API key or workspace + model + day |
| OpenAI | provider API key or project + model + day |
| Bedrock | tag or inference profile or IAM principal + day |
| Azure | resource + deployment + day |
| Vertex | project + SKU + day |

The prerequisite is already in place: every spend row now records which provider credential
served it, which is the column a day-grain join needs. That work was done for billing
attribution and happens to be the foundation for this.

## Scope, split into shippable plans

This is several independent subsystems. Each plan below produces working software on its
own and is worth reviewing separately.

1. **Ingestion spine and OpenRouter reconciliation.** The fact table, the connector
   contract, the scheduled runner, the OpenRouter connector, and a reconciliation read.
   Ends with real deltas for real requests.
   Plan: `docs/superpowers/plans/2026-09-13-provider-billing-ingestion.md`
2. **Anthropic and OpenAI connectors.** Same family, day-grain joins, admin credentials, and
   the first real test of attributing a provider's aggregate back to a team.
3. **Cloud billing family.** Bedrock, Azure and Vertex. A different ingestion shape
   entirely, and the place to be honest about freshness in the UI.
4. **Reconciliation reporting.** The screens a finance person reads, including escaped
   spend.
5. **Make the FOCUS export honest.** Separate `BilledCost` from `ListCost` and
   `EffectiveCost` now that the first is knowable, and populate `InvoiceId` where a provider
   gives one. Existing CloudZero and Vantage customers benefit without changing anything.

## What is deliberately not in scope

Acting on what reconciliation finds. No automatic price-table correction, no blocking on a
detected discrepancy, no rewriting historical spend rows. The product reports the gap and
names its cause; a human decides. Rewriting recorded spend from a provider's later
assertion would destroy the audit trail that makes the comparison meaningful.
