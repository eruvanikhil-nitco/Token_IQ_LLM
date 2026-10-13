import { describe, expect, it } from "vitest";

import { all_admin_roles } from "@/utils/roles";

import {
  ACCESS_CONTROL_BASE_TAB,
  ACCESS_CONTROL_TABS,
  accessControlIsVisible,
  visibleAccessControlTabs,
  type AccessControlViewer,
} from "./accessControlTabs";

/**
 * Users, Access Groups and the audit log were three things under three different rules, and the
 * merge moves those rules inside the page. These pin the rules rather than the layout, because the
 * failure to avoid is a tab appearing to somebody who was never allowed the page behind it.
 */

const ADMIN = "proxy_admin";
const INTERNAL_USER = "Internal User";

const viewer = (over: Partial<AccessControlViewer> = {}): AccessControlViewer => ({
  userRole: ADMIN,
  isOrgAdmin: false,
  enabledPagesInternalUsers: null,
  adminRoles: all_admin_roles,
  ...over,
});

describe("which tabs Administration > Access Control shows", () => {
  it("gives an admin every tab, in a fixed order", () => {
    expect(visibleAccessControlTabs(viewer())).toEqual(["users", "roles", "access-groups", "audit-log"]);
  });

  it("shows the roles tab to whoever may already see who the users are", () => {
    // It describes the roles an installation has rather than granting anything, so it follows the
    // rule of the Users tab beside it rather than inventing a third one.
    const orgAdmin = viewer({ userRole: INTERNAL_USER, isOrgAdmin: true });

    expect(visibleAccessControlTabs(orgAdmin)).toContain("roles");
    expect(visibleAccessControlTabs(viewer({ userRole: INTERNAL_USER }))).not.toContain("roles");
  });

  it("gives a non-admin nothing, because every tab here was an admin-only page", () => {
    const seen = visibleAccessControlTabs(viewer({ userRole: INTERNAL_USER }));

    expect(seen).toEqual([]);
    expect(accessControlIsVisible(viewer({ userRole: INTERNAL_USER }))).toBe(false);
  });

  it("admits an organization admin to Users only, which is what Users alone allowed", () => {
    // The one asymmetry between the three. Access Groups never admitted an org admin, and the
    // audit log was reachable only through admin-only Admin Settings.
    const orgAdmin = viewer({ userRole: INTERNAL_USER, isOrgAdmin: true });

    expect(visibleAccessControlTabs(orgAdmin)).toEqual(["users", "roles"]);
    expect(accessControlIsVisible(orgAdmin)).toBe(true);
  });

  it("ignores the per-installation allowlist for an admin, as the sidebar always did", () => {
    const restricted = viewer({ enabledPagesInternalUsers: [] });

    expect(visibleAccessControlTabs(restricted)).toEqual(["users", "roles", "access-groups", "audit-log"]);
  });

  it("applies the allowlist to an organization admin, tab by tab", () => {
    const named = viewer({ userRole: INTERNAL_USER, isOrgAdmin: true, enabledPagesInternalUsers: ["users"] });
    const notNamed = viewer({ userRole: INTERNAL_USER, isOrgAdmin: true, enabledPagesInternalUsers: ["logs"] });

    expect(visibleAccessControlTabs(named)).toEqual(["users", "roles"]);
    expect(visibleAccessControlTabs(notNamed)).toEqual([]);
  });

  it("keeps the audit log out of the allowlist, having never had a page id to be named by", () => {
    // It was a tab inside Admin Settings, so no installation could have listed it, and treating a
    // missing entry as a denial would hide it from every admin whose installation sets the list.
    const listed = viewer({ enabledPagesInternalUsers: ["users"] });

    expect(visibleAccessControlTabs(listed)).toContain("audit-log");
  });

  it("names a base tab that is one of the tabs", () => {
    expect(ACCESS_CONTROL_TABS).toContain(ACCESS_CONTROL_BASE_TAB);
  });
});
