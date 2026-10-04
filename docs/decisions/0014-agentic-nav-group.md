# The Agentic group in the sidebar

> **Status: REMOVED from the nav. Pages still exist and are still routable.**

## What was removed

The `Agentic` group in the AI Gateway section of `leftnav.tsx`, with its three children:
`Agents`, `Workflow Runs` and `Memory`.

Also removed: the now-dead `item.key === "agents"` branch in the role filter, which could
never match once the entry was gone, and the orphaned `Bot` and `Workflow` icon imports.
`Database` stayed, since Vector Stores still uses it.

## What was NOT removed

The pages themselves. `/agents`, `/workflows` and `/memory` are still built and still
reachable by typing the URL or following a bookmark. Only the way in was taken away.

Two props are now inert in `leftnav.tsx`: `disableAgentsForInternalUsers` and
`allowAgentsForTeamAdmins`. They are still declared and still passed by
`SidebarProvider.tsx`, which owns their state, so removing them means touching that file
too. Left in place deliberately. `knip` will likely flag them, alongside the other orphans
this branch has accumulated: `DocsLink`, `BlogDropdown`, `AutoRoutersTabPanel`,
`components/AutoRouters/` and `add_auto_router_tab`.

The three remaining `"Agentic"` strings in the built bundle are unrelated: a guardrail tag
in `guardrail_garden_data.ts` and a complexity-router tier label in
`ComplexityRouterConfig.tsx`.

## Tests

Four tests were built around this group. Rather than dropping the coverage they were
converted to assert its absence, for admin viewers, internal users and admins. The admin
case also asserts `Guardrails Monitor` still renders, so an absence result cannot be a
whole-sidebar failure in disguise. 34 tests pass.

## How to restore

```bash
git revert --no-commit <this commit>
cd ui/litellm-dashboard && npm run build
rm -rf ../../litellm/proxy/_experimental/out/* && cp -r ./out/* ../../litellm/proxy/_experimental/out/ && rm -rf ./out
```

Remember the rebuild. `litellm/proxy/_experimental/out` is what the proxy serves, so
reverting the source alone changes nothing visible.

## Removed code

Not inlined here. `git show <this commit> -- ui/litellm-dashboard/src` has the exact diff,
and unlike the enterprise entry there is no licensing reason to duplicate it.
