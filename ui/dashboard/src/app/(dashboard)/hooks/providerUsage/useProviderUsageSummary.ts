import { useQuery } from "@tanstack/react-query";

import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
import { providerUsageSummaryCall } from "@/components/networking";
import { all_admin_roles } from "@/utils/roles";
import type { ProviderUsageSummaryResponse } from "@/components/networking";

export const useProviderUsageSummary = (provider: string, days: number) => {
  const { accessToken, userRole } = useAuthorized();

  return useQuery<ProviderUsageSummaryResponse>({
    queryKey: ["provider-usage-summary", provider, days],
    queryFn: async () => providerUsageSummaryCall(accessToken!, provider, days),
    enabled: Boolean(accessToken && provider) && all_admin_roles.includes(userRole ?? ""),
  });
};
