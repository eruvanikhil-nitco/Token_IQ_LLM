# Token IQ product design

Agreed in planning on 2026-09-14. Nothing has been built from this document yet, and every build step starts only when the product owner says go

## What Token IQ is

Token IQ tells a company what it spends on AI, who spent it, whether the bill is right, and what to change. It reads three sources, shows each one on its own, merges them without counting anything twice, and turns the result into business and technical recommendations

The **gateway** is the proxy that application traffic passes through. **Provider APIs** are the usage and cost reports that OpenAI, Anthropic, Azure OpenAI, AWS Bedrock, Google Vertex and OpenRouter publish about a company's own accounts. **User tools** are the admin reports that Claude Code, ChatGPT and Codex, GitHub Copilot and Cursor publish about the people using them

## Where the product stands on 2026-09-14

| Area | State |
|---|---|
| Gateway data | Works and is mature, inherited from LiteLLM along with its usage screens |
| Provider API ingestion | The engine is built: provider facts are stored idempotently, compared against gateway spend per request and per day, and fetched on a schedule from one replica. Six connectors exist. OpenRouter is the only one proven against real traffic; OpenAI, Anthropic, Bedrock, Azure and Vertex are built but have never run against a real account, so none of the five is established as working. Since `2026-09-16-provider-connections.md` the raw provider payload is stored on every fact, several accounts per provider are read separately, every fetch attempt is recorded, and the Provider APIs page shows each connection's state with What We Fetch and Sync History. Nothing reads the stored payloads back yet: that is Usage / APIs |
| Teams | Complete |
| Projects | Backend complete. Project spend is written and project budgets enforce since commits `6eba2ae1e2` and `ae7f344c6b`. The UI exists but is hidden behind a Beta switch and limited to admins |
| Users | Exist as internal users. A person's cost is now shown on their own page and on the Ledger's Seats & Commitments tab, counting the gateway traffic they drove plus the flat subscriptions assigned to them, with the parts always listed separately rather than blended into one figure. Every answer says on its face that it does not include what the person spent inside Claude Code, Copilot, Cursor or Codex, and stops saying so on its own the day a connector lands. Two rules hold: a seat is a fee for a period and is never spread across days, because a daily share of a monthly subscription is a number nobody was charged; and a subscription priced in one currency is left out of a total in another rather than converted, so the same person shows a different total when asked in dollars and in euros, each correct. Privacy is enforced in the endpoint, not the screen: a person may read their own cost and nobody else's, and only an admin may read everyone's. One limit found by testing and left as it is: a seat counts only when its whole period fits inside the window asked for, so narrowing to a single day inside a month shows that person's gateway spend with no subscription beside it. That is the correct arithmetic, since a month's fee cannot be attributed to one day, but the screen shows a bare zero rather than saying the subscription covers a wider period. The date pickers default to a calendar month, which is the case this was built for |
| User tools | Researched on 2026-09-14 from each vendor's documentation, nothing built. Per-user cost is genuinely available for Claude and Cursor and, with care, GitHub Copilot; ChatGPT and Codex look available on enterprise plans but the API details are unverified. Every tool gates this behind a business or enterprise plan, and personal subscriptions expose nothing. **No real account of any kind is available to this project**, so no user-tool connector can be verified. Five of the six provider connectors are in the same position. Every time something on this branch ran against real infrastructure it found a defect no test had caught, so any connector written from documentation alone must be treated as unproven until an account exists |. No connector is built. Phase 4's test is that a person's total includes their tool usage and their seats: seats are done, tool usage is not and cannot be until an account exists. The User Directory, the User Tools data-source page and the Tools tab on a user are all deferred for the same reason, since each one only has meaning once a tool reports something
| Attribution and unallocated spend | Built. For each provider account and day the provider's figure is compared against the gateway's, and whatever the provider charged beyond what the gateway recorded is offered to a rule that maps that account to a team, project or user. Spend no rule claims is reported as unallocated by name rather than spread across owners. Three limits are deliberate and visible on the screen rather than hidden: the gateway side is grouped by day alone, because a gateway spend log names the virtual key that served a call and never the provider account the provider later billed, so a customer with several accounts on one provider gets the per-account split from the provider's side only; a gateway request that recorded no provider name belongs to no provider's comparison, so it is invisible to reconciliation rather than charged to the wrong provider; and Google AI Studio traffic arrives as `gemini`, which has no billing connector and so can never be reconciled and must not be confused with Vertex. Rules keyed on a provider's own API key are not built, because no connector records that identifier, so such a rule could never match anything |
| Usage / Combined | Built, and it opens by default. Source Comparison shows every provider day by day with what the provider billed, what the gateway recorded, the difference and a status of matched, gap, not settled yet or provider reported nothing. Unallocated lists only differences nobody has claimed, each linking to the rule that would assign it. Cost Explorer groups gateway spend by team, project, user, provider or model and shows spend that bypassed the gateway beside it. Five limits are stated on the screen rather than hidden: spend is coloured by two sources and not four, because user tools and seat fees are Phase 4; a grouping with no rows says so instead of drawing an empty chart, which is what project does on an installation with no project spend; gateway spend whose rows carry no team or user is reported as a named figure rather than dropped, because it cannot belong to any bar; spend that bypassed the gateway can never reach a model or provider bar, since an attribution rule names a team, project or user and not a model, so it is reported on its own with that sentence; and the shared date range spans the three Combined views only, because Gateway keeps the filters it already had |
| Ledger and bill reconciliation | Three of the five Ledger tabs are built. Cost Ledger lists every cost line a provider reported, with how the figure was arrived at and who owns the account it came from; the gateway's own records are deliberately absent, because the two describe the same money and listing both would count it twice. Invoices accepts a bill an admin enters by hand, since almost no provider publishes invoices through an API, along with the credits, discounts, tax and commitments that explain a difference from usage. Bill Reconciliation sets the two against each other and always shows the unexplained remainder, with its sign, because a bill larger than the ledger and one smaller than it are different problems. Currency is carried and never converted: a bill in another currency is refused for comparison and both currencies are named, because a rate nobody chose would look authoritative and not be. Seats & Commitments is not built, because seats are flat per-person fees for user tools, which are Phase 4 with no data and no connector, so the screen could only show what someone typed into it; commitments are meanwhile captured as an adjustment on the bill, which is where a customer reads them off it anyway. Pricing Adjustments is not built either: it is a move of the existing Cost Tracking settings into a new group rather than new capability, and it belongs with the sidebar reorganisation. Uploading an invoice file is not built; a bill is typed in |
| Recommendations | Four rules are built and run over real data, each card carrying what was noticed, the evidence behind it, who should act and an amount only when there is an honest one. Two rules carry a figure and two deliberately carry none, since a risk and a stale limit are not costs. Of the two figures, one is money already being spent rather than money that could stop being spent, and it is labelled that way everywhere it appears. Four further rules are deferred, each for a reason recorded below. The existing Cost Optimization page remains the technical deep dive behind the cards |
| Per-team courier and translator mode | Done |

## How Token IQ is sold and delivered

Token IQ is a product sold to many companies. **Each customer company gets its own separate installation** with its own proxy, database and settings, and we host every installation in our own cloud. Installing into a customer's own cloud may come later

A shared platform was rejected because the codebase has no tenant boundary to build on. Of roughly 80 tables, only about 10 record an owning organisation. Provider credentials, models, prompts, policies, audit logs, SSO settings, UI settings, general config, budgets and provider billing facts have no owner column at all. Credential names are unique across the whole installation, and models, general settings and logging callbacks are held once in process memory. Fencing companies apart inside one installation would mean rewriting most of the data layer and would cut the fork off from upstream fixes, while a single mistaken query could show one company another company's spend or billing credentials

Inside an installation the company is the top of the hierarchy, which is why the Organizations page stays hidden

Delivering this way needs working Docker images, a deployment pipeline, automated provisioning of a new customer installation, and one-step upgrades across all installations. Database migrations already apply automatically at boot. A staff-only console showing each installation's version, health and subscription comes later

## Licensing rules

The repository carries two licences. Everything outside `enterprise/` is MIT, which allows commercial use, modification and hosting as long as the copyright notice and licence text are kept. The `enterprise/` folder was under the BerriAI Enterprise licence, which allows production use only with a paid subscription, forbids selling or distributing the code, and assigns ownership of any modification to BerriAI. Commit `728daee2d8` removed that folder on 2026-09-03 and the proxy runs without it

These rules follow from that, and every phase must respect them:

1. A rebuilt feature is written from our own design. Nothing is copied or adapted from LiteLLM enterprise code, including this repository's history before `728daee2d8` and the enterprise folder in upstream LiteLLM
2. LiteLLM licence key checks are replaced by Token IQ's own plan system, which Token IQ needs anyway to sell tiers
3. LiteLLM's copyright notice and MIT text stay in `LICENSE`
4. The LiteLLM name and logo do not appear anywhere a customer can see. The dashboard is mostly rebranded, but 18 backend error messages and 9 email templates still mention LiteLLM
5. A dependency scan on 2026-09-14 covered 216 Python and 741 JavaScript packages and found no AGPL, SSPL or BUSL licences. The LGPL packages (the psycopg Postgres driver at runtime, sharp at build time only) and MPL packages (certifi, tqdm, orjson, lightningcss, axe-core) create no obligations while unmodified and hosted by us. The scan is repeated before any installation in a customer's cloud
6. A lawyer reviews this position before the first customer

### Features behind LiteLLM's licence key

Some features are MIT code switched off by a licence check, and Token IQ's plan system replaces the check:

| Feature | Why Token IQ needs it |
|---|---|
| Assigning team admins | The team, project and user permission model depends on it |
| SSO for more than 5 users | Every company customer expects single sign-on |
| SCIM user sync | Data Sources / User Directory |
| JWT and OAuth2 token auth | How larger companies connect their identity systems |
| Models limited to one team | Teams bringing their own provider keys |
| Tags on keys | Cost attribution |
| Per-model budgets on keys | Budget control |
| Enforced request parameters | Company guardrails |
| Route restrictions, request and file size limits | Security |
| Google Secret Manager | Credential storage |
| Spend report, fine-tuning endpoints, priority rate limit reservation | Gateway features |

Other features lived only in the deleted enterprise folder, so they must be rebuilt from scratch if Token IQ wants them: email alerts over SMTP, SendGrid and Resend, PagerDuty alerts, secret detection and hiding, Llama Guard, LLM Guard, banned keywords, blocked user lists, OpenAI and Google moderation, Aporia, callback controls, managed file and batch access checks, the original audit log endpoints, and a custom SSO handler

The audit trail itself survives. Admin Settings / Audit Log already works, because it reads `/audit/list`, a fresh implementation added on 2026-09-10 that is not based on enterprise code. The Logs page's Audit Logs tab still calls the deleted `/audit` route and shows nothing, and `/audit/list` checks no role, so organisation admins can read the whole installation's trail. Phase 0 fixes both

## The counting rule

A request that goes through the gateway to a provider appears twice: once in the gateway's own records and once in the provider's cost report. The separate Gateway and APIs views each show their source exactly as it is. The Combined view never adds the two together

For each provider and day, **the provider's figure says how much was spent** and **the gateway's figure says who spent it**. Whatever the provider charged beyond what the gateway recorded is spend that bypassed the gateway. It gets its own line, assigned to a team, project or user through attribution rules, or shown as unallocated when no rule matches

Every figure carries its source and an evidence level (`reconciled`, `priced` or `allocated`, already implemented in `litellm/types/proxy/provider_billing.py`) and a freshness marker. Provider data arrives hours to days late, so a day that has not settled is labelled "not settled yet" rather than being shown as a gap

## Data sources

### Gateway

Today's spend logs and daily rollups, including the per-project rollup added on 2026-09-13

### Provider APIs

| Provider | What we read | Detail level | Status |
|---|---|---|---|
| OpenRouter | Generation API | Per request | Built, proven on real traffic |
| OpenAI | Organization Costs API | Per day | Built, never run on a real account |
| Anthropic | Admin Cost Report | Per day | Built, never run on a real account |
| AWS Bedrock | Cost Explorer | Per day | Built, never run on a real account |
| Azure OpenAI | Cost Management query | Per day | Built, never run on a real account. One connector covers Azure and Azure OpenAI |
| Google Vertex | BigQuery billing export | Per day | Built, never run on a real account |

Request-level forensics is only possible for OpenRouter. For every other provider the finest comparison is per model per day, and the UI says so

Token IQ cannot embed a provider's real dashboard, because those pages need the provider's own login and block embedding. The Summary view rebuilds the same figures from the provider's API instead

The inside of these pages borrows from established cloud cost platforms, researched in `docs/superpowers/specs/2026-09-15-cost-platform-reference.md`. Within the agreed tabs that means four connection states (Not connected, Waiting for first data, Healthy, Needs attention), a key type check before saving, the stated refresh delay and history on What We Fetch, a data source label and one provider-independent set of dimensions on every row, and a per-provider window for how long figures may still change. Three ideas from that research need a decision before they are planned: cost per customer or feature, accepting request-level logs from outside the gateway, and spend beyond AI

### User tools

What each tool exposes is researched in `docs/superpowers/specs/2026-09-14-user-tools-data-research.md`. Per-user cost is documented for Claude and Cursor, available for GitHub Copilot as seat fees plus billed AI credits with a caveat for enterprise-owned organizations, and unverified for ChatGPT and Codex until a real Enterprise admin account confirms OpenAI's Cost API. Every tool requires a business or enterprise plan, and personal subscriptions paid through expenses are invisible to every API

Claude Code and GitHub Copilot were chosen first. The research recommends building Claude first, then Cursor, then Copilot once its billing caveat is checked, then ChatGPT and Codex

### Credentials

All credentials are entered in one place, Data Sources. The existing LLM Credentials page is renamed **LLM Provider Credentials**. Each credential is labelled by purpose, either **model access** (used to serve models) or **billing access** (used to read costs), because OpenAI and Anthropic cost reports need an admin key that is different from the key that calls models. Billing credentials are read-only, stored encrypted and never shown back

## Hierarchy and who sees what

Inside a company's installation the hierarchy is **teams**, then **projects** and **users** within each team. The product uses the words teams, projects and users throughout

A proxy admin sees the whole company. A team admin sees their own team, its projects and its users. A user sees only their own cost. Team admins are currently behind LiteLLM's licence key, so Phase 0 moves them onto Token IQ's plan system before Phase 1 relies on them

Budgets behave differently by source. A team or project budget blocks further gateway requests, but it cannot stop someone's Claude Code or Copilot usage, so for user tools and direct provider spend a budget only alerts. The UI states which of the two applies

Attribution rules map provider keys, workspaces, cloud accounts and tool logins to a team, project or user. Anything unmatched stays visible as unallocated spend with an owner, and is never spread silently across teams. Every change to a rule is recorded

## Navigation

### Tab rules

These rules apply to every page:

1. The sidebar chooses a thing, and tabs show views of that thing. A feature's settings sit in a Settings tab at the end of its own page
2. Detail pages share one shape: a header with name, copyable ID, status and key figures, followed by tabs
3. Overview comes first and Settings comes last
4. Each kind of thing has one home: credentials in Data Sources, cost adjustments in Ledger, budgets under Organisation
5. The chosen tab is in the URL so a shared link opens the same view
6. Every data screen has a freshness badge, a source label and an export button

**No existing page or tab is removed or merged.** Pages and tabs may move or be renamed, and every old address redirects to the new one. Ten merge and removal suggestions were rejected on 2026-09-14 and are not reintroduced without fresh approval. The eight pages that have routes but no sidebar entry (Organizations, Agents, Workflows, Memory, Caching, Vector Stores, Search Tools, Tool Policies) stay out of the sidebar

To keep future upstream merges manageable, the reorganisation is done mostly in the sidebar definition (`ui/litellm-dashboard/src/components/leftnav.tsx`) and the redirect map (`ui/litellm-dashboard/src/utils/migratedPages.ts`) rather than by moving page folders

### Full sidebar

Status: NEW is a Token IQ addition, SAME is unchanged, MOVED and RENAMED keep all content

```
HOME
  Overview ............................ NEW
      total spend across all sources, change against last period, bill match per
      provider, share unallocated, top recommendations, data freshness

ANALYTICS
  Usage ............................... Gateway tab SAME, APIs and Combined tabs NEW
      Combined opens by default. Its Cost Explorer colours two sources, not four:
      user tools and seat fees wait for Phase 4 and are not drawn as empty
      categories. Its date range spans the three Combined views only; Gateway
      keeps the filters it already had
      Gateway    Cost | Models | Keys | MCP | Endpoints   (view picker gains Project)
      APIs       Provider accounts: All | OpenAI | Anthropic | Azure OpenAI | Bedrock | Vertex | OpenRouter
                 User tools: All | Claude Code | ChatGPT & Codex | Copilot | Cursor
                 each provider and tool: Summary | Raw Data
      Combined   Cost Explorer | Source Comparison | Unallocated   (opens by default)
  Classic Usage ....................... MOVED from Experimental, RENAMED from Old Usage
      All Up | Team Based | Customer | Tag Based | Cost | Activity
  Ledger .............................. NEW
      Cost Ledger | Bill Reconciliation | Invoices | Seats & Commitments
      Pricing Adjustments is a move of the existing Cost Tracking settings and
      belongs with the sidebar reorganisation, so it is not shown as an empty tab
      (Pricing Adjustments holds all of Cost Tracking: Provider Discounts, Fee/Price Margin,
       Block Unpriced Models, Pricing Calculator)
  Recommendations ..................... NEW
      All | Business | Technical | Done & Dismissed
  Cost Optimization ................... MOVED from Observability
      Caching | Compression | Auto-Router Usage | Shadow Evals
  Logs ................................ MOVED from Observability
      Request Logs | Audit Logs | Deleted Keys | Deleted Teams
  Reports ............................. NEW (Phase 6)
      Scheduled | Team Statements | Exports

ORGANISATION
  Teams ............................... SAME, two NEW detail tabs
      list:   Your Teams | Available Teams | Default Team Settings
      detail: Overview | My User | Virtual Keys | Members | Member Permissions
              | Projects (NEW) | Budget (NEW) | Settings
  Projects ............................ Beta label removed, on by default, team admins allowed
      list shows spend and budget columns
      detail: Overview | Keys | Provider Accounts (NEW) | Budget | Settings
  Users ............................... RENAMED from Internal Users
      list:   Users | Default Settings
      detail: Overview | Details | Seats (NEW)
      The Tools tab is not built: no user tool reports anything yet, and a tab that
      can never have a value is worse than an absent one
  Access Groups ....................... SAME
      Models | MCP | Agents
  Budgets ............................. MOVED from Access Control
      Budgets | Assign Budget | Examples | Model Access Group Budgets (MOVED from Models)
  Attribution Rules ................... NEW
      Cloud Accounts | Unmatched
      Provider Keys is not built: no connector records a provider's own API key id, so a
      rule of that kind could never match a fact. Tool Logins waits for user tools in
      Phase 4. Neither is shown as an empty tab, because a control that silently does
      nothing is worse than an absent one

DATA SOURCES .......................... NEW group
  Provider APIs ....................... NEW
      one tab per provider: Connection | What We Fetch | Sync History
  User Tools .......................... NEW
      one tab per tool: Connection | What We Fetch | Sync History
  LLM Provider Credentials ............ MOVED from Models, RENAMED from LLM Credentials
  User Directory ...................... NEW
      SSO Sync | SCIM (MOVED from Admin Settings) | Import

GATEWAY
  Virtual Keys ........................ SAME
      detail: Overview | Savings | Settings
  Providers ........................... SAME
      Overview | Models
  Models + Endpoints .................. SAME apart from two tabs moved out
      All Models | Add Model | Pass-Through Endpoints | Health Status | Model Retry Settings
      | Model Limits | Model Pricing | Model Group Alias | Price Data Reload
  Playground .......................... SAME
  API Playground ...................... MOVED from Experimental

SAFETY
  Guardrails .......................... MOVED from AI Gateway
      Guardrails | Garden | Playground | Submitted
      detail: Overview | Settings
  Guardrails Monitor .................. MOVED from Observability
  Policies ............................ MOVED from AI Gateway
      Policies | Templates | Attachments | Simulator

BUILD
  MCP Servers ......................... MOVED from AI Gateway
      Servers | Toolsets | Connect | Tool Search | Semantic Filter | Network Settings | Submitted
  Skills .............................. MOVED from AI Gateway
  Prompts ............................. MOVED from Experimental
  Tag Management ...................... MOVED from Experimental
  AI Hub .............................. MOVED from Developer Tools
      Models | Agents | MCP | Skills
  API Reference ....................... MOVED from Developer Tools
      OpenAI | LangChain | LlamaIndex

SETTINGS
  Admin Settings ...................... SAME apart from SCIM moved out
      SSO Settings | Security Settings | UI Settings | Logging Settings | Audit Log
      | Hashicorp Vault | CyberArk Conjur | Plugins
  Router Settings ..................... SAME
      General | Loadbalancing | Fallbacks | Routing Groups | Prompt Caching
  Logging & Alerts .................... SAME
      Logging Callbacks | CloudZero Cost Tracking | Alerting Types | Alerting Settings
      | Email Alerts | MS Teams Alerts
  UI Theme ............................ SAME
```

The Experimental, Observability, AI Gateway, Access Control and Developer Tools group labels go away because every page in them has a new home. No page inside them is lost

## Key screens

### Usage

A filter bar shared by all three tabs holds the date range, team, project and user filters, an export button and a freshness badge. A filter chosen on one tab stays applied when switching to another

**Gateway** is today's usage page, unchanged except that its view picker gains Project

**APIs** has one tab per provider account and one per user tool, grouped separately. Each has a **Summary** tab (headline totals, spend over time, spend by model, spend by whatever the provider can break down by, and a note on detail level and delay) and a **Raw Data** tab (the rows exactly as the provider sent them, searchable, with column choice, the original response per row, and CSV or JSON export). A source that is not connected shows a prompt to connect it in Data Sources instead of an empty chart

**Combined** opens by default. **Cost Explorer** groups spend by team, project, user, provider, model or source, coloured by where the money went: through the gateway, outside the gateway, user tools and seat fees. **Source Comparison** shows, per provider per day, the gateway figure, the provider figure, the gap and a status of Matched, Gap or Not settled yet. **Unallocated** lists spend with no owner and links to the attribution rule that would assign it

### Data Sources

Each provider and tool has a card with **Connection** (state, credential, required permission and a Test button backed by the existing `/provider/billing/probe`), **What We Fetch** (the endpoints read, in plain words, and how often) and **Sync History** (every fetch, its row count and any failure). Sync history lives only here and is not repeated in Usage

### Ledger

**Cost Ledger** lists every cost line with its source, evidence level and owner. **Bill Reconciliation** compares the ledger total with the provider's bill for a week, month or year and breaks the gap into credits, discounts, tax, commitments and the unexplained remainder. **Invoices** accepts uploaded or entered invoices, since few providers expose invoices through an API. **Seats & Commitments** holds flat per-person subscriptions and prepaid or reserved capacity. **Pricing Adjustments** holds the existing Cost Tracking settings

### Users

A user's detail page shows their total cost across gateway usage, user tools and seat fees. **Tools** breaks that down per tool, and **Seats** lists the subscriptions assigned to them. The same user tool also appears company-wide in Usage / APIs

## Add Model uses saved credentials only

Add Model stops offering a field for typing a key and offers only a choice of saved credential. Four conditions come with that:

1. The credential picker has a **New credential** button that opens the credential form in place, saves the credential to the shared list and selects it
2. Team admins can create credentials that belong to their own team and see only those, since the LLM Provider Credentials page is admin-only today
3. A credential can hold connection details without a secret, for providers that use no key, such as a local Ollama or Bedrock and Vertex running on cloud permissions
4. Models already created with a typed key keep working, and admins get a one-click action to move that key into a saved credential. Nothing is converted automatically

The change covers the UI first. Models added through the API or the config file may still carry a key, and whether to enforce the same rule there is decided later from real usage. Add Model gains a "Manage LLM Provider Credentials" link beside the picker

## Recommendations

Recommendations are rules evaluated over the combined data rather than a model's guesses. Each card states what was noticed, the evidence behind it, who should act, and an amount only when there is an honest one. A card can be marked done or dismissed, and a dismissed card stays reachable rather than vanishing, so a decision leaves a trace. No card is ever stored: every one is recomputed from current data on each request, so a problem that gets fixed stops appearing on its own and one that returns is seen again instead of staying hidden behind a decision somebody made months ago

### The figure rule

An amount is only called a saving when acting on the card would reduce what the company pays. Everything else carries a different label or no number at all. A card therefore carries an amount together with what kind of amount it is, and the type refuses a figure with no kind and a kind with no figure, so a rule cannot reach a screen having got this wrong. Three kinds exist:

- money that could stop being spent, which is the only one a screen may present as a saving
- money already being spent and unwatched, where acting makes it visible and owned but changes no total
- no figure, where there is nothing honest to quantify and the card says so rather than showing a zero

The reason is plain. Most of what these rules find is not a saving. Spend that escaped the gateway is money the company is paying either way, and concentration on one provider is a risk rather than a cost. A number labelled saving beside either would not survive a finance lead asking one question, and it would discredit every other card on the screen

### The four rules that are built

| Rule | Kind | What it reports | Figure |
|---|---|---|---|
| Spend reached a provider without passing through the gateway | Business | Provider spend nobody has claimed, and the accounts it came from | Money already being spent, never called a saving |
| Money spent on requests that failed | Technical | Failed requests and the share of the total they represent | Money that could stop being spent, and only when the spend on those requests is actually known |
| Every provider dollar goes through one provider | Business | The provider and its share | None. A risk, not a cost |
| A budget no longer matches what is actually spent | Business | The limit and what was spent against it | None. Acting changes a limit, not spend |

### The four rules that are deferred, and why

Unused seats to reclaim needs tool usage to know a seat is unused, and a person with no gateway traffic may still be using the tool daily; recommending someone lose their licence on that basis would be wrong. A cheaper model that performs well enough needs a judgment about output quality that cost data cannot make, and a swap made on price alone can quietly degrade a customer's product. Committed pricing needs contract terms nobody has given us. Caching that is available but unused needs to know caching is available for that model and provider, which the data does not say, and the existing Cost Optimization page already covers caching as a deep dive

## What the product must handle

| Concern | How Token IQ handles it |
|---|---|
| Seat and subscription costs | Seats & Commitments, included in each user's total, since tool plans are mostly flat per-person fees |
| Bills that differ from usage reports | Invoices and Bill Reconciliation account for credits, discounts, tax and commitments |
| Double counting | The counting rule |
| Spend with no owner | Unallocated, visible and owned |
| Late data | Freshness badges and a "not settled yet" state |
| Budgets that cannot block a source | The UI says whether a budget blocks or only alerts |
| One person with different logins per tool | User Directory links identities |
| Privacy of per-person cost | Users see only their own cost and team admins see their team |
| Personal AI subscriptions | Stated as a known blind spot |
| Admin key safety | Read-only, encrypted, never displayed |
| Currency | Every cost keeps its original currency alongside a converted figure |
| Changes to attribution | Every rule change is recorded |
| Growth of raw provider data | A retention period per installation |

## Phases

**Phase 0, product readiness.** Token IQ's own plan system replacing LiteLLM licence checks, starting with team admins. Docker images that build from a clean checkout and a deployment pipeline for customer installations. The Logs page Audit Logs tab moved onto the working audit trail, with the audit endpoint limited to admins. Rebranding of the remaining customer-visible LiteLLM text. Done when a fresh installation builds, deploys and lets a team admin be assigned without a LiteLLM licence. The work is planned in `docs/superpowers/plans/2026-09-14-token-iq-plan-system.md` and `docs/superpowers/plans/2026-09-14-release-readiness.md`, and deployment waits on the choice of cloud provider

**Phase 1, organisation and navigation.** Projects switched on, without the Beta label and open to team admins, with spend and budget columns and the daily report connected. New Projects and Budget tabs on teams. Users renamed. The full sidebar reorganisation with redirects. Project added to the Gateway view picker. Done when every existing page and tab is reachable in its new place and every old address redirects

**Phase 2, data sources and provider accounts.** Azure and Vertex connectors, storage of raw provider responses, verification of the OpenAI, Anthropic and Bedrock connectors on real read-only accounts, the Data Sources pages, the LLM Provider Credentials move with purpose labels, the Add Model change, and Usage / APIs with Summary and Raw Data. Done when each connected provider shows real Summary and Raw Data for a customer

**Phase 3, combined view and ledger.** Attribution rules, unallocated spend, Usage / Combined, Cost Ledger, Invoices and Bill Reconciliation. Done when a month's provider bill can be reconciled against the ledger with every gap explained or marked unexplained

Phase 3 is complete as of 2026-09-29, and the completion test was run rather than assumed: September's OpenRouter ledger totals `0.00780515`, entering that as the bill reconciles as balanced with an unexplained remainder of exactly zero, a bill higher than usage balances when tax or a commitment covers the difference, a bill lower balances when a credit covers it, removing the explanation brings the remainder back at exactly the right size, and the same amount billed in euros is refused with both currencies named. That holds for OpenRouter, the one provider with real data. The other five connectors have still never run against a real account, so nothing downstream of them is established as working

**Phase 4, users and user tools.** The research report on user tool APIs comes first. Then User Directory, seats, the Claude Code and Copilot connectors, and the Tools and Seats tabs on users. Done when a user's total cost includes their tool usage and seats

**Phase 5, recommendations.** The first business and technical rules with evidence and savings. Done when recommendations show real savings figures from a customer's own data

Phase 5's test is not met, and the gap is worth stating plainly rather than reading the four built rules as completion. Two of the four rules carry a figure at all. One of those two, spend that escaped the gateway, is money already being spent and is not a saving under the rule above, so exactly one rule can ever produce a savings figure, and it does so only when the spend attached to failed requests is known. The only real data any of this runs against is one provider's, since five of the six provider connectors have still never seen a real account. So the rules and the screen are built and verified against the data that exists, and the phase stays open until a customer's own data can produce a savings figure

**Phase 6, reports, alerts and forecasts.** Scheduled reports, team statements, exports, anomaly alerts and forecasts

## Decisions

| Date | Decision |
|---|---|
| 2026-09-14 | Three sources, shown separately and then combined under the counting rule |
| 2026-09-14 | The hierarchy uses teams, projects and users, never "employees" |
| 2026-09-14 | Usage has Gateway, APIs and Combined tabs, and Combined opens by default |
| 2026-09-14 | Project is added to the Gateway view picker |
| 2026-09-14 | No existing page or tab is removed or merged, and all ten merge suggestions are rejected |
| 2026-09-14 | The eight pages without sidebar entries stay hidden |
| 2026-09-14 | LLM Credentials is renamed LLM Provider Credentials and moves to Data Sources |
| 2026-09-14 | Add Model offers saved credentials only, under the four conditions |
| 2026-09-14 | Claude Code and GitHub Copilot are the first user tools |
| 2026-09-14 | Invoices may be uploaded or entered by finance |
| 2026-09-14 | Users see their own cost, and team admins see their team |
| 2026-09-14 | The navigation reorganisation happens in Phase 1 |
| 2026-09-14 | One separate installation per customer company, hosted in our cloud |
| 2026-09-14 | Features behind LiteLLM's licence key are built by Token IQ under the licensing rules |

## Open questions

1. The four questions only a real account can answer, listed at the end of the user tools research
2. The outcome of the legal review of the licensing position
3. The tiers of Token IQ's plan system and which features each includes
4. Which invoice formats finance will upload
5. The currency conversion source and how often rates refresh
6. How long raw provider data is retained by default
7. Whether the saved-credential rule for Add Model is also enforced for the API and config file
