import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
import {
  addCurrencyRateCall,
  addProviderRateCall,
  currencyRatesCall,
  deleteCurrencyRateCall,
  deleteProviderRateCall,
  providerRatesCall,
} from "@/components/networking";
import { all_admin_roles } from "@/utils/roles";
import type { CurrencyRate, CurrencyRateBody, ProviderRate, ProviderRateBody } from "@/components/networking";

const PROVIDER_RATES_KEY = ["pricing-provider-rates"];
const CURRENCY_RATES_KEY = ["pricing-currency-rates"];

export const useProviderRates = () => {
  const { accessToken, userRole } = useAuthorized();

  return useQuery<ProviderRate[]>({
    queryKey: PROVIDER_RATES_KEY,
    queryFn: async () => providerRatesCall(accessToken!),
    enabled: Boolean(accessToken) && all_admin_roles.includes(userRole ?? ""),
  });
};

/**
 * Recording a rate changes what every past and future figure costs, so nothing that reads a cost
 * may keep its cached answer: the ledger, the overview and the explorer all re-ask.
 */
export const useAddProviderRate = () => {
  const { accessToken } = useAuthorized();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (body: ProviderRateBody) => addProviderRateCall(accessToken!, body),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: PROVIDER_RATES_KEY });
      await queryClient.invalidateQueries({ queryKey: ["ledger-lines"] });
      await queryClient.invalidateQueries({ queryKey: ["overview"] });
    },
  });
};

export const useDeleteProviderRate = () => {
  const { accessToken } = useAuthorized();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (rateId: string) => deleteProviderRateCall(accessToken!, rateId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: PROVIDER_RATES_KEY });
      await queryClient.invalidateQueries({ queryKey: ["ledger-lines"] });
      await queryClient.invalidateQueries({ queryKey: ["overview"] });
    },
  });
};

export const useCurrencyRates = () => {
  const { accessToken, userRole } = useAuthorized();

  return useQuery<CurrencyRate[]>({
    queryKey: CURRENCY_RATES_KEY,
    queryFn: async () => currencyRatesCall(accessToken!),
    enabled: Boolean(accessToken) && all_admin_roles.includes(userRole ?? ""),
  });
};

export const useAddCurrencyRate = () => {
  const { accessToken } = useAuthorized();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (body: CurrencyRateBody) => addCurrencyRateCall(accessToken!, body),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: CURRENCY_RATES_KEY });
    },
  });
};

export const useDeleteCurrencyRate = () => {
  const { accessToken } = useAuthorized();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (rateId: string) => deleteCurrencyRateCall(accessToken!, rateId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: CURRENCY_RATES_KEY });
    },
  });
};
