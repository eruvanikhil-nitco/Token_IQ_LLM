import { useQuery } from "@tanstack/react-query";
import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
import { spendByModel, type ModelSpend } from "@/app/(dashboard)/projects/_components/spendByModel";
import { projectDailyActivityCall } from "@/components/networking";
import type { DailyData } from "@/components/UsagePage/types";
import { projectKeys, projectReaderRoles } from "./useProjects";

export const PROJECT_SPEND_WINDOW_DAYS = 30;

const DAY_MS = 24 * 60 * 60 * 1000;

type ReportPage = { results: DailyData[]; metadata: { total_pages: number } };

export const useProjectSpendByModel = (projectId: string) => {
  const { accessToken, userRole } = useAuthorized();

  return useQuery<ModelSpend[]>({
    queryKey: [...projectKeys.detail(projectId), "spend-by-model"],
    queryFn: async () => {
      const endTime = new Date();
      const startTime = new Date(endTime.getTime() - PROJECT_SPEND_WINDOW_DAYS * DAY_MS);
      const fetchPage = (page: number): Promise<ReportPage> =>
        projectDailyActivityCall(accessToken!, startTime, endTime, page, [projectId]);
      const firstPage = await fetchPage(1);
      const laterPages = await Promise.all(
        Array.from({ length: Math.max(firstPage.metadata.total_pages - 1, 0) }, (_, index) => fetchPage(index + 2)),
      );
      return spendByModel([firstPage, ...laterPages].flatMap((page) => page.results));
    },
    enabled: Boolean(accessToken && projectId) && projectReaderRoles.includes(userRole ?? ""),
  });
};
