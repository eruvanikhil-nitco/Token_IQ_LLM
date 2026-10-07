import { useQuery } from "@tanstack/react-query";

import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
import { providerSyncHistoryCall } from "@/components/networking";
import { all_admin_roles } from "@/utils/roles";
import type { ProviderSyncHistoryRow, ProviderSyncOutcome } from "@/components/networking";

export type { ProviderSyncHistoryRow, ProviderSyncOutcome };

export const SYNC_HISTORY_ROWS = 50;

export const useProviderSyncHistory = (provider: string) => {
  const { accessToken, userRole } = useAuthorized();

  return useQuery<ProviderSyncHistoryRow[]>({
    queryKey: ["provider-sync-history", provider],
    queryFn: async () => (await providerSyncHistoryCall(accessToken!, provider, SYNC_HISTORY_ROWS)).rows,
    enabled: Boolean(accessToken && provider) && all_admin_roles.includes(userRole ?? ""),
  });
};
