# What user tools reveal about the people using them

Research for Phase 4 of `docs/product/2026-09-14-token-iq-product-design.md`, done on 2026-09-14 from each vendor's own documentation. It answers that design's first open question: what per-user usage and cost data Claude Code, GitHub Copilot, ChatGPT and Codex, and Cursor actually expose

Nothing here has been tried against a real account. Where a vendor's page could not be read directly, the finding says so and is marked unverified

## The short answer

| Tool | Per-user cost | Per-user tokens | Per-user activity | Plan needed | Delay |
|---|---|---|---|---|---|
| Claude Code on a Claude Console organization | Yes, estimated, per model per day | Yes | Yes | Any organization with the Admin API | About 1 hour |
| Claude on a Claude Enterprise plan (chat, Claude Code and more) | Yes, per user, post-discount | Yes | Yes | Claude Enterprise, and cost only on usage-based plans | 4 to 24 hours, revised for 30 days |
| Claude Code through OpenTelemetry | Yes, estimated, near real time | Yes | Yes | Any, but the company must turn telemetry on for its developers | Seconds |
| GitHub Copilot | Seat fee plus AI credits per user, with an enterprise caveat | No | Yes | Copilot Business or Enterprise | About 1 day |
| Codex and ChatGPT on an Enterprise workspace | Credits per user exist, but the API details are unverified | Unverified | Yes | ChatGPT Enterprise or Edu | Unverified |
| Codex on an OpenAI API key | Tokens per user or key, priced by us | Yes | No | Any OpenAI API organization | Existing connector cadence |
| Cursor | Yes, billed cents per request and per member | Yes | Yes | Cursor Enterprise | About 1 hour |
| Personal subscriptions (Claude Pro or Max, ChatGPT Plus or Pro, Copilot Pro, Cursor Pro) | No | No | No | Not reachable | Not applicable |

Per-user cost is genuinely available for Claude, Cursor and, with care, Copilot. ChatGPT and Codex look available on Enterprise plans but need a real admin account to confirm. Every tool gates its admin data behind business or enterprise plans, so Token IQ's value here depends on which plans a customer has bought

## Claude Code and Claude

How a company buys Claude decides which of three sources applies, and a large customer may need more than one

### Claude Code Analytics API, for Claude Console organizations

`GET https://api.anthropic.com/v1/organizations/usage_report/claude_code?starting_at=YYYY-MM-DD` returns one record per user per day. It authenticates with an Admin API key (`sk-ant-admin01-...`) created by an organization admin, or an OAuth token with `org:admin`. Workspace keys are rejected, and the API is free

Each record identifies the actor either by `email_address` for people signed in through OAuth or by `api_key_name` for people using an API key. A `customer_type` field says whether the usage is pay-as-you-go API or a Pro or Team subscription. Records carry sessions, lines of code, commits, pull requests and tool accept and reject counts, plus a `model_breakdown` with input, output, cache read and cache creation tokens and `estimated_cost.amount` in cents USD

Data appears within about an hour, one day per request, with cursor pagination up to 1000 records per page, and no stated deletion period. It covers Claude Code on the Claude API only. Usage through Bedrock, Vertex, Microsoft Foundry or Claude Platform on AWS is excluded

### Claude Enterprise Analytics API, for Claude Enterprise organizations

Claude Enterprise reports Claude Code activity for claude.ai users here instead, together with chat and other products. It uses a separate Analytics API key with the `read:analytics` scope that only the organization's primary owner can create, in claude.ai organization settings. An Admin API key cannot call it, and an Analytics key cannot call the Admin API

| Endpoint | What it gives Token IQ |
|---|---|
| `GET /v1/organizations/analytics/user_cost_report` | Cost per user, ranked by spend, with `actor` carrying `user_id`, `email` and `name`, and `amount` in fractional cents as a decimal string (post-discount, pre-credit) alongside `list_amount` |
| `GET /v1/organizations/analytics/cost_report` | Cost over time by minute, hour or day, groupable by `product`, `model`, `rbac_group_id`, `cost_type`, `token_type` and more |
| `GET /v1/organizations/analytics/user_usage_report` | Tokens per user |
| `GET /v1/organizations/analytics/usage_report` | Tokens over time |
| `GET /v1/organizations/analytics/users?date=` | Per-user daily activity across chat, Claude Code, Cowork, Design, Office and Science |
| `GET /v1/organizations/analytics/summaries` | Daily, weekly and monthly active users and seat counts |

The `products[]` filter accepts `chat`, `claude-tag`, `claude_code`, `claude_design`, `claude_in_chrome`, `cowork` and `office_agent`, so Token IQ can separate a person's Claude Code cost from their chat cost

Three limits matter. **Cost and usage endpoints only report real cost on usage-based Enterprise plans.** On seat-based Enterprise plans they reflect usage credits only, and the seat fee has to come from Seats & Commitments. **Cost figures move for 30 days.** They usually arrive within 4 hours but can take 24, and Anthropic advises querying dates at least 30 days old for invoicing-grade totals, which maps directly onto the design's "not settled yet" state. Engagement data lags by about a day. Data starts on 2026-01-01, the rate limit is 60 requests a minute for the whole organization, and Claude Code used through Bedrock is not included

### OpenTelemetry, for near real-time cost from any deployment

Claude Code emits OpenTelemetry metrics when `CLAUDE_CODE_ENABLE_TELEMETRY=1` is set, and a company can enforce that for every developer through Claude Code's managed settings file, which overrides developer settings. The metrics include `claude_code.cost.usage` in USD and `claude_code.token.usage` split by input, output, cache read and cache creation, each labelled with `model`. The attributes include `user.email` whenever the user signed in, plus `organization.id`, `user.account_uuid` and `session.id`

The metrics export over OTLP (gRPC, HTTP JSON or HTTP protobuf) or Prometheus. The cost is Claude Code's own estimate. The documentation does not state whether telemetry covers Bedrock or Vertex deployments, but because the client emits it, it is the only source that could see Claude Code usage the two APIs exclude. That makes it worth offering to customers who run Claude Code on their own cloud accounts

Using it means Token IQ runs an OTLP receiver that each customer's developer machines can reach, which is a heavier piece of infrastructure than polling an API

### Claude Team plan

Team plan owners get a Claude Code usage dashboard, refreshed daily for the current month, with a per-member lines-of-code CSV export. Anthropic's help article documents no per-user cost API for Team. The Claude Code Analytics API labels some records `subscription` for Pro and Team customers, so a Team organization with Admin API access may be covered, but this needs a real Team account to confirm

## GitHub Copilot

Copilot cost per person is mostly a fixed seat fee. Since 1 June 2026 each seat also includes an allowance of AI credits, consumed by tokens at published model rates, and usage beyond the allowance is billed. The seat prices are Business at $19 and Enterprise at $39 per user per month

### Seats

`GET /orgs/{org}/copilot/billing` returns the plan and a seat breakdown with total, active and inactive seats for the cycle. `GET /orgs/{org}/copilot/billing/seats` lists every assignment with `assignee` login, `created_at`, `last_activity_at`, `last_activity_editor`, `plan_type`, `pending_cancellation_date` and `assigning_team`. Only organization owners can call these, with `manage_billing:copilot` or `read:org`

This is enough for the seat line of a user's cost and for a strong business recommendation: seats with no recent activity are money to reclaim

### Usage metrics

The usage metrics API became generally available on 2026-02-27. Enterprise endpoints live under `/enterprises/{enterprise}/copilot/metrics/reports/` and organization endpoints under `/orgs/{org}/copilot/metrics/reports/`. Each returns signed download links to NDJSON files, as a 1-day report per day or the latest 28-day report. Reports exist from 2025-10-10 and stay available for a year

The per-user reports (`users-1-day`, `users-28-day`) carry `user_id` and `user_login`, prompt, generation and acceptance counts, lines suggested and accepted, flags for agent, chat, CLI and code review use, breakdowns by IDE, feature, language and model, an `ai_adoption_phase` and `ai_credits_used`. GitHub describes the credits figure as "for consumption analysis, not invoicing totals". There are no token or cost fields. The enterprise endpoints need an enterprise owner, billing manager or someone with the "View Enterprise Copilot Metrics" permission, and the "Copilot usage metrics" policy set to enabled everywhere

### Billed AI credits per user

`GET /organizations/{org}/settings/billing/ai_credit/usage` (and the matching premium request endpoint) accepts a `user` filter and returns `quantity`, `grossAmount`, `discountAmount`, `netAmount` and `model` by day, month or year. This is the billed figure

There is a caveat. A GitHub community report says the `user` filter is blocked for organizations that belong to an enterprise, unless the request is made at enterprise level by an enterprise owner or billing manager using a classic personal access token with `admin:enterprise`. The report concerned premium requests, and whether the same applies to AI credits needs checking on a real enterprise account. Users whose licence is billed through an organization or enterprise never appear in the user-level billing endpoints

### Identity

Copilot identifies people by GitHub login, not email. Token IQ's User Directory has to link GitHub logins to company users, which companies using GitHub Enterprise Managed Users or SSO can usually supply

## ChatGPT and Codex

Codex is billed in one of two ways, and they need different sources

### Codex on an OpenAI API key

Codex used with an API key is billed at API token rates to the customer's OpenAI API organization, so it already appears in the OpenAI data Token IQ reads. The existing connector (`litellm/provider_billing/openai.py`) calls `GET /v1/organization/costs` grouped by `line_item`. The Costs API groups by `project_id` and `line_item`, while the Usage API (`GET /v1/organization/usage/completions`) also groups by `user_id` and `api_key_id` and returns tokens. Per-person Codex cost on an API key therefore means reading tokens per key or user from the Usage API and pricing them, which gives an `allocated` or `priced` figure rather than a billed one

### Codex and ChatGPT on a ChatGPT plan

Codex usage inside a ChatGPT plan draws on the same credits and limits as ChatGPT Work. On 2026-06-18 OpenAI added a Global Admin Console view for ChatGPT Enterprise that breaks credit consumption down by user, product and model across ChatGPT and Codex, with monthly limits at workspace, group and user level. It exposes the same data through what OpenAI calls a unified Cost API. **The Cost API's endpoint, fields, key type and plan eligibility are unverified**, because OpenAI's help center and announcement pages refused automated access and the public docs pages that could be read did not describe it. A real Enterprise admin account is needed before this connector is designed

ChatGPT Enterprise and Edu also have the Compliance Logs Platform. A workspace owner or admin creates a workspace-scoped admin key, and immutable JSONL log files are exported per time window and retained for 30 days. Its categories include Codex usage logs covering the CLI, IDE extension and cloud tasks. Those logs also contain prompts and responses, which Token IQ has no reason to store, so Compliance Logs is a fallback source for usage and never a place to pull conversation content from

ChatGPT Business gets workspace-level credit controls, but whether it gets per-user cost data through an API is unverified. Personal Plus and Pro subscriptions expose nothing

## Cursor

Cursor's admin data is the most complete of the four, but only for **Enterprise** teams. Its API overview lists the Admin, Analytics and AI Code Tracking APIs as available to "Enterprise teams" only. A team administrator creates an API key (`crsr_...`) in the Cursor dashboard, used as the username in Basic authentication, and every admin can see it

| Endpoint | What it gives Token IQ |
|---|---|
| `POST /teams/filtered-usage-events` | One row per request: `timestamp`, `userEmail`, `model`, `kind`, `maxMode`, `isChargeable`, `isTokenBasedCall`, `tokenUsage` with input, output, cache write and cache read tokens and `totalCents`, and `chargedCents`, the billed amount including Cursor's token fee and matching the dashboard. 60 requests a minute |
| `POST /teams/spend` | Current billing cycle spend per member: `spendCents`, `overallSpendCents`, `fastPremiumRequests`, `email`, and the member's limits |
| `POST /teams/daily-usage-data` | Per-user daily activity: lines added and accepted, tab, chat, agent and composer requests, requests from the subscription versus usage-based billing versus the member's own API key, and most used model. 30 days per request |
| `GET /teams/members` | `id`, `email`, `name`, `role`, `isRemoved` |
| `GET /teams/groups` | Billing groups with spend |

Data is aggregated hourly, and Cursor asks for these endpoints to be polled at most once an hour. A reported bug means removed members vanish from `daily-usage-data` even for dates they were active, while `filtered-usage-events` still returns them, so cost must be built from usage events. The Analytics API adds richer activity per user but carries no cost

`chargedCents` is a billed figure per request, which makes Cursor the one user tool where Token IQ can show `reconciled`-grade per-user cost at request level

## What this means for Token IQ's design

**Counting.** A developer using Claude Code or Codex with an API key on the company's own Anthropic or OpenAI organization shows up three times: in the provider cost report Token IQ already reads, in the tool's analytics, and in the gateway if the traffic goes through it. The counting rule in the design extends to user tools: the provider cost report stays the figure for how much was spent, and the tool data answers who spent it. Only tool usage billed outside the provider API organization, such as Claude Enterprise credits, Copilot seats and credits, ChatGPT plan credits and Cursor charges, adds to the total

**Evidence levels.** Cursor's `chargedCents`, Copilot's `netAmount` and Claude Enterprise's post-discount `amount` are billed figures and map to `reconciled` once settled. Claude Code Analytics `estimated_cost` and OpenTelemetry cost are estimates and map to `priced`. Codex on an API key, priced from tokens, is `allocated`

**Identity.** Claude and Cursor identify people by email and Copilot by GitHub login, while OpenAI's identifier is unverified. User Directory needs email as the primary key, with GitHub logins linked to it

**Freshness.** Claude Enterprise cost revises for 30 days, Copilot reports daily, and Cursor and the Claude Code Analytics API lag about an hour. Each source needs its own settling window, which the existing `settling_cutoff` helper in `litellm/provider_billing/cloud_rows.py` already models

**Plans.** Every one of these needs a business or enterprise plan on the customer's side, and Data Sources has to tell a customer plainly when their plan does not allow a connection

**Credentials.** Each tool adds its own admin key type: an Anthropic Admin key, a Claude Enterprise Analytics key that only a primary owner can create, a GitHub token with Copilot billing or enterprise scopes, an OpenAI workspace admin key and a Cursor admin key. All of them are billing-access credentials under the design's credential rules

## Recommended Phase 4 order

1. **Claude**, through both the Claude Code Analytics API and the Claude Enterprise Analytics API. Both are fully documented, give real per-user cost, and share Anthropic's existing admin authentication patterns with the connector already built
2. **Cursor**, through `filtered-usage-events` and `spend`. It is fully documented with billed per-request cost, but Enterprise only
3. **GitHub Copilot**, through seats, usage metrics and AI credit billing. It is fully documented, but the per-user billing caveat for enterprise-owned organizations must be checked on a real account first
4. **ChatGPT and Codex**, starting with a real Enterprise admin account to document the Cost API. Codex on an API key can be covered earlier from the existing OpenAI connector by adding Usage API grouping by user and key
5. **Claude Code OpenTelemetry**, later, for customers who need near real-time figures or run Claude Code on their own cloud accounts, since it needs an OTLP receiver per installation

## What still needs a real account

1. A ChatGPT Enterprise admin account, to document the Cost API endpoint, fields and key type
2. A GitHub enterprise owner, to confirm whether per-user AI credit billing works for enterprise-owned organizations
3. A Claude Team plan organization, to confirm whether the Claude Code Analytics API covers it
4. A Claude Code deployment on Bedrock or Vertex, to confirm whether OpenTelemetry reports cost there

## Sources

- Claude Code Analytics API: <https://platform.claude.com/docs/en/manage-claude/claude-code-analytics-api>
- Claude Analytics APIs, including Enterprise: <https://platform.claude.com/docs/en/manage-claude/analytics-api>
- Claude Enterprise Analytics API reference: <https://platform.claude.com/docs/en/api/admin/analytics>
- Claude Code monitoring with OpenTelemetry: <https://code.claude.com/docs/en/monitoring-usage>
- Claude Code usage analytics by plan: <https://support.claude.com/en/articles/12157520-claude-code-usage-analytics>
- GitHub Copilot usage metrics REST API: <https://docs.github.com/en/rest/copilot/copilot-usage-metrics>
- GitHub Copilot usage metrics fields: <https://docs.github.com/en/copilot/reference/copilot-usage-metrics/copilot-usage-metrics>
- GitHub Copilot user management REST API: <https://docs.github.com/en/rest/copilot/copilot-user-management>
- GitHub billing usage REST API: <https://docs.github.com/en/rest/billing/usage>
- GitHub Copilot usage-based billing announcement: <https://github.blog/news-insights/company-news/github-copilot-is-moving-to-usage-based-billing/>
- GitHub community report on per-user premium request usage for enterprise-owned organizations: <https://github.com/orgs/community/discussions/184208>
- Copilot metrics general availability: <https://github.blog/changelog/2026-02-27-copilot-metrics-is-now-generally-available/>
- Codex pricing and billing paths: <https://learn.chatgpt.com/docs/pricing>
- ChatGPT Work admin FAQ: <https://learn.chatgpt.com/docs/enterprise/work-admin-faq>
- OpenAI Usage API reference: <https://developers.openai.com/api/reference/resources/admin/subresources/organization/subresources/usage/methods/completions>
- OpenAI Usage and Costs API cookbook: <https://developers.openai.com/cookbook/examples/completions_usage_api>
- OpenAI enterprise spend controls announcement (could not be fetched directly): <https://openai.com/index/chatgpt-enterprise-spend-controls/>
- Secondary report of the same announcement: <https://enterprisedna.co/resources/news/openai-chatgpt-enterprise-spend-controls-analytics-june-2026/>
- OpenAI Compliance Platform (could not be fetched directly): <https://help.openai.com/en/articles/9261474-openai-compliance-platform-for-enterprise-and-edu-customers>
- Cursor Admin API: <https://cursor.com/docs/account/teams/admin-api>
- Cursor Analytics API: <https://cursor.com/docs/account/teams/analytics-api>
- Cursor API plan eligibility: <https://cursor.com/docs/api>
- Cursor forum report on removed members missing from daily usage data: <https://forum.cursor.com/t/admin-api-teams-daily-usage-data-omits-removed-members-still-returned-by-filtered-usage-events/165528>
