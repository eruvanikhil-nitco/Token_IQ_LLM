import { describe, expect, it } from "vitest";
import {
  effectiveForProvider,
  filterByName,
  effectiveForTeam,
  hasOverrides,
  ruleFor,
  withRule,
  withoutUnknownSubjects,
  type CaptureTable,
} from "./captureRules";

describe("ruleFor", () => {
  it("reads the three states apart", () => {
    const table: CaptureTable = { sales: true, hr: false };

    expect(ruleFor(table, "sales")).toBe("capture");
    expect(ruleFor(table, "hr")).toBe("exclude");
    // Absent is not the same as excluded: it falls through to the provider or the default.
    expect(ruleFor(table, "support")).toBe("default");
  });

  it("treats a missing table as no rules at all", () => {
    expect(ruleFor(undefined, "hr")).toBe("default");
  });
});

describe("withRule", () => {
  it("stores an explicit decision", () => {
    expect(withRule({}, "hr", "exclude")).toEqual({ hr: false });
    expect(withRule({}, "sales", "capture")).toEqual({ sales: true });
  });

  it("removes the key when the rule goes back to the default", () => {
    // Storing null or false here would turn "no opinion" into an exclusion.
    expect(withRule({ hr: false, sales: true }, "hr", "default")).toEqual({ sales: true });
  });

  it("leaves other subjects alone", () => {
    expect(withRule({ hr: false }, "sales", "capture")).toEqual({ hr: false, sales: true });
  });

  it("does not mutate the table it was given", () => {
    const original: CaptureTable = { hr: false };

    withRule(original, "sales", "capture");

    expect(original).toEqual({ hr: false });
  });
});

describe("hasOverrides", () => {
  it("is false for nothing and for an empty table", () => {
    expect(hasOverrides(undefined)).toBe(false);
    expect(hasOverrides({})).toBe(false);
  });

  it("is true once a rule exists, including an exclusion", () => {
    expect(hasOverrides({ hr: false })).toBe(true);
  });
});

describe("effectiveForTeam", () => {
  it("falls back to the gateway default when the team has no rule", () => {
    expect(effectiveForTeam({}, "t1", "sales", true)).toBe(true);
    expect(effectiveForTeam({}, "t1", "sales", false)).toBe(false);
  });

  it("lets a rule be written against the readable alias", () => {
    expect(effectiveForTeam({ sales: false }, "t1", "sales", true)).toBe(false);
  });

  it("prefers the id when both an id and an alias rule exist", () => {
    // Aliases can be renamed or repeated; the id cannot.
    expect(effectiveForTeam({ t1: true, sales: false }, "t1", "sales", false)).toBe(true);
  });

  it("keeps an exclusion even when the gateway captures everything", () => {
    expect(effectiveForTeam({ hr: false }, "hr", undefined, true)).toBe(false);
  });
});

describe("effectiveForProvider", () => {
  it("falls back to the gateway default", () => {
    expect(effectiveForProvider({}, "bedrock", true)).toBe(true);
  });

  it("honours an explicit rule either way", () => {
    expect(effectiveForProvider({ bedrock: false }, "bedrock", true)).toBe(false);
    expect(effectiveForProvider({ bedrock: true }, "bedrock", false)).toBe(true);
  });
});

describe("withoutUnknownSubjects", () => {
  it("drops rules for subjects that no longer exist", () => {
    // Deleting a team should not leave a rule behind that silently applies to a reused name.
    expect(withoutUnknownSubjects({ hr: false, gone: true }, ["hr"])).toEqual({ hr: false });
  });

  it("keeps everything when all subjects are known", () => {
    expect(withoutUnknownSubjects({ hr: false, sales: true }, ["hr", "sales"])).toEqual({
      hr: false,
      sales: true,
    });
  });

  it("handles a missing table", () => {
    expect(withoutUnknownSubjects(undefined, ["hr"])).toEqual({});
  });
});

describe("filterByName", () => {
  const teams = [{ name: "Human Resources" }, { name: "Sales" }, { name: "sales-eu" }];
  const nameOf = (t: { name: string }) => t.name;

  it("returns everything when the search is empty or whitespace", () => {
    expect(filterByName(teams, nameOf, "")).toHaveLength(3);
    expect(filterByName(teams, nameOf, "   ")).toHaveLength(3);
  });

  it("matches anywhere in the name, not just the start", () => {
    expect(filterByName(teams, nameOf, "resource").map(nameOf)).toEqual(["Human Resources"]);
  });

  it("ignores case, because nobody types the capitalisation right", () => {
    expect(filterByName(teams, nameOf, "SALES").map(nameOf)).toEqual(["Sales", "sales-eu"]);
  });

  it("returns nothing when there is no match, so the table can say so", () => {
    expect(filterByName(teams, nameOf, "legal")).toEqual([]);
  });

  it("does not mutate or reorder the source list", () => {
    const result = filterByName(teams, nameOf, "");

    expect(result).not.toBe(teams);
    expect(result.map(nameOf)).toEqual(["Human Resources", "Sales", "sales-eu"]);
  });
});
