import { useQuery } from "@tanstack/react-query";

import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
import { overviewCall } from "@/components/networking";
import { all_admin_roles } from "@/utils/roles";
import type { OverviewResponse } from "@/components/networking";

export const overviewKeys = {
  all: ["overview"] as const,
  period: (start: string, end: string) => ["overview", start, end] as const,
};

export const useOverview = (periodStart: string, periodEnd: string) => {
  const { accessToken, userRole } = useAuthorized();

  return useQuery<OverviewResponse>({
    queryKey: overviewKeys.period(periodStart, periodEnd),
    queryFn: async () => overviewCall(accessToken!, periodStart, periodEnd),
    enabled: Boolean(accessToken) && all_admin_roles.includes(userRole ?? ""),
  });
};
