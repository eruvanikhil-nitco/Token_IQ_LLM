import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
import { decideRecommendationCall, recommendationsCall, undoRecommendationCall } from "@/components/networking";
import { all_admin_roles } from "@/utils/roles";
import type { RecommendationDecision, RecommendationsResponse } from "@/components/networking";

const KEY = ["recommendations"];

export const useRecommendations = (periodStart: string, periodEnd: string) => {
  const { accessToken, userRole } = useAuthorized();

  return useQuery<RecommendationsResponse>({
    queryKey: [...KEY, periodStart, periodEnd],
    queryFn: async () => recommendationsCall(accessToken!, periodStart, periodEnd),
    enabled: Boolean(accessToken) && all_admin_roles.includes(userRole ?? ""),
  });
};

export const useDecideRecommendation = () => {
  const { accessToken } = useAuthorized();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (input: { ruleId: string; state: RecommendationDecision }) =>
      decideRecommendationCall(accessToken!, input.ruleId, input.state),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: KEY });
    },
  });
};

export const useUndoRecommendation = () => {
  const { accessToken } = useAuthorized();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (ruleId: string) => undoRecommendationCall(accessToken!, ruleId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: KEY });
    },
  });
};
