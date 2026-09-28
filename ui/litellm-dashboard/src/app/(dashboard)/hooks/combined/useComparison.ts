import { useQuery } from "@tanstack/react-query";

import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
import { combinedComparisonCall } from "@/components/networking";
import { all_admin_roles } from "@/utils/roles";
import type { ComparisonResponse } from "@/components/networking";

export const useComparison = (days: number) => {
  const { accessToken, userRole } = useAuthorized();

  return useQuery<ComparisonResponse>({
    queryKey: ["combined-comparison", days],
    queryFn: async () => combinedComparisonCall(accessToken!, days),
    enabled: Boolean(accessToken) && all_admin_roles.includes(userRole ?? ""),
  });
};
