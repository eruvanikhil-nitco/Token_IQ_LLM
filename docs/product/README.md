# What the product should become

## The two documents

**`2026-09-14-token-iq-product-design.md`** is the agreed direction: what Token IQ is, the
three sources it reads, how they combine without double counting, and the hierarchy of teams,
projects and users.

**`token-iq-product-blueprint.html`** is the page-by-page reference. Open it in a browser.

**`2026-09-15-cost-platform-reference.md`** is research into how established cost platforms
present provider data, kept as a reference for the native provider pages.

## How to read the blueprint

It is a specification, not code. Build pages to match its names, tabs and role rules using
the dashboard's existing component library. Never copy its CSS or its markup.

Where things are inside it:

| Section | What it covers |
|---|---|
| 02 `id="structure"` | Every page, its tabs, and what is deliberately not on it |
| 04 `id="roles"` | The eight roles, and what each can manage or only view |
| 05 `id="helpsys"` | Page guides, the two-tab setup dialogs, naming rules |
| 06 `id="sources"` | How each account connects |
| 07 and 08 | The recommendations engine and the Savings Simulator |
| 12 and 13 | What is missing, and the build order |

## The machine-readable model

Inside the `<script>` beginning `/* Token IQ v7 page model` there are three objects worth
more than the rendered page, because they are precise where prose is not:

- **`TIQ_PAGES`** gives each page its key, group, name, tabs, actions, help text, and access
  per role, where `e` is manage, `v` view, `t` own team, `r` own team read-only, `o` own data
  and `n` hidden. Team Lead variants are nested under `lead`
- **`TIQ_MATRIX`** and **`TIQ_MROLES`** give the permission matrix for all eight roles
- **`TIQ_MODALS`** gives every setup dialog, field by field, with labels, types, options,
  explanations, examples and whether each is required

Phase 5A of the independent-codebase programme extracts these into committed JSON, so that
pages can be built and tested against the model rather than against somebody's reading of a
mockup.

## Two rules

**The figures in the mockup are example data.** They are there so the page looks real. Never
hard-code one.

**The blueprint does not override a decision record.** Where it shows something a decision
removed, such as anything that routes a request, the decision wins and the discrepancy is
worth raising rather than quietly building.
