import { useQuery } from "@tanstack/react-query";
import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
import { spendByModel, type ModelSpend } from "@/app/(dashboard)/projects/_components/spendByModel";
import { projectDailyActivityCall } from "@/components/networking";
import type { DailyData } from "@/components/UsagePage/types";
import { projectKeys, projectReaderRoles } from "./useProjects";

export const PROJECT_SPEND_WINDOW_DAYS = 30;

const DAY_MS = 24 * 60 * 60 * 1000;

export const useProjectSpendByModel = (projectId: string) => {
  const { accessToken, userRole } = useAuthorized();

  return useQuery<ModelSpend[]>({
    queryKey: [...projectKeys.detail(projectId), "spend-by-model"],
    queryFn: async () => {
      const endTime = new Date();
      const startTime = new Date(endTime.getTime() - PROJECT_SPEND_WINDOW_DAYS * DAY_MS);
      const report: { results: DailyData[] } = await projectDailyActivityCall(accessToken!, startTime, endTime, 1, [
        projectId,
      ]);
      return spendByModel(report.results);
    },
    enabled: Boolean(accessToken && projectId) && projectReaderRoles.includes(userRole ?? ""),
  });
};
