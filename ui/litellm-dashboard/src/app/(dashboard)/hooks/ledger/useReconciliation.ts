import { useQuery } from "@tanstack/react-query";

import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
import { reconciliationCall } from "@/components/networking";
import { all_admin_roles } from "@/utils/roles";
import type { ReconciliationResponse } from "@/components/networking";

export const useReconciliation = (provider: string, periodStart: string, periodEnd: string) => {
  const { accessToken, userRole } = useAuthorized();

  return useQuery<ReconciliationResponse>({
    queryKey: ["ledger-reconciliation", provider, periodStart, periodEnd],
    queryFn: async () => reconciliationCall(accessToken!, provider, periodStart, periodEnd),
    enabled: Boolean(accessToken && provider) && all_admin_roles.includes(userRole ?? ""),
  });
};
