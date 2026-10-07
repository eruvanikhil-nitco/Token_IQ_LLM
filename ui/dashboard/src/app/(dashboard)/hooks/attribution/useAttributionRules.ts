import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
import { attributionRulesCall, deleteAttributionRuleCall, upsertAttributionRuleCall } from "@/components/networking";
import { all_admin_roles } from "@/utils/roles";
import type { AttributionOwnerType, AttributionRuleListResponse } from "@/components/networking";

const RULES_KEY = ["attribution-rules"];

export const useAttributionRules = () => {
  const { accessToken, userRole } = useAuthorized();

  return useQuery<AttributionRuleListResponse>({
    queryKey: RULES_KEY,
    queryFn: async () => attributionRulesCall(accessToken!),
    enabled: Boolean(accessToken) && all_admin_roles.includes(userRole ?? ""),
  });
};

export interface RuleDraft {
  provider: string;
  match_value: string;
  owner_type: AttributionOwnerType;
  owner_id: string;
  note?: string | null;
}

/**
 * Saving and deleting both invalidate the unallocated figures as well as the rule list.
 *
 * A rule is the only thing that moves money between "owned" and "unallocated", so leaving the
 * unallocated query cached would show an admin the totals from before their own edit.
 */
export const useSaveAttributionRule = () => {
  const { accessToken } = useAuthorized();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (draft: RuleDraft) =>
      upsertAttributionRuleCall(accessToken!, { ...draft, match_type: "cloud_account" }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: RULES_KEY });
      await queryClient.invalidateQueries({ queryKey: ["attribution-unallocated"] });
    },
  });
};

export const useDeleteAttributionRule = () => {
  const { accessToken } = useAuthorized();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (ruleId: string) => deleteAttributionRuleCall(accessToken!, ruleId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: RULES_KEY });
      await queryClient.invalidateQueries({ queryKey: ["attribution-unallocated"] });
    },
  });
};
