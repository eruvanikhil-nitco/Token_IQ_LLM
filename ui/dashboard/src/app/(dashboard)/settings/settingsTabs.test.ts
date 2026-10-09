import { describe, expect, it } from "vitest";

import { all_admin_roles, internalUserRoles } from "@/utils/roles";

import {
  SETTINGS_BASE_TAB,
  SETTINGS_TABS,
  SETTINGS_TAB_LABELS,
  SETTINGS_TAB_LEGACY_PAGE,
  settingsIsVisible,
  visibleSettingsTabs,
} from "./settingsTabs";

/**
 * Admin Settings, Logging & Alerts and UI Theme were three admin-only pages, so unlike the other
 * two merges there is no asymmetry between the tabs. What these hold down is that the three really
 * do stand or fall together, and that every tab still names the old page id its links used.
 */

describe("which tabs Administration > Settings shows", () => {
  it("gives an admin all three, in a fixed order", () => {
    expect(visibleSettingsTabs({ userRole: "proxy_admin", adminRoles: all_admin_roles })).toEqual([
      "admin",
      "logging-and-alerts",
      "ui-theme",
    ]);
  });

  it("gives a non-admin nothing, because all three pages were admin-only", () => {
    for (const role of [...internalUserRoles, "customer"]) {
      expect(visibleSettingsTabs({ userRole: role, adminRoles: all_admin_roles })).toEqual([]);
      expect(settingsIsVisible({ userRole: role, adminRoles: all_admin_roles })).toBe(false);
    }
  });

  it("shows the entry to every admin role, not just the proxy admin", () => {
    for (const role of all_admin_roles) {
      expect(settingsIsVisible({ userRole: role, adminRoles: all_admin_roles })).toBe(true);
    }
  });

  it("keeps a legacy page id and a label for every tab", () => {
    // A tab with no legacy id would silently drop the `?page=` link that used to reach it.
    for (const tab of SETTINGS_TABS) {
      expect(SETTINGS_TAB_LEGACY_PAGE[tab]).toBeTruthy();
      expect(SETTINGS_TAB_LABELS[tab]).toBeTruthy();
    }
  });

  it("names the pages this merged, so a rename cannot quietly drop one", () => {
    expect(Object.values(SETTINGS_TAB_LEGACY_PAGE)).toEqual(["admin-panel", "logging-and-alerts", "ui-theme"]);
  });

  it("names a base tab that is one of the tabs", () => {
    expect(SETTINGS_TABS).toContain(SETTINGS_BASE_TAB);
  });
});
