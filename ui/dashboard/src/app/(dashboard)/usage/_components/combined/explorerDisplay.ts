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
