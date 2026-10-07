import { describe, expect, it } from "vitest";
import { hasDetail, objectKindOptions, objectLabel, renderValue, shortId, type AuditEntry } from "./auditRows";

const entry = (overrides: Partial<AuditEntry> = {}): AuditEntry => ({
  id: "a1",
  changed_at: "2026-09-10T10:31:20",
  action: "updated",
  table_name: "LiteLLM_TeamTable",
  object_id: "cd4318d5-f2f7-4182-992d-46fad28beb9b",
  changed_by: "default_user_id",
  summary: "max_budget",
  changes: [{ field: "max_budget", before: "5.0", after: "12.5" }],
  ...overrides,
});

describe("objectLabel", () => {
  it("says what a person would say, not what the table is called", () => {
    expect(objectLabel("LiteLLM_VerificationToken")).toBe("Virtual key");
    expect(objectLabel("LiteLLM_TeamTable")).toBe("Team");
    expect(objectLabel("LiteLLM_ProxyModelTable")).toBe("Model");
  });

  it("falls back to the raw name rather than hiding an unmapped table", () => {
    // A new table upstream should still be visible, just unlabelled.
    expect(objectLabel("LiteLLM_SomethingNew")).toBe("LiteLLM_SomethingNew");
  });
});

describe("objectKindOptions", () => {
  it("lists each kind once, labelled and alphabetical", () => {
    const entries = [
      entry({ table_name: "LiteLLM_VerificationToken" }),
      entry({ table_name: "LiteLLM_TeamTable" }),
      entry({ table_name: "LiteLLM_VerificationToken" }),
    ];

    expect(objectKindOptions(entries)).toEqual([
      { value: "LiteLLM_TeamTable", label: "Team" },
      { value: "LiteLLM_VerificationToken", label: "Virtual key" },
    ]);
  });

  it("is empty when there is nothing recorded", () => {
    expect(objectKindOptions([])).toEqual([]);
  });
});

describe("shortId", () => {
  it("shortens a long id but keeps the recognisable start", () => {
    expect(shortId("cd4318d5-f2f7-4182-992d-46fad28beb9b")).toBe("cd4318d5-f2f…");
  });

  it("leaves a short id alone rather than adding an ellipsis to nothing", () => {
    expect(shortId("short")).toBe("short");
  });
});

describe("hasDetail", () => {
  it("is false when nothing changed, so the row is not expandable for no reason", () => {
    expect(hasDetail(entry({ changes: [] }))).toBe(false);
  });

  it("is true when there is something to show", () => {
    expect(hasDetail(entry())).toBe(true);
  });
});

describe("renderValue", () => {
  it("shows the value when there is one", () => {
    expect(renderValue("5.0", "updated")).toBe("5.0");
  });

  it("reads as not set on a creation, where nothing was there before", () => {
    expect(renderValue(null, "created")).toBe("not set");
  });

  it("reads as removed on an update or deletion, where something was there", () => {
    expect(renderValue(null, "updated")).toBe("removed");
    expect(renderValue(null, "deleted")).toBe("removed");
  });

  it("does not confuse an empty string with a missing value", () => {
    // "" is a real value someone set; null means the field was absent.
    expect(renderValue("", "updated")).toBe("");
  });
});
