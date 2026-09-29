import { describe, expect, it } from "vitest";

import type { ConnectionState } from "./connectionState";
import { stateBadgeVariant, stateLabel, verificationBadgeVariant, verificationLabel } from "./connectionState";

describe("connection state presentation", () => {
  it("names every state in plain language", () => {
    expect(stateLabel("not_connected")).toBe("Not connected");
    expect(stateLabel("waiting_for_first_data")).toBe("Waiting for first data");
    expect(stateLabel("healthy")).toBe("Healthy");
    expect(stateLabel("needs_attention")).toBe("Needs attention");
  });

  it("marks only a failing connection as destructive", () => {
    // Colouring 'waiting for first data' like a failure would send admins looking for a
    // problem on a connection that is working exactly as designed.
    expect(stateBadgeVariant("needs_attention")).toBe("destructive");
    expect(stateBadgeVariant("healthy")).toBe("default");
    expect(stateBadgeVariant("waiting_for_first_data")).toBe("secondary");
    expect(stateBadgeVariant("not_connected")).toBe("outline");
  });

  it("shows a state it does not recognise plainly, not as a calm default", () => {
    // A build one release behind the backend can see a state outside this union. Blanking the
    // label or colouring it like "not connected" would hide exactly the case a human needs to
    // notice, so an unknown state must fail toward visible and destructive, never toward calm.
    const unknownState = "pending_migration" as ConnectionState;

    expect(stateLabel(unknownState)).toBe("pending_migration");
    expect(stateBadgeVariant(unknownState)).toBe("destructive");
  });
});

describe("verification", () => {
  it("says plainly when a connector has never met a real account", () => {
    expect(verificationLabel(false)).toContain("Never run against a real account");
  });

  it("says so when it has, so the two are never confused", () => {
    expect(verificationLabel(true)).not.toContain("Never");
    expect(verificationLabel(true)).toContain("Proved");
  });

  it("does not dress an unverified connector up as a problem, because it may just be unused", () => {
    expect(verificationBadgeVariant(false)).toBe("outline");
  });
});
