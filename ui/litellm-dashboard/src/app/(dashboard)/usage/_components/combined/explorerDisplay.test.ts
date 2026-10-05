import { describe, expect, it } from "vitest";

import { DIMENSIONS, barWidths } from "./explorerDisplay";
import type { ExplorerSlice } from "@/components/networking";

const slice = (through: string, outside: string, key = "t-1"): ExplorerSlice => ({
  key,
  name: key,
  through_gateway: through,
  outside_gateway: outside,
});

describe("barWidths", () => {
  it("scales every bar against the largest total, so the widest fills the row", () => {
    const widths = barWidths([slice("10", "0"), slice("5", "0", "t-2")]);
    expect(widths[0].gateway).toBe(100);
    expect(widths[1].gateway).toBe(50);
  });

  it("gives the two parts of one bar their own widths", () => {
    const widths = barWidths([slice("6", "4")]);
    expect(widths[0].gateway).toBe(60);
    expect(widths[0].outside).toBe(40);
  });

  it("draws nothing rather than dividing by zero when there is no spend", () => {
    const widths = barWidths([slice("0", "0")]);
    expect(widths[0]).toEqual({ gateway: 0, outside: 0 });
  });

  it("handles an empty set without producing a bar", () => {
    expect(barWidths([])).toEqual([]);
  });
});

describe("dimensions", () => {
  it("offers exactly the groupings the backend can answer", () => {
    expect(DIMENSIONS.map((d) => d.value)).toEqual(["team", "project", "user", "provider", "model"]);
  });
});
