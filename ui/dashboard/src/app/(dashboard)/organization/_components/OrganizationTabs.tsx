"use client";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import TabScroller from "@/components/shared/TabScroller";
import Teams from "@/components/Teams";
import { all_admin_roles, internalUserRoles } from "@/utils/roles";
import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
import { useTeams } from "@/app/(dashboard)/hooks/teams/useTeams";
import { useUISettings } from "@/app/(dashboard)/hooks/uiSettings/useUISettings";
import { useTabRouting } from "@/app/(dashboard)/hooks/useTabRouting";
import { createTabRoutes } from "@/utils/tabRoutes";
import { ProjectsPage } from "@/app/(dashboard)/projects/_components/ProjectsPage";

import {
  ORGANIZATION_BASE_TAB,
  ORGANIZATION_TAB_LABELS,
  ORGANIZATION_TABS,
  visibleOrganizationTabs,
  type OrganizationTab,
} from "../organizationTabs";

const routes = createTabRoutes("organization", ORGANIZATION_TABS);

/**
 * Administration > Organization: Teams and Projects, which were two sidebar entries.
 *
 * Each tab keeps its own URL, so `/organization/` and `/organization/projects/` are both
 * addressable and the legacy `?page=teams` and `?page=projects` links still arrive at the right
 * one. Which tabs exist is decided by `visibleOrganizationTabs`, the same function the sidebar
 * asks, because a viewer who cannot open Projects must not be shown the tab.
 */
export default function OrganizationTabs() {
  const { accessToken, userId, userRole, premiumUser } = useAuthorized();
  const { data: teams } = useTeams();
  const { data: uiSettings } = useUISettings();

  // The same two settings the sidebar reads, from the same place. Taking them as props would
  // let a direct link to a tab show a feature the installation has turned off.
  const enableProjectsUI = Boolean(uiSettings?.values?.enable_projects_ui ?? true);
  const enabledPagesInternalUsers = uiSettings?.values?.enabled_ui_pages_internal_users ?? null;

  const viewer = {
    userRole,
    userId,
    teams: teams ?? null,
    enabledPagesInternalUsers,
    enableProjectsUI,
    internalUserRoles,
    adminRoles: all_admin_roles,
  };
  const visible = visibleOrganizationTabs(viewer);

  const baseTabKey = visible.includes(ORGANIZATION_BASE_TAB) ? ORGANIZATION_BASE_TAB : (visible[0] ?? "");
  const { activeKey, onTabChange } = useTabRouting({ routes, baseTabKey, visibleKeys: visible });

  const panel = (tab: OrganizationTab) =>
    tab === "teams" ? (
      <Teams accessToken={accessToken} userID={userId} userRole={userRole} premiumUser={premiumUser ?? false} />
    ) : (
      <ProjectsPage />
    );

  if (visible.length === 0) {
    return null;
  }

  return (
    <Tabs value={activeKey} onValueChange={onTabChange}>
      <TabScroller className="mb-4">
        <TabsList variant="line" className="h-auto w-max flex-nowrap justify-start">
          {visible.map((tab) => (
            <TabsTrigger key={tab} value={tab} className="flex-none">
              {ORGANIZATION_TAB_LABELS[tab]}
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
