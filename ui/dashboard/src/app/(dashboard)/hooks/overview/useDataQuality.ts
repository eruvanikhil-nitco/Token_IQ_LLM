import { useQuery } from "@tanstack/react-query";

import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
import { dataQualityCall } from "@/components/networking";
import { all_admin_roles } from "@/utils/roles";
import type { DataQualityIssue, DataQualityResponse, InvoiceCoverage } from "@/components/networking";

export type { DataQualityIssue, DataQualityResponse, InvoiceCoverage };

export const dataQualityKeys = {
  all: ["data-quality"] as const,
};

export const useDataQuality = () => {
  const { accessToken, userRole } = useAuthorized();

  return useQuery<DataQualityResponse>({
    queryKey: dataQualityKeys.all,
    queryFn: async () => await dataQualityCall(accessToken!),
    enabled: Boolean(accessToken) && all_admin_roles.includes(userRole ?? ""),
  });
};
