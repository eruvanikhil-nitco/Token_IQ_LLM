import { describe, expect, it } from "vitest";

import { probeHeadline, probeTone, provedAgainstRealAccount } from "./probeResult";
import type { BillingProbeResult } from "@/components/networking";

const result = (over: Partial<BillingProbeResult> = {}): BillingProbeResult => ({
  provider: "anthropic",
  credential_name: "acme-anthropic",
  outcome: "fetched",
  facts_found: 3,
  sample_cost: "1.25",
  detail: null,
  ...over,
});

describe("probeHeadline", () => {
  it("says how many rows came back, so a reader knows the key really works", () => {
    expect(probeHeadline(result({ facts_found: 3 }))).toContain("3 cost rows");
  });

  it("counts one row as a row rather than one rows", () => {
    expect(probeHeadline(result({ facts_found: 1 }))).toContain("1 cost row");
    expect(probeHeadline(result({ facts_found: 1 }))).not.toContain("rows");
  });

  it("separates a working key with no spend from a key that does not work", () => {
    const quiet = probeHeadline(result({ facts_found: 0, detail: "nothing in this window" }));
    const broken = probeHeadline(result({ outcome: "failed", facts_found: 0 }));

    expect(quiet).not.toEqual(broken);
    expect(quiet).toContain("answered");
  });

  it("says nothing was tried when there is no credential, rather than implying a failure", () => {
    expect(probeHeadline(result({ outcome: "not_configured", facts_found: 0 }))).toContain("Nothing was tried");
  });
});

describe("probeTone", () => {
  it("treats a key that answered with no data as a warning, not a success", () => {
    expect(probeTone(result({ facts_found: 0 }))).toBe("warning");
    expect(probeTone(result({ facts_found: 2 }))).toBe("good");
  });

  it("treats a refusal and a missing connector as bad", () => {
    expect(probeTone(result({ outcome: "failed", facts_found: 0 }))).toBe("bad");
    expect(probeTone(result({ outcome: "no_connector", facts_found: 0 }))).toBe("bad");
  });
});

describe("provedAgainstRealAccount", () => {
  it("is only true once real data came back, because that is the thing no test can fake", () => {
    expect(provedAgainstRealAccount(result({ facts_found: 2 }))).toBe(true);
    expect(provedAgainstRealAccount(result({ facts_found: 0 }))).toBe(false);
    expect(provedAgainstRealAccount(result({ outcome: "failed", facts_found: 0 }))).toBe(false);
  });
});
