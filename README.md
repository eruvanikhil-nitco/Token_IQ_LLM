# Token IQ

An observer-only LLM gateway. Clients call one OpenAI-compatible endpoint, Token IQ forwards
the request to the provider unchanged, and returns the provider's answer unchanged. It watches
traffic and accounts for it. It does not rewrite it.

Built on [LiteLLM](https://github.com/BerriAI/litellm), which does the provider translation.
Token IQ is a fork that removes the parts of that gateway which alter a request or silently
change where it goes.

## What observer-only means here

A gateway that quietly retries against a different provider, falls back to a cheaper model, or
answers from its own cache is convenient and occasionally very confusing: the response a client
receives is not the one their chosen provider produced. Token IQ closes those paths.

- **The provider and model never change.** Retries go back to the same endpoint. Fallback
  configuration is refused at startup rather than ignored, and so are duplicate deployments of
  the same model name, because both let a request end up somewhere the caller did not name.
- **Scored routing is gone.** Latency, cost, usage and complexity strategies were removed, so
  there is no scoring layer left to pick a different deployment.
- **Cooldowns are disabled.** A provider that returned errors is still called if a client asks
  for it, rather than being quietly skipped.
- **Responses are never served from cache.** Cache reads always miss, and both paths that would
  enable caching now refuse.
- **Retries are limited to cases where nothing was processed**: 429, 502, 503, 504, and
  connection failures. A read timeout is not retried, because the provider may already have run
  the request and billed for it.

Enterprise-gated features are removed rather than shown as upsells.

## Requirements

- Python 3.10 to 3.14 (this checkout runs 3.12)
- Docker, for the Postgres database
- Node 20 and npm, only if you are changing the dashboard

## Running it

Start the database and the proxy:

```powershell
docker start tokeniq_db
.\run-proxy.ps1
```

`run-proxy.ps1` reads the database credentials from the running container, so no password is
stored in the repo or typed on the command line. The gateway comes up on
<http://localhost:4001> and the dashboard on <http://localhost:4001/ui/>.

If the database container does not exist yet:

```bash
docker compose up -d db
```

### Calling it

A client needs two things: the base URL and a virtual key. The key authenticates the caller and
carries its budget, rate limits and model access. It cannot route anything on its own, which is
why the base URL is shown beside every key in the dashboard.

```bash
curl http://localhost:4001/v1/chat/completions \
  -H "Authorization: Bearer sk-your-key" \
  -H "Content-Type: application/json" \
  -d '{"model": "your-model", "messages": [{"role": "user", "content": "hello"}]}'
```

Any OpenAI-compatible SDK works by pointing `base_url` at the gateway. The proxy serves both
`/chat/completions` and `/v1/chat/completions`, so a base URL with or without `/v1` is fine for
OpenAI-style clients. Anthropic's SDK appends `/v1/messages` itself, so give it the base URL
without `/v1`.

## Configuring it

Models, credentials and settings live in `litellm/proxy/dev_config.yaml`, and models added
through the dashboard are stored in Postgres. `general_settings.store_model_in_db` must stay
enabled for the second kind to load at startup.

The **Providers** tab lists only providers the gateway is actually set up for: those carrying
credentials, plus any that have served traffic. A provider whose deployments point at unset
environment variables cannot answer a request, so listing it would describe a gateway that is
not there.

### Keys, teams and budgets

A **virtual key** is stored as a SHA-256 hash, so a lost key is replaced rather than recovered.
Each key carries its own model access, spend cap and rate limits.

A **team** is the unit above it, which usually maps to a department. Teams hold a shared budget
with a reset period, model access, rate limits, members with roles, and a block switch that
stops the whole team at once. Keys belong to teams, and both sets of limits apply, so a team
cap holds no matter how many keys sit inside it.

## Development

```bash
make bootstrap                  # install backend and dashboard dependencies
make check                      # lint, types and the budget gates
```

Backend tests mirror the source tree under `tests/test_litellm/`:

```bash
pytest tests/test_litellm/proxy/management_endpoints/
```

The dashboard lives in `ui/litellm-dashboard`. Run `npm run dev` there for a live server on
port 3000, or `npm run build` to produce the static bundle the proxy serves. Run only the test
files your change touches; the full suite is large and CI runs it anyway.

Every deletion and significant change in this fork is recorded in `project_usage/`, with the
reasoning and instructions for restoring it.

## Licence

MIT, inherited from LiteLLM. See [LICENSE](LICENSE). The upstream copyright notice stays in
place; only the product name differs.

Powered by NITCO Inc.
