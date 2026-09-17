import { useQuery } from "@tanstack/react-query";

import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
import { providerUsageRawCall } from "@/components/networking";
import { all_admin_roles } from "@/utils/roles";
import type { ProviderUsageRawResponse } from "@/components/networking";

export const useProviderUsageRaw = (provider: string, limit: number, before: string | null) => {
  const { accessToken, userRole } = useAuthorized();

  return useQuery<ProviderUsageRawResponse>({
    queryKey: ["provider-usage-raw", provider, limit, before],
    queryFn: async () => providerUsageRawCall(accessToken!, provider, limit, before),
    enabled: Boolean(accessToken && provider) && all_admin_roles.includes(userRole ?? ""),
  });
};
