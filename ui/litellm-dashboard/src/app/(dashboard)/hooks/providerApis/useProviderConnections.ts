import { useQuery } from "@tanstack/react-query";

import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
import { providerConnectionsCall } from "@/components/networking";
import { all_admin_roles } from "@/utils/roles";
import type { ConnectionState } from "@/app/(dashboard)/provider-apis/_components/connectionState";

export interface ProviderConnectionAccount {
  credential_name: string;
  state: ConnectionState;
  detail: string | null;
  last_sync_at: string | null;
  last_outcome: string | null;
  facts_stored: number;
}

export interface ProviderFetchDetail {
  endpoint: string;
  endpoint_url: string;
  grain: string;
  refresh_seconds: number;
  window_hours: number;
  delay_note: string;
  history_note: string;
}

export interface ProviderConnection {
  provider: string;
  display_name: string;
  state: ConnectionState;
  accounts: ProviderConnectionAccount[];
  fetches: ProviderFetchDetail;
}

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
