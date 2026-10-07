import { describe, expect, it } from "vitest";

import { describeCadence, describeWindow } from "./fetchCadence";

describe("describeCadence", () => {
  it("reads five minutes as minutes, not three hundred seconds", () => {
    expect(describeCadence(300)).toBe("Every 5 minutes");
  });

  it("reads an hour as an hour", () => {
    expect(describeCadence(3600)).toBe("Every hour");
  });

  it("reads a sub-minute cadence in seconds", () => {
    expect(describeCadence(45)).toBe("Every 45 seconds");
  });
});

describe("describeWindow", () => {
  it("reads twenty four hours as a day", () => {
    expect(describeWindow(24)).toBe("The last 1 day");
  });

  it("reads a part day in hours", () => {
    expect(describeWindow(6)).toBe("The last 6 hours");
  });
});
