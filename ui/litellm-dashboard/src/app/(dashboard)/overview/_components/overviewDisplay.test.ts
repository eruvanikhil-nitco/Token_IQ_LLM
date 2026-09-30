import { describe, expect, it } from "vitest";

import {
  MATCH_LABEL,
  MATCH_TONE,
  changeDirection,
  changeLabel,
  formatAmount,
  formatShare,
  formatSynced,
} from "./overviewDisplay";

describe("formatAmount", () => {
  it("shows a dash rather than a zero when there is no figure", () => {
    /* Zero asserts the company spent nothing. On a landing page that reads as "you are free"
       when the truth is "nothing is connected yet". */
    expect(formatAmount(null)).toBe("—");
    expect(formatAmount("")).toBe("—");
    expect(formatAmount(null)).not.toContain("0");
  });

  it("rounds a headline tile for reading, since nothing on this page is subtracted from it", () => {
    expect(formatAmount("1234.567")).toBe("$1,234.57");
  });

  it("still shows a real amount under a cent rather than rounding it away to nothing", () => {
    expect(formatAmount("0.00780515")).toBe("$0.0078");
    expect(formatAmount("0.0000072")).not.toBe("$0.00");
  });
});

describe("changeLabel", () => {
  it("tells a rise from a fall in words, not only by colour", () => {
    expect(changeLabel("50")).toContain("Up");
    expect(changeLabel("-50")).toContain("Down");
  });

  it("drops the minus sign from the amount it shows", () => {
    expect(changeLabel("-50")).toContain("$50");
    expect(changeLabel("-50")).not.toContain("$-50");
  });

  it("says there is nothing to compare against rather than leaving a blank", () => {
    /* A blank space next to a number looks like a figure that failed to load. */
    expect(changeLabel(null)).toMatch(/no earlier period/i);
  });
});

describe("changeDirection", () => {
  it("separates up, down and unknown", () => {
    expect(changeDirection("5")).toBe("up");
    expect(changeDirection("-5")).toBe("down");
    expect(changeDirection(null)).toBe("unknown");
  });
});

describe("match status", () => {
  it("gives every state words, so colour is never the only signal", () => {
    for (const label of Object.values(MATCH_LABEL)) {
      expect(label.trim().length).toBeGreaterThan(0);
    }
  });

  it("tells a bill bigger than the gateway's record apart from a smaller one", () => {
    expect(MATCH_LABEL.gateway_saw_less).not.toEqual(MATCH_LABEL.gateway_saw_more);
  });

  it("does not mark a provider read only through its bill as a problem", () => {
    /* It is a normal way to run. A permanent amber badge on a working connection teaches
       people to ignore the column. */
    expect(MATCH_TONE.not_seen_by_gateway).toBe("neutral");
    expect(MATCH_TONE.matched).toBe("good");
    expect(MATCH_TONE.gateway_saw_less).toBe("warning");
  });
});

describe("formatSynced", () => {
  it("says never rather than showing an empty cell", () => {
    expect(formatSynced(null)).toBe("Never");
  });

  it("says never rather than Invalid Date when the time cannot be read", () => {
    expect(formatSynced("not a date")).toBe("Never");
  });

  it("renders a real time", () => {
    expect(formatSynced("2026-09-18T11:11:46+00:00")).not.toBe("Never");
  });
});

describe("formatShare", () => {
  it("shows a dash rather than nought per cent when the share cannot be worked out", () => {
    expect(formatShare(null)).toBe("—");
  });

  it("renders a share with its unit", () => {
    expect(formatShare("99.3")).toBe("99.3%");
  });
});
