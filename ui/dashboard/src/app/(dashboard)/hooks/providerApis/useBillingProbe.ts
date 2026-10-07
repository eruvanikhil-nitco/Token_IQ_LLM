import { useMutation } from "@tanstack/react-query";

import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
import { probeProviderBillingCall } from "@/components/networking";
import type { BillingProbeResult } from "@/components/networking";

/**
 * Try one provider's billing API now and report what came back.
 *
 * A mutation rather than a query: this costs a real call against the provider, so it happens
 * when someone asks for it and never on render.
 */
export const useBillingProbe = () => {
  const { accessToken } = useAuthorized();

  return useMutation<BillingProbeResult, Error, string>({
    mutationFn: async (provider: string) => probeProviderBillingCall(accessToken!, provider),
  });
};
