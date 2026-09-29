import type { RecommendationFigureKind } from "@/components/networking";

/**
 * What the number beside a card actually is.
 *
 * `already_spent_unwatched` must never read as a saving. The money is being spent either way;
 * acting makes it visible and owned. A label promising a saving there would not survive a
 * finance lead asking one question, and it would discredit every other card on the screen.
 */
export const FIGURE_LABEL: Record<RecommendationFigureKind, string> = {
  could_stop_spending: "Could stop spending",
  already_spent_unwatched: "Already being spent, unwatched",
  none: "",
};

/** An amount, or nothing at all. Never a zero standing in for "we could not work this out". */
export const formatFigure = (
  figure: string | null,
  kind: RecommendationFigureKind,
  currency: string | null,
): string => {
  if (figure === null || kind === "none") return "";
  const symbol = currency === "USD" ? "$" : `${currency ?? ""} `;
  return `${symbol}${figure.trim()}`;
};

export const KIND_LABEL: Record<"business" | "technical", string> = {
  business: "Business",
  technical: "Technical",
};

export const DECISION_LABEL: Record<"done" | "dismissed", string> = {
  done: "Done",
  dismissed: "Dismissed",
};
