# What established cost platforms do with AI provider data

Reference research for Phase 2 (Data Sources and Usage / APIs), gathered on 2026-09-15 from the public documentation of three established cloud cost platforms that already read OpenAI and Anthropic cost data. The platforms are not named here, following the repository rule against naming companies. The findings are summarised in our own words, and nothing below changes the agreed tab plan in `2026-09-14-token-iq-product-design.md`

## Patterns all three share

### Connections

Each provider is connected once, from an integrations area, with a read-only admin key. None of them can take an action that costs money, and they say so on the connection page

A single vendor often needs two separate connections, each with its own key type. One covers the developer platform (costs by project or workspace, model, token type and key). The other covers the vendor's business product, such as a chat workspace or coding assistant, with costs by user. The two are set up, refreshed and shown separately

The setup form checks the key's type before saving. A platform admin key and an analytics key look different, and pasting the wrong one produces a clear message instead of a failed sync later

A connection moves through visible states: waiting for its first data, healthy, and failing with a reason such as a rejected key or missing permission

### Freshness and history

Data refreshes once a day. The documentation states the typical delay, which ranges from a few hours to a day

On first connection each platform backfills history, usually up to twelve months, and states the earliest date the provider can return. Some newer analytics endpoints only have data from a fixed start date

Recent figures can still change. One platform notes that enterprise billing keeps adjusting for up to 30 days, so the current month moves after the fact

### Labelling every row

Every cost row records which data source it came from, so developer platform spend and business product spend from the same vendor can be filtered apart

On top of each provider's own fields, the platforms apply one provider-independent set of dimensions automatically, so a report can group across vendors without custom mapping. The common set is:

| Dimension | Meaning |
|---|---|
| Model | cleaned model name |
| Raw model | model name exactly as the provider reported it, with version |
| Model maker | who built the model, which differs from the seller on cloud marketplaces |
| Token type | input, output, cache read, cache write |
| Service tier | default, priority, batch, flex |
| Region | where the request ran |
| API key | which key was charged |
| User | email, display name and the provider's user id, where the provider gives them |
| Account scope | the provider's organisation, project or workspace |

### Allocation

Costs are assigned to teams, products and customers by rules that map existing metadata (keys, workspaces, projects, account names) to owners, without re-tagging anything at the provider. One platform proposes these rules automatically from metadata, and an admin approves, edits or rejects them in bulk. The stated goal is that every dollar has an owner, with anything unmatched listed separately

One platform publishes a record format for request-level logs: an event id for de-duplication, timestamp, provider, model, token counts by type, account, region, tier, key and free-form allocation tags. Provider cost is then split across the logged requests in proportion to their tokens

### Views and actions

AI spend sits in the same reports, budgets and dashboards as the rest of a company's spend. Alerts fire on sudden jumps, for example an agent stuck in a loop, and go to chat, email or paging tools. Two platforms emphasise cost per customer, per feature or per transaction by combining spend with the company's own product metrics

## What Token IQ takes, by agreed tab

### Data Sources / Provider APIs and User Tools

- **Connection** shows one of four states: Not connected, Waiting for first data, Healthy, Needs attention (with the reason and what to fix). It shows a Read-only badge and checks the key type before saving
- Where a vendor needs two connections, the developer platform connection lives under Provider APIs and the business product connection lives under User Tools. This matches the agreed split, for example Anthropic under Provider APIs and Claude Code under User Tools
- **What We Fetch** lists, per endpoint, the refresh cadence, the typical delay, how much history the first connection loads, and the earliest date the provider can return
- **Sync History** shows the first backfill's progress as well as each daily fetch

### Usage / APIs

- **Summary** adds breakdowns by token type, service tier and key or workspace next to spend by model, and by user where the provider supplies it
- The existing note on detail level and delay also says how many recent days may still change, per provider
- **Raw Data** keeps every provider field and adds the normalised dimensions and the data source as extra columns

### Usage / Combined

- **Cost Explorer** groups by the normalised dimensions above, so a model or token type means the same thing whichever source it came from
- Every row carries its source: gateway, provider API, user tool or seat fee. This is already how the counting rule colours spend

### Attribution Rules (Phase 3)

- Suggested rules built from key names, workspace names and project names, approved, edited or rejected in bulk. Unmatched stays its own tab, and the aim is that every dollar has an owner

### Ledger (Phase 3)

- Each provider's settling window, such as up to 30 days for enterprise billing, decides how long its figures show "not settled yet"

### Reports and alerts (Phase 6)

- Alerts on sudden spend jumps, sent to chat or email, as Phase 6 already plans

## Ideas that need a decision before they are planned

- **Cost per customer or per feature.** This needs the customer's own product metrics joined to spend. It is not in the agreed plan
- **Accepting request-level logs from outside the gateway** in a published record format, so traffic that bypasses the gateway can still be attributed per request
- **Spend beyond AI** (cloud infrastructure and other software subscriptions) in the same reports. It is not in the agreed plan, and it would change what Token IQ is
