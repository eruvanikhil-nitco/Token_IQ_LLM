import type { ModelHubData } from "@/components/AIHub/ModelHubTableColumns";

/** Whether a row was built from recorded traffic rather than from a configured deployment. */
export const isObservedOnly = (model: ModelHubData): boolean => model.is_observed_only === true;

/**
 * Models this gateway is actually set up for.
 *
 * A config file can hold sample deployments pointing at environment variables nobody set,
 * which cannot serve a request. `/provider/overview` already decides which providers carry
 * credentials or have served traffic, so this keeps only models belonging to one of them.
 *
 * Observed-only rows are kept regardless: they exist because traffic happened, and the daily
 * table sometimes records a model group with no provider to match on.
 *
 * An undefined provider list means "not known yet", and everything is kept. Hiding models
 * because a request is in flight, or because the caller is unauthenticated as on the public
 * hub, would be worse than showing one too many.
 */
export const filterModelsByVisibleProviders = (
  models: ModelHubData[],
  visibleProviders: readonly string[] | undefined,
): ModelHubData[] => {
  if (visibleProviders === undefined) return models;
  const visible = new Set(visibleProviders);
  return models.filter((model) => isObservedOnly(model) || (model.providers ?? []).some((p) => visible.has(p)));
};
