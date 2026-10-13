import { describe, expect, it } from "vitest";

import {
  AREAS,
  BLUEPRINT_ROLES,
  GRANTABLE,
  allowedPages,
  areaOf,
  grantableNow,
  matrixValue,
  pagesTheBlueprintHides,
  pagesVisibleToday,
  permits,
  readsAs,
  roleLabel,
  whyNotGrantable,
  type BlueprintRole,
} from "./roles";

/**
 * The test that makes the rest of the role work safe.
 *
 * An authorisation mistake does not throw. A wrong mapping permits, and the person who notices is
 * the one who should not have been able to see the page, so the property worth asserting is not
 * that the mapping is right but that it cannot be wrong in the dangerous direction.
 */

const TODAYS_ROLES = [
  "proxy_admin",
  "proxy_admin_viewer",
  "org_admin",
  "internal_user",
  "internal_user_viewer",
  "team",
  "customer",
  "Admin",
  "Admin Viewer",
  "Internal User",
  "Internal Viewer",
] as const;

describe("reading today's role as one of the blueprint's eight", () => {
  it("never lets a person open a page they cannot open today", () => {
    for (const role of TODAYS_ROLES) {
      const today = pagesVisibleToday(role);
      for (const page of allowedPages(role)) {
        expect(today, `${role} gained ${page}`).toContain(page);
      }
    }
  });

  it("gives nothing at all to a role it does not recognise", () => {
    // The fail-closed direction. A role nobody mapped must read as nothing rather than default to
    // the strongest reading, which is how an authorisation mapping grants by accident.
    expect(readsAs("some_role_from_a_later_release")).toBeNull();
    expect(allowedPages("some_role_from_a_later_release")).toEqual([]);
    expect(readsAs(null)).toBeNull();
    expect(readsAs(undefined)).toBeNull();
    expect(allowedPages(null)).toEqual([]);
  });

  it("reads the two gateway identities as no blueprint role", () => {
    // `team` is the identity a JWT caller presents and `customer` is an end user of somebody
    // else's application. Neither opens Token IQ, and giving either one a role would invent an
    // account that can sign in.
    expect(readsAs("team")).toBeNull();
    expect(readsAs("customer")).toBeNull();
  });

  it("reads only the proxy admin as the owner", () => {
    const owners = TODAYS_ROLES.filter((role) => readsAs(role) === "org-owner");
    expect(owners).toEqual(["proxy_admin", "Admin"]);
  });

  it("reads a viewer as a viewer rather than as the admin it can already see pages of", () => {
    expect(readsAs("proxy_admin_viewer")).toBe("org-viewer");
    expect(readsAs("Admin Viewer")).toBe("org-viewer");
  });

  it("reads both internal roles as a team member, the weakest of the eight that signs in", () => {
    expect(readsAs("internal_user")).toBe("team-member");
    expect(readsAs("internal_user_viewer")).toBe("team-member");
    expect(allowedPages("internal_user")).not.toContain("settings");
  });
});

describe("the matrix", () => {
  it("answers for every area and every role", () => {
    for (const area of AREAS) {
      for (const role of BLUEPRINT_ROLES) {
        expect(matrixValue(role, area), `${role} on ${area}`).not.toBe("");
      }
    }
  });

  it("holds the blueprint's own words rather than a level somebody flattened them to", () => {
    expect(matrixValue("finance-admin", "data-sources")).toBe("View; upload invoices");
    expect(matrixValue("team-lead-manage", "budgets")).toBe("View; request changes");
    expect(matrixValue("service-account", "reports")).toBe("Read API");
  });

  it("denies an area to a role the blueprint gives it no row for", () => {
    expect(permits("finance-admin", "settings")).toBe(false);
    expect(permits("org-viewer", "pricing")).toBe(false);
    expect(permits("team-member", "invoice-reconciliation")).toBe(false);
    expect(permits("org-owner", "team-home")).toBe(false);
  });

  it("grants an area a role does hold", () => {
    expect(permits("finance-admin", "invoice-reconciliation")).toBe(true);
    expect(permits("finance-admin", "pricing")).toBe(true);
    expect(permits("team-lead-read", "projects-and-keys")).toBe(true);
    expect(permits("team-member", "cost-data")).toBe(true);
  });

  it("permits nothing for a role that is null", () => {
    for (const area of AREAS) {
      expect(permits(null, area)).toBe(false);
    }
  });

  it("puts each money page in exactly one area, and leaves the gateway's own pages out", () => {
    expect(areaOf("ledger")).toBe("invoice-reconciliation");
    expect(areaOf("cost-tracking")).toBe("pricing");
    expect(areaOf("settings")).toBe("settings");
    expect(areaOf("llm-playground")).toBeNull();
    expect(areaOf("guardrails")).toBeNull();
  });

  it("lets a page the matrix never mentions keep the rule it has today", () => {
    // Otherwise adopting the matrix would silently deny every engine page, because an area table
    // that does not mention a page would read as a denial of it.
    expect(allowedPages("proxy_admin")).toContain("llm-playground");
    expect(allowedPages("proxy_admin")).toContain("mcp-servers");
  });
});

describe("what adopting the matrix would take away", () => {
  it("names the entries an admin viewer would lose, rather than quietly removing them", () => {
    // Removing an entry somebody has today is the owner's call, so this is reported and acted on
    // by nothing. The blueprint's Org Viewer is read-only over finance, not over configuration.
    const hidden = pagesTheBlueprintHides("proxy_admin_viewer");

    expect(hidden).toContain("settings");
    expect(hidden).toContain("data-sources");
    expect(hidden).toContain("cost-tracking");
    expect(hidden).not.toContain("new_usage");
  });

  it("takes nothing from the owner", () => {
    expect(pagesTheBlueprintHides("proxy_admin")).toEqual([]);
  });

  it("reports every page as hidden for a role it does not recognise", () => {
    const hidden = pagesTheBlueprintHides("customer");
    expect(hidden).toEqual(pagesVisibleToday("customer"));
  });
});

describe("which of the eight an installation can grant", () => {
  it("can grant only the four that have a role underneath them", () => {
    const grantable = BLUEPRINT_ROLES.filter(grantableNow);
    expect(grantable).toEqual(["org-owner", "org-admin", "org-viewer", "team-member"]);
  });

  it("says why each of the other four cannot be granted yet", () => {
    for (const role of BLUEPRINT_ROLES.filter((candidate) => !grantableNow(candidate))) {
      expect(whyNotGrantable(role), role).toBeTruthy();
    }
  });

  it("says nothing about a role that can be granted", () => {
    expect(whyNotGrantable("org-owner")).toBeNull();
  });

  it("grants each one through a role that exists today", () => {
    const underlying = Object.values(GRANTABLE).filter((value): value is string => value !== null);
    for (const role of underlying) {
      expect(TODAYS_ROLES as readonly string[], role).toContain(role);
    }
  });

  it("maps no role onto a stronger one than itself", () => {
    // The specific way this fails open: a role granted through `proxy_admin` has every power there
    // is, so only the owner may be granted that way.
    const throughProxyAdmin = BLUEPRINT_ROLES.filter((role) => GRANTABLE[role] === "proxy_admin");
    expect(throughProxyAdmin).toEqual(["org-owner"]);
  });

  it("names all eight the way the blueprint does", () => {
    expect(BLUEPRINT_ROLES.map((role: BlueprintRole) => roleLabel(role))).toEqual([
      "Org Owner",
      "Org Admin",
      "Finance Admin",
      "Org Viewer",
      "Team Lead (Manage)",
      "Team Lead (Read-only)",
      "Team Member",
      "Service Account",
    ]);
  });
});
