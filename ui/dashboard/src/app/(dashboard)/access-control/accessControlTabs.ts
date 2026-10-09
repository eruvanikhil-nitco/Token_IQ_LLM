export const ACCESS_CONTROL_TABS = ["users", "access-groups", "audit-log"] as const;

export type AccessControlTab = (typeof ACCESS_CONTROL_TABS)[number];

export const ACCESS_CONTROL_BASE_TAB: AccessControlTab = "users";

export const ACCESS_CONTROL_TAB_LABELS: Readonly<Record<AccessControlTab, string>> = {
  users: "Users",
  "access-groups": "Access Groups",
  "audit-log": "Audit Log",
};

/**
 * The legacy `?page=` id each tab was reachable as, so old links still resolve.
 *
 * The audit log has none: it was a tab inside Admin Settings rather than a page of its own, so
 * nothing ever linked to it directly and there is no old address to keep alive.
 */
export const ACCESS_CONTROL_TAB_LEGACY_PAGE: Readonly<Partial<Record<AccessControlTab, string>>> = {
  users: "users",
  "access-groups": "access-groups",
};

export interface AccessControlViewer {
  userRole: string;
  isOrgAdmin: boolean;
  enabledPagesInternalUsers?: string[] | null;
  adminRoles: readonly string[];
}

/**
 * Which tabs of Administration > Access Control this viewer may see.
 *
 * Users, Access Groups and the audit log were three things under three rules that collapse to two.
 * All three required an admin role, and an admin role skipped the per-installation page list, so
 * for an admin the list never applied. The one asymmetry is that Users also admitted an
 * organization admin by membership, who holds no admin role and therefore does face the list.
 *
 * Both the sidebar and the page ask this, so a tab cannot appear to someone who was never allowed
 * the page behind it.
 */
export function visibleAccessControlTabs(viewer: AccessControlViewer): readonly AccessControlTab[] {
  const adminRole = viewer.adminRoles.includes(viewer.userRole);
  const enabledPages = viewer.enabledPagesInternalUsers;
  const listAllowsUsers = enabledPages == null || enabledPages.includes(ACCESS_CONTROL_TAB_LEGACY_PAGE.users ?? "");

  const allowed: Readonly<Record<AccessControlTab, boolean>> = {
    users: adminRole || (viewer.isOrgAdmin && listAllowsUsers),
    "access-groups": adminRole,
    "audit-log": adminRole,
  };

  return ACCESS_CONTROL_TABS.filter((tab) => allowed[tab]);
}

/** Whether the merged sidebar entry leads anywhere at all for this viewer. */
export function accessControlIsVisible(viewer: AccessControlViewer): boolean {
  return visibleAccessControlTabs(viewer).length > 0;
}
