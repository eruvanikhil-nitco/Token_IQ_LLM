/**
 * The admin roles that may read this page but not change it.
 *
 * Spelled out rather than derived. `isViewOnlyRole` in `utils/roles` looks like the right helper
 * and is not: it omits `proxy_admin_viewer`, which the role enum documents as view-only, and
 * nothing outside its own module calls it. Deriving from `rolesWithWriteAccess` is also wrong
 * here, because that list omits `org_admin`, whom the blueprint gives manage.
 */
const READ_ONLY_ADMIN_ROLES: readonly string[] = ["Admin Viewer", "proxy_admin_viewer"];

/**
 * The blueprint's four tabs, in the order it lists them.
 *
 * Declared in full and in order even though they arrive one at a time, so a tab landing later goes
 * where the blueprint puts it rather than on the end. `built` is what decides whether it is offered:
 * a tab that renders nothing is worse than a tab that is not there yet, which is the blueprint's own
 * rule about empty states.
 */
export const DATA_SOURCES_TAB_ORDER = ["overview", "accounts", "gateway", "uploads"] as const;

export type DataSourcesTab = (typeof DATA_SOURCES_TAB_ORDER)[number];

interface TabSpec {
  label: string;
  description: string;
  built: boolean;
}

export const DATA_SOURCES_TABS: Readonly<Record<DataSourcesTab, TabSpec>> = {
  overview: {
    label: "Overview",
    description:
      "Can the data be trusted? Health and freshness of every source, invoice coverage, and data quality issues to fix.",
    built: true,
  },
  accounts: {
    label: "Accounts",
    description:
      "Every connected account. Each row opens its raw records: the data exactly as received, before Token IQ priced or allocated it.",
    built: true,
  },
  gateway: {
    label: "Gateway",
    description: "The Token IQ gateway: observed traffic, request log, virtual keys and upstream endpoints.",
    built: false,
  },
  uploads: {
    label: "Uploads",
    description: "Invoices, workspace exports and contracts that have no API, uploaded or forwarded by email.",
    built: false,
  },
};

/** Manage, read, or cannot open it at all. */
export type DataSourcesAccess = "manage" | "view" | "hidden";

export interface DataSourcesViewer {
  userRole: string;
  adminRoles: readonly string[];
}

/**
 * What this viewer may do with Data Sources.
 *
 * The blueprint gives the page `acc:{A:'e',F:'v',V:'n',L:'n',R:'n',M:'n'}`: Org Admin manages it,
 * Finance Admin reads it, and no other role sees it. Finance Admin does not exist yet, nor do six of
 * the blueprint's eight roles; they are build step 4. What exists is an admin tier whose read-only
 * members are already treated this way elsewhere, so the rule maps onto that: an admin role opens
 * the page, and a read-only one gets a view rather than the actions.
 *
 * The page is hidden rather than emptied for everyone else, because its own description is "every
 * place Token IQ gets usage and cost data from", which names accounts a Team Member has no business
 * enumerating.
 */
export function dataSourcesAccess(viewer: DataSourcesViewer): DataSourcesAccess {
  if (!viewer.adminRoles.includes(viewer.userRole)) {
    return "hidden";
  }
  return READ_ONLY_ADMIN_ROLES.includes(viewer.userRole) ? "view" : "manage";
}

/**
 * Which tabs to render for this viewer.
 *
 * A view and a manage see the same tabs: the difference is the actions on them, not what can be
 * read. Keeping that here rather than per tab is what stops the two drifting into different pages.
 */
export function visibleDataSourcesTabs(viewer: DataSourcesViewer): readonly DataSourcesTab[] {
  if (dataSourcesAccess(viewer) === "hidden") {
    return [];
  }
  return DATA_SOURCES_TAB_ORDER.filter((tab) => DATA_SOURCES_TABS[tab].built);
}

/** Whether the sidebar entry leads anywhere at all for this viewer. */
export function dataSourcesIsVisible(viewer: DataSourcesViewer): boolean {
  return visibleDataSourcesTabs(viewer).length > 0;
}
