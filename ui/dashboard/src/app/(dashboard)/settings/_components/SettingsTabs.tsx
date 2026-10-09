"use client";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import TabScroller from "@/components/shared/TabScroller";
import LoggingAndAlertsSettings from "@/components/settings";
import { all_admin_roles } from "@/utils/roles";
import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
import useProxySettings from "@/app/(dashboard)/hooks/proxySettings/useProxySettings";
import { useTabRouting } from "@/app/(dashboard)/hooks/useTabRouting";
import { createTabRoutes } from "@/utils/tabRoutes";
import AdminPanel from "@/app/(dashboard)/admin-panel/_components/AdminPanel";
import UIThemeSettings from "@/app/(dashboard)/ui-theme/UIThemeSettings";

import {
  SETTINGS_BASE_TAB,
  SETTINGS_TABS,
  SETTINGS_TAB_LABELS,
  visibleSettingsTabs,
  type SettingsTab,
} from "../settingsTabs";

const routes = createTabRoutes("settings", SETTINGS_TABS);

/**
 * Administration > Settings: what were the Admin Settings, Logging & Alerts and UI Theme pages.
 *
 * The blueprint's Settings page also carries data retention, system health, licence and feature
 * flags. None of those exists yet, so they are not stubbed here: an empty tab is worse than an
 * absent one. Each tab keeps its own URL, so the old `?page=` links still arrive at the right one.
 */
export default function SettingsTabs() {
  const { accessToken, userId, userRole, premiumUser } = useAuthorized();
  const proxySettings = useProxySettings(accessToken);

  const visible = visibleSettingsTabs({ userRole, adminRoles: all_admin_roles });
  const baseTabKey = visible.includes(SETTINGS_BASE_TAB) ? SETTINGS_BASE_TAB : (visible[0] ?? "");
  const { activeKey, onTabChange } = useTabRouting({ routes, baseTabKey, visibleKeys: visible });

  const panel = (tab: SettingsTab) => {
    if (tab === "admin") {
      return <AdminPanel proxySettings={proxySettings} />;
    }
    if (tab === "logging-and-alerts") {
      return (
        <LoggingAndAlertsSettings
          userID={userId}
          userRole={userRole}
          accessToken={accessToken}
          premiumUser={premiumUser}
        />
      );
    }
    return <UIThemeSettings userID={userId} userRole={userRole} accessToken={accessToken} />;
  };

  if (visible.length === 0) {
    return null;
  }

  return (
    <Tabs value={activeKey} onValueChange={onTabChange}>
      <TabScroller className="mb-4">
        <TabsList variant="line" className="h-auto w-max flex-nowrap justify-start">
          {visible.map((tab) => (
            <TabsTrigger key={tab} value={tab} className="flex-none">
              {SETTINGS_TAB_LABELS[tab]}
            </TabsTrigger>
          ))}
        </TabsList>
      </TabScroller>
      {visible.map((tab) => (
        <TabsContent key={tab} value={tab}>
          {panel(tab)}
        </TabsContent>
      ))}
    </Tabs>
  );
}
