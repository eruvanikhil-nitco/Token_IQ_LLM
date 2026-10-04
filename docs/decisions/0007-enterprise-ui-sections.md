# Enterprise upsell sections in the Admin UI

## Why this was removed

With the enterprise package gone, the dashboard still advertised the features it could no
longer run. `premium_user` is False without a `LITELLM_LICENSE`, so every one of these
blocks rendered an upsell rather than a feature: a page telling the user to buy a licence,
sitting behind a nav entry that looked like a working page.

## What was removed

Commit `c0590867d8`, 19 files, 89 insertions and 254 deletions.

- **Audit Logs**, the full-page "Enterprise Feature" screen with a preview screenshot
  (`AuditLogsPanel.tsx:88`)
- **Organizations**, the "requires a valid key to use" gate, plus the Organizations sidebar
  entry, since the panel was gated end to end
- **Deleted Keys** and **Deleted Teams**, both "Coming soon to Enterprise" banners
- **Key/Team logging settings**, the langfuse and datadog teaser badges and the notice;
  the component now returns null for free users
- **Alerting settings**, premium rows no longer render, replacing a button that linked to a
  Google Form
- **Pass-through Security**, the whole card, which was a permanently-off switch plus an upsell
- **Old Usage**, tag options no longer render as disabled "Enterprise only Feature" entries
- **Account menus**, the Premium/Standard tier badge and its upgrade tooltip, in both the
  navbar dropdown and the sidebar panel

## What was deliberately kept

Controls that are disabled with an explanatory hint were left alone: "Assigning team admins
is a premium feature", "Premium feature - Upgrade to set guardrails by key", the model
max-budget editor, the key prompts field, SSO config in Admin Settings. Removing the hint
leaves a dead control with no explanation, and enabling it would surface a feature the
backend still rejects. The licence-expiry banner also stayed, since it reports real state
rather than advertising.

## Note on the tests

Assertions were inverted rather than deleted, so reintroducing an upsell fails the suite.
One test was dropped outright: `PremiumLoggingSettings.test.tsx` had a case that read the
component's own source and asserted it contained Tailwind token class names. That tests
structure rather than behaviour, and with the markup gone it had nothing left to assert.

## How to restore

```bash
git revert --no-commit c0590867d8
cd ui/litellm-dashboard && npm run build
rm -rf ../../litellm/proxy/_experimental/out/* && cp -r ./out/* ../../litellm/proxy/_experimental/out/ && rm -rf ./out
```

Remember the rebuild. `litellm/proxy/_experimental/out` is the bundle the proxy actually
serves, so reverting the source alone changes nothing the user sees.

## Removed code

The complete diff, source and tests:

```diff
commit c0590867d8e5da387b042121547391ac76a164b9
Author: Nikhil Eruva <n.eruva@nitcoinc.com>
Date:   Thu Sep 3 18:14:56 2026 +0530

    feat(ui): stop advertising Enterprise features in the dashboard
    
    Removes the upsell blocks, tier badges and enterprise-gated rows that
    free users saw, and drops the Organizations nav entry, whose panel was
    gated end to end.
    
    Controls that are merely disabled with a hint are left alone: dropping
    the hint leaves an unexplained dead control, and enabling one would
    surface a feature the proxy still rejects without a license.
    
    Tests are inverted rather than deleted, so reintroducing an upsell
    fails them. The PremiumLoggingSettings source-grep test is dropped
    outright: it asserted the file contained Tailwind token classes, which
    tests structure rather than behaviour, and the component no longer
    renders markup of its own.
    
    Rebuilt litellm/proxy/_experimental/out so the served bundle matches.
    
    Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
    Claude-Session: https://claude.ai/code/session_01Q8g6YpZrv3Jvye6Rxycjeg

diff --git a/ui/litellm-dashboard/src/app/(dashboard)/old-usage/_components/usage.tsx b/ui/litellm-dashboard/src/app/(dashboard)/old-usage/_components/usage.tsx
index 42be1b34f0..a560aeb5bf 100644
--- a/ui/litellm-dashboard/src/app/(dashboard)/old-usage/_components/usage.tsx
+++ b/ui/litellm-dashboard/src/app/(dashboard)/old-usage/_components/usage.tsx
@@ -130,13 +130,15 @@ const UsagePage: React.FC<UsagePageProps> = ({ accessToken, token, userRole, use
 
   const tagOptions: TagOption[] = [
     { value: ALL_TAGS, label: "All Tags", disabled: false },
-    ...allTagNames
-      .filter((tag) => tag !== ALL_TAGS)
-      .map((tag) => ({
-        value: tag,
-        label: premiumUser ? tag : `âœ¨ ${tag} (Enterprise only Feature)`,
-        disabled: !premiumUser,
-      })),
+    ...(premiumUser
+      ? allTagNames
+          .filter((tag) => tag !== ALL_TAGS)
+          .map((tag) => ({
+            value: tag,
+            label: tag,
+            disabled: false,
+          }))
+      : []),
   ];
 
   function valueFormatterNumbers(number: number) {
diff --git a/ui/litellm-dashboard/src/app/(dashboard)/organizations/_components/OrganizationsPanel.test.tsx b/ui/litellm-dashboard/src/app/(dashboard)/organizations/_components/OrganizationsPanel.test.tsx
index c15b9fcadd..4e57329d70 100644
--- a/ui/litellm-dashboard/src/app/(dashboard)/organizations/_components/OrganizationsPanel.test.tsx
+++ b/ui/litellm-dashboard/src/app/(dashboard)/organizations/_components/OrganizationsPanel.test.tsx
@@ -86,11 +86,11 @@ beforeEach(() => {
 });
 
 describe("OrganizationsPanel", () => {
-  it("gates non-premium users behind the enterprise notice", () => {
+  it("shows non-premium users the panel itself, with no enterprise notice", () => {
     renderPanel({ premiumUser: false });
 
-    expect(screen.getByText(/LiteLLM Enterprise feature/i)).toBeInTheDocument();
-    expect(screen.queryByText("+ Create New Organization")).not.toBeInTheDocument();
+    expect(screen.queryByText(/LiteLLM Enterprise feature/i)).not.toBeInTheDocument();
+    expect(screen.getByText("+ Create New Organization")).toBeInTheDocument();
   });
 
   it("shows the create button for a premium admin", () => {
diff --git a/ui/litellm-dashboard/src/app/(dashboard)/organizations/_components/OrganizationsPanel.tsx b/ui/litellm-dashboard/src/app/(dashboard)/organizations/_components/OrganizationsPanel.tsx
index 4fe4cf47b9..a92362e135 100644
--- a/ui/litellm-dashboard/src/app/(dashboard)/organizations/_components/OrganizationsPanel.tsx
+++ b/ui/litellm-dashboard/src/app/(dashboard)/organizations/_components/OrganizationsPanel.tsx
@@ -78,25 +78,6 @@ const OrganizationsPanel: React.FC<OrganizationsPanelProps> = ({ userRole, acces
     setOrgToDelete(null);
   };
 
-  if (!premiumUser) {
-    return (
-      <div className="mx-4 mt-4">
-        <p className="text-sm text-muted-foreground">
-          This is a LiteLLM Enterprise feature, and requires a valid key to use. Get a trial key{" "}
-          <a
-            href="https://www.litellm.ai/#pricing"
-            target="_blank"
-            rel="noopener noreferrer"
-            className="text-primary underline-offset-4 hover:underline"
-          >
-            here
-          </a>
-          .
-        </p>
-      </div>
-    );
-  }
-
   return (
     <div className="mx-4 mt-4 flex flex-col gap-4">
       {(userRole === "Admin" || userRole === "Org Admin") && (
diff --git a/ui/litellm-dashboard/src/components/DeletedKeysPage/DeletedKeysPage.test.tsx b/ui/litellm-dashboard/src/components/DeletedKeysPage/DeletedKeysPage.test.tsx
index ee2f42ad85..5a4cba2c9b 100644
--- a/ui/litellm-dashboard/src/components/DeletedKeysPage/DeletedKeysPage.test.tsx
+++ b/ui/litellm-dashboard/src/components/DeletedKeysPage/DeletedKeysPage.test.tsx
@@ -92,13 +92,14 @@ it("should render DeletedKeysPage component", () => {
   expect(screen.getByText("Test Key Alias")).toBeInTheDocument();
 });
 
-it("should show the enterprise notice for a non-premium user", () => {
+it("should not advertise Enterprise to a non-premium user", () => {
   renderWithProviders(<DeletedKeysPage />);
 
-  expect(screen.getByText("Coming soon to Enterprise")).toBeInTheDocument();
+  expect(screen.queryByText("Coming soon to Enterprise")).not.toBeInTheDocument();
   expect(
-    screen.getByText("Deleted key auditing is graduating from beta into our Enterprise audit & compliance suite."),
-  ).toBeInTheDocument();
+    screen.queryByText("Deleted key auditing is graduating from beta into our Enterprise audit & compliance suite."),
+  ).not.toBeInTheDocument();
+  expect(screen.getByText("Test Key Alias")).toBeInTheDocument();
 });
 
 it("should show skeleton rows while the initial load is pending", () => {
diff --git a/ui/litellm-dashboard/src/components/DeletedKeysPage/DeletedKeysPage.tsx b/ui/litellm-dashboard/src/components/DeletedKeysPage/DeletedKeysPage.tsx
index 0af668b5e9..f20afe1d9b 100644
--- a/ui/litellm-dashboard/src/components/DeletedKeysPage/DeletedKeysPage.tsx
+++ b/ui/litellm-dashboard/src/components/DeletedKeysPage/DeletedKeysPage.tsx
@@ -1,29 +1,16 @@
 "use client";
 import { useState } from "react";
 import { PaginationState } from "@tanstack/react-table";
-import { Info } from "lucide-react";
-import { Alert, AlertDescription, AlertTitle } from "@/components/shared/Alert";
 import { useDeletedKeys } from "@/app/(dashboard)/hooks/keys/useKeys";
-import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
 import { DeletedKeysTable } from "./DeletedKeysTable/DeletedKeysTable";
 
 export default function DeletedKeysPage() {
-  const { premiumUser } = useAuthorized();
   const [pagination, setPagination] = useState<PaginationState>({ pageIndex: 0, pageSize: 50 });
 
   const { data: keysData, isLoading } = useDeletedKeys(pagination.pageIndex + 1, pagination.pageSize);
 
   return (
     <div className="flex flex-col gap-4">
-      {!premiumUser && (
-        <Alert>
-          <Info />
-          <AlertTitle>Coming soon to Enterprise</AlertTitle>
-          <AlertDescription>
-            Deleted key auditing is graduating from beta into our Enterprise audit &amp; compliance suite.
-          </AlertDescription>
-        </Alert>
-      )}
       <DeletedKeysTable
         keys={keysData?.keys || []}
         totalCount={keysData?.total_count || 0}
diff --git a/ui/litellm-dashboard/src/components/DeletedTeamsPage/DeletedTeamsPage.test.tsx b/ui/litellm-dashboard/src/components/DeletedTeamsPage/DeletedTeamsPage.test.tsx
index 6bf5d1caf6..ee2f9024ca 100644
--- a/ui/litellm-dashboard/src/components/DeletedTeamsPage/DeletedTeamsPage.test.tsx
+++ b/ui/litellm-dashboard/src/components/DeletedTeamsPage/DeletedTeamsPage.test.tsx
@@ -42,13 +42,14 @@ it("should render DeletedTeamsPage component", () => {
   expect(screen.getByText("Test Team")).toBeInTheDocument();
 });
 
-it("should show the enterprise notice for a non-premium user", () => {
+it("should not advertise Enterprise to a non-premium user", () => {
   renderWithProviders(<DeletedTeamsPage />);
 
-  expect(screen.getByText("Coming soon to Enterprise")).toBeInTheDocument();
+  expect(screen.queryByText("Coming soon to Enterprise")).not.toBeInTheDocument();
   expect(
-    screen.getByText("Deleted team auditing is graduating from beta into our Enterprise audit & compliance suite."),
-  ).toBeInTheDocument();
+    screen.queryByText("Deleted team auditing is graduating from beta into our Enterprise audit & compliance suite."),
+  ).not.toBeInTheDocument();
+  expect(screen.getByText("Test Team")).toBeInTheDocument();
 });
 
 it("should show skeleton rows while the initial load is pending", () => {
diff --git a/ui/litellm-dashboard/src/components/DeletedTeamsPage/DeletedTeamsPage.tsx b/ui/litellm-dashboard/src/components/DeletedTeamsPage/DeletedTeamsPage.tsx
index eab150d6ab..6677edd2e5 100644
--- a/ui/litellm-dashboard/src/components/DeletedTeamsPage/DeletedTeamsPage.tsx
+++ b/ui/litellm-dashboard/src/components/DeletedTeamsPage/DeletedTeamsPage.tsx
@@ -1,25 +1,12 @@
 "use client";
-import { Info } from "lucide-react";
-import { Alert, AlertDescription, AlertTitle } from "@/components/shared/Alert";
 import { useDeletedTeams } from "@/app/(dashboard)/hooks/teams/useTeams";
-import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
 import { DeletedTeamsTable } from "./DeletedTeamsTable/DeletedTeamsTable";
 
 export default function DeletedTeamsPage() {
-  const { premiumUser } = useAuthorized();
   const { data: teamsData, isLoading } = useDeletedTeams(1, 100);
 
   return (
     <div className="flex flex-col gap-4">
-      {!premiumUser && (
-        <Alert>
-          <Info />
-          <AlertTitle>Coming soon to Enterprise</AlertTitle>
-          <AlertDescription>
-            Deleted team auditing is graduating from beta into our Enterprise audit &amp; compliance suite.
-          </AlertDescription>
-        </Alert>
-      )}
       <DeletedTeamsTable teams={teamsData || []} isLoading={isLoading} />
     </div>
   );
diff --git a/ui/litellm-dashboard/src/components/Navbar/UserDropdown/UserDropdown.test.tsx b/ui/litellm-dashboard/src/components/Navbar/UserDropdown/UserDropdown.test.tsx
index cad5ced340..23d4651948 100644
--- a/ui/litellm-dashboard/src/components/Navbar/UserDropdown/UserDropdown.test.tsx
+++ b/ui/litellm-dashboard/src/components/Navbar/UserDropdown/UserDropdown.test.tsx
@@ -99,18 +99,21 @@ describe("UserDropdown", () => {
     });
   });
 
-  it("should display Standard badge for non-premium users", async () => {
+  it("should show no tier badge and no upgrade prompt to a non-premium user", async () => {
     const user = userEvent.setup();
     renderWithProviders(<UserDropdown onLogout={mockOnLogout} />);
 
     await user.click(getAccountTrigger());
 
     await waitFor(() => {
-      expect(screen.getByText("Standard")).toBeInTheDocument();
+      expect(screen.getByTestId("user-dropdown-panel")).toBeInTheDocument();
     });
+    expect(screen.queryByText("Standard")).not.toBeInTheDocument();
+    expect(screen.queryByText("Premium")).not.toBeInTheDocument();
+    expect(screen.queryByText("Upgrade to Premium for advanced features")).not.toBeInTheDocument();
   });
 
-  it("should display Premium badge for premium users", async () => {
+  it("should show no tier badge to a premium user either", async () => {
     const user = userEvent.setup();
     mockUseAuthorizedImpl = () => ({
       userId: "test-user-id",
@@ -124,8 +127,9 @@ describe("UserDropdown", () => {
     await user.click(getAccountTrigger());
 
     await waitFor(() => {
-      expect(screen.getByText("Premium")).toBeInTheDocument();
+      expect(screen.getByTestId("user-dropdown-panel")).toBeInTheDocument();
     });
+    expect(screen.queryByText("Premium")).not.toBeInTheDocument();
   });
 
   it("should call onLogout when logout is clicked", async () => {
diff --git a/ui/litellm-dashboard/src/components/Navbar/UserDropdown/UserDropdown.tsx b/ui/litellm-dashboard/src/components/Navbar/UserDropdown/UserDropdown.tsx
index 95f76dbb2c..55be1231c4 100644
--- a/ui/litellm-dashboard/src/components/Navbar/UserDropdown/UserDropdown.tsx
+++ b/ui/litellm-dashboard/src/components/Navbar/UserDropdown/UserDropdown.tsx
@@ -9,13 +9,12 @@ import {
   setLocalStorageItem,
 } from "@/utils/localStorageUtils";
 import { navAccountDisplayName } from "@/components/Navbar/navDisplayName";
-import { ChevronDown, ChevronsUpDown, Crown, LogOut, Mail, ShieldCheck, User } from "lucide-react";
+import { ChevronDown, ChevronsUpDown, LogOut, Mail, ShieldCheck, User } from "lucide-react";
 import { Avatar, AvatarFallback } from "@/components/ui/avatar";
 import { Badge } from "@/components/ui/badge";
 import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
 import { Separator } from "@/components/ui/separator";
 import { Switch } from "@/components/ui/switch";
-import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
 import CopyButton from "@/components/shared/CopyButton";
 import { cn } from "@/lib/cva.config";
 import React, { useEffect, useState } from "react";
@@ -63,7 +62,7 @@ interface UserDropdownProps {
 }
 
 const UserDropdown: React.FC<UserDropdownProps> = ({ onLogout, variant = "navbar", collapsed = false }) => {
-  const { userId, userEmail, userRoleLabel: userRole, premiumUser } = useAuthorized();
+  const { userId, userEmail, userRoleLabel: userRole } = useAuthorized();
   const disableShowPrompts = useDisableShowPrompts();
   const disableBlogPosts = useDisableBlogPosts();
   const disableBouncingIcon = useDisableBouncingIcon();
@@ -81,22 +80,6 @@ const UserDropdown: React.FC<UserDropdownProps> = ({ onLogout, variant = "navbar
           <Mail className="size-4" />
           <span className="text-muted-foreground">{userEmail || "-"}</span>
         </div>
-        {premiumUser ? (
-          <Badge>
-            <Crown className="size-3" />
-            Premium
-          </Badge>
-        ) : (
-          <TooltipProvider>
-            <Tooltip>
-              <TooltipTrigger render={<Badge variant="outline" />}>
-                <Crown className="size-3" />
-                Standard
-              </TooltipTrigger>
-              <TooltipContent side="left">Upgrade to Premium for advanced features</TooltipContent>
-            </Tooltip>
-          </TooltipProvider>
-        )}
       </div>
       <Separator className="my-2" />
       <div className="flex w-full items-center justify-between gap-2">
diff --git a/ui/litellm-dashboard/src/components/SidebarAccountMenu/SidebarAccountMenu.test.tsx b/ui/litellm-dashboard/src/components/SidebarAccountMenu/SidebarAccountMenu.test.tsx
index 9d56a889ed..e62042b3f2 100644
--- a/ui/litellm-dashboard/src/components/SidebarAccountMenu/SidebarAccountMenu.test.tsx
+++ b/ui/litellm-dashboard/src/components/SidebarAccountMenu/SidebarAccountMenu.test.tsx
@@ -113,16 +113,18 @@ describe("SidebarAccountMenu", () => {
     expect(screen.getAllByText("Admin").length).toBeGreaterThan(0);
   });
 
-  it("should display Standard tier for non-premium users", async () => {
+  it("should show no Tier row to a non-premium user", async () => {
     const user = userEvent.setup();
     renderWithProviders(<SidebarAccountMenu onLogout={mockOnLogout} />);
 
     await openMenu(user);
 
-    expect(screen.getByText("Standard")).toBeInTheDocument();
+    expect(screen.queryByText("Tier")).not.toBeInTheDocument();
+    expect(screen.queryByText("Standard")).not.toBeInTheDocument();
+    expect(screen.getByText("Role")).toBeInTheDocument();
   });
 
-  it("should display Premium tier for premium users", async () => {
+  it("should show no Tier row to a premium user either", async () => {
     const user = userEvent.setup();
     mockUseAuthorizedImpl = () => ({
       userId: "test-user-id",
@@ -136,7 +138,8 @@ describe("SidebarAccountMenu", () => {
 
     await openMenu(user);
 
-    expect(screen.getByText("Premium")).toBeInTheDocument();
+    expect(screen.queryByText("Tier")).not.toBeInTheDocument();
+    expect(screen.queryByText("Premium")).not.toBeInTheDocument();
   });
 
   it("should render a clickable version badge linking to the release notes", async () => {
diff --git a/ui/litellm-dashboard/src/components/SidebarAccountMenu/SidebarAccountMenu.tsx b/ui/litellm-dashboard/src/components/SidebarAccountMenu/SidebarAccountMenu.tsx
index ea0b82869c..c2b5b3205a 100644
--- a/ui/litellm-dashboard/src/components/SidebarAccountMenu/SidebarAccountMenu.tsx
+++ b/ui/litellm-dashboard/src/components/SidebarAccountMenu/SidebarAccountMenu.tsx
@@ -14,7 +14,7 @@ import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover
 import { Separator } from "@/components/ui/separator";
 import { Switch } from "@/components/ui/switch";
 import { cn } from "@/lib/cva.config";
-import { ChevronsUpDown, Crown, IdCard, LogOut, Mail, ShieldCheck } from "lucide-react";
+import { ChevronsUpDown, IdCard, LogOut, Mail, ShieldCheck } from "lucide-react";
 import React from "react";
 
 const RELEASE_NOTES_URL = "https://docs.litellm.ai/release_notes";
@@ -81,7 +81,7 @@ interface SidebarAccountMenuProps {
 }
 
 const SidebarAccountMenu: React.FC<SidebarAccountMenuProps> = ({ onLogout, collapsed = false }) => {
-  const { userId, userEmail, userRoleLabel: userRole, premiumUser, accessToken } = useAuthorized();
+  const { userId, userEmail, userRoleLabel: userRole, accessToken } = useAuthorized();
   const { data: healthData } = useHealthReadinessDetails(accessToken);
   const version = healthData?.litellm_version;
   const disableShowPrompts = useDisableShowPrompts();
@@ -193,19 +193,6 @@ const SidebarAccountMenu: React.FC<SidebarAccountMenuProps> = ({ onLogout, colla
         </div>
 
         <div className="flex flex-col px-3 py-2">
-          <InfoRow icon={<Crown className="size-[17px]" />} label="Tier">
-            {premiumUser ? (
-              <Badge variant="outline" className="gap-1 border-warning/30 bg-warning/10 text-warning">
-                <Crown />
-                Premium
-              </Badge>
-            ) : (
-              <Badge variant="secondary" className="gap-1" title="Upgrade to Premium for advanced features">
-                <Crown />
-                Standard
-              </Badge>
-            )}
-          </InfoRow>
           <InfoRow icon={<ShieldCheck className="size-[17px]" />} label="Role">
             <Badge variant="secondary">{userRole}</Badge>
           </InfoRow>
diff --git a/ui/litellm-dashboard/src/components/alerting/dynamic_form.integration.test.tsx b/ui/litellm-dashboard/src/components/alerting/dynamic_form.integration.test.tsx
index 7764052173..4cceceb053 100644
--- a/ui/litellm-dashboard/src/components/alerting/dynamic_form.integration.test.tsx
+++ b/ui/litellm-dashboard/src/components/alerting/dynamic_form.integration.test.tsx
@@ -202,14 +202,15 @@ describe("DynamicForm change notifications", () => {
 });
 
 describe("DynamicForm premium gating", () => {
-  it("hides the control behind an upsell and registers no value when the user is not premium", async () => {
+  it("drops the row entirely, with no upsell, when the user is not premium", async () => {
     const user = userEvent.setup();
     const { handleSubmit } = renderForm({
       settings: [{ ...SETTINGS[1], premium_field: true }],
       premiumUser: false,
     });
 
-    expect(screen.getByText(/Enterprise Feature/)).toBeInTheDocument();
+    expect(screen.queryByText(/Enterprise Feature/)).not.toBeInTheDocument();
+    expect(screen.queryByText("region_name")).not.toBeInTheDocument();
     expect(screen.queryByDisplayValue("us-east")).not.toBeInTheDocument();
 
     await submit(user);
diff --git a/ui/litellm-dashboard/src/components/alerting/dynamic_form.tsx b/ui/litellm-dashboard/src/components/alerting/dynamic_form.tsx
index 42aa58ca0e..e986f3e27d 100644
--- a/ui/litellm-dashboard/src/components/alerting/dynamic_form.tsx
+++ b/ui/litellm-dashboard/src/components/alerting/dynamic_form.tsx
@@ -87,49 +87,41 @@ const DynamicForm: React.FC<DynamicFormProps> = ({
 
   return (
     <form onSubmit={form.handleSubmit(onFinish)} noValidate>
-      {alertingSettings.map((value, index) => (
-        <TableRow key={index}>
-          <TableCell>
-            <p className="text-sm">{value.field_name}</p>
-            <p className="mt-1 text-[0.65rem] italic text-muted-foreground">{value.field_description}</p>
-          </TableCell>
-          {value.premium_field && !premiumUser ? (
+      {alertingSettings
+        .filter((value) => !value.premium_field || premiumUser)
+        .map((value, index) => (
+          <TableRow key={index}>
             <TableCell>
-              <Button className="flex items-center justify-center">
-                <a href="https://forms.gle/W3U4PZpJGFHWtHyA9" target="_blank">
-                  âœ¨ Enterprise Feature
-                </a>
-              </Button>
+              <p className="text-sm">{value.field_name}</p>
+              <p className="mt-1 text-[0.65rem] italic text-muted-foreground">{value.field_description}</p>
             </TableCell>
-          ) : (
             <TableCell>{renderControl(value)}</TableCell>
-          )}
-          <TableCell>
-            {value.stored_in_db == true ? (
-              <Badge variant="secondary">
-                <CircleCheck />
-                In DB
-              </Badge>
-            ) : value.stored_in_db == false ? (
-              <Badge variant="outline">In Config</Badge>
-            ) : (
-              <Badge variant="outline">Not Set</Badge>
-            )}
-          </TableCell>
-          <TableCell>
-            <Button
-              type="button"
-              variant="ghost"
-              size="icon-sm"
-              aria-label={`Reset ${value.field_name}`}
-              onClick={() => handleResetField(value.field_name, index)}
-              className="text-destructive"
-            >
-              <Trash2 className="size-5" />
-            </Button>
-          </TableCell>
-        </TableRow>
-      ))}
+            <TableCell>
+              {value.stored_in_db == true ? (
+                <Badge variant="secondary">
+                  <CircleCheck />
+                  In DB
+                </Badge>
+              ) : value.stored_in_db == false ? (
+                <Badge variant="outline">In Config</Badge>
+              ) : (
+                <Badge variant="outline">Not Set</Badge>
+              )}
+            </TableCell>
+            <TableCell>
+              <Button
+                type="button"
+                variant="ghost"
+                size="icon-sm"
+                aria-label={`Reset ${value.field_name}`}
+                onClick={() => handleResetField(value.field_name, index)}
+                className="text-destructive"
+              >
+                <Trash2 className="size-5" />
+              </Button>
+            </TableCell>
+          </TableRow>
+        ))}
       <div>
         <Button type="submit">Update Settings</Button>
       </div>
diff --git a/ui/litellm-dashboard/src/components/common_components/PassThroughSecuritySection.tsx b/ui/litellm-dashboard/src/components/common_components/PassThroughSecuritySection.tsx
index c7aac09fd0..363f6cda35 100644
--- a/ui/litellm-dashboard/src/components/common_components/PassThroughSecuritySection.tsx
+++ b/ui/litellm-dashboard/src/components/common_components/PassThroughSecuritySection.tsx
@@ -14,31 +14,17 @@ const PassThroughSecuritySection: React.FC<PassThroughSecuritySectionProps> = ({
   authEnabled,
   onAuthChange,
 }) => {
+  if (!premiumUser) {
+    return null;
+  }
+
   return (
     <Card className="block p-6">
       <h3 className="mb-2 text-lg font-semibold text-foreground">Security</h3>
       <p className="mb-4 text-sm text-muted-foreground">
         When enabled, requests to this endpoint will require a valid LiteLLM Virtual Key
       </p>
-      {premiumUser ? (
-        <Switch checked={authEnabled} onCheckedChange={onAuthChange} />
-      ) : (
-        <div>
-          <div className="mb-3 flex items-center">
-            <Switch disabled checked={false} />
-            <span className="ml-2 text-sm text-muted-foreground">Authentication (Premium)</span>
-          </div>
-          <div className="rounded-lg border border-warning/20 bg-warning/10 p-3">
-            <p className="text-sm text-warning">
-              Setting authentication for pass-through endpoints is a LiteLLM Enterprise feature. Get a trial key{" "}
-              <a href="https://www.litellm.ai/#pricing" target="_blank" rel="noopener noreferrer" className="underline">
-                here
-              </a>
-              .
-            </p>
-          </div>
-        </div>
-      )}
+      <Switch checked={authEnabled} onCheckedChange={onAuthChange} />
     </Card>
   );
 };
diff --git a/ui/litellm-dashboard/src/components/common_components/PremiumLoggingSettings.test.tsx b/ui/litellm-dashboard/src/components/common_components/PremiumLoggingSettings.test.tsx
index 76b90bdca9..f8c04b8407 100644
--- a/ui/litellm-dashboard/src/components/common_components/PremiumLoggingSettings.test.tsx
+++ b/ui/litellm-dashboard/src/components/common_components/PremiumLoggingSettings.test.tsx
@@ -1,32 +1,15 @@
-import { readFileSync } from "fs";
-import { resolve } from "path";
 import React from "react";
 import { describe, it, expect, vi } from "vitest";
 import { renderWithProviders, screen } from "../../../tests/test-utils";
 import PremiumLoggingSettings from "./PremiumLoggingSettings";
 
-const SOURCE_PATH = resolve(process.cwd(), "src/components/common_components/PremiumLoggingSettings.tsx");
-
-const HARDCODED_PALETTE =
-  /\b(?:text|bg|border|hover:bg|hover:text|hover:border|dark:bg|dark:text|dark:border|ring|divide|fill|stroke)-(?:gray|slate|zinc|neutral|stone|red|blue|green|yellow|amber|orange|indigo|purple|pink|rose|teal|cyan|sky|violet|fuchsia|lime|emerald)-\d+(?:\/\d+)?\b/g;
-
-const SEMANTIC_TOKEN =
-  /\b(?:text|bg|border|hover:bg|hover:text|ring|divide|fill|stroke)-(?:foreground|muted-foreground|muted|background|card|popover|primary|secondary|destructive|border|input|accent|ring)(?:-foreground)?(?:\/\d+)?\b/g;
-
 describe("PremiumLoggingSettings", () => {
-  it("styles itself from semantic tokens instead of hardcoded palette classes", () => {
-    const source = readFileSync(SOURCE_PATH, "utf8");
+  it("renders nothing at all for a free user, with no Enterprise upsell", () => {
+    const { container } = renderWithProviders(<PremiumLoggingSettings value={[]} onChange={vi.fn()} />);
 
-    expect(source).toContain("export function PremiumLoggingSettings");
-    expect(source.match(SEMANTIC_TOKEN) ?? []).not.toHaveLength(0);
-    expect(source.match(HARDCODED_PALETTE) ?? []).toHaveLength(0);
-  });
-
-  it("shows the enterprise notice and withholds the editor from a free user", () => {
-    renderWithProviders(<PremiumLoggingSettings value={[]} onChange={vi.fn()} />);
-
-    expect(screen.getByText(/LiteLLM Enterprise feature/)).toBeInTheDocument();
-    expect(screen.getByText("âœ¨ langfuse-logging")).toBeInTheDocument();
+    expect(container).toBeEmptyDOMElement();
+    expect(screen.queryByText(/LiteLLM Enterprise feature/)).not.toBeInTheDocument();
+    expect(screen.queryByText("âœ¨ langfuse-logging")).not.toBeInTheDocument();
     expect(screen.queryByText("Logging Integrations")).not.toBeInTheDocument();
   });
 
diff --git a/ui/litellm-dashboard/src/components/common_components/PremiumLoggingSettings.tsx b/ui/litellm-dashboard/src/components/common_components/PremiumLoggingSettings.tsx
index d1f3cfe671..ec8fd14c95 100644
--- a/ui/litellm-dashboard/src/components/common_components/PremiumLoggingSettings.tsx
+++ b/ui/litellm-dashboard/src/components/common_components/PremiumLoggingSettings.tsx
@@ -1,5 +1,4 @@
 import React from "react";
-import { Badge } from "@/components/ui/badge";
 import LoggingSettings from "../team/LoggingSettings";
 
 interface PremiumLoggingSettingsProps {
@@ -18,28 +17,7 @@ export function PremiumLoggingSettings({
   onDisabledCallbacksChange,
 }: PremiumLoggingSettingsProps) {
   if (!premiumUser) {
-    return (
-      <div>
-        <div className="flex flex-wrap gap-2 mb-3">
-          <Badge variant="secondary" className="opacity-50">
-            âœ¨ langfuse-logging
-          </Badge>
-          <Badge variant="secondary" className="opacity-50">
-            âœ¨ datadog-logging
-          </Badge>
-        </div>
-        <div className="p-3 bg-muted border border-border rounded-lg">
-          <p className="text-sm text-muted-foreground">
-            Setting Key/Team logging settings is a LiteLLM Enterprise feature. Global Logging Settings are available for
-            all free users. Get a trial key{" "}
-            <a href="https://www.litellm.ai/#pricing" target="_blank" rel="noopener noreferrer" className="underline">
-              here
-            </a>
-            .
-          </p>
-        </div>
-      </div>
-    );
+    return null;
   }
 
   return (
diff --git a/ui/litellm-dashboard/src/components/leftnav.test.tsx b/ui/litellm-dashboard/src/components/leftnav.test.tsx
index c3e1f924d0..5069c81a55 100644
--- a/ui/litellm-dashboard/src/components/leftnav.test.tsx
+++ b/ui/litellm-dashboard/src/components/leftnav.test.tsx
@@ -187,7 +187,6 @@ describe("Sidebar (leftnav)", () => {
       "Guardrails Monitor",
       "Teams",
       "Internal Users",
-      "Organizations",
       "Access Groups",
       "Budgets",
       "API Reference",
@@ -469,7 +468,7 @@ describe("Sidebar (leftnav)", () => {
     });
   });
 
-  it("should show Organizations tab for organization admins", () => {
+  it("no longer shows the Organizations tab, even to organization admins", () => {
     mockUseAuthorized.mockReturnValue({
       userId: "org-admin-user-id",
       accessToken: "test-access-token",
@@ -506,7 +505,7 @@ describe("Sidebar (leftnav)", () => {
 
     renderWithProviders(<Sidebar {...defaultProps} />);
 
-    expect(screen.getByText("Organizations")).toBeInTheDocument();
+    expect(screen.queryByText("Organizations")).not.toBeInTheDocument();
   });
 
   it("marks the selected page's nav item active", () => {
diff --git a/ui/litellm-dashboard/src/components/leftnav.tsx b/ui/litellm-dashboard/src/components/leftnav.tsx
index 51ba36348e..4ab2845f96 100644
--- a/ui/litellm-dashboard/src/components/leftnav.tsx
+++ b/ui/litellm-dashboard/src/components/leftnav.tsx
@@ -28,7 +28,6 @@ import {
   Blocks,
   Bot,
   BookOpen,
-  Building2,
   Boxes,
   ChevronRight,
   Code2,
@@ -238,13 +237,6 @@ const menuGroups: MenuGroup[] = [
         roles: all_admin_roles,
       },
       { key: "users", page: "users", label: "Internal Users", icon: <User {...ICON} />, roles: all_admin_roles },
-      {
-        key: "organizations",
-        page: "organizations",
-        label: "Organizations",
-        icon: <Building2 {...ICON} />,
-        roles: all_admin_roles,
-      },
       {
         key: "access-groups",
         page: "access-groups",
diff --git a/ui/litellm-dashboard/src/components/view_logs/AuditLogsPanel.tsx b/ui/litellm-dashboard/src/components/view_logs/AuditLogsPanel.tsx
index 81bd4a19f7..f1f3ed2fe2 100644
--- a/ui/litellm-dashboard/src/components/view_logs/AuditLogsPanel.tsx
+++ b/ui/litellm-dashboard/src/components/view_logs/AuditLogsPanel.tsx
@@ -1,7 +1,6 @@
 import { useCallback, useState } from "react";
 import { useQuery, keepPreviousData } from "@tanstack/react-query";
 import { ColumnFiltersState, OnChangeFn, PaginationState } from "@tanstack/react-table";
-import { resolveLogoSrc } from "@/lib/assetPaths";
 import { uiAuditLogsCall } from "../networking";
 import { AuditLogEntry } from "./AuditLogsTableColumns";
 import { AuditLogsTable } from "./AuditLogsTable";
@@ -16,9 +15,6 @@ interface AuditLogsProps {
   premiumUser: boolean;
 }
 
-const asset_logos_folder = "/ui/assets/";
-const auditLogsPreviewImg = `${asset_logos_folder}audit-logs-preview.png`;
-
 const PAGE_SIZE = 50;
 
 interface AuditLogsResponse {
@@ -85,34 +81,6 @@ export default function AuditLogsPanel({
     setDrawerOpen(true);
   }, []);
 
-  if (!premiumUser) {
-    return (
-      <div style={{ textAlign: "center", marginTop: "20px" }}>
-        <h1 style={{ display: "block", marginBottom: "10px" }}>âœ¨ Enterprise Feature.</h1>
-        <p style={{ display: "block", marginBottom: "10px" }}>
-          This is a LiteLLM Enterprise feature, and requires a valid key to use.
-        </p>
-        <p style={{ display: "block", marginBottom: "20px", fontStyle: "italic" }}>
-          Here&apos;s a preview of what Audit Logs offer:
-        </p>
-        <img
-          src={resolveLogoSrc(auditLogsPreviewImg)}
-          alt="Audit Logs Preview"
-          style={{
-            maxWidth: "100%",
-            maxHeight: "700px",
-            borderRadius: "8px",
-            boxShadow: "0 4px 8px rgba(0,0,0,0.1)",
-            margin: "0 auto",
-          }}
-          onError={(e) => {
-            (e.target as HTMLImageElement).style.display = "none";
-          }}
-        />
-      </div>
-    );
-  }
-
   return (
     <>
       <div className="flex items-center justify-between mb-4">
```
