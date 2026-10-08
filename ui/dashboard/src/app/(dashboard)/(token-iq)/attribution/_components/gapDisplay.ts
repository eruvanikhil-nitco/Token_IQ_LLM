import type { AttributionGapState, UnallocatedLine } from "@/components/networking";

/**
 * What each state means to the person reading the screen.
 *
 * These are claims, not labels. "Matched" says the two sources agree, so it must never be shown
 * for a day the provider has not reported: that is why "no_provider_data" exists separately.
 */
export const STATE_LABEL: Record<AttributionGapState, string> = {
  owned: "Owned",
  unallocated: "No rule matches",
  matched: "Matched",
  not_settled: "Not settled yet",
  no_provider_data: "Provider reported nothing",
};

export const STATE_EXPLANATION: Record<AttributionGapState, string> = {
  owned: "A rule assigns this spend to a team, project or user.",
  unallocated: "The provider charged more than the gateway recorded, and no rule claims it.",
  matched: "The gateway recorded at least what the provider billed, so there is nothing to assign.",
  not_settled: "The provider has not finished billing this day, so no comparison is made yet.",
  no_provider_data: "The provider has reported nothing for this day, so there is nothing to compare.",
};

/** Money arrives as exact digit strings. Format for reading without ever parsing to a number. */
export const formatAmount = (amount: string | null): string => {
  if (amount === null) return "—";
  const trimmed = amount.trim();
  if (trimmed === "") return "—";
  return `$${trimmed}`;
};

export const hasOwner = (line: UnallocatedLine): boolean => line.state === "owned";

/** Only a positive unclaimed gap is worth an admin's attention; the rest is noise on this tab. */
export const needsAttention = (line: UnallocatedLine): boolean => line.state === "unallocated";
