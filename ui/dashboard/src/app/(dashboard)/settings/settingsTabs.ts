export const SETTINGS_TABS = ["admin", "logging-and-alerts", "ui-theme"] as const;

export type SettingsTab = (typeof SETTINGS_TABS)[number];

export const SETTINGS_BASE_TAB: SettingsTab = "admin";

export const SETTINGS_TAB_LABELS: Readonly<Record<SettingsTab, string>> = {
  admin: "Admin",
  "logging-and-alerts": "Logging & Alerts",
  "ui-theme": "UI Theme",
};

/** The legacy `?page=` id each tab was reachable as, so old links still resolve. */
export const SETTINGS_TAB_LEGACY_PAGE: Readonly<Record<SettingsTab, string>> = {
  admin: "admin-panel",
  "logging-and-alerts": "logging-and-alerts",
  "ui-theme": "ui-theme",
};

export interface SettingsViewer {
  userRole: string;
  adminRoles: readonly string[];
}

/**
 * Which tabs of Administration > Settings this viewer may see.
 *
 * All three pages this merges were admin-only and an admin role skipped the per-installation page
 * list, so unlike Organization and Access Control there is no asymmetry to carry: the three tabs
 * stand or fall together. The function exists anyway so the sidebar and the page cannot drift, and
 * so the next tab the blueprint adds has one place to declare its rule.
 */
export function visibleSettingsTabs(viewer: SettingsViewer): readonly SettingsTab[] {
  return viewer.adminRoles.includes(viewer.userRole) ? SETTINGS_TABS : [];
}

/** Whether the merged sidebar entry leads anywhere at all for this viewer. */
export function settingsIsVisible(viewer: SettingsViewer): boolean {
  return visibleSettingsTabs(viewer).length > 0;
}
