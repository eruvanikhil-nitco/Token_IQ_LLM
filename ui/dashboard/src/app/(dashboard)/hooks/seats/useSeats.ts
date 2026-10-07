import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
import { deleteSeatCall, seatsCall, upsertSeatCall } from "@/components/networking";
import { all_admin_roles } from "@/utils/roles";
import type { SeatCadence, SeatListResponse } from "@/components/networking";

const SEATS_KEY = ["seats"];

export const useSeats = () => {
  const { accessToken, userRole } = useAuthorized();

  return useQuery<SeatListResponse>({
    queryKey: SEATS_KEY,
    queryFn: async () => seatsCall(accessToken!),
    enabled: Boolean(accessToken) && all_admin_roles.includes(userRole ?? ""),
  });
};

export interface SeatDraft {
  tool: string;
  user_id: string;
  cadence: SeatCadence;
  currency: string;
  amount: string;
  period_start: string;
  period_end: string;
  note?: string | null;
}

/**
 * Saving or removing a seat invalidates the per-person costs as well as the seat list.
 *
 * A seat is part of a person's total, so leaving those cached would show an admin the figures
 * from before their own edit.
 */
export const useSaveSeat = () => {
  const { accessToken } = useAuthorized();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (draft: SeatDraft) => upsertSeatCall(accessToken!, draft),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: SEATS_KEY });
      await queryClient.invalidateQueries({ queryKey: ["user-costs"] });
      await queryClient.invalidateQueries({ queryKey: ["user-cost"] });
    },
  });
};

export const useDeleteSeat = () => {
  const { accessToken } = useAuthorized();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (seatId: string) => deleteSeatCall(accessToken!, seatId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: SEATS_KEY });
      await queryClient.invalidateQueries({ queryKey: ["user-costs"] });
      await queryClient.invalidateQueries({ queryKey: ["user-cost"] });
    },
  });
};
