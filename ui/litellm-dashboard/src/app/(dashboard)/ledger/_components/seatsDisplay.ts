import type { SeatCadence, UserCost } from "@/components/networking";

export const CADENCE_LABEL: Record<SeatCadence, string> = {
  monthly: "Monthly",
  annual: "Annual",
};

/**
 * Whether this person's figure is missing a part, and should say so.
 *
 * Always true while no user tool is connected. It reads from the response rather than being
 * hardcoded here, so the day a connector lands the screen stops warning on its own.
 */
export const isIncomplete = (cost: UserCost): boolean => !cost.tool_usage_known;

/** A person with no subscription in the currency asked for, which is not the same as none at all. */
export const hasNoSeats = (cost: UserCost): boolean => cost.seat_lines.length === 0;
