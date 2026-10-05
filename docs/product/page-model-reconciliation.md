# The page model against the shipped UI

Phase 5A task 1 step 2. The blueprint describes the product as intended; the dashboard is what
exists. This records where they disagree, per discrepancy, rather than quietly making one match the
other.

Generated from `page-model.json` and the folders under
`ui/litellm-dashboard/src/app/(dashboard)/`, excluding `components/` and `hooks/`, which hold shared
code rather than routes.

## What matches

Thirteen of the blueprint's 25 pages have something shipped for them today, through the navigation
mapping in section 12 of `docs/plans/2026-10-04-independent-codebase.md`. Those are the screens phase
5A rebuilds: Overview, Cost Explorer, Invoice Reconciliation, Recommendations, Cost Allocation, Data
Sources, Budgets, Organization, Access Control, Pricing & Rates, Settings, Integrations and Policies.

## Twelve blueprint pages have nothing shipped

| Page | Group | Tabs |
|---|---|---:|
| Team Home | My Team | 0 |
| Members & Access | My Team | 4 |
| Projects & Keys | My Team | 2 |
| Scorecards | Analytics | 3 |
| Reports | Analytics | 5 |
| Savings Simulator | Optimization | 2 |
| Change Impact | Optimization | 2 |
| Realized Savings | Optimization | 2 |
| Anomalies & Alerts | Governance | 3 |
| Contracts & Licenses | Governance | 4 |
| My Usage | | 4 |
| Documentation | | 0 |

**Neither side drifted.** Every one of these is in the blueprint's own section 12, "Badly missing",
and in its build order as a later step: the My Team pages and guidance are step 4, Realized Savings is
step 5, the Savings Simulator is step 6, Anomalies & Alerts is step 8, Contracts & Licenses and Change
Impact are step 9, and Scorecards, Reports and the rest are step 10.

So this is not a gap for phase 5A to close. Phase 5A makes the screens that exist understandable; it
does not build the twelve that do not. Recorded here so that a later reading of the page model does
not mistake them for something phase 5A left undone.

## Ten shipped folders no blueprint page accounts for

```
agents  api-reference  memory  playground  prompts
search-tools  skills  transform-request  vector-stores  workflows
```

**This is worth more than it looks.** Eight of the ten are features the phase 0 inventory proposes
deleting on entirely separate evidence: `agents`, `memory`, `prompts`, `search-tools`, `skills` and
`vector-stores` are named in section 9's delete list, and `workflows` and `playground` are upstream
features the product never mentions. The blueprint does not account for them because they are not part
of Token IQ, and the inventory proposes removing their backends because nothing in Token IQ reaches
them. Two documents written at different times, from different evidence, agreeing.

The remaining two are not features. `api-reference` renders the OpenAPI document and
`transform-request` is a developer tool for inspecting a request's translation. Both are reasonable
things for a gateway's admin UI to carry and neither appears in the blueprint, which is a gap in the
blueprint rather than in the product.

## How to regenerate

```
node scripts/product/extract_page_model.mjs
```

`tests/code_coverage_tests/test_page_model.py` re-runs the extractor and fails if
`page-model.json` no longer matches the blueprint, so the committed model cannot go stale without a
test saying so.
