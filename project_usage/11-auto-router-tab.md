# The Auto-Routers tab in Models + Endpoints

> **Status: REMOVED from the UI. Components and API retained.** This is a visibility
> change only. See the warning at the end: it does not stop an auto-router being created.

## What an auto-router is

Semantic model selection. You define routes, each with example utterances and a target
model. On each request the router embeds the prompt, finds the closest route, and sends the
call to that route's model. The client asks for one model name and the model that actually
serves it is chosen from what they typed.

The substitution is `async_pre_routing_hook` in
`litellm/router_strategy/auto_router/auto_router.py`:

```python
return PreRoutingHookResponse(
    model=route_name or self.default_model,
    messages=messages,
)
```

That return value replaces the model for the rest of the request.

## Why it was removed

It is the clearest contradiction of a forwarding gateway. The caller commits to a model and
the proxy substitutes a different one after reading the prompt, invisibly in the response.
Unlike a fallback it is not even an error path; it is the feature working as designed.

Three incidental costs, true regardless of the observer requirement: every request pays an
extra embedding call through `LiteLLMRouterEncoder` before the real call; prompts are
truncated to `DEFAULT_AUTO_ROUTER_MAX_INPUT_CHARS` before matching; and when the embedding
call fails, `_matched_route_name` swallows the error and silently returns the default model.

## What was removed

`app/(dashboard)/models-and-endpoints/page.tsx` only: the `AutoRoutersTabPanel` import, the
`"auto-routers"` member of the `ModelTabSlug` union, its `"Auto-Routers"` label, its
`renderPanel` case, its entry in `visibleSlugs`, and the beta-badge branch that special-cased
it alongside `access-group-budgets`.

## What was kept, and why

The components are still on disk and now have no callers:
`panels/AutoRoutersTabPanel.tsx`, `components/AutoRouters/*` and
`components/add_model/add_auto_router_tab.tsx`, plus their tests. Keeping them makes the
restore a few lines. `knip` may flag them as unused.

Cost Optimization was left alone deliberately. `AutoRouterBenchmarksTab`,
`useAutoRouterBenchmarks`, `ShadowEvalStartForm` and `TierTurnsChart` are built around
comparing auto-router choices, so removing auto-routers from that page would hollow it out
rather than tidy it. The string "Auto-Routers tab" survives in exactly one bundle chunk,
which is that page.

## Tests

Three cases covered this tab: its ordering, its panel rendering, and its visibility to
non-admins. They were replaced with one asserting the tab is absent while All Models and
Add Model remain, so the surrounding tab list stays covered and a regression that reinstates
the tab fails. 7 tests pass in `page.test.tsx`.

## This does NOT disable auto-routing

Hiding the tab is cosmetic. The `/auto_router` management endpoints still exist, and
`Router._is_auto_router_deployment` (`router.py:8676`) still recognises the config, so an
auto-router can still be created through the API or a config file. The startup guard in
`12-pre-routing-model-substitution.md` is what actually closes that door.

## How to restore

```bash
git revert --no-commit <this commit>
cd ui/litellm-dashboard && npm run build
rm -rf ../../litellm/proxy/_experimental/out/* && cp -r ./out/* ../../litellm/proxy/_experimental/out/ && rm -rf ./out
```

## Removed code

```diff
diff --git a/ui/litellm-dashboard/src/app/(dashboard)/models-and-endpoints/page.test.tsx b/ui/litellm-dashboard/src/app/(dashboard)/models-and-endpoints/page.test.tsx
index 84a0511317..575a7e6577 100644
--- a/ui/litellm-dashboard/src/app/(dashboard)/models-and-endpoints/page.test.tsx
+++ b/ui/litellm-dashboard/src/app/(dashboard)/models-and-endpoints/page.test.tsx
@@ -7,7 +7,6 @@ import ModelsAndEndpointsPage from "./page";
 
 vi.mock("./panels/AllModelsPanel", () => ({ default: () => <div data-testid="panel-all-models" /> }));
 vi.mock("./panels/AddModelPanel", () => ({ default: () => <div data-testid="panel-add" /> }));
-vi.mock("./panels/AutoRoutersTabPanel", () => ({ default: () => <div data-testid="panel-auto-routers" /> }));
 vi.mock("./panels/LlmCredentialsPanel", () => ({ default: () => <div data-testid="panel-credentials" /> }));
 vi.mock("./panels/PassThroughPanel", () => ({ default: () => <div data-testid="panel-pass-through" /> }));
 vi.mock("./panels/HealthStatusPanel", () => ({ default: () => <div data-testid="panel-health" /> }));
@@ -116,41 +115,13 @@ describe("ModelsAndEndpointsPage", () => {
     expect(screen.getByRole("tab", { name: "All Models" })).toBeInTheDocument();
   });
 
-  // Read parity: the Auto-Routers list stays reachable for a view-only admin; only the
-  // create affordance inside it is withheld, which AutoRoutersTabPanel decides.
-  it("keeps the Auto-Routers tab for a view-only admin session", () => {
-    mockUseAuthorized.mockReturnValue(VIEW_ONLY_ADMIN);
+  // The Auto-Routers tab was removed: semantic model selection picks a model the caller
+  // did not ask for, which this gateway must never do.
+  it("does not offer an Auto-Routers tab to an admin who can create models", () => {
     renderPage();
-    expect(screen.getByRole("tab", { name: /Auto-Routers/ })).toBeInTheDocument();
-  });
-
-  // Auto-routers are excluded from the All Models table, so this tab is their home: the only
-  // place in the product to list, create, edit or delete one.
-  describe("Auto-Routers tab", () => {
-    it("sits third, after All Models and Add Model", () => {
-      renderPage();
-
-      const tabs = screen.getAllByRole("tab").map((tab) => tab.textContent);
-      expect(tabs[0]).toContain("All Models");
-      expect(tabs[1]).toBe("Add Model");
-      expect(tabs[2]).toContain("Auto-Routers");
-      // Badged Beta while the tab settles; BetaBadge renders the label text.
-      expect(tabs[2]).toContain("Beta");
-    });
 
-    it("renders its panel when selected", async () => {
-      const user = userEvent.setup();
-      renderPage();
-
-      await user.click(screen.getByRole("tab", { name: /Auto-Routers/ }));
-      expect(screen.getByTestId("panel-auto-routers")).toBeInTheDocument();
-    });
-
-    it("is hidden from non-admins, who cannot write models", () => {
-      mockUseAuthorized.mockReturnValue(NON_ADMIN);
-      renderPage();
-
-      expect(screen.queryByRole("tab", { name: /Auto-Routers/ })).not.toBeInTheDocument();
-    });
+    expect(screen.queryByRole("tab", { name: /Auto-Routers/ })).not.toBeInTheDocument();
+    expect(screen.getByRole("tab", { name: "All Models" })).toBeInTheDocument();
+    expect(screen.getByRole("tab", { name: "Add Model" })).toBeInTheDocument();
   });
 });
diff --git a/ui/litellm-dashboard/src/app/(dashboard)/models-and-endpoints/page.tsx b/ui/litellm-dashboard/src/app/(dashboard)/models-and-endpoints/page.tsx
index 34c9d87004..c8a5560e43 100644
--- a/ui/litellm-dashboard/src/app/(dashboard)/models-and-endpoints/page.tsx
+++ b/ui/litellm-dashboard/src/app/(dashboard)/models-and-endpoints/page.tsx
@@ -15,7 +15,6 @@ import TeamInfoView from "@/components/team/TeamInfo";
 import { useModelDetailRouting } from "@/app/(dashboard)/models-and-endpoints/detailNavigation";
 import { useModelDashboardData } from "@/app/(dashboard)/models-and-endpoints/useModelDashboardData";
 import AllModelsPanel from "@/app/(dashboard)/models-and-endpoints/panels/AllModelsPanel";
-import AutoRoutersTabPanel from "@/app/(dashboard)/models-and-endpoints/panels/AutoRoutersTabPanel";
 import AddModelPanel from "@/app/(dashboard)/models-and-endpoints/panels/AddModelPanel";
 import LlmCredentialsPanel from "@/app/(dashboard)/models-and-endpoints/panels/LlmCredentialsPanel";
 import PassThroughPanel from "@/app/(dashboard)/models-and-endpoints/panels/PassThroughPanel";
@@ -29,7 +28,6 @@ import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
 
 type ModelTabSlug =
   | "add"
-  | "auto-routers"
   | "llm-credentials"
   | "pass-through"
   | "health"
@@ -42,7 +40,6 @@ const BASE_TAB_KEY = "all-models";
 
 const TAB_LABELS: Record<ModelTabSlug, string> = {
   add: "Add Model",
-  "auto-routers": "Auto-Routers",
   "llm-credentials": "LLM Credentials",
   "pass-through": "Pass-Through Endpoints",
   health: "Health Status",
@@ -56,8 +53,6 @@ const renderPanel = (key: string) => {
   switch (key) {
     case BASE_TAB_KEY:
       return <AllModelsPanel />;
-    case "auto-routers":
-      return <AutoRoutersTabPanel />;
     case "add":
       return <AddModelPanel />;
     case "llm-credentials":
@@ -105,7 +100,6 @@ export default function ModelsAndEndpointsPage() {
     () => [
       "",
       ...(canCreate ? (["add"] as const) : []),
-      ...(isAdmin || canCreate ? (["auto-routers"] as const) : []),
       ...(isAdmin
         ? ([
             "llm-credentials",
@@ -124,7 +118,7 @@ export default function ModelsAndEndpointsPage() {
   const allModelsLabel = isAdmin ? "All Models" : "Your Models";
   const tabLabel = (slug: "" | ModelTabSlug): React.ReactNode => {
     if (!slug) return allModelsLabel;
-    if (slug === "auto-routers" || slug === "access-group-budgets") {
+    if (slug === "access-group-budgets") {
       return (
         <span className="flex items-center gap-2">
           {TAB_LABELS[slug]} <BetaBadge />
```
