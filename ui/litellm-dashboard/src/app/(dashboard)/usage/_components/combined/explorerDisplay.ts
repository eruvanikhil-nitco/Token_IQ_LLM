import type { ExplorerSlice } from "@/components/networking";

export const DIMENSIONS = [
  { value: "team", label: "Team" },
  { value: "project", label: "Project" },
  { value: "user", label: "User" },
  { value: "provider", label: "Provider" },
  { value: "model", label: "Model" },
] as const;

export type ExplorerDimension = (typeof DIMENSIONS)[number]["value"];

/**
 * Bar width as a percentage of the widest slice.
 *
 * Amounts are exact digit strings and are only ever parsed here, for geometry. Nothing a
 * reader sees as money passes through a float: the labels print the original string.
 */
export const barWidths = (slices: readonly ExplorerSlice[]): readonly { gateway: number; outside: number }[] => {
  const totals = slices.map((s) => Number(s.through_gateway) + Number(s.outside_gateway));
  const widest = Math.max(...totals, 0);
  if (widest <= 0) return slices.map(() => ({ gateway: 0, outside: 0 }));
  return slices.map((s) => ({
    gateway: (Number(s.through_gateway) / widest) * 100,
    outside: (Number(s.outside_gateway) / widest) * 100,
  }));
};

/**
 * The two series stack rather than sit side by side, and that is deliberate.
 *
 * They are disjoint by construction: outside-gateway spend is what the provider charged BEYOND
 * what the gateway recorded, so the two never describe the same money and their sum is a real
 * total. Stacking the provider figure on the gateway figure would be the double count the
 * counting rule forbids; stacking the excess on it is not.
 */
export const stackIsATotal = true;
