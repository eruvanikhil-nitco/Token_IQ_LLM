import { useQuery } from "@tanstack/react-query";

import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
import { toolConnectionsCall } from "@/components/networking";
import { all_admin_roles } from "@/utils/roles";
import type { ToolConnection, ToolConnectionAccount, ToolFetchDetail } from "@/components/networking";

export type { ToolConnection, ToolConnectionAccount, ToolFetchDetail };

export const toolConnectionKeys = {
  all: ["tool-connections"] as const,
};

export const useToolConnections = () => {
  const { accessToken, userRole } = useAuthorized();

  return useQuery<ToolConnection[]>({
    queryKey: toolConnectionKeys.all,
    queryFn: async () => (await toolConnectionsCall(accessToken!)).tools,
    enabled: Boolean(accessToken) && all_admin_roles.includes(userRole ?? ""),
  });
};
