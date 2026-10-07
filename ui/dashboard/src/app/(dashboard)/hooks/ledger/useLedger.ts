import { useQuery } from "@tanstack/react-query";

import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
import { ledgerLinesCall } from "@/components/networking";
import { all_admin_roles } from "@/utils/roles";
import type { LedgerLinesResponse } from "@/components/networking";

export const useLedger = (provider: string | null, periodStart: string, periodEnd: string) => {
  const { accessToken, userRole } = useAuthorized();

  return useQuery<LedgerLinesResponse>({
    queryKey: ["ledger-lines", provider, periodStart, periodEnd],
    queryFn: async () => ledgerLinesCall(accessToken!, provider, periodStart, periodEnd),
    enabled: Boolean(accessToken) && all_admin_roles.includes(userRole ?? ""),
  });
};
