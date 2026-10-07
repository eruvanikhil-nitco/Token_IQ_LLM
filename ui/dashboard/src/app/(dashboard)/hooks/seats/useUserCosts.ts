import { useQuery } from "@tanstack/react-query";

import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
import { userCostCall, userCostsCall } from "@/components/networking";
import { all_admin_roles } from "@/utils/roles";
import type { UserCost, UserCostListResponse } from "@/components/networking";

export const useUserCosts = (periodStart: string, periodEnd: string, currency: string) => {
  const { accessToken, userRole } = useAuthorized();

  return useQuery<UserCostListResponse>({
    queryKey: ["user-costs", periodStart, periodEnd, currency],
    queryFn: async () => userCostsCall(accessToken!, periodStart, periodEnd, currency),
    enabled: Boolean(accessToken) && all_admin_roles.includes(userRole ?? ""),
  });
};

/**
 * One person's cost. Not gated on an admin role here: the server lets a person read their own,
 * and gating in the browser would hide a page they are entitled to see.
 */
export const useUserCost = (userId: string, periodStart: string, periodEnd: string, currency: string) => {
  const { accessToken } = useAuthorized();

  return useQuery<UserCost>({
    queryKey: ["user-cost", userId, periodStart, periodEnd, currency],
    queryFn: async () => userCostCall(accessToken!, userId, periodStart, periodEnd, currency),
    enabled: Boolean(accessToken && userId),
  });
};
