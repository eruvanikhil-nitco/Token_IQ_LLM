import { isAdminRole, isUserTeamAdminForAnyTeam } from "@/utils/roles";
import type { Team } from "@/components/key_team_helpers/key_list";

export const ORGANIZATION_TABS = ["teams", "projects"] as const;

export type OrganizationTab = (typeof ORGANIZATION_TABS)[number];

export const ORGANIZATION_BASE_TAB: OrganizationTab = "teams";

export const ORGANIZATION_TAB_LABELS: Readonly<Record<OrganizationTab, string>> = {
  teams: "Teams",
  projects: "Projects",
};

/** The legacy `?page=` id each tab used to be reachable as, so old links still resolve. */
export const ORGANIZATION_TAB_LEGACY_PAGE: Readonly<Record<OrganizationTab, string>> = {
  teams: "teams",
  projects: "projects",
};

export interface OrganizationViewer {
  userRole: string;
  userId: string | null;
  teams: Team[] | null;
  enabledPagesInternalUsers?: string[] | null;
  enableProjectsUI?: boolean;
  internalUserRoles: readonly string[];
  adminRoles: readonly string[];
}

/**
 * Which tabs of Administration > Organization this viewer may see.
 *
 * Teams and Projects were two sidebar entries with two different sets of rules, and merging them
 * into one entry moves those rules inside the page. Returning them from one place is what keeps the
 * sidebar and the page agreeing: a viewer who may not open Projects must neither see the tab nor
 * see an entry that leads nowhere.
 */
export function visibleOrganizationTabs(viewer: OrganizationViewer): readonly OrganizationTab[] {
  const admin = isAdminRole(viewer.userRole);
  const enabledPages = viewer.enabledPagesInternalUsers;

  const permitted = (legacyPage: string): boolean => admin || enabledPages == null || enabledPages.includes(legacyPage);

  const teams = permitted(ORGANIZATION_TAB_LEGACY_PAGE.teams);

  const projectRoles = [...viewer.adminRoles, ...viewer.internalUserRoles];
  const featureOn = viewer.enableProjectsUI ?? false;
  const roleAllowsProjects = projectRoles.includes(viewer.userRole);
  const administersATeam = admin || isUserTeamAdminForAnyTeam(viewer.teams, viewer.userId ?? "");
  const allowedProjectsPage = permitted(ORGANIZATION_TAB_LEGACY_PAGE.projects);
  const projectsOfferedToRole = featureOn && roleAllowsProjects;
  const projects = projectsOfferedToRole && administersATeam && allowedProjectsPage;

  return ORGANIZATION_TABS.filter((tab) => (tab === "teams" ? teams : projects));
}

/** Whether the merged sidebar entry leads anywhere at all for this viewer. */
export function organizationIsVisible(viewer: OrganizationViewer): boolean {
  return visibleOrganizationTabs(viewer).length > 0;
}
