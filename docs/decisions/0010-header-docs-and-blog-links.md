# Docs and Blog links in the header toolbar

> **Status: REMOVED from both headers. Components retained.** The link and dropdown
> components still exist on disk but nothing renders them.

## What was removed

The top-right toolbar rendered a `Docs` outbound link to `https://docs.litellm.ai/docs/`
and a `Blog` dropdown that fetched LiteLLM blog posts and linked to
`https://docs.litellm.ai/blog`.

Both are rendered in two places, because the dashboard has two header implementations:

- `components/DashboardHeader.tsx` lines 65-66, the current sidebar-era header
- `components/navbar.tsx`, inside a `<nav aria-label="Product documentation">` wrapper

Both call sites and their imports are gone. Verified against the built bundle:
`docs.litellm.ai/blog` now appears in 0 files.

## What was deliberately kept

`docs.litellm.ai/docs/` still appears in 34 files of the built bundle. Those are
contextual help links inside feature pages, for example the auto-router docs link in
`NotificationsBell`, and the guardrail and settings pages. They were not part of the header
toolbar and were left alone.

`CommunityEngagementButtons` was also left in place. It sits next to the removed links but
is a separate control and was not in scope.

The version badge in `navbar.tsx` still links to `docs.litellm.ai/release_notes`. It is a
version indicator rather than a docs link, so it stayed.

## Orphaned components

`components/Navbar/DocsLink/DocsLink.tsx` and
`components/Navbar/BlogDropdown/BlogDropdown.tsx` now have no callers outside their own
tests. They were not deleted, so restoring is a two-line change. Note that `knip` is
configured in this project and may flag them as unused exports.

Their supporting pieces are also still present and unused by the headers: the
`useBlogPosts` hook, the `useDisableBlogPosts` hook (still read by `UserDropdown` for its
"Hide Blog Posts" toggle), and `navProductLinkClass.ts`.

## Tests

`navbar.test.tsx` asserted `getByText("Docs")` in its render test; it now asserts Docs and
the blog dropdown are absent while the notifications button and account menu remain, so the
rest of the toolbar is still covered. Its `vi.mock` for `BlogDropdown` was dead once the
import went, and was removed.

`DashboardHeader.test.tsx` had a test asserting Docs carried the shared product-link class.
That test had no subject left, so it was replaced with one asserting neither link renders.
Its now-unused `NAV_PRODUCT_LINK_CLASS` import was dropped.

19 tests pass across both files.

## How to restore

```bash
git revert --no-commit <this commit>
cd ui/litellm-dashboard && npm run build
rm -rf ../../litellm/proxy/_experimental/out/* && cp -r ./out/* ../../litellm/proxy/_experimental/out/ && rm -rf ./out
```

Remember the rebuild: `litellm/proxy/_experimental/out` is what the proxy serves, so
reverting the source alone changes nothing visible.

## Removed code

```diff
diff --git a/ui/litellm-dashboard/src/components/DashboardHeader.test.tsx b/ui/litellm-dashboard/src/components/DashboardHeader.test.tsx
index 6a06e1ba61..129e3a9bb4 100644
--- a/ui/litellm-dashboard/src/components/DashboardHeader.test.tsx
+++ b/ui/litellm-dashboard/src/components/DashboardHeader.test.tsx
@@ -1,7 +1,6 @@
 import { afterEach, describe, expect, it, vi } from "vitest";
 import { act, fireEvent, render, screen } from "@testing-library/react";
 import { DashboardHeader } from "./DashboardHeader";
-import { NAV_PRODUCT_LINK_CLASS } from "@/components/Navbar/navProductLinkClass";
 
 const { mockUsePluginMode, mockUseUISettings, state } = vi.hoisted(() => {
   const state = {
@@ -56,14 +55,11 @@ describe("DashboardHeader breadcrumb", () => {
     expect(screen.queryByText("Observability")).not.toBeInTheDocument();
   });
 
-  it("styles Docs with the shared product-link class instead of a muted toolbar button", () => {
+  it("no longer renders the Docs or Blog links in the header toolbar", () => {
     render(<DashboardHeader page="logs" />);
 
-    const docs = screen.getByRole("link", { name: "Docs" });
-    for (const cls of NAV_PRODUCT_LINK_CLASS.trim().split(/\s+/)) {
-      expect(docs).toHaveClass(cls);
-    }
-    expect(docs).not.toHaveClass("text-muted-foreground");
+    expect(screen.queryByRole("link", { name: "Docs" })).not.toBeInTheDocument();
+    expect(screen.queryByText("Blog")).not.toBeInTheDocument();
   });
 
   it("renders the tools divider centered rather than stretched to the top of the row", () => {
diff --git a/ui/litellm-dashboard/src/components/DashboardHeader.tsx b/ui/litellm-dashboard/src/components/DashboardHeader.tsx
index fe824ce074..847cb5604b 100644
--- a/ui/litellm-dashboard/src/components/DashboardHeader.tsx
+++ b/ui/litellm-dashboard/src/components/DashboardHeader.tsx
@@ -9,8 +9,6 @@ import {
 } from "@/components/ui/breadcrumb";
 import { ToolbarSeparator } from "@/components/shared/ToolbarSeparator";
 import { getBreadcrumb } from "@/components/leftnav";
-import { BlogDropdown } from "@/components/Navbar/BlogDropdown/BlogDropdown";
-import { DocsLink } from "@/components/Navbar/DocsLink/DocsLink";
 import { CommunityEngagementButtons } from "@/components/Navbar/CommunityEngagementButtons/CommunityEngagementButtons";
 import { NotificationsBell } from "@/components/Navbar/NotificationsBell/NotificationsBell";
 import ViewSwitcher from "@/components/Navbar/ViewSwitcher";
@@ -62,8 +60,6 @@ export function DashboardHeader({ page }: DashboardHeaderProps) {
             <ToolbarSeparator />
           </>
         )}
-        <DocsLink />
-        <BlogDropdown />
         {!hideCommunityLinks && <CommunityEngagementButtons />}
         <ToolbarSeparator />
         <ThemeToggle />
diff --git a/ui/litellm-dashboard/src/components/navbar.test.tsx b/ui/litellm-dashboard/src/components/navbar.test.tsx
index e33ec40491..420d118cfc 100644
--- a/ui/litellm-dashboard/src/components/navbar.test.tsx
+++ b/ui/litellm-dashboard/src/components/navbar.test.tsx
@@ -14,10 +14,6 @@ vi.mock("@/app/(dashboard)/hooks/useDisableBouncingIcon", () => ({
   useDisableBouncingIcon: () => false,
 }));
 
-vi.mock("./Navbar/BlogDropdown/BlogDropdown", () => ({
-  BlogDropdown: () => <div data-testid="blog-dropdown">Blog</div>,
-}));
-
 const mockUserDropdownData = vi.hoisted(() => ({
   current: () => ({
     userId: "test-user",
@@ -147,8 +143,10 @@ describe("Navbar", () => {
     renderWithProviders(<Navbar {...defaultProps} />);
 
     expect(screen.getByRole("button", { name: /^notifications$/i })).toBeInTheDocument();
-    expect(screen.getByText("Docs")).toBeInTheDocument();
     expect(screen.getByRole("button", { name: /open account menu/i })).toBeInTheDocument();
+    // Docs and Blog were removed from the header; the rest of the toolbar stays.
+    expect(screen.queryByText("Docs")).not.toBeInTheDocument();
+    expect(screen.queryByTestId("blog-dropdown")).not.toBeInTheDocument();
   });
 
   it("should link the logo to the UI home route rather than the proxy origin", () => {
diff --git a/ui/litellm-dashboard/src/components/navbar.tsx b/ui/litellm-dashboard/src/components/navbar.tsx
index 88cd125ea1..121a3aae17 100644
--- a/ui/litellm-dashboard/src/components/navbar.tsx
+++ b/ui/litellm-dashboard/src/components/navbar.tsx
@@ -12,8 +12,6 @@ import { Badge } from "@/components/ui/badge";
 import { PanelLeftClose, PanelLeftOpen } from "lucide-react";
 import Link from "next/link";
 import React from "react";
-import { BlogDropdown } from "./Navbar/BlogDropdown/BlogDropdown";
-import { DocsLink } from "./Navbar/DocsLink/DocsLink";
 import { CommunityEngagementButtons } from "./Navbar/CommunityEngagementButtons/CommunityEngagementButtons";
 import { cn } from "@/lib/cva.config";
 import { NotificationsBell } from "./Navbar/NotificationsBell/NotificationsBell";
@@ -139,14 +137,6 @@ const Navbar: React.FC<NavbarProps> = ({
               </div>
             )}
 
-            <nav
-              aria-label="Product documentation"
-              className={`flex min-w-0 items-center gap-2 ${showWorkerSwitch ? "border-l border-border pl-4" : ""}`}
-            >
-              <DocsLink />
-              <BlogDropdown />
-            </nav>
-
             {!hideCommunityLinks && (
               <div className="flex shrink-0 items-center border-l border-border pl-4">
                 <CommunityEngagementButtons />
```
