import type { ModelHubData } from "@/components/AIHub/ModelHubTableColumns";
import type { ProviderRow } from "./types";

export interface ModelUsageRow {
  model_group: string;
  /** Providers that served this model group. Empty when the daily rows carry no provider. */
  providers: string[];
  requests: number;
  tokens: number;
  spend: number;
}

/** Minimal shape both tables filter on. */
interface HasProviders {
  providers?: string[];
}

/**
 * The label for the usage window.
 *
 * Never says "24h": LiteLLM_DailyUserSpend buckets by whole UTC day, so the figures
 * cover whole days including today and cannot answer a rolling window.
 */
export const usageWindowLabel = (rollupDays: number): string =>
  rollupDays === 1 ? "Today (UTC)" : `Last ${rollupDays} UTC days`;

/** Provider rows narrowed to one provider, or all of them when nothing is selected. */
export const filterProviderRows = (rows: ProviderRow[], selectedProvider: string | null): ProviderRow[] =>
  selectedProvider ? rows.filter((row) => row.provider === selectedProvider) : rows;

/** Models narrowed to one provider. A model can be served by several, so this matches
 *  membership rather than equality. */
export const filterModelsByProvider = <T extends HasProviders>(models: T[], selectedProvider: string | null): T[] =>
  selectedProvider ? models.filter((model) => model.providers?.includes(selectedProvider)) : models;

/** Usage keyed by model group, for the table's per-row lookup. */
export const indexUsageByModel = (usage: ModelUsageRow[]): Map<string, ModelUsageRow> =>
  new Map(usage.map((row) => [row.model_group, row]));

/**
 * Whether a row has traffic worth rendering as numbers.
 *
 * A model with no requests renders a dash rather than zeros: "never called" and "called
 * but cost nothing" are different facts, and a model priced only by the provider can
 * legitimately show requests with zero spend.
 */
export const hasUsage = (usage: ModelUsageRow | undefined): usage is ModelUsageRow =>
  usage !== undefined && usage.requests > 0;

/**
 * Rows for models that recorded traffic but have no deployment left.
 *
 * The table is otherwise built from the configured model list, so a model removed after it
 * served requests would be fetched and then silently dropped, hiding real spend from an
 * observer gateway whose whole job is reporting what happened.
 *
 * The synthetic row carries no pricing or capabilities because the catalogue is keyed on
 * models this proxy serves; those columns render dashes, which is honest.
 */
export const observedOnlyModels = (configured: ModelHubData[], usage: ModelUsageRow[]): ModelHubData[] => {
  const known = new Set(configured.map((model) => model.model_group));
  return usage
    .filter((row) => !known.has(row.model_group) && row.requests > 0)
    .map((row) => ({
      model_group: row.model_group,
      providers: row.providers,
      supports_parallel_function_calling: false,
      supports_vision: false,
      supports_function_calling: false,
      is_public_model_group: false,
      is_observed_only: true,
    }));
};
