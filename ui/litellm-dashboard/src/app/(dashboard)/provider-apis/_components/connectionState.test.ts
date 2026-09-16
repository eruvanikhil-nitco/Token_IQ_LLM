import { describe, expect, it } from "vitest";

import { STATE_LABELS, stateBadgeVariant } from "./connectionState";

describe("connection state presentation", () => {
  it("names every state in plain language", () => {
    expect(STATE_LABELS).toEqual({
      not_connected: "Not connected",
      waiting_for_first_data: "Waiting for first data",
      healthy: "Healthy",
      needs_attention: "Needs attention",
    });
  });

  it("marks only a failing connection as destructive", () => {
    // Colouring 'waiting for first data' like a failure would send admins looking for a
    // problem on a connection that is working exactly as designed.
    expect(stateBadgeVariant("needs_attention")).toBe("destructive");
    expect(stateBadgeVariant("healthy")).toBe("default");
    expect(stateBadgeVariant("waiting_for_first_data")).toBe("secondary");
    expect(stateBadgeVariant("not_connected")).toBe("outline");
  });
});
