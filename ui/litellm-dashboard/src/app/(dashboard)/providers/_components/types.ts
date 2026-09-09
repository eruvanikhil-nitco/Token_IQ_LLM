export interface ProviderRow {
  provider: string;
  models_configured: number;
  models_in_catalogue: number;
  has_credentials: boolean;
  /** False when the provider only appears in recorded traffic, with no deployment left. */
  is_configured: boolean;
  requests: number;
  spend: number;
  last_used: string | null;
}

export interface ProviderOverviewResponse {
  total_providers: number;
  total_models: number;
  total_requests: number;
  total_spend: number;
  /** Whole UTC days the request and spend figures cover. The daily rollup cannot
   *  answer a rolling window, so the UI must not label these as "24h". */
  rollup_days: number;
  providers: ProviderRow[];
}
