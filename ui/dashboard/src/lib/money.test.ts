import { describe, expect, it } from "vitest";

import { formatMoney } from "./money";

describe("formatMoney", () => {
  it("shows nothing for an absent figure rather than a zero", () => {
    expect(formatMoney(null, "USD")).toBe("—");
    expect(formatMoney("", "USD")).toBe("—");
    expect(formatMoney("   ", "USD")).toBe("—");
  });

  it("shows an ordinary amount to two decimal places", () => {
    expect(formatMoney("12.5", "USD")).toBe("$12.50");
    expect(formatMoney("0.5", "USD")).toBe("$0.50");
    expect(formatMoney("7", "USD")).toBe("$7.00");
  });

  it("groups thousands so a large figure is readable at a glance", () => {
    expect(formatMoney("1234567.891", "USD")).toBe("$1,234,567.89");
    expect(formatMoney("1000", "USD")).toBe("$1,000.00");
  });

  it("rounds half up, carrying into the integer part", () => {
    expect(formatMoney("1.995", "USD")).toBe("$2.00");
    expect(formatMoney("9.999", "USD")).toBe("$10.00");
    expect(formatMoney("999.999", "USD")).toBe("$1,000.00");
  });

  it("keeps a real amount visible instead of rounding it away to zero", () => {
    // The whole point: $0.00 asserts the company spent nothing. These did spend something.
    expect(formatMoney("0.00780515", "USD")).toBe("$0.0078");
    expect(formatMoney("0.0000072", "USD")).toBe("$0.0000072");
    expect(formatMoney("0.00005815", "USD")).toBe("$0.000058");
  });

  it("never rounds a sub-cent amount up to a whole cent", () => {
    // $0.01 for eight tenths of a cent overstates it, and overstating a bill is the one
    // direction a cost product must not err in.
    expect(formatMoney("0.005", "USD")).toBe("$0.005");
    expect(formatMoney("0.0099", "USD")).toBe("$0.0099");
    expect(formatMoney("0.01", "USD")).toBe("$0.01");
  });

  it("shows an exact zero as a plain zero, because that one really is nothing", () => {
    expect(formatMoney("0", "USD")).toBe("$0.00");
    expect(formatMoney("0.00", "USD")).toBe("$0.00");
    expect(formatMoney("0.000000", "USD")).toBe("$0.00");
  });

  it("keeps the sign on a negative amount", () => {
    expect(formatMoney("-12.5", "USD")).toBe("-$12.50");
    expect(formatMoney("-0.0000072", "USD")).toBe("-$0.0000072");
  });

  it("names a currency it has no symbol for rather than dropping it", () => {
    // Showing "10" for ten krona beside "$10" would read as the same amount.
    expect(formatMoney("10", "SEK")).toBe("SEK 10.00");
    expect(formatMoney("10", null)).toBe("10.00");
  });

  it("uses the symbol for the currencies it knows", () => {
    expect(formatMoney("10", "EUR")).toBe("€10.00");
    expect(formatMoney("10", "GBP")).toBe("£10.00");
  });

  it("never loses precision through a binary float", () => {
    // 0.1 + 0.2 territory: these digit strings cannot survive a round trip through Number.
    expect(formatMoney("9007199254740993.01", "USD")).toBe("$9,007,199,254,740,993.01");
    expect(formatMoney("0.1000000000000000055511151231257827", "USD")).toBe("$0.10");
  });

  it("refuses to guess at input that is not a decimal number", () => {
    expect(formatMoney("abc", "USD")).toBe("—");
    expect(formatMoney("1.2.3", "USD")).toBe("—");
    expect(formatMoney("1e5", "USD")).toBe("—");
  });
});
