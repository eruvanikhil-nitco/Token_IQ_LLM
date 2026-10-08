import type { MatchStatus } from "@/components/networking";
import { formatMoney } from "@/lib/money";

/** The overview endpoint reports every figure in one currency, named alongside them. */
export const formatAmount = (amount: string | null): string => formatMoney(amount, "USD");

export type ChangeDirection = "up" | "down" | "unknown";

/** Which way spend moved, or that there is nothing to compare against. */
export const changeDirection = (change: string | null): ChangeDirection => {
  if (change === null || change.trim() === "") return "unknown";
  return change.trim().startsWith("-") ? "down" : "up";
};

/**
 * How the change reads beside the total.
 *
 * A first period says so rather than showing nothing, because a blank space next to a number
 * looks like a figure that failed to load.
 */
export const changeLabel = (change: string | null): string => {
  const direction = changeDirection(change);
  if (direction === "unknown") return "No earlier period to compare";
  const amount = (change ?? "").trim().replace(/^-/, "");
  return direction === "up" ? `Up $${amount} on the period before` : `Down $${amount} on the period before`;
};

export const MATCH_LABEL: Record<MatchStatus, string> = {
  matched: "Matched",
  gateway_saw_less: "Spend bypassed the gateway",
  gateway_saw_more: "Gateway recorded more than billed",
  not_seen_by_gateway: "Read from the bill only",
};

/**
 * Colour never carries the meaning on its own, so every state also has the words above.
 *
 * `not_seen_by_gateway` is deliberately neutral rather than a warning: reading a provider
 * only through its bill is a normal way to run, and a permanent amber badge on a working
 * connection teaches people to ignore the column.
 */
export const MATCH_TONE: Record<MatchStatus, "good" | "warning" | "neutral"> = {
  matched: "good",
  gateway_saw_less: "warning",
  gateway_saw_more: "warning",
  not_seen_by_gateway: "neutral",
};

/** A sync time a person can read, or the plain truth that it has never run. */
export const formatSynced = (when: string | null): string => {
  if (when === null) return "Never";
  const parsed = new Date(when);
  return Number.isNaN(parsed.getTime()) ? "Never" : parsed.toLocaleString();
};

/**
 * What share of provider spend nobody owns.
 *
 * Absent rather than "0%" when it cannot be worked out, for the same reason as the amounts:
 * nobody owning any of nothing is not the same as everything being accounted for.
 */
export const formatShare = (share: string | null): string => (share === null ? "—" : `${share}%`);
