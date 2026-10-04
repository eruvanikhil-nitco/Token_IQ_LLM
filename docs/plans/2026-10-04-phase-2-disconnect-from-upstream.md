# Phase 2: disconnect from upstream

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Token IQ stops depending on BerriAI for anything at runtime, at build time or as a
process, and every one of those dependencies has a named owner here instead.

**Architecture:** Upstream supplied four things beyond source code: files downloaded at
startup, documentation the error messages link to, images and packages, and processes nobody
wrote down. Each is replaced or deleted deliberately, and the phase ends by proving with a
blocked network that nothing is left.

**Tech Stack:** Python 3.12, pytest, GitHub Actions, Renovate or Dependabot.

**Spec:** `docs/specs/2026-10-04-token-iq-independent-codebase.md`, section 5.2

## The rule this phase must not break

**A stale price does not fail. It silently makes every figure in the product wrong.**

`model_prices_and_context_window.json` holds 3,560 models and is downloaded from BerriAI at
startup today. It is the input to every cost this product reports. If it stops updating,
nothing crashes, no test goes red, and no alert fires: the ledger keeps reconciling, the
Overview keeps showing a total, and all of it is quietly incorrect for any model whose price
moved.

That is why the price pipeline is the largest task here and why it has three independent
defences rather than one. The file is bundled and read locally, so a network failure cannot
make it stale without anybody noticing. A daily job proposes upstream's changes as a pull
request, so staleness becomes a visible queue rather than silence. And the product checks its
own prices against real bills, so a wrong price surfaces as a reconciliation variance even if
review missed it.

## Facts measured on 4 Oct 2026, where they differ from the source document

| What | Document says | Measured |
|---|---|---|
| L1, Python files linking upstream, in `litellm/` | about 65 files, 121 lines | **127 files, 283 lines** |
| L1, the same in `tests/` | not mentioned | **211 files** |
| L2, UI links to `docs.litellm.ai` | about 64 | **83** |
| Models in the price file | not stated | **3,560, 2.1 MB** |
| Workflows named for deletion | about 20 | **17 of them exist**, out of 50 total |

The tests were the omission worth catching. 211 test files carry those URLs. Most are issue
links in comments and some are deliberate fixture data, such as a search test whose fake
results happen to be LiteLLM pages, but any test asserting on the text of a message this
phase rewrites will fail. Each rewritten message is checked against its tests rather than
assumed independent.

## Global Constraints

- The runtime makes no network call to any BerriAI host. Proven by a socket-blocking test
  and by a container run with restricted networking, not by reading the code
- No price is ever deleted while price history still needs it. Retired, never removed
- Deleting a feature deletes its tests, its config keys, its UI and its docs in the same
  commit
- One feature per commit, so any single removal can be reverted alone
- The upstream price file stays the *source* of new models. It is MIT licensed and covered
  by `NOTICE`. Only the update job fetches it, never a running installation
- Python line length 120, no `Any`, `: Final` on variables, immutable collections
- Tests check behaviour and must fail when the behaviour is mutated

---

## Task 1: Prices load from a bundled file, and the runtime cannot reach the network

**Files:**
- Create: `data/pricing/model_prices.json`, `data/pricing/price_history.jsonl`
- Modify: `litellm/litellm_core_utils/get_model_cost_map.py`, `litellm/__init__.py`
- Create: `tests/token_iq/pricing/test_price_loader.py`

- [ ] **Step 1: Write the failing tests**

The one that matters most blocks sockets for the whole test and then loads prices. If the
loader can still reach out, that test fails. Everything else here is detail beside it.

Also: a model absent from the bundled file is reported as having no price rather than
defaulting to zero, because a zero price turns a real cost into free usage and nothing
downstream can tell the difference.

- [ ] **Step 2: Bundle the file and make the loader local-only**

Move the file to `data/pricing/model_prices.json`. Remove the remote URL and the
`LITELLM_LOCAL_MODEL_COST_MAP` switch, which has no meaning once local is the only mode.
Keep one copy: there is a `_backup.json` beside it today, and two files that must agree is a
bug waiting to happen.

- [ ] **Step 3: Prove it with the network down**

Run the proxy in a container with outbound traffic blocked except to configured providers.
It starts, prices load, nothing is attempted against `raw.githubusercontent.com`.

- [ ] **Step 4: Commit**

---

## Task 2: Price history, so a past month can be re-priced at the prices of that month

**Files:**
- Create: `litellm/pricing/history.py`, the `ModelPriceHistory` table
- Create: `tests/token_iq/pricing/test_price_history.py`

- [ ] **Step 1: Write the failing tests**

A lookup for a date returns the price in effect on that date, not the current one. A model
whose price changed twice returns the right one for each period. A model with no history
entry falls back to the bundled price rather than to nothing.

This is what makes the Savings Simulator and any re-pricing of a closed month honest. Without
it, re-running last quarter silently values it at today's prices.

- [ ] **Step 2: Build it**

Append-only `price_history.jsonl`, one line per accepted change, holding model, provider,
field, old, new, `effective_from`, source and `approved_by`. Loaded into the table at
startup. The live gateway uses the current price; the ledger and any re-pricing look up the
price in effect on the day.

- [ ] **Step 3: Commit**

---

## Task 3: The daily update job

**Files:**
- Create: `scripts/update_model_prices.py`,
  `.github/workflows/update-model-prices.yml`
- Create: `tests/token_iq/pricing/test_price_update.py`

- [ ] **Step 1: Write the failing tests**

Against fixture files, so the tests do not depend on what upstream published today: an added
model is classified as an addition, a changed price as a change, a removed model as a
removal. A change above 50%, a change to zero, and a change to a model in
`data/pricing/models_in_use.txt` are each flagged for review regardless of size.

- [ ] **Step 2: Build it**

Fetch, filter to supported providers, validate the schema, classify into additions, changes
and removals. Additions auto-merge when tests pass. Changes need the named price owner.
Removals are marked retired, never deleted. The history lines go into the pull request so the
reviewer sees exactly what would be recorded.

`--model <name>` updates one model immediately through the same review, for the case where a
price is wrong and waiting a day is not acceptable.

- [ ] **Step 3: Dry-run it against a fixture and read the pull request it produces**

- [ ] **Step 4: Commit**

---

## Task 4: The product checks its own prices

**Files:**
- Modify: the reconciliation rules
- Create: tests beside the existing recommendation rules

- [ ] **Step 1: Write the failing test**

A model whose gateway-priced cost differs from its provider-billed cost by more than 2% for
seven consecutive days raises a recommendation that its list price may be wrong, linking to
the price entry.

- [ ] **Step 2: Build it**

This is the third defence and the only one that catches a price nobody noticed was wrong.
Review catches what review looks at; a bill catches everything.

- [ ] **Step 3: Commit**

---

## Task 5: The other three runtime downloads

**Files:** `litellm/__init__.py` lines 417 to 429 and what they reach

- [ ] **Step 1: Bundle the Anthropic beta-header config (R2)**

Same treatment as prices: a bundled file, refreshed by the same job, every change reviewed.

- [ ] **Step 2: Delete the auto-router presets (R3)**

Routing is outside observer-only by decisions 0001, 0011 and 0012. The presets go with the
feature.

- [ ] **Step 3: Delete the blog feed (R4)**

`blog_posts_url`, `get_blog_posts.py`, `blog_posts.json` and the UI panel that shows them.
A product does not ship a reader for another company's blog.

- [ ] **Step 4: Confirm nothing downloads at startup**

`litellm/__init__.py` has no URL left in that block.

- [ ] **Step 5: Commit, one feature per commit**

---

## Task 6: Messages that stand on their own

**Files:** 127 files in `litellm/`, plus the UI

- [ ] **Step 1: Rewrite the Python messages (L1)**

283 lines across 127 files point a user at LiteLLM's documentation or GitHub. Each becomes a
message that helps without the link, or points at Token IQ's own documentation.

The worked example, because it is the most common: a model with no price currently tells the
user to add it to a file in somebody else's repository. It should say the model has no price
in Token IQ's list and name the page where that is fixed.

Comments citing upstream issues lose the link or the whole comment. They are archaeology.

- [ ] **Step 2: Check each rewritten message against the tests**

211 test files mention those URLs. Most are issue links in comments and some are deliberate
fixture data, but a test asserting on message text will fail, and that failure is correct:
it is telling you the message is part of the contract.

- [ ] **Step 3: Remove the UI links and upsells (L2)**

83 links to `docs.litellm.ai`, plus the enterprise and pricing upsells in
`create_key_button.tsx`, `PromptCompressionTab.tsx` and `CustomCodeModal.tsx`. Help links
point at the in-product documentation page. An upsell for another company's paid tier has no
business in a product sold per installation.

- [ ] **Step 4: Regenerate the API types (L3)**

`npm run gen:api` after the docstrings are fixed, so the upstream example URLs in
`schema.d.ts` go. Never hand-edited.

- [ ] **Step 5: Commit**

---

## Task 7: Workflows, images, packages, scripts and data files

**Files:** `.github/workflows/`, `helm/`, `pyproject.toml`, `scripts/`, the data files

- [ ] **Step 1: Delete the workflows that serve BerriAI's public project**

17 of the named ones exist, out of 50. Issue triage and labelling, branch and model upkeep,
release and publishing. Keep the test, lint, security-scan and image-build workflows. Update
`.github/ci-coverage-allowlist.yml` and check whether `.circleci/` still has a purpose before
deleting it.

- [ ] **Step 2: Images and packages (I1, I2)**

The Helm chart pulls `ghcr.io/berriai/litellm` in 18 places. **Ask the owner first whether
Helm survives at all**, given the 30 September decision to deploy on AWS ECS with Terraform.
Repointing a chart nobody deploys is wasted work. `pyproject.toml` metadata becomes Token
IQ's; the licence stays MIT with the notice.

- [ ] **Step 3: Delete the install and upstream-maintenance scripts (I3, I4)**

`scripts/install.sh`, `scripts/install-cli.sh`, the curl hint in the autoroute CLI, and the
scripts that served upstream's own processes. Token IQ is installed by `deploy/`.

- [ ] **Step 4: Decide each data file (D1 to D7)**

Prices and the beta-header config get owners in Tasks 1 and 5. `cost.json` and
`blog_posts.json` are deleted. The rest depend on whether their feature survives phase 5, so
anything uncertain is recorded rather than guessed, and `provider_endpoints_support.json`
waits for that decision instead of being trimmed now.

- [ ] **Step 5: Commit, one concern per commit**

---

## Task 8: Dependency updates, and naming the owners

**Files:** `renovate.json` or `.github/dependabot.yml`, `docs/status.md`

- [ ] **Step 1: Configure the updater**

Covering `uv.lock` and `pyproject.toml`, the dashboard's `package-lock.json`, the Dockerfile
base-image digests and the GitHub Actions. Minor updates grouped weekly, security updates
immediately.

- [ ] **Step 2: Name the owners**

The price owner, the security-advisory owner and the provider-API owner, by name, in
`docs/status.md`. **This needs the owner to tell you three names.** A process with nobody's
name on it is not a process, and writing "the team" here would be pretending.

- [ ] **Step 3: Commit**

---

## Task 9: Prove it, and hand over

- [ ] **Step 1: The search returns nothing**

```bash
git grep -n -E "raw\.githubusercontent\.com/BerriAI|github\.com/BerriAI|ghcr\.io/berriai|docs\.litellm\.ai|www\.litellm\.ai|models\.litellm\.ai|litellm\.ai|berri\.ai|railway\.app" \
  -- . ':!docs/decisions' ':!docs/plans' ':!CHANGELOG.md' ':!LICENSE' ':!NOTICE' \
  ':!scripts/update_model_prices.py' ':!.github/workflows/update-model-prices.yml'
```

- [ ] **Step 2: The network proof**

Outbound blocked except to configured providers. The proxy starts, prices load, the Overview
page renders, and no request leaves for any other host.

- [ ] **Step 3: Compare against the phase 0 baseline**

Nothing newly failing, nothing disappeared.

- [ ] **Step 4: Record it and commit**

---

## Self-Review

**1. Spec coverage**

| Spec requirement (5.2) | Task |
|---|---|
| Four runtime downloads replaced or deleted | Tasks 1 and 5 |
| Bundled price file, read locally | Task 1 |
| Price history, re-pricing a past period | Task 2 |
| Daily job, additions auto-merge, changes reviewed | Task 3 |
| Variance above 2% for 7 days raises an alert | Task 4 |
| Messages and links stand alone | Task 6 |
| Workflows, images, packages, scripts, data files | Task 7 |
| Renovate or Dependabot, owners named | Task 8 |
| Search returns nothing, network proof | Task 9 |

**2. Placeholder scan**

No "TBD". Two places need the owner rather than a guess, and both say so: whether Helm
survives, and the three names.

**3. Type consistency**

The price loader, the history lookup and the update script share one schema for a price
entry, defined once, so a field cannot mean one thing when bundled and another when compared.

**4. The thing a reviewer should check hardest**

That the runtime cannot reach the network for prices, and that the bundled file is the only
copy.

Both failures are silent in the same way. If a remote fetch survives anywhere, an
installation behind a firewall gets whatever the last successful download left behind and
reports confident, wrong numbers. If two copies of the price file exist, they diverge, and
which one a given code path reads becomes a coin toss nobody knows they are flipping.

The second thing to check is that no price was deleted. A model retired upstream still has to
price the months it was in use, and "removed because upstream removed it" would quietly
break every historical figure that touches it.
