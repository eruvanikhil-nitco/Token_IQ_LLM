import { useQuery } from "@tanstack/react-query";

import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
import { attributionUnallocatedCall } from "@/components/networking";
import { all_admin_roles } from "@/utils/roles";
import type { UnallocatedResponse } from "@/components/networking";

export const useUnallocated = (provider: string, days: number) => {
  const { accessToken, userRole } = useAuthorized();

  return useQuery<UnallocatedResponse>({
    queryKey: ["attribution-unallocated", provider, days],
    queryFn: async () => attributionUnallocatedCall(accessToken!, provider, days),
    enabled: Boolean(accessToken && provider) && all_admin_roles.includes(userRole ?? ""),
  });
};
