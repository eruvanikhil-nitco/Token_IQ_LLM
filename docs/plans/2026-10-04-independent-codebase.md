# Token IQ: independent codebase and restructure, instructions for Claude Code

## How to use this file

There are two files. Put both in the repository before starting:

| File | Where to put it | What it is for |
|---|---|---|
| `TOKEN_IQ_RESTRUCTURE.md` (this file) | repository root for now; phase 1 moves it to `docs/plans/2026-10-04-independent-codebase.md` | **What to do and in what order.** Follow it phase by phase. |
| `tokeniq-blueprint.html` (the Token IQ Product Blueprint) | `docs/product/token-iq-product-blueprint.html` | **What the product should become.** A design reference for UI and features. Section 12 of this file says how to read it. Do not copy its mockup code into the product. |

Start Claude Code at the root of the `Token_IQ_LLM` checkout, on branch `litellm_token_iq`,
and say:
"Read `TOKEN_IQ_RESTRUCTURE.md` and do phase 0. Stop and show me the results before phase 1."
Run each later phase the same way, one pull request per phase, and review each one before
merging.

---

## 1. Decisions this plan carries out

These were decided by the project owner on 4 Oct 2026. Phase 1 records them as decision
records.

1. **Token IQ becomes an independent codebase.**
   - The fork from LiteLLM is disconnected and upstream is never merged again.
   - This **reverses** the rule in `project_usage/21-client-facing-rebrand.md` that kept
     `litellm` identifiers so upstream merges stayed possible.
2. **No `litellm` name anywhere in the product.** The goal covers:
   - package, module, class and function names;
   - command names;
   - environment variables and config keys;
   - HTTP headers and metric names;
   - database tables;
   - Docker images, folders, UI text and logs.

   **The only exceptions:**
   - the licence text and attribution notice (required by the MIT licence, see below);
   - historical decision records and the changelog;
   - a temporary compatibility module for one release (phase 7), which is then deleted.
3. **Licence obligation.** LiteLLM is MIT-licensed. The MIT licence requires the original
   copyright notice and licence text to stay with copies of the software. So:
   - keep `LICENSE` with BerriAI's copyright notice;
   - add a NITCO copyright line;
   - add a `NOTICE` file saying "Token IQ includes code derived from LiteLLM (MIT License,
     Copyright (c) 2023 Berri AI)".

   Never delete the original notice. It is legal text, not branding, and customers never see
   it in the product.
4. **Remove before renaming.** Upstream features that Token IQ does not use are deleted
   before the big rename, so no effort goes into renaming code that is about to be removed.
5. **Rename in layers, with one transition release.** Running installations keep working
   while customers move to the new names:
   - environment variables;
   - config keys;
   - request headers;
   - database tables.

### Target names (the rename map is built from this in phase 6)

| Today | New name |
|---|---|
| Python package `litellm` | `token_iq.gateway` (the engine: provider translation, proxy, auth, spend tracking) |
| Token IQ product modules (`litellm/provider_billing`, `ledger`, …) | `token_iq.<module>` (phase 3) |
| Distribution name `litellm` (`pyproject.toml`) | `token-iq` |
| `litellm-proxy-extras` (migrations package) | `token-iq-migrations`, Python package `token_iq_migrations` |
| Commands `litellm`, `litellm-proxy`, `lite` | `token-iq` (server), `token-iq-cli` (admin client) |
| Environment variables `LITELLM_*` | `TOKEN_IQ_*` |
| Config keys `litellm_settings`, `litellm_params` | `gateway_settings`, `model_params` |
| HTTP headers `x-litellm-*` | `x-token-iq-*` |
| Prometheus metrics `litellm_*` | `token_iq_*` |
| Database models and tables `LiteLLM_*` (85 models) | models without the prefix (`LiteLLM_TeamTable` → `TeamTable`); tables in snake_case (`team_table`) in a later migration |
| Redis and cache key prefixes `litellm…` | `token_iq…` |
| Identifiers containing LiteLLM (`LiteLLMRoutes`, `litellm_logging`, `litellm_core_utils`) | `GatewayRoutes`, `gateway_logging`, `core_utils` (rules in phase 6) |
| `ui/litellm-dashboard/` | `ui/dashboard/` |
| `tests/test_litellm/` | `tests/gateway/` |
| Docker images, Helm chart, Terraform names | `token-iq…` |

### Naming conventions (everything new follows these)

| Where | Convention | Example |
|---|---|---|
| Product name in UI, docs, emails | **Token IQ** (two words) | "Token IQ API" |
| Python | `token_iq` package, snake_case modules, `TokenIq…` classes, `TOKEN_IQ_` env vars | `token_iq/connectors/billing/openai.py` |
| UI folders, URLs, CSS, Terraform, HTTP headers, images | kebab-case | `src/token-iq/`, `x-token-iq-project` |
| Tests | `tests/<mirror of package path>/test_<module>.py` | `tests/token_iq/connectors/billing/test_openai.py` |
| Design specs and plans | `YYYY-MM-DD-kebab-slug.md` | `2026-09-29-recommendations.md` |
| Decision records | `NNNN-kebab-slug.md` | `0022-independent-codebase.md` |
| API routers | resource name, plural, no `_endpoints` suffix | `projects.py` |
| "Courier mode" | the UI says **"Pass-through mode"** | |

---

## 2. Facts measured on 3 Oct 2026 (commit `353edcc`)

**Fork state.** The fork was taken from upstream on 3 Sep 2026 and never merged since. The
working branch is `litellm_token_iq`; `main` is stale (11 Sep).

**Token IQ footprint.** 431 files were created for Token IQ. List them with:

```bash
git log --author="Nikhil" --diff-filter=A --name-only --format="" | sort -u | grep -v "^litellm/proxy/_experimental/out"
```

**Size of the rename, from `project_usage/21`:**

- 521,641 occurrences of `litellm` across 5,513 files;
- 33,271 imports;
- 58,350 `litellm.x` calls;
- about 445 distinct `LITELLM_*` environment variables;
- about 180 `x-litellm-*` headers;
- 85 Prisma models, all named `LiteLLM_*`;
- three identical copies of `schema.prisma`.

**Runtime dependency on upstream.** `litellm/__init__.py` lines ~417–429 download four things at
startup. Three come from `raw.githubusercontent.com/BerriAI/litellm/main/`, and the fourth is the
LiteLLM blog RSS from `docs.litellm.ai`:

- `model_prices_and_context_window.json`, which holds **every price Token IQ uses**;
- `anthropic_beta_headers_config.json`;
- `autorouter_presets.json`.

Several files also reference `litellm.ai` or `berri.ai`. Find them with
`rg -l "litellm\.ai|berri\.ai" litellm`.

**Optional Rust bridge.** `litellm/rust_bridge/` checks `native_bridge_available()`. The build
backend is maturin only because of this bridge.

**Defects:**

- **41 Token IQ test files run in no CI job.** `.github/scripts/assert_ci_coverage.py` fails.
- **OpenAI line items stored as models.** `provider_billing/openai.py` lines 62–73 store the
  billing `line_item` in `model`.
- **Bedrock needs long-lived keys.** `provider_billing/bedrock.py` lines 120 and 171 require
  static access keys.

---

## 3. Ground rules for every phase

1. **Branches and commits.** One phase, one branch, one pull request. Commit in small steps
   with messages like `refactor(rename): …`, `chore(prune): …`, `docs: …`.
2. **Moves.** Use `git mv`, so history follows files. Create an `__init__.py` in every new
   Python package folder, including test folders.
3. **Rename by map, not by hand.** For anything bigger than a few files:
   - write the rename map to a CSV in `docs/plans/`;
   - show it for review;
   - apply it with a script (libcst for Python, ts-morph or jscodeshift for TypeScript, sed
     only for plain strings);
   - commit the script.
4. **Update every reference after a move or rename:**
   - imports;
   - `mock.patch` and `monkeypatch` strings;
   - `importlib` strings;
   - CI YAML, the Makefile, Dockerfiles, `pyproject.toml`, `pyrightconfig.json` and the ruff
     configs;
   - Helm and Terraform;
   - doc links;
   - comments that cite paths.
5. **Behaviour stays the same** except where a phase says otherwise. No new features during
   this work.
6. **Stop and ask when:**
   - a phase would delete a database column or table;
   - a phase would break a running installation's configuration;
   - a circular import cannot be resolved by the move itself.

   Report the evidence instead of working around it.
7. **Status updates.** After each phase, update `docs/status.md` (`PROJECT.md` before phase 1)
   with what changed and what was left, with reasons.

### Checks that every phase must pass

| Check | Command |
|---|---|
| Python tests for touched areas | `uv run pytest <paths> -q`, same result as the phase 0 baseline |
| CI coverage guard | `python .github/scripts/assert_ci_coverage.py` |
| Lint and types | `make lint` (or the repo's equivalent) |
| Proxy starts | start the proxy, call `/health/liveliness`, open the Overview page |
| UI | `npm run build && npx vitest run && npm run lint` in the dashboard folder |
| Image | `docker build .`, then the image starts |

---

## 4. Phase 0: baseline and inventory (no changes)

1. Run and record:
   - the Token IQ tests: `tests/test_litellm/{provider_billing,tool_usage,ledger,attribution,overview,seats,recommendations,repositories}`,
     `tests/test_litellm/proxy/{management_endpoints,auth,pass_through_endpoints,spend_tracking,db,credential_endpoints}`,
     `tests/deploy`;
   - the full unit suite once, as a reference;
   - `assert_ci_coverage.py`, which fails today;
   - lint;
   - the UI build and tests;
   - the Docker build.

   Note every test that already fails; those are not yours to fix.
2. Count names: `rg -i -c litellm --glob '!**/node_modules/**' | awk -F: '{s+=$2} END {print s}'`.
   Also count environment variables, headers and metrics. Use them to track progress.
3. Write `docs/plans/2026-10-04-feature-usage-inventory.md`, a table with one row per
   top-level folder in `litellm/` and `litellm/proxy/`. Columns:
   - what it does;
   - whether Token IQ uses it, with evidence: an import chain from a Token IQ module or from
     the proxy paths Token IQ serves, a config that enables it, or a UI page that calls it;
   - a proposal: keep, delete or unsure.

   This table drives phase 5. **Stop here for owner review.**

---

## 5. Phase 1: decisions, licence and documentation (docs only)

### Decision records

Add these to the new `docs/decisions/` folder:

- `0022-independent-codebase.md`: the hard fork. Why, what is lost (upstream provider fixes,
  price updates, security fixes) and how each is replaced (phase 2).
- `0023-remove-litellm-names.md`: the rename. Target names (section 1), the compatibility
  window (phase 7) and the licence exception.
- Update `0021-client-facing-rebrand.md` with a note at the top: "Superseded by 0022 and 0023."

### Licence

- Keep `LICENSE`. Remove the paragraph about the `enterprise/` directory, which no longer
  exists. Keep the MIT text and BerriAI's copyright line, and add
  `Copyright (c) 2026 NITCO Inc.`.
- Add the `NOTICE` file from section 1.

### Documentation moves

| From | To |
|---|---|
| `PROJECT.md` | `docs/status.md` |
| `project_usage/README.md` | `docs/decisions/README.md` (update links) |
| `project_usage/NN-slug.md` | `docs/decisions/00NN-slug.md` |
| `docs/superpowers/specs/2026-09-14-token-iq-product-design.md` and `2026-09-15-cost-platform-reference.md` | `docs/product/` |
| other `docs/superpowers/specs/*` | `docs/specs/` |
| `docs/superpowers/plans/*` | `docs/plans/` |
| `TOKEN_IQ_RESTRUCTURE.md` (this file) | `docs/plans/2026-10-04-independent-codebase.md` |
| the blueprint | `docs/product/token-iq-product-blueprint.html` |

### New and updated files

- **`docs/README.md`:** the documentation index (one paragraph per folder), plus a glossary.
  Glossary terms: observer-only, pass-through mode, virtual key, provider usage fact,
  evidence level (reconciled, priced, allocated), attribution, seat.
- **`docs/product/README.md`:** what the blueprint is, and how to read it (section 12 of this
  file).
- **`README.md`:** keep the current content. Remove "Built on LiteLLM" from the opening.
  Credit LiteLLM in an "Acknowledgements" line that points to `NOTICE`. Add a
  "Repository layout" section that describes the final layout from section 11 of this file.
- **`CLAUDE.md`:** rewrite for Token IQ. Keep the existing coding rules (comments, tests,
  mutation testing). Replace the upstream-specific parts with:
  - the observer-only rule;
  - the counting rule: the headline total is provider-billed cost, plus tool spend that is
    on no provider bill, plus seats; gateway cost is attribution and is never added;
  - where code lives;
  - the naming conventions;
  - "update `docs/status.md` at the end of every session".
- **`AGENTS.md` and `GEMINI.md`:** leave as is (they point to `CLAUDE.md`).

**Check:** `rg -n "project_usage/|docs/superpowers|PROJECT\.md" -g '!docs/plans/**' -g '!docs/decisions/**'`
returns nothing.

---

## 6. Phase 2: disconnect from upstream

Upstream LiteLLM did more for this codebase than supply code. It also kept data files current,
answered runtime downloads, hosted documentation the error messages link to, published the
Docker image the Helm chart pulls, and bumped dependencies. Every one of these needs a new
owner. The register below was measured on 3–4 Oct 2026. Re-run the searches in step 7 to
confirm it is complete.

### 6.1 Dependency register (what upstream provided, and what replaces it)

#### Downloaded from upstream at runtime

| # | What | Where | Replacement |
|---|---|---|---|
| R1 | **Model prices and context windows**: every price Token IQ uses | `litellm/__init__.py` `model_cost_map_url` → `raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json`; loader `litellm_core_utils/get_model_cost_map.py` | Token IQ price pipeline (6.2). The runtime reads only the bundled file. |
| R2 | **Anthropic beta-header config** (which beta headers each provider accepts) | `anthropic_beta_headers_url` → BerriAI raw GitHub; `anthropic_beta_headers_manager.py` | Bundled file, refreshed by the same daily job as prices (6.2), reviewed the same way |
| R3 | **Auto-router presets** | `autorouter_presets_url` → BerriAI raw GitHub | Delete with the auto-router (phase 5). Routing is outside observer-only (decisions 0001, 0011, 0012). |
| R4 | **LiteLLM blog RSS** shown in the UI | `blog_posts_url` → `docs.litellm.ai/blog/rss.xml`; `get_blog_posts.py`, `blog_posts.json` | Delete the feature and its UI panel. A "What's new" panel, if wanted, reads Token IQ's own `CHANGELOG.md`. |

#### Links that send users to LiteLLM

| # | What | Where | Replacement |
|---|---|---|---|
| L1 | Error and log messages that link users to LiteLLM docs or GitHub ("Add it here - github.com/BerriAI/…/model_prices…", "See https://docs.litellm.ai/…") | about 121 lines in 65 Python files (`rg -n "docs\.litellm\.ai\|github\.com/BerriAI" -g '*.py' litellm`), plus `proxy_cli.py` start-up banner | Rewrite each message to stand alone. Where a link helps, point to Token IQ documentation (`docs/` or the product docs site). For "model isn't mapped": "Model X has no price in Token IQ's price list. Add it in Pricing & Rates or ask your administrator." Code comments citing upstream issues: delete, or keep the explanation without the link. |
| L2 | UI links to LiteLLM docs and upsell pages | about 64 links to `docs.litellm.ai`; `www.litellm.ai/enterprise` (`create_key_button.tsx`), `www.litellm.ai/#pricing` (`PromptCompressionTab.tsx`), `models.litellm.ai/guardrails` (`CustomCodeModal.tsx`) | Remove upsells. Point help links at the in-product Documentation page. Delete pages removed in phase 5. |
| L3 | Generated API types with upstream example URLs | `ui/…/src/lib/http/schema.d.ts` (`litellm-production-7002.up.railway.app`) | Regenerate from Token IQ's OpenAPI after the docs strings are fixed. Never edit by hand. |

#### Images, packages and scripts

| # | What | Where | Replacement |
|---|---|---|---|
| I1 | Helm chart pulls **BerriAI's Docker image** | `helm/litellm-helm/values.yaml` (`ghcr.io/berriai/litellm`), its tests; `docker/README.md` | Point at Token IQ's own registry and images (built by `deploy/images/build.py`), or delete Helm if installations use only the AWS ECS and Terraform path chosen on 30 Sep. |
| I2 | Package metadata and workspace | `pyproject.toml` `Repository = "https://github.com/BerriAI/litellm"`, `authors`; `litellm-proxy-extras/pyproject.toml` (`authors = BerriAI`, description) | Token IQ metadata. Licence stays MIT, with the notice. |
| I3 | Install scripts that download from BerriAI | `scripts/install.sh`, `scripts/install-cli.sh`, the `curl … raw.githubusercontent.com/BerriAI/…/install.sh` hint in `proxy/client/cli/commands/autoroute/commands.py` | Delete. Token IQ is installed by `deploy/` (images and installations). |
| I4 | Scripts that serve upstream's own processes | `scripts/create_litellm_branch.{sh,ps1}`, `scripts/sync_together_ai_models.py`, `scripts/auto-close-duplicates*.ts`, `scripts/adaptive_router_demo`, `scripts/verify_adaptive_router.py` | Delete with their workflows. |

#### Data files that upstream kept current

Each of these needs a Token IQ owner, or deletion:

| # | File | Decision |
|---|---|---|
| D1 | `model_prices_and_context_window.json`, its `litellm/…_backup.json` copy, and the schema | Owned by the price pipeline (6.2) |
| D2 | `provider_endpoints_support.json` | Read by `proxy/public_endpoints/public_endpoints.py`. Keep it only if the public endpoints stay after phase 5, and trim it to supported providers. Otherwise delete it. |
| D3 | `policy_templates.json` (and `litellm/policy_templates_backup.json`) | Delete with guardrails and policy templates (phase 5), unless kept |
| D4 | `mcp_servers.json`, `router_plugins.json` | Delete (MCP and routing removed) |
| D5 | `whitelisted_bedrock_models.txt` | Keep if Bedrock tests use it; the owner is the Bedrock connector |
| D6 | `license_cache.json` (dependency licence check) | Keep. It is refreshed by the dependency update job (6.3). |
| D7 | `litellm/cost.json`, `litellm/blog_posts.json` | Delete both. `cost.json` is an unused leftover holding three 2023 prices; nothing reads it. `blog_posts.json` goes with R4. |

#### Processes upstream did for you

| # | What | Replacement |
|---|---|---|
| P1 | Dependency and base-image updates (`uv.lock`, `package-lock.json`, Chainguard image digests, GitHub Actions versions) | Renovate or Dependabot (6.3) |
| P2 | Security fixes | Watch upstream's security advisories (GitHub "Watch → Security alerts" on BerriAI/litellm, or the GitHub Advisory Database for the `litellm` package). For each advisory: check whether the affected code still exists in Token IQ, apply a fix, and record it in `CHANGELOG.md`. Keep `osv-scan`, `codeql`, `image-scan` and secret scanning in CI. |
| P3 | Provider API changes (new request fields, deprecations) | Contract tests per supported provider (`tests/token_iq/connectors/*/contract`, plus the gateway's provider tests). A monthly check of each supported provider's changelog is assigned to a named person. |

### 6.2 The price pipeline

The goal: prices are current within a day, every change is traceable, and past months can be
re-priced at the prices of that time.

1. **Source.** Upstream's public file stays the source of new models and price changes. It is
   MIT-licensed and covered by `NOTICE`. It is fetched only by the update job, never by
   running installations.
2. **Bundled file.**
   - Location: `data/pricing/model_prices.json`. In phase 6 it moves to wherever the engine
     package expects it; keep one copy.
   - Contents: only the providers Token IQ supports (after phase 5), plus Token IQ's own
     additions.
   - The runtime loader reads this file only. Remove the remote URL and the
     `LITELLM_LOCAL_MODEL_COST_MAP` switch, because local is now the only mode.
3. **Price history.**
   - Every accepted change is appended to `data/pricing/price_history.jsonl`. Each line holds
     `model`, `provider`, `field`, `old`, `new`, `effective_from`, `source` (upstream commit
     or "manual") and `approved_by`.
   - At startup, the history loads into a `ModelPriceHistory` table.
   - The ledger, Savings Simulator and any re-pricing of a past period look up the price in
     effect on each day. The live gateway uses the current price.
   - Contracted discounts from Pricing & Rates still apply on top.
4. **Daily update job.** `scripts/update_model_prices.py` runs in
   `.github/workflows/update-model-prices.yml` and opens a pull request. It:
   1. fetches upstream's file;
   2. filters to supported providers;
   3. validates the schema;
   4. sorts the differences into three kinds:

      | Kind | Example | Handling |
      |---|---|---|
      | **Additions** | a new model | **Auto-merge** when the tests pass |
      | **Changes** | a price or context window changed | **Needs review** by a named price owner. Flag any change above 50%, any change to zero, and any change to a model seen in the last 30 days of a production installation's traffic (a list exported to `data/pricing/models_in_use.txt`). |
      | **Removals** | a model retired upstream | **Needs review.** Never delete a price that history still needs; mark it retired. |

   Run the price tests. Write the history lines into the pull request.
5. **Emergency path.** `scripts/update_model_prices.py --model <name>` updates one model
   immediately through the same review.
6. **Bills check the prices.** Invoice Reconciliation already compares gateway-priced cost
   with provider-billed cost. Add a rule: when one model's variance is consistently above 2%
   for 7 days, raise an alert that its list price may be wrong, linking to the price entry.
   The product then catches the price errors that review misses.
7. **Tests.** Cover:
   - the loader never makes a network call (block sockets in the test);
   - history lookups return the price in effect on a given date;
   - the update script classifies additions, changes and removals correctly on fixture
     files.

Do the same for the Anthropic beta-header config (R2): the same job, a separate file, and
review of every change.

### 6.3 Steps

1. **Git.** Remove any `upstream` remote. The repository owner does the GitHub settings:
   - make `litellm_token_iq` the default branch (or fast-forward `main` to it) and protect it;
   - optionally rename the repository to `token-iq`. GitHub keeps redirects.
2. **Workflows.** In `.github/workflows/`, delete those that serve BerriAI's public project:
   - issue triage and labels: `auto-close-duplicates`, `check_duplicate_issues`,
     `close_low_quality_prs`, `issue-keyword-labeler`, `label-component`, `stale`,
     `triage_issue_with_llm`, `triage_reconsider`;
   - branch and model upkeep: `create_daily_oss_agent_shin_branch`,
     `create_daily_staging_branch`, `sync-together-ai-models`, `weekly_load_anomaly`;
   - release and publishing: `create-release*`, `report-rust-release-wheel`,
     `publish-basedpyright-base-counts`, `auto_update_price_and_context_window` (replaced by
     6.2);
   - any workflow publishing to PyPI or BerriAI's registries.

   Keep the test, lint, security-scan and image-build workflows. Update
   `.github/ci-coverage-allowlist.yml`, and the CircleCI config if it references deleted
   files. Delete `.circleci/` if CI runs only on GitHub Actions; check first.
3. **Runtime downloads R1–R4.** Build the price pipeline (6.2). Bundle R2. Delete R3 and R4.
4. **Links L1–L3.** Rewrite the messages, remove the upsells, regenerate the API types.
5. **Images, packages and scripts I1–I4; data files D1–D7.** Act on each row above.
6. **Dependency updates P1.** Add `renovate.json`, or `.github/dependabot.yml`, covering:
   - `uv.lock` / `pyproject.toml`;
   - `ui/…/package-lock.json`;
   - Dockerfile base-image digests (Chainguard, uv, node);
   - GitHub Actions.

   Group minor updates weekly. Security updates go immediately. Name the owners of P2 and P3
   in `docs/status.md`.
7. **Prove nothing is left.** Each search must return nothing outside history docs and the
   allowed files:

   ```bash
   rg -n "raw\.githubusercontent\.com/BerriAI|github\.com/BerriAI|ghcr\.io/berriai|docs\.litellm\.ai|www\.litellm\.ai|models\.litellm\.ai|litellm\.ai|berri\.ai|railway\.app" \
      -g '!docs/decisions/**' -g '!docs/plans/**' -g '!CHANGELOG.md' -g '!LICENSE' -g '!NOTICE' \
      -g '!scripts/update_model_prices.py' -g '!.github/workflows/update-model-prices.yml'
   ```

**Check:**

- With outbound network blocked except to the configured providers, the proxy starts,
  prices load from the bundled file, and no request leaves for any other host. Check this
  with a socket-blocking test, and in a container started with `--network` restricted.
- The price update job runs once in dry-run mode and produces a correct pull request against
  a fixture.

## 7. Phase 3: one package for Token IQ's own modules

Create `token_iq/` at the root, with an `__init__.py` in every folder. Move with `git mv`:

| From | To |
|---|---|
| `litellm/provider_billing/` (16 files) | `token_iq/connectors/billing/` (same names) |
| `litellm/tool_usage/` (10) | `token_iq/connectors/tools/` (same names) |
| `litellm/ledger/`, `attribution/`, `overview/`, `seats/` | `token_iq/ledger/`, `attribution/`, `overview/`, `seats/` |
| `litellm/recommendations/` (with `rules/`) | `token_iq/recommendations/` |
| 11 files in `litellm/repositories/` (see below) | `token_iq/repositories/` |
| `litellm/proxy/management_endpoints/` Token IQ routers (see below) | `token_iq/api/` |
| `litellm/proxy/auth/courier_model_names.py` | `token_iq/proxy/courier_model_names.py` |
| `litellm/proxy/auth/team_api_access.py` | `token_iq/proxy/team_api_access.py` |
| `litellm/proxy/credential_endpoints/credential_access.py` | `token_iq/proxy/credential_access.py` |
| `litellm/proxy/db/spend_log_retention.py` | `token_iq/proxy/spend_log_retention.py` |
| `litellm/proxy/pass_through_endpoints/same_target_retry.py` | `token_iq/proxy/same_target_retry.py` |
| `litellm/proxy/spend_tracking/capture_policy.py` | `token_iq/proxy/capture_policy.py` |
| `litellm/proxy/auth/token_iq_plan.py` | `token_iq/plan.py` |
| `litellm/types/proxy/{attribution,invoice,provider_billing,recommendation,seat,team_api_access,tool_usage}.py` | `token_iq/types/` (same names) |
| `litellm/types/proxy/management_endpoints/{attribution,combined,ledger,overview,recommendation,seat,tool}_endpoints.py` | `token_iq/types/api/{attribution,combined,ledger,overview,recommendations,seats,tools}.py` |

**Repositories (11 files):**

- `attribution_rule_repository.py`
- `gap_repository.py`
- `gateway_spend_repository.py`
- `invoice_repository.py`
- `ledger_repository.py`
- `overview_repository.py`
- `provider_sync_run_repository.py`
- `provider_usage_fact_repository.py`
- `recommendation_state_repository.py`
- `seat_repository.py`
- `tool_usage_fact_repository.py`

**Routers (from `litellm/proxy/management_endpoints/` into `token_iq/api/`):**

| From | To |
|---|---|
| `attribution.py` | `attribution.py` |
| `audit_log_endpoints.py` | `audit_log.py` |
| `audit_log_diff.py` | `audit_log_diff.py` |
| `combined_usage.py` | `combined_usage.py` |
| `courier_coverage.py` | `courier_coverage.py` |
| `ledger.py` | `ledger.py` |
| `model_discovery.py` | `model_discovery.py` |
| `overview.py` | `overview.py` |
| `project_endpoints.py` | `projects.py` |
| `provider_connections.py` | `provider_connections.py` |
| `provider_overview.py` | `provider_overview.py` |
| `provider_reconciliation.py` | `provider_reconciliation.py` |
| `provider_usage.py` | `provider_usage.py` |
| `recommendations.py` | `recommendations.py` |
| `seats.py` | `seats.py` |
| `tool_connections.py` | `tool_connections.py` |

### Update the importers

11 upstream files import moved modules (about 38 import lines):

- `litellm/proxy/proxy_server.py`, at about these lines:

  | Line (approx.) | Old module | New module |
  |---|---|---|
  | 273 | `token_iq_plan` | `token_iq.plan` |
  | 503–505 | `provider_billing` startup | `token_iq.connectors.billing` |
  | 506–563 | the routers | `token_iq.api.*` |
  | 9338, 9341 | lazy `spend_log_retention` | `token_iq.proxy.spend_log_retention` |
  | ~13867 | lazy `provider_overview` | `token_iq.api.provider_overview` |

- `litellm/proxy/_types.py`
- `litellm/proxy/auth/auth_checks.py`
- `litellm/models/team.py`
- `litellm/proxy/management_endpoints/team_endpoints.py`
- `litellm/proxy/management_endpoints/key_management_endpoints.py`
- `litellm/proxy/management_endpoints/model_management_endpoints.py`
- `litellm/proxy/pass_through_endpoints/pass_through_endpoints.py`
- `litellm/proxy/credential_endpoints/endpoints.py`
- `litellm/proxy/spend_tracking/spend_tracking_utils.py`
- `litellm/types/proxy/management_endpoints/team_endpoints.py`

Then update the 76 test and script files (73 `mock.patch` strings).

If `token_iq/types/team_api_access.py` imports from `litellm.proxy._types`, the move creates a
cycle. In that case, leave that one file in place, note it in `docs/status.md`, and phase 6
resolves it.

### Packaging and tools

- **Packaging:** add `python-packages = ["token_iq"]` under `[tool.maturin]`, or switch the
  build backend if phase 5 removes Rust. Confirm `import token_iq` works in a non-editable
  install and in the Docker image.
- **Tools:** add `token_iq` to `pyrightconfig.json` `include`, to the Makefile lint and
  format targets, to the `'litellm/**/*.py'` filters and `cd litellm` steps in
  `.github/workflows/test-linting.yml`, and to the circular-import test.

### Check

`rg -n -g '!docs/**' -g '!*.md' -g '!litellm/proxy/_experimental/**' "litellm[./](provider_billing|tool_usage|ledger|attribution|overview|seats|recommendations)\b"`
returns nothing. Repeat the check for each other moved path.

---

## 8. Phase 4: tests mirror the package, and CI runs them

Create `tests/token_iq/__init__.py` and an `__init__.py` in every subfolder.

### Moves

| From | To |
|---|---|
| `tests/test_litellm/provider_billing/` (with `contract/`) | `tests/token_iq/connectors/billing/`; rename `test_<provider>_connector.py` → `test_<provider>.py` |
| `tests/test_litellm/tool_usage/` (with `contract/`) | `tests/token_iq/connectors/tools/` |
| `tests/test_litellm/{ledger,attribution,overview,seats,recommendations}/` | `tests/token_iq/{same}/` |
| the 10 Token IQ files in `tests/test_litellm/repositories/` | `tests/token_iq/repositories/` |
| `tests/test_litellm/types/proxy/test_provider_billing.py` | `tests/token_iq/types/` |
| `tests/deploy/` | `tests/token_iq/deploy/` |
| `tests/test_litellm/proxy/auth/test_token_iq_plan.py` | `tests/token_iq/test_plan.py` |
| 18 Token IQ files in `tests/test_litellm/proxy/management_endpoints/` | `tests/token_iq/api/` (see below) |
| the five hook tests | `tests/token_iq/proxy/` (see below) |

**Repository tests (10 files):** attribution_rule, gap, gateway_spend, invoice, ledger,
provider_sync_run, provider_usage_fact, recommendation_state, seat, tool_usage_fact.

**Deploy tests:** in `tests/token_iq/deploy/`, change `REPO = Path(__file__).resolve().parents[2]`
to `parents[3]`.

**API tests (18 files):**

- `test_attribution`
- `test_audit_log_diff`
- `test_audit_log_endpoints` → `test_audit_log`
- `test_combined_usage`
- `test_courier_coverage`
- `test_team_courier_coverage`
- `test_daily_reconciliation`
- `test_ledger`
- `test_model_discovery`
- `test_overview`
- `test_project_endpoints` → `test_projects`
- `test_provider_connections`
- `test_provider_overview`
- `test_provider_reconciliation`
- `test_provider_usage`
- `test_recommendations`
- `test_seats`
- `test_tool_connections`

**Hook tests (5 files):**

- `proxy/auth/test_team_api_access.py`
- `proxy/credential_endpoints/test_credential_access.py`
- `proxy/db/test_spend_log_retention.py`
- `proxy/pass_through_endpoints/test_same_target_retry.py`
- `proxy/spend_tracking/test_capture_policy.py`

### Shared test hooks and fixtures

Fixtures and hook functions are found by name in a conftest, so re-export them.

- **`tests/token_iq/conftest.py`:** re-export every fixture from
  `tests/test_litellm/conftest.py`, including the autouse isolation fixtures.
- **`tests/token_iq/api/conftest.py` and `tests/token_iq/proxy/conftest.py`:** re-export
  everything from `tests/test_litellm/proxy/conftest.py`, including the
  `pytest_runtest_setup` / `pytest_runtest_teardown` hook pair and
  `_reset_graceful_shutdown_state`. Underscore names need an explicit import.
- **`proxy/` only:** also re-export `tests/test_litellm/proxy/db/conftest.py`.

Phase 6 renames these source paths along with the rest.

### CI

Add a `token-iq` shard to `.github/workflows/test-unit.yml`, copying an existing shard's
fields:

```yaml
          - shard: token-iq
            artifact-name: token-iq
            test-path: "tests/token_iq"
            workers: 2
            reruns: 1
            timeout-minutes: 20
            job-timeout-minutes: 60
```

**Check:**

- `assert_ci_coverage.py` exits 0.
- `pytest tests/token_iq` passes with and without `-n 4`, same as the baseline.

---

## 9. Phase 5: delete what Token IQ does not use

Do this only after the owner has approved the inventory from phase 0.

### Probably keep (verify with the inventory)

- the proxy server, auth, virtual keys, teams, users, organizations, budgets, rate limits and
  spend tracking;
- pass-through endpoints;
- the OpenAI-compatible endpoint;
- secret managers in use (AWS);
- the Prisma client and migrations;
- the admin UI pages that Token IQ shows;
- the provider transformations for the providers Token IQ supports. These are the providers
  on the Providers page and in customer configs: at least OpenAI, Azure OpenAI and Azure AI,
  Anthropic, Bedrock, Vertex AI and Gemini, and OpenRouter. Confirm the list with the owner.

### Probably delete (verify with the inventory)

- **Routing, already removed or switched off by decisions 0001–0005 and 0012:**
  `router_strategy/`, the router's load-balancing, fallback and cooldown code, and response
  caching.
- **Upstream features Token IQ does not use:**
  - agents and A2A (`a2a_protocol/`, agent endpoints);
  - MCP (`experimental_mcp_client/`, MCP server endpoints and UI);
  - guardrails and the policy engine (unless used);
  - RAG and vector stores;
  - skills, prompts management and evals;
  - realtime, video, image, OCR, search and rerank APIs;
  - fine-tuning, sandbox, compression;
  - provider folders in `litellm/llms/` for providers not supported;
  - playgrounds, auto-router presets.
- **Other folders and files:**
  - `cookbook/`, `examples/`;
  - the root `gateway/` and `backend/` (upstream route-trimming entrypoints; delete unless a
    deployment uses them);
  - `render.yaml`, `qa_sticky_session.sh`, `cosign.pub` (if not used for your own image
    signing);
  - `terraform/litellm/`, `terraform/provider/`;
  - upstream docs, upstream Helm values Token IQ does not deploy.
- **Rust:** `litellm-rust/` and `litellm/rust_bridge/`. The bridge is optional
  (`native_bridge_available()`). If it goes, switch the build backend from maturin to
  hatchling (`[build-system] requires = ["hatchling"]`, packages `token_iq`, and the engine
  package until phase 6 renames it). Remove the Rust CI.

### How to delete

Delete one feature at a time, each in its own commit:

1. Delete the code, its tests, its UI pages and navigation entries, its config keys and its
   docs.
2. Run the import check: `python -c "import litellm.proxy.proxy_server"`, or start the proxy.
3. Run the remaining tests.

If something still imports a deleted module, keep the feature and record why. Never delete a
Prisma model or migration in this phase. Unused tables are handled in phase 8.

**Check:** all phase checks pass. Record the file-count reduction in `docs/status.md`.

---

## 10. Phases 6–10: remove the LiteLLM name

### Phase 6: rename the engine package

Build `docs/plans/rename-map.csv` with columns `kind, old, new, files`, and get it reviewed
first. Rules:

- **Package:** `litellm` → `token_iq.gateway`, by moving the folder to `token_iq/gateway/`.
  - Subpackages keep their names: `litellm.proxy` → `token_iq.gateway.proxy`.
  - Drop the redundant prefix: `litellm_core_utils` → `core_utils`.
- **Module-level use:**
  - `import litellm` → `from token_iq import gateway`;
  - `litellm.<attr>` → `gateway.<attr>`;
  - `from litellm.x import y` → `from token_iq.gateway.x import y`.

  Where the name `gateway` is already bound in a module, use `tiq_gateway`, and list those
  files in the map.
- **Identifiers containing the name:** `LiteLLM`, `Litellm`, `litellm`, `LITELLM` become
  `Gateway`, `Gateway`, `gateway`, `GATEWAY`. For example `LiteLLMRoutes` → `GatewayRoutes`
  and `litellm_logging` → `gateway_logging`.
  - Special cases: `litellm_params` → `model_params`, `litellm_settings` →
    `gateway_settings`.
  - Resolve collisions by hand, and list them.
- **Strings:** user-visible text says "Token IQ"; logger names and internal strings use
  `token_iq`.
  - Do **not** change env-var names, config keys, headers, metric names, Redis keys or
    database names in this phase. They follow in phases 7–9.
  - Leave strings that are an external provider's API field names, for example a provider
    response field that happens to say litellm. Check each one.
- **Tests:** `tests/test_litellm/` → `tests/gateway/`, mirroring `token_iq/gateway/`.
  - Update conftest re-exports, CI shards and `SHARDED_ROOTS` in
    `.github/scripts/assert_ci_coverage.py`.
  - Update the test-quality and type budgets (`*-budget.json`, which key on paths).
- **Packaging:**
  - In `pyproject.toml`: `name = "token-iq"`; scripts `token-iq = "token_iq.gateway:run_server"`
    and `token-iq-cli = "token_iq.gateway.proxy.client.cli:cli"`.
  - Remove the old `litellm`, `lite` and `litellm-proxy` scripts.
  - Packages: `token_iq` only.
  - Update the Dockerfile and `docker/*entrypoint*.sh`, which call `litellm` and copy
    `litellm/proxy/...` paths.
  - Move the bundled UI path `litellm/proxy/_experimental/out` to
    `token_iq/gateway/proxy/ui_bundle/`, and update the code that serves it and the
    Dockerfile.
- Apply with libcst in one scripted pass, then fix what remains by hand. Commit the codemod
  script.

**Check:**

- `rg -n "\blitellm\b" --type py` matches only env-var, config, header, metric, Redis and
  database names (phases 7–9).
- All checks pass.

### Phase 7: compatibility for one transition release

Customers' running configuration must keep working on upgrade. Create **one** module,
`token_iq/gateway/compat.py`. It is the only Python file allowed to contain the old names,
and it is deleted in the release after next.

| Area | New name is read first | Old name still accepted | Warning |
|---|---|---|---|
| Environment variables | `TOKEN_IQ_<X>` | `LITELLM_<X>` | logs a deprecation warning once per name |
| Config keys (`config.yaml` and the config stored in the database) | `gateway_settings`, `model_params` | `litellm_settings`, `litellm_params` (old names are written back as new on the next save) | yes |
| Request headers | `x-token-iq-*` | `x-litellm-*` | only the new names are sent in responses |

- **Environment variables:** route every lookup through one helper. Replace about 445 direct
  `os.getenv("LITELLM_…")` and `os.environ` uses.
- **API JSON:** the dashboard and API return the new key names. Update the UI in the same pull
  request. List each changed field in `CHANGELOG.md`.

Then rename in deployment files: `.env.example`, `docker-compose*.yml`, Helm values,
`deploy/installations/` manifests, Terraform variables and `docs/`.

Add `CHANGELOG.md` with an "Upgrading" section that lists every renamed variable, key and
header. Generate the list from the rename map.

**Check:**

- A test starts the proxy with an old-style `.env` and `config.yaml` and confirms it works and
  warns.
- A second test does the same with the new names.

### Phase 8: database names

Do this in two steps, in two releases.

**Step 1 (this phase): code names only, no data change.**

- In all three `schema.prisma` copies, rename the models: `LiteLLM_TeamTable` → `TeamTable`,
  and so on for all 85.
- Add `@@map("LiteLLM_TeamTable")` (and `@map` for any field whose name is renamed) so the
  real tables are untouched. `check-schema-sync.yml` must still pass.
- Update every Prisma accessor (`prisma_client.db.litellm_teamtable` → `.teamtable`) and every
  raw SQL string that names a table, with the codemod.
- Rename the migrations package: `litellm-proxy-extras` → `token-iq-migrations`, Python
  package `token_iq_migrations`. Update the migration runner (`ci_cd/run_migration.py`,
  `litellm/proxy/prisma_migration.py`) and the Dockerfile `COPY` lines.
- **Do not rename existing migration folders.** Prisma tracks them by name in
  `_prisma_migrations`.

**Step 2 (separate release, after a backup): real table names.**

- Add one migration that renames each table to snake_case (`ALTER TABLE "LiteLLM_TeamTable" RENAME TO "team_table"`),
  along with its indexes, constraints and sequences. Then remove the `@@map` lines.
- Write `docs/runbooks/rename-tables.md`, covering backup, maintenance window and rollback
  (rename back).
- Test on a copy of a real installation's database first.
- Ask the owner before merging.

### Phase 9: everything else that shows the name

- **Prometheus metrics:** `litellm_*` → `token_iq_*`. This breaks existing dashboards and
  alerts, so list them in `CHANGELOG.md` and update any dashboards in the repo.
- **Redis and cache key prefixes** → `token_iq`. In-flight cache entries are lost on upgrade,
  which is harmless for caches. Any spend or rate-limit counters held in Redis must be flushed
  to the database before upgrading; say so in the upgrade notes.
- **Logs:** logger names, OpenTelemetry service names and span attributes. Keep `gen_ai.*`
  standard attributes as they are.
- **UI:**
  - folder `ui/litellm-dashboard/` → `ui/dashboard/`, and the `package.json` name;
  - every visible string;
  - Token IQ pages in an `app/(dashboard)/(token-iq)/` route group, which keeps URLs;
  - Token IQ hooks, components and lib in `src/token-iq/`.

  Move a folder whole only when all its files are Token IQ's. For example, `projects/` has
  only 4 of 28 files that are Token IQ's.
- **Docker, Helm, Terraform:** image and chart names `token-iq…`.
  `terraform/tokeniq/installation` → `deploy/terraform/installation`.
- **Scripts:** `run-proxy.ps1` → `scripts/dev/run-proxy.ps1`. Fix
  `$repo = (Resolve-Path "$PSScriptRoot\..\..").Path`.
- **Navigation labels:** match the blueprint, using the label table in section 12.

### Phase 10: keep it clean

- Add `tests/repo/test_no_litellm_name.py`. It fails if `litellm` (any case) appears anywhere
  in the repository except:
  - `LICENSE`, `NOTICE` and `CHANGELOG.md`;
  - `docs/decisions/`;
  - `docs/plans/`, which is historical;
  - `token_iq/gateway/compat.py` and its test, until the compatibility release ends;
  - the upstream price-update script and workflow, which name the upstream source.

  Run it in CI.
- In the release after the transition release, delete `compat.py` and its test, remove those
  allowlist entries, and ship step 2 of phase 8.
- Generalise the existing branding gates (`check_openapi_docs_do_not_name_litellm.py`,
  `check_customer_messages_do_not_name_litellm.py`) into this one test, then delete them.

### Fixes to make along the way (separate PRs, each with a regression test that fails first)

1. **OpenAI line items:** split `line_item` into model and meter, for example
   "gpt-4.1-2025-04-14, input" → model `gpt-4.1-2025-04-14`, meter `input`. Items with no
   model get model `None` and meter set to the item text. Keep existing `fact_key`s stable.
2. **Bedrock:** add IAM role plus external ID (STS AssumeRole) as the recommended method.
   Keep access keys as "not recommended".

---

## 11. Final layout

```text
token-iq/   (repository)
├─ README.md            what Token IQ is, quick start, repository layout
├─ CHANGELOG.md         releases and upgrade notes (renamed settings)
├─ LICENSE  NOTICE      MIT terms; attribution to LiteLLM (legal requirement)
├─ CLAUDE.md            rules for coding agents
├─ token_iq/
│  ├─ gateway/          the engine: provider translation, proxy, auth, keys, spend tracking
│  ├─ api/              Token IQ product API routers
│  ├─ connectors/       billing/ (providers) and tools/ (Claude Code, Copilot, Cursor)
│  ├─ ledger/  attribution/  overview/  seats/  recommendations/
│  ├─ repositories/     database access for Token IQ tables
│  ├─ proxy/            Token IQ hooks inside the gateway
│  ├─ types/            data types and API schemas
│  └─ plan.py
├─ token_iq_migrations/ Prisma migrations package (was litellm-proxy-extras)
├─ schema.prisma        (plus the two synced copies Prisma needs)
├─ tests/
│  ├─ token_iq/         product tests
│  ├─ gateway/          engine tests (was test_litellm)
│  └─ repo/             repository-wide checks (no-litellm-name gate)
├─ ui/dashboard/        the admin and product UI
├─ deploy/              images/, installations/, terraform/, helm/
├─ docs/                README, status.md, product/, decisions/, specs/, plans/, runbooks/
├─ scripts/             dev/, update_model_prices.py, quality gates
└─ pyproject.toml  Makefile  Dockerfile
```

---

## 12. Using the blueprint for product changes (after phase 4)

The blueprint (`docs/product/token-iq-product-blueprint.html`) is a single HTML page. Read it
as a specification, not as code.

### Where things are

- **Section 02 (`id="structure"`):** every page, its tabs and what is deliberately not on it.
- **Section 04 (`id="roles"`):** the eight roles, what a Team Lead sees, and the Manage vs
  Read-only table.
- **Section 05 (`id="helpsys"`):** page guides, the two-tab setup dialogs and naming rules.
- **Section 06 (`id="sources"`):** how each account connects.
- **Sections 07–08:** the recommendations engine and the Savings Simulator.
- **Sections 12–13:** what is missing, and the build order.

### The machine-readable model

In the `<script>` that starts with `/* Token IQ v7 page model`:

- **`window.TIQ_PAGES`:** each page's key, group, name, `acc` (access per role: `e` manage,
  `v` view, `t` own team, `r` own team read-only, `o` own data, `n` hidden), tabs, actions,
  help text and suggested assistant questions. Team Lead versions are under `lead`.
- **`window.TIQ_MATRIX` and `TIQ_MROLES`:** the permission matrix for all eight roles.
- **`window.TIQ_MODALS`:** every setup dialog, with each field's label, type, options,
  explanation, example and whether it is required. `connect.variants` holds the fields for
  each account type, including Custom source.

### Rules

- The figures in the mockup are example data. Never hard-code them.
- Build pages to match the blueprint's names, tabs and role rules. Use the existing UI
  component library, not the mockup's CSS.
- Follow section 13's build order. Phase 9's navigation labels map like this:

| Today | Blueprint |
|---|---|
| Usage | Analytics › Cost Explorer |
| Ledger | Analytics › Invoice Reconciliation |
| Recommendations | Optimization › Recommendations |
| Attribution Rules | Administration › Cost Allocation |
| Provider APIs, User Tools, LLM Provider Credentials, Providers, Models + Endpoints, Virtual Keys, Logs | Data › Data Sources (Overview, Accounts, Gateway, Uploads) |
| Budgets | Governance › Budgets & Forecasts |
| Teams, Projects | Administration › Organization |
| Users, Access Groups, Audit log | Administration › Access Control |
| Cost Tracking | Administration › Pricing & Rates |
| Admin Settings, Logging & Alerts, UI Theme | Administration › Settings |

---

## 13. Definition of done

- [ ] Decision records 0022 and 0023 are written; `LICENSE` and `NOTICE` meet the MIT
      attribution requirement.
- [ ] Every row of the dependency register (6.1) is closed. The 6.3 search returns nothing,
      and no runtime call leaves for upstream.
- [ ] Prices load from the bundled file. The daily update job opens pull requests, additions
      auto-merge, and changes are reviewed. Past periods re-price from `price_history`.
- [ ] Renovate or Dependabot is active. Owners for security advisories (P2) and provider API
      changes (P3) are named in `docs/status.md`.
- [ ] Unused upstream features are deleted, as approved in the inventory.
- [ ] `tests/repo/test_no_litellm_name.py` passes in CI, and the allowlist is as small as
      section 10 says.
- [ ] An installation configured with old `LITELLM_*` names upgrades and keeps working, with
      warnings. `CHANGELOG.md` lists every rename.
- [ ] `assert_ci_coverage.py` passes. The Token IQ and gateway tests match the baseline.
- [ ] The Docker image builds and starts; the Overview page loads; a request through the
      gateway is recorded.
- [ ] `docs/status.md` records what was done, what was deferred (for example step 2 of
      phase 8) and why.
