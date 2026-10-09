import { describe, expect, it } from "vitest";

import { all_admin_roles, internalUserRoles } from "@/utils/roles";
import type { Team } from "@/components/key_team_helpers/key_list";

import {
  ORGANIZATION_BASE_TAB,
  ORGANIZATION_TABS,
  organizationIsVisible,
  visibleOrganizationTabs,
  type OrganizationViewer,
} from "./organizationTabs";

/**
 * Teams and Projects were two sidebar entries under two different sets of rules. Merging them into
 * one entry moves those rules inside the page, so these pin the rules rather than the layout: a
 * viewer who could not open Projects before must not get it through a tab now.
 */

const ADMIN = "proxy_admin";
const INTERNAL_USER = "Internal User";
const OUTSIDER = "customer";

const teamAdminOf = (userId: string): Team[] => [{ team_id: "t1", team_alias: "t1", members_with_roles: [{ user_id: userId, role: "admin" }] } as unknown as Team];

const viewer = (over: Partial<OrganizationViewer> = {}): OrganizationViewer => ({
  userRole: ADMIN,
  userId: "u1",
  teams: null,
  enabledPagesInternalUsers: null,
  enableProjectsUI: true,
  internalUserRoles,
  adminRoles: all_admin_roles,
  ...over,
});

describe("which tabs Administration > Organization shows", () => {
  it("gives an admin both tabs, in a fixed order", () => {
    expect(visibleOrganizationTabs(viewer())).toEqual(["teams", "projects"]);
  });

  it("hides Projects entirely when the feature is off", () => {
    expect(visibleOrganizationTabs(viewer({ enableProjectsUI: false }))).toEqual(["teams"]);
  });

  it("hides Projects from a role that was never allowed it", () => {
    expect(visibleOrganizationTabs(viewer({ userRole: OUTSIDER }))).toEqual(["teams"]);
  });

  it("hides Projects from an unlisted role even when that viewer administers a team", () => {
    // The role check on its own. Without this, dropping it leaves every other condition still
    // blocking the case above, so the rule could be deleted with the suite staying green.
    const seen = visibleOrganizationTabs(viewer({ userRole: OUTSIDER, teams: teamAdminOf("u1") }));

    expect(seen).toEqual(["teams"]);
  });

  it("hides Projects from an internal user who administers no team", () => {
    expect(visibleOrganizationTabs(viewer({ userRole: INTERNAL_USER, teams: [] }))).toEqual(["teams"]);
  });

  it("shows Projects to an internal user who administers a team", () => {
    const seen = visibleOrganizationTabs(viewer({ userRole: INTERNAL_USER, teams: teamAdminOf("u1") }));

    expect(seen).toContain("projects");
  });

  it("respects the per-installation page allowlist for a non-admin, tab by tab", () => {
    const onlyTeams = viewer({
      userRole: INTERNAL_USER,
      teams: teamAdminOf("u1"),
      enabledPagesInternalUsers: ["teams"],
    });
    const onlyProjects = viewer({
      userRole: INTERNAL_USER,
      teams: teamAdminOf("u1"),
      enabledPagesInternalUsers: ["projects"],
    });

    expect(visibleOrganizationTabs(onlyTeams)).toEqual(["teams"]);
    expect(visibleOrganizationTabs(onlyProjects)).toEqual(["projects"]);
  });

  it("ignores the allowlist for an admin, as the sidebar always did", () => {
    const restricted = viewer({ enabledPagesInternalUsers: [] });

    expect(visibleOrganizationTabs(restricted)).toEqual(["teams", "projects"]);
  });

  it("leaves a non-admin with nothing when the allowlist names neither tab", () => {
    const nothing = viewer({ userRole: INTERNAL_USER, enabledPagesInternalUsers: ["logs"] });

    expect(visibleOrganizationTabs(nothing)).toEqual([]);
    expect(organizationIsVisible(nothing)).toBe(false);
  });

  it("shows the entry whenever any tab is reachable, and not otherwise", () => {
    expect(organizationIsVisible(viewer())).toBe(true);
    expect(organizationIsVisible(viewer({ enableProjectsUI: false }))).toBe(true);
    expect(organizationIsVisible(viewer({ userRole: INTERNAL_USER, enabledPagesInternalUsers: [] }))).toBe(false);
  });

  it("names a base tab that is one of the tabs", () => {
    expect(ORGANIZATION_TABS).toContain(ORGANIZATION_BASE_TAB);
  });
});
