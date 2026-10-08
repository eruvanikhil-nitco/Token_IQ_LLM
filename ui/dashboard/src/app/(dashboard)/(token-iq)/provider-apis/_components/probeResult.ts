import type { BillingProbeResult } from "@/components/networking";

export type ProbeTone = "good" | "warning" | "bad";

/**
 * What a connection test actually told us.
 *
 * The detail the probe returns is passed through untouched rather than folded into a generic
 * failure message. The whole value of this button is telling someone which of a wrong key, a
 * missing entitlement, a wrong account or a provider outage they are looking at, and every one
 * of those arrives as a different sentence from the provider.
 */
export const probeHeadline = (result: BillingProbeResult): string => {
  switch (result.outcome) {
    case "fetched":
      return result.facts_found > 0
        ? `The provider answered and reported ${result.facts_found} cost ${result.facts_found === 1 ? "row" : "rows"}`
        : "The provider answered, but reported no cost in this window";
    case "not_configured":
      return "Nothing was tried, because this provider has no usable credential yet";
    case "failed":
      return "The provider refused or could not answer";
    case "no_connector":
      return "This build has no connector for that provider";
  }
};

export const probeTone = (result: BillingProbeResult): ProbeTone => {
  if (result.outcome === "fetched") return result.facts_found > 0 ? "good" : "warning";
  if (result.outcome === "not_configured") return "warning";
  return "bad";
};

/** True once a probe has proved the credential really reaches the provider and gets data back. */
export const provedAgainstRealAccount = (result: BillingProbeResult): boolean =>
  result.outcome === "fetched" && result.facts_found > 0;
