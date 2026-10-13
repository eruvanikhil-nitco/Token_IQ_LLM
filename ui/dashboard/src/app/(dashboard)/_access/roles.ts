/**
 * The blueprint's eight roles, as a reading of what a person already is.
 *
 * Authorisation changes fail open. Today's roles are wired into the sign-in path, every management
 * endpoint and the sidebar; the blueprint's eight are a different vocabulary with different powers,
 * and mapping one onto the other wrongly does not throw, it grants. A Finance Admin who inherited
 * `proxy_admin` because a mapping defaulted that way could change settings, and nobody would see a
 * stack trace.
 *
 * So this module never grants. `readsAs` answers which of the eight a person signed in today
 * already is, and `allowedPages` is defined as an intersection with what that person can already
 * see, which makes over-granting structurally impossible rather than merely unintended. A role
 * nothing maps to reads as null and sees nothing.
 *
 * What it does not do is take pages away. The intersection would hide six entries from an Admin
 * Viewer, because the blueprint's Org Viewer is read-only over finance rather than over
 * configuration, and hiding an entry somebody has today is the owner's call. `pagesTheBlueprintHides`
 * states that difference so it can be decided rather than discovered.
 */

import { menuGroups } from "@/components/leftnav";

export const BLUEPRINT_ROLES = [
  "org-owner",
  "org-admin",
  "finance-admin",
  "org-viewer",
  "team-lead-manage",
  "team-lead-read",
  "team-member",
  "service-account",
] as const;

export type BlueprintRole = (typeof BLUEPRINT_ROLES)[number];

const ROLE_LABELS: Readonly<Record<BlueprintRole, string>> = {
  "org-owner": "Org Owner",
  "org-admin": "Org Admin",
  "finance-admin": "Finance Admin",
  "org-viewer": "Org Viewer",
  "team-lead-manage": "Team Lead (Manage)",
  "team-lead-read": "Team Lead (Read-only)",
  "team-member": "Team Member",
  "service-account": "Service Account",
};

export function roleLabel(role: BlueprintRole): string {
  return ROLE_LABELS[role];
}

/**
 * Which blueprint role a person signed in today already is.
 *
 * Deliberately partial. `team` is the JWT identity a gateway caller presents and `customer` is an
 * end user of somebody else's application: neither is a person who opens Token IQ, and giving
 * either a blueprint role would be inventing an account. Anything unrecognised reads as null, which
 * every function here treats as seeing nothing.
 */
export function readsAs(userRole: string | null | undefined): BlueprintRole | null {
  switch (userRole) {
    case "proxy_admin":
    case "Admin":
      return "org-owner";
    case "proxy_admin_viewer":
    case "Admin Viewer":
      return "org-viewer";
    case "org_admin":
    case "Org Admin":
      return "org-admin";
    case "internal_user":
    case "Internal User":
    case "internal_user_viewer":
    case "Internal Viewer":
      return "team-member";
    default:
      return null;
  }
}

/** What the blueprint says a role may do with one area, in its own words. */
export type MatrixValue = string;

export const AREAS = [
  "cost-data",
  "invoice-reconciliation",
  "budgets",
  "recommendations",
  "savings-simulator",
  "anomalies",
  "reports",
  "data-sources",
  "organization",
  "pricing",
  "users-and-roles",
  "settings",
  "projects-and-keys",
  "team-home",
  "audit-log",
] as const;

export type Area = (typeof AREAS)[number];

/**
 * The blueprint's own permission matrix, as data.
 *
 * Its words rather than a normalised enum, because "Own team" and "View" and "View; upload
 * invoices" say different things and flattening them to one level is where a reading becomes a
 * guess. The only thing read mechanically is "—", which means this role does not have the area at
 * all. The scoped values become a scope in task 3, where the server enforces them.
 */
const MATRIX: Readonly<Record<Area, Readonly<Record<BlueprintRole, MatrixValue>>>> = {
  "cost-data": {
    "org-owner": "All",
    "org-admin": "All",
    "finance-admin": "All",
    "org-viewer": "All",
    "team-lead-manage": "Own team",
    "team-lead-read": "Own team",
    "team-member": "Own usage",
    "service-account": "By scope",
  },
  "invoice-reconciliation": {
    "org-owner": "Manage",
    "org-admin": "Manage",
    "finance-admin": "Manage",
    "org-viewer": "View",
    "team-lead-manage": "—",
    "team-lead-read": "—",
    "team-member": "—",
    "service-account": "—",
  },
  budgets: {
    "org-owner": "Manage",
    "org-admin": "Manage",
    "finance-admin": "Manage",
    "org-viewer": "View",
    "team-lead-manage": "View; request changes",
    "team-lead-read": "View",
    "team-member": "—",
    "service-account": "—",
  },
  recommendations: {
    "org-owner": "Manage",
    "org-admin": "Manage",
    "finance-admin": "View",
    "org-viewer": "View",
    "team-lead-manage": "Assign within team",
    "team-lead-read": "View",
    "team-member": "—",
    "service-account": "—",
  },
  "savings-simulator": {
    "org-owner": "Manage",
    "org-admin": "Manage",
    "finance-admin": "Manage",
    "org-viewer": "View",
    "team-lead-manage": "Own team",
    "team-lead-read": "View",
    "team-member": "—",
    "service-account": "—",
  },
  anomalies: {
    "org-owner": "Manage",
    "org-admin": "Manage",
    "finance-admin": "Own subscriptions",
    "org-viewer": "View",
    "team-lead-manage": "Own team",
    "team-lead-read": "View",
    "team-member": "Own limit alerts",
    "service-account": "—",
  },
  reports: {
    "org-owner": "Manage",
    "org-admin": "Manage",
    "finance-admin": "Manage",
    "org-viewer": "View, export",
    "team-lead-manage": "Own team",
    "team-lead-read": "View, export",
    "team-member": "Own usage",
    "service-account": "Read API",
  },
  "data-sources": {
    "org-owner": "Manage",
    "org-admin": "Manage",
    "finance-admin": "View; upload invoices",
    "org-viewer": "—",
    "team-lead-manage": "—",
    "team-lead-read": "—",
    "team-member": "—",
    "service-account": "Ingest only",
  },
  organization: {
    "org-owner": "Manage",
    "org-admin": "Manage",
    "finance-admin": "View",
    "org-viewer": "—",
    "team-lead-manage": "—",
    "team-lead-read": "—",
    "team-member": "—",
    "service-account": "—",
  },
  pricing: {
    "org-owner": "Manage",
    "org-admin": "Manage",
    "finance-admin": "Manage",
    "org-viewer": "—",
    "team-lead-manage": "—",
    "team-lead-read": "—",
    "team-member": "—",
    "service-account": "—",
  },
  "users-and-roles": {
    "org-owner": "Manage",
    "org-admin": "Manage",
    "finance-admin": "View",
    "org-viewer": "View",
    "team-lead-manage": "—",
    "team-lead-read": "—",
    "team-member": "—",
    "service-account": "—",
  },
  settings: {
    "org-owner": "Manage",
    "org-admin": "Manage",
    "finance-admin": "—",
    "org-viewer": "—",
    "team-lead-manage": "—",
    "team-lead-read": "—",
    "team-member": "—",
    "service-account": "—",
  },
  "projects-and-keys": {
    "org-owner": "Manage",
    "org-admin": "Manage",
    "finance-admin": "—",
    "org-viewer": "—",
    "team-lead-manage": "Own team",
    "team-lead-read": "View",
    "team-member": "View own",
    "service-account": "—",
  },
  "team-home": {
    "org-owner": "—",
    "org-admin": "—",
    "finance-admin": "—",
    "org-viewer": "—",
    "team-lead-manage": "Own team",
    "team-lead-read": "Own team",
    "team-member": "—",
    "service-account": "—",
  },
  "audit-log": {
    "org-owner": "View",
    "org-admin": "View",
    "finance-admin": "View",
    "org-viewer": "View",
    "team-lead-manage": "Team activity",
    "team-lead-read": "Team activity",
    "team-member": "—",
    "service-account": "—",
  },
};

const NOT_HELD = "—";

/** What the blueprint says, word for word, so a screen can show its own vocabulary. */
export function matrixValue(role: BlueprintRole, area: Area): MatrixValue {
  return MATRIX[area][role];
}

/** Whether a role has an area at all. The one thing read mechanically from the matrix. */
export function permits(role: BlueprintRole | null, area: Area): boolean {
  return role !== null && MATRIX[area][role] !== NOT_HELD;
}

/**
 * Which sidebar pages belong to each area.
 *
 * Partial on purpose. The matrix covers what Token IQ does with money; the gateway's own pages, the
 * playground, guardrails, MCP servers and the model hub are not rows in it, and a page in no area
 * keeps whatever rule it has today rather than being denied by a matrix that never mentioned it.
 */
const AREA_PAGES: Readonly<Record<Area, readonly string[]>> = {
  "cost-data": ["overview", "new_usage", "usage", "logs"],
  "invoice-reconciliation": ["ledger"],
  budgets: ["budgets"],
  recommendations: ["recommendations"],
  "savings-simulator": ["cost-optimization"],
  anomalies: [],
  reports: [],
  "data-sources": ["data-sources"],
  organization: ["organization"],
  pricing: ["attribution", "cost-tracking"],
  "users-and-roles": ["access-control"],
  settings: ["settings", "router-settings"],
  "projects-and-keys": ["api-keys"],
  "team-home": [],
  "audit-log": [],
};

export function areaOf(page: string): Area | null {
  return AREAS.find((area) => AREA_PAGES[area].includes(page)) ?? null;
}

/** An entry with no role list is open to everyone, which is how the sidebar already reads it. */
function listAdmits(roles: readonly string[] | undefined, userRole: string | null | undefined): boolean {
  if (roles === undefined) {
    return true;
  }
  return userRole != null && roles.includes(userRole);
}

/** Every page the sidebar shows this role today, which is the ceiling nothing here may exceed. */
export function pagesVisibleToday(userRole: string | null | undefined): readonly string[] {
  return menuGroups.flatMap((group) =>
    listAdmits(group.roles, userRole)
      ? group.items.flatMap((item) => (listAdmits(item.roles, userRole) ? [item.page] : []))
      : [],
  );
}

/**
 * The pages a person may open, as an intersection with what they can already open.
 *
 * The intersection is the safety property, not a tidiness: a mapping that named a stronger role, or
 * an area table that granted something new, still cannot widen this past today's answer. An
 * unrecognised role reads as null and gets nothing.
 */
export function allowedPages(userRole: string | null | undefined): readonly string[] {
  const role = readsAs(userRole);
  if (role === null) {
    return [];
  }
  return pagesVisibleToday(userRole).filter((page) => {
    const area = areaOf(page);
    return area === null || permits(role, area);
  });
}

/**
 * What adopting the matrix in the sidebar would take away from this role.
 *
 * The difference exists and is worth deciding rather than discovering: an Admin Viewer reads as Org
 * Viewer, and the blueprint's Org Viewer is read-only over finance rather than over configuration,
 * so the matrix hides entries that role has today. Removing an entry somebody already has is the
 * owner's call, so this reports the difference and nothing acts on it yet.
 */
export function pagesTheBlueprintHides(userRole: string | null | undefined): readonly string[] {
  const allowed = allowedPages(userRole);
  return pagesVisibleToday(userRole).filter((page) => !allowed.includes(page));
}

/**
 * Whether an installation can actually create a person with this role.
 *
 * Four of the eight have no underlying role to grant, so a screen offering them would be offering
 * an account nobody can sign in as. Service Account is separate again: it is a token rather than a
 * person, and the gateway already issues those.
 */
export const GRANTABLE: Readonly<Record<BlueprintRole, string | null>> = {
  "org-owner": "proxy_admin",
  "org-admin": "org_admin",
  "finance-admin": null,
  "org-viewer": "proxy_admin_viewer",
  "team-lead-manage": null,
  "team-lead-read": null,
  "team-member": "internal_user",
  "service-account": null,
};

const UNGRANTABLE_REASONS: Readonly<Record<BlueprintRole, string>> = {
  "org-owner": "",
  "org-admin": "",
  "finance-admin":
    "Needs a role that manages invoices, budgets and pricing but not settings, which no underlying role is",
  "org-viewer": "",
  "team-lead-manage": "Needs a role scoped to one team, which arrives when scope is enforced where the data is read",
  "team-lead-read": "Needs the same team scope, read-only",
  "team-member": "",
  "service-account": "Issued as a virtual key rather than as a person who signs in",
};

export function grantableNow(role: BlueprintRole): boolean {
  return GRANTABLE[role] !== null;
}

/** Why a role cannot be granted yet, or null when it can. */
export function whyNotGrantable(role: BlueprintRole): string | null {
  return grantableNow(role) ? null : UNGRANTABLE_REASONS[role];
}
