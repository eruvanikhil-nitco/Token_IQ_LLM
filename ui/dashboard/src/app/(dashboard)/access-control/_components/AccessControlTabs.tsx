"use client";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import TabScroller from "@/components/shared/TabScroller";
import AuditLogView from "@/components/Settings/AdminSettings/AuditLog/AuditLogView";
import { all_admin_roles } from "@/utils/roles";
import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
import useIsOrgAdmin from "@/app/(dashboard)/hooks/useIsOrgAdmin";
import { useTeams } from "@/app/(dashboard)/hooks/teams/useTeams";
import { useUISettings } from "@/app/(dashboard)/hooks/uiSettings/useUISettings";
import { useTabRouting } from "@/app/(dashboard)/hooks/useTabRouting";
import { createTabRoutes } from "@/utils/tabRoutes";
import { ViewUserDashboard } from "@/app/(dashboard)/users/_components";
import { AccessGroupsPage } from "@/app/(dashboard)/access-groups/_components/AccessGroupsPage";

import {
  ACCESS_CONTROL_BASE_TAB,
  ACCESS_CONTROL_TABS,
  ACCESS_CONTROL_TAB_LABELS,
  visibleAccessControlTabs,
  type AccessControlTab,
} from "../accessControlTabs";

const routes = createTabRoutes("access-control", ACCESS_CONTROL_TABS);

/**
 * Administration > Access Control: Users, Access Groups and the audit log.
 *
 * Users and Access Groups were sidebar entries; the audit log was a tab inside Admin Settings,
 * which is why it has no legacy address of its own. Each tab keeps its own URL, so the old
 * `?page=users` and `?page=access-groups` links still arrive at the right one.
 */
export default function AccessControlTabs() {
  const { accessToken, token, userId, userRole } = useAuthorized();
  const isOrgAdmin = useIsOrgAdmin();
  const { data: teams } = useTeams();
  const { data: uiSettings } = useUISettings();

  const viewer = {
    userRole,
    isOrgAdmin,
    enabledPagesInternalUsers: uiSettings?.values?.enabled_ui_pages_internal_users ?? null,
    adminRoles: all_admin_roles,
  };
  const visible = visibleAccessControlTabs(viewer);

  const baseTabKey = visible.includes(ACCESS_CONTROL_BASE_TAB) ? ACCESS_CONTROL_BASE_TAB : (visible[0] ?? "");
  const { activeKey, onTabChange } = useTabRouting({ routes, baseTabKey, visibleKeys: visible });

  const panel = (tab: AccessControlTab) => {
    if (tab === "users") {
      return (
        <ViewUserDashboard
          userID={userId}
          userRole={userRole}
          token={token}
          teams={teams ?? null}
          accessToken={accessToken}
        />
      );
    }
    return tab === "access-groups" ? <AccessGroupsPage /> : <AuditLogView />;
  };

  if (visible.length === 0) {
    return null;
  }

  return (
    <Tabs value={activeKey} onValueChange={onTabChange}>
      <TabScroller className="mb-4">
        <TabsList variant="line" className="h-auto w-max flex-nowrap justify-start">
          {visible.map((tab) => (
            <TabsTrigger key={tab} value={tab} className="flex-none">
              {ACCESS_CONTROL_TAB_LABELS[tab]}
            </TabsTrigger>
          ))}
        </TabsList>
      </TabScroller>
      {visible.map((tab) => (
        <TabsContent key={tab} value={tab}>
          {panel(tab)}
        </TabsContent>
      ))}
    </Tabs>
  );
}
