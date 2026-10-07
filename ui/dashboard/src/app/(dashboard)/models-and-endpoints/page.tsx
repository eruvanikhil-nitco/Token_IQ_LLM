"use client";

import { useMemo, useState } from "react";
import { RefreshCw } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
import { useTeams } from "@/app/(dashboard)/hooks/teams/useTeams";
import { useUISettings } from "@/app/(dashboard)/hooks/uiSettings/useUISettings";
import { all_admin_roles, internalUserRoles } from "@/utils/roles";
import { canCreateModels } from "@/utils/modelPermissions";
import CostOptimizationFeedbackBanner from "@/components/molecules/cost_optimization_feedback_banner";
import ModelInfoView from "@/components/model_info_view";
import TeamInfoView from "@/components/team/TeamInfo";
import { useModelDetailRouting } from "@/app/(dashboard)/models-and-endpoints/detailNavigation";
import { useModelDashboardData } from "@/app/(dashboard)/models-and-endpoints/useModelDashboardData";
import AllModelsPanel from "@/app/(dashboard)/models-and-endpoints/panels/AllModelsPanel";
import AddModelPanel from "@/app/(dashboard)/models-and-endpoints/panels/AddModelPanel";
import PassThroughPanel from "@/app/(dashboard)/models-and-endpoints/panels/PassThroughPanel";
import HealthStatusPanel from "@/app/(dashboard)/models-and-endpoints/panels/HealthStatusPanel";
import ModelRetrySettingsPanel from "@/app/(dashboard)/models-and-endpoints/panels/ModelRetrySettingsPanel";
import ModelLimitsTab from "@/app/(dashboard)/models-and-endpoints/components/ModelLimitsTab";
import ModelGroupAliasPanel from "@/app/(dashboard)/models-and-endpoints/panels/ModelGroupAliasPanel";
import PriceDataPanel from "@/app/(dashboard)/models-and-endpoints/panels/PriceDataPanel";
import ModelPricingTab from "@/app/(dashboard)/models-and-endpoints/components/ModelPricingTab";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import TabScroller from "@/components/shared/TabScroller";

type ModelTabSlug =
  | "add"
  | "pass-through"
  | "health"
  | "retry-settings"
  | "model-limits"
  | "model-pricing"
  | "model-group-alias"
  | "price-data";

const BASE_TAB_KEY = "all-models";

export const TAB_LABELS: Record<ModelTabSlug, string> = {
  add: "Add Model",
  "pass-through": "Pass-Through Endpoints",
  health: "Health Status",
  "retry-settings": "Model Retry Settings",
  "model-limits": "Model Limits",
  "model-pricing": "Model Pricing",
  "model-group-alias": "Model Group Alias",
  "price-data": "Price Data Reload",
};

const renderPanel = (key: string) => {
  switch (key) {
    case BASE_TAB_KEY:
      return <AllModelsPanel />;
    case "add":
      return <AddModelPanel />;
    case "pass-through":
      return <PassThroughPanel />;
    case "health":
      return <HealthStatusPanel />;
    case "retry-settings":
      return <ModelRetrySettingsPanel />;
    case "model-limits":
      return <ModelLimitsTab />;
    case "model-pricing":
      return <ModelPricingTab />;
    case "model-group-alias":
      return <ModelGroupAliasPanel />;
    case "price-data":
      return <PriceDataPanel />;
    default:
      return null;
  }
};

export default function ModelsAndEndpointsPage() {
  const { accessToken, userRole, userId: userID, premiumUser, isViewOnly } = useAuthorized();
  const { data: teams } = useTeams();
  const { data: uiSettings } = useUISettings();
  const queryClient = useQueryClient();
  const { modelId, teamId, close } = useModelDetailRouting();
  const { availableModelAccessGroups, allModelsOnProxy } = useModelDashboardData();

  const [activeKey, setActiveKey] = useState<string>(BASE_TAB_KEY);
  const [lastRefreshed, setLastRefreshed] = useState("");

  const isInternalUser = userRole && internalUserRoles.includes(userRole);
  const canCreate = canCreateModels(
    { userRole, userID, isViewOnly },
    {
      teams: teams ?? null,
      disabledForInternalUsers:
        isInternalUser === true && uiSettings?.values?.disable_model_add_for_internal_users === true,
    },
  );
  const isAdmin = all_admin_roles.includes(userRole);

  const visibleSlugs = useMemo<Array<"" | ModelTabSlug>>(
    () => [
      "",
      ...(canCreate ? (["add"] as const) : []),
      ...(isAdmin
        ? ([
            "pass-through",
            "health",
            "retry-settings",
            "model-limits",
            "model-pricing",
            "model-group-alias",
            "price-data",
          ] as const)
        : []),
    ],
    [canCreate, isAdmin],
  );

  const allModelsLabel = isAdmin ? "All Models" : "Your Models";
  const tabLabel = (slug: "" | ModelTabSlug): React.ReactNode => (slug ? TAB_LABELS[slug] : allModelsLabel);

  const handleRefreshClick = () => {
    setLastRefreshed(new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }));
    queryClient.invalidateQueries({ queryKey: ["models", "list"] });
  };

  const invalidateModels = () => queryClient.invalidateQueries({ queryKey: ["models", "list"] });

  if (teamId) {
    return (
      <div className="w-full h-full">
        <TeamInfoView
          teamId={teamId}
          onClose={close}
          accessToken={accessToken}
          is_team_admin={userRole === "Admin"}
          is_proxy_admin={userRole === "Proxy Admin"}
          userModels={allModelsOnProxy}
          editTeam={false}
          onUpdate={invalidateModels}
          premiumUser={premiumUser}
        />
      </div>
    );
  }

  return (
    <div className="mx-4">
      <div className="mt-2 flex w-full flex-col gap-2 p-8">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold">Models + Endpoints</h2>
            {isAdmin ? (
              <p className="text-sm text-muted-foreground">Add and manage models for the proxy</p>
            ) : (
              <p className="text-sm text-muted-foreground">Add models for teams you are an admin for.</p>
            )}
          </div>
        </div>

        <CostOptimizationFeedbackBanner />

        {modelId ? (
          <ModelInfoView
            modelId={modelId}
            onClose={close}
            accessToken={accessToken}
            userID={userID}
            userRole={userRole}
            isViewOnly={isViewOnly}
            onModelUpdate={invalidateModels}
            modelAccessGroups={availableModelAccessGroups}
          />
        ) : (
          <Tabs value={activeKey} onValueChange={setActiveKey}>
            <div className="flex min-w-0 flex-nowrap items-center gap-3 border-b">
              <TabScroller className="flex-1">
                <TabsList variant="line" className="w-max justify-start">
                  {visibleSlugs.map((slug) => {
                    const key = slug || BASE_TAB_KEY;
                    return (
                      <TabsTrigger key={key} value={key} className="flex-none">
                        {tabLabel(slug)}
                      </TabsTrigger>
                    );
                  })}
                </TabsList>
              </TabScroller>
              <div className="flex shrink-0 items-center gap-2 pb-1">
                {lastRefreshed && (
                  <span className="text-xs text-muted-foreground">Last Refreshed: {lastRefreshed}</span>
                )}
                <Button variant="ghost" size="icon-sm" onClick={handleRefreshClick} aria-label="Refresh models">
                  <RefreshCw />
                </Button>
              </div>
            </div>
            {visibleSlugs.map((slug) => {
              const key = slug || BASE_TAB_KEY;
              return (
                <TabsContent key={key} value={key} className="pt-4">
                  {renderPanel(key)}
                </TabsContent>
              );
            })}
          </Tabs>
        )}
      </div>
    </div>
  );
}
