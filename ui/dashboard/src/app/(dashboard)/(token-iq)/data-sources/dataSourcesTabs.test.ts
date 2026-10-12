import { describe, expect, it } from "vitest";

import { all_admin_roles, internalUserRoles } from "@/utils/roles";

import {
  DATA_SOURCES_TABS,
  DATA_SOURCES_TAB_ORDER,
  dataSourcesAccess,
  gatewayPagesMovedFor,
  visibleDataSourcesTabs,
  type DataSourcesViewer,
} from "./dataSourcesTabs";

/**
 * The blueprint gives this page `acc:{A:'e',F:'v',V:'n',L:'n',R:'n',M:'n'}`: Org Admin manages it,
 * Finance Admin views it, and every other role cannot see it at all. It is the first of these pages
 * whose access is not simply admin-or-nothing, so the rule is worth pinning before the page exists.
 *
 * Finance Admin does not exist in the product yet, nor do six of the blueprint's eight roles: they
 * are build step 4. What exists is an admin tier with read-only members, so the rule maps onto that
 * and the test says which roles it was mapped to, rather than leaving it to be rediscovered.
 */

const viewer = (userRole: string): DataSourcesViewer => ({ userRole, adminRoles: all_admin_roles });

describe("who may open Data Sources", () => {
  it("lets a proxy admin manage it", () => {
    expect(dataSourcesAccess(viewer("proxy_admin"))).toBe("manage");
  });

  it("lets an organisation admin manage it", () => {
    expect(dataSourcesAccess(viewer("org_admin"))).toBe("manage");
  });

  it("gives a read-only admin a view, not a manage", () => {
    // The nearest thing to the blueprint's Finance Admin that exists today. A view must not carry
    // the "+ Connect account" action, which is the only thing on the page that changes anything.
    expect(dataSourcesAccess(viewer("Admin Viewer"))).toBe("view");
    expect(dataSourcesAccess(viewer("proxy_admin_viewer"))).toBe("view");
  });

  it("hides it from everyone else", () => {
    for (const role of [...internalUserRoles, "customer", "team"]) {
      expect(dataSourcesAccess(viewer(role))).toBe("hidden");
    }
  });

  it("shows no tabs at all to a role that cannot see the page", () => {
    expect(visibleDataSourcesTabs(viewer("Internal User"))).toEqual([]);
  });

  it("shows the built tabs to a viewer who may read it", () => {
    expect(visibleDataSourcesTabs(viewer("Admin Viewer")).length).toBeGreaterThan(0);
  });

  it("shows a read-only admin exactly what an admin sees, since the difference is the actions", () => {
    expect(visibleDataSourcesTabs(viewer("Admin Viewer"))).toEqual(visibleDataSourcesTabs(viewer("proxy_admin")));
  });
});

describe("the tabs themselves", () => {
  it("declares all four the blueprint names, in its order", () => {
    // Declared once, so a tab arriving later lands in the right place rather than on the end.
    expect(DATA_SOURCES_TAB_ORDER).toEqual(["overview", "accounts", "gateway", "uploads"]);
  });

  it("only offers the ones that are actually built", () => {
    // A tab that exists and renders nothing is worse than a tab that is not there yet, and this is
    // the blueprint's own rule about empty states.
    const built = visibleDataSourcesTabs(viewer("proxy_admin"));

    expect(built.every((tab) => DATA_SOURCES_TABS[tab].built)).toBe(true);
    expect(built).toEqual(["overview", "accounts", "gateway", "uploads"]);
  });

  it("opens on Overview, because that is the tab the blueprint puts first", () => {
    // Which tab the page lands on, since the first visible one is the base route. The legacy
    // provider-apis and user-tools ids point at data-sources/accounts for exactly this reason.
    expect(visibleDataSourcesTabs(viewer("proxy_admin"))[0]).toBe("overview");
  });

  it("keeps the built tabs in the blueprint's order rather than the order they were written", () => {
    const built = visibleDataSourcesTabs(viewer("proxy_admin"));
    const positions = built.map((tab) => DATA_SOURCES_TAB_ORDER.indexOf(tab));

    expect(positions).toEqual([...positions].sort((a, b) => a - b));
  });

  it("gives every tab the label and description the blueprint wrote for it", () => {
    for (const key of DATA_SOURCES_TAB_ORDER) {
      expect(DATA_SOURCES_TABS[key].label).toBeTruthy();
      expect(DATA_SOURCES_TABS[key].description).toBeTruthy();
    }
  });
});

describe("the pages the Gateway tab took over", () => {
  it("has them moved for a viewer who can open this page", () => {
    // The owner's decision on 12 Oct 2026: the request log and virtual keys move. The sidebar asks
    // this so the entry disappears exactly when the tab that replaced it appears.
    expect(gatewayPagesMovedFor(viewer("proxy_admin"))).toBe(true);
    expect(gatewayPagesMovedFor(viewer("Admin Viewer"))).toBe(true);
  });

  it("leaves them where they are for a role this page is hidden from", () => {
    // Both are pages every role uses and this page is admin-only, so moving them unconditionally
    // would take away the two screens a team member uses most and leave nothing in their place.
    for (const role of [...internalUserRoles, "customer", "team"]) {
      expect(gatewayPagesMovedFor(viewer(role)), role).toBe(false);
    }
  });
});
