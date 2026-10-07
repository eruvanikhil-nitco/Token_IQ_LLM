import { useQuery } from "@tanstack/react-query";

import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
import { providerConnectionsCall } from "@/components/networking";
import { all_admin_roles } from "@/utils/roles";
import type {
  ProviderConnection,
  ProviderConnectionAccount,
  ProviderConnectionState,
  ProviderFetchDetail,
} from "@/components/networking";

export type { ProviderConnection, ProviderConnectionAccount, ProviderConnectionState, ProviderFetchDetail };

export const providerConnectionKeys = {
  all: ["provider-connections"] as const,
};

export const useProviderConnections = () => {
  const { accessToken, userRole } = useAuthorized();

  return useQuery<ProviderConnection[]>({
    queryKey: providerConnectionKeys.all,
    queryFn: async () => (await providerConnectionsCall(accessToken!)).providers,
    enabled: Boolean(accessToken) && all_admin_roles.includes(userRole ?? ""),
  });
};
