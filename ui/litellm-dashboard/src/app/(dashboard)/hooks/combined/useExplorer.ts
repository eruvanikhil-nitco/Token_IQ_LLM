import { useQuery } from "@tanstack/react-query";

import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
import { combinedExplorerCall } from "@/components/networking";
import { all_admin_roles } from "@/utils/roles";
import type { ExplorerResponse } from "@/components/networking";

export const useExplorer = (dimension: string, days: number) => {
  const { accessToken, userRole } = useAuthorized();

  return useQuery<ExplorerResponse>({
    queryKey: ["combined-explorer", dimension, days],
    queryFn: async () => combinedExplorerCall(accessToken!, dimension, days),
    enabled: Boolean(accessToken && dimension) && all_admin_roles.includes(userRole ?? ""),
  });
};
