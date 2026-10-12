import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
import { deleteInvoiceCall, invoicesCall, upsertInvoiceCall } from "@/components/networking";
import { all_admin_roles } from "@/utils/roles";
import type { Adjustment, InvoiceListResponse } from "@/components/networking";

import { UPLOADS_KEY } from "./useUploads";

const INVOICES_KEY = ["ledger-invoices"];

export const useInvoices = () => {
  const { accessToken, userRole } = useAuthorized();

  return useQuery<InvoiceListResponse>({
    queryKey: INVOICES_KEY,
    queryFn: async () => invoicesCall(accessToken!),
    enabled: Boolean(accessToken) && all_admin_roles.includes(userRole ?? ""),
  });
};

export interface InvoiceDraft {
  provider: string;
  period_start: string;
  period_end: string;
  currency: string;
  total: string;
  adjustments: Adjustment[];
  note?: string | null;
}

/**
 * Saving or deleting a bill invalidates the reconciliation as well as the list.
 *
 * A bill is the only thing reconciliation compares the ledger against, so leaving that query
 * cached would show an admin the verdict from before their own edit.
 */
export const useSaveInvoice = () => {
  const { accessToken } = useAuthorized();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (draft: InvoiceDraft) => upsertInvoiceCall(accessToken!, draft),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: INVOICES_KEY });
      await queryClient.invalidateQueries({ queryKey: ["ledger-reconciliation"] });
      // The Uploads tab is the list a bill was most likely entered from, and the row it just
      // filled in is the one still saying no bill has been entered.
      await queryClient.invalidateQueries({ queryKey: UPLOADS_KEY });
    },
  });
};

export const useDeleteInvoice = () => {
  const { accessToken } = useAuthorized();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (invoiceId: string) => deleteInvoiceCall(accessToken!, invoiceId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: INVOICES_KEY });
      await queryClient.invalidateQueries({ queryKey: ["ledger-reconciliation"] });
      // The Uploads tab is the list a bill was most likely entered from, and the row it just
      // filled in is the one still saying no bill has been entered.
      await queryClient.invalidateQueries({ queryKey: UPLOADS_KEY });
    },
  });
};
