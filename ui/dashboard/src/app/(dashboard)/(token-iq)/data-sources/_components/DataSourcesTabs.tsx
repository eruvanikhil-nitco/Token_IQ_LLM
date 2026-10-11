"use client";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import TabScroller from "@/components/shared/TabScroller";
import { all_admin_roles } from "@/utils/roles";
import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
import { useTabRouting } from "@/app/(dashboard)/hooks/useTabRouting";
import { createTabRoutes } from "@/utils/tabRoutes";

import {
  DATA_SOURCES_TABS,
  DATA_SOURCES_TAB_ORDER,
  dataSourcesAccess,
  visibleDataSourcesTabs,
  type DataSourcesTab,
} from "../dataSourcesTabs";
import AccountsTab from "./AccountsTab";
import OverviewTab from "./OverviewTab";

const routes = createTabRoutes("data-sources", DATA_SOURCES_TAB_ORDER);

/**
 * Data › Data Sources: every place Token IQ gets usage and cost data from.
 *
 * Four tabs in the blueprint, arriving one at a time. Only the built ones are offered, because a
 * tab that renders nothing is worse than one that is not there yet. Each tab keeps its own URL, so
 * the pages this replaces can redirect to the right one.
 *
 * No figure here crosses the provider/gateway line. The Accounts tab totals raw records, which is
 * not money; a page whose job is "every place data comes from" is the natural place for somebody to
 * add a grand total, and that total would be the one addition the counting rule forbids.
 */
export default function DataSourcesTabs() {
  const { userRole } = useAuthorized();

  const viewer = { userRole, adminRoles: all_admin_roles };
  const visible = visibleDataSourcesTabs(viewer);
  const access = dataSourcesAccess(viewer);

  const baseTabKey = visible[0] ?? "";
  const { activeKey, onTabChange } = useTabRouting({ routes, baseTabKey, visibleKeys: visible });

  if (visible.length === 0) {
    return null;
  }

  const panel = (tab: DataSourcesTab) => {
    switch (tab) {
      case "overview":
        return <OverviewTab />;
      case "accounts":
        return <AccountsTab />;
      default:
        return null;
    }
  };

  return (
    <Tabs value={activeKey} onValueChange={onTabChange}>
      <TabScroller className="mb-4">
        <TabsList variant="line" className="h-auto w-max flex-nowrap justify-start">
          {visible.map((tab) => (
            <TabsTrigger key={tab} value={tab} className="flex-none">
              {DATA_SOURCES_TABS[tab].label}
            </TabsTrigger>
          ))}
        </TabsList>
      </TabScroller>
      {visible.map((tab) => (
        <TabsContent key={tab} value={tab} className="flex flex-col gap-4">
          <p className="text-sm text-muted-foreground">{DATA_SOURCES_TABS[tab].description}</p>
          {access === "view" ? (
            <p className="text-sm text-muted-foreground">
              View only. Connections are added and changed by an administrator.
            </p>
          ) : null}
          {panel(tab)}
        </TabsContent>
      ))}
    </Tabs>
  );
}
