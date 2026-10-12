import { describe, expect, it } from "vitest";

import { MIGRATED_PAGES } from "@/utils/migratedPages";

import {
  GATEWAY_BASE_VIEW,
  GATEWAY_VIEWS,
  GATEWAY_VIEW_SPECS,
  gatewayMovedPages,
  gatewayViewFor,
  gatewayViewHref,
} from "./gatewayViews";

/**
 * The Gateway tab is the one merge that moves pages a customer uses every day, so what these
 * assert is that nothing it absorbed became unreachable and that no `?view=` value lands nowhere.
 */

describe("the views the blueprint names", () => {
  it("covers traffic, keys and upstreams, in the blueprint's order", () => {
    expect(GATEWAY_VIEWS).toEqual(["request-log", "virtual-keys", "upstreams"]);
  });

  it("opens on the request log, which is what observed traffic looks like", () => {
    expect(GATEWAY_BASE_VIEW).toBe("request-log");
  });

  it("gives every view a label and a sentence saying what it is", () => {
    for (const view of GATEWAY_VIEWS) {
      expect(GATEWAY_VIEW_SPECS[view].label, view).toBeTruthy();
      expect(GATEWAY_VIEW_SPECS[view].description, view).toBeTruthy();
    }
  });

  it("names the upstreams view the blueprint's own path points at", () => {
    // The blueprint writes /data-sources/gateway?view=upstreams, so that value is part of the
    // contract rather than a name I chose.
    expect(GATEWAY_VIEWS).toContain("upstreams");
  });
});

describe("which page each view used to be", () => {
  it("accounts for the request log, virtual keys and the forwarding credentials", () => {
    expect(gatewayMovedPages()).toEqual(["logs", "api-keys", "llm-provider-credentials"]);
  });

  it("keeps every address it absorbed resolving", () => {
    // The trap this whole page is built around. Seven sidebar entries become one, and each of
    // them is an address somebody has bookmarked or written into a runbook.
    for (const page of gatewayMovedPages()) {
      expect(MIGRATED_PAGES[page], page).toBeTruthy();
    }
  });

  it("sends the forwarding credentials to the view that now holds them", () => {
    expect(MIGRATED_PAGES["llm-provider-credentials"]).toBe("data-sources/gateway");
  });

  it("leaves the request log and virtual keys at their own addresses", () => {
    // Both are pages for roles that cannot open Data Sources at all, so the address has to keep
    // serving the page rather than redirecting into a tab those roles are refused.
    expect(MIGRATED_PAGES["logs"]).toBe("logs");
    expect(MIGRATED_PAGES["api-keys"]).toBe("api-keys");
  });
});

describe("the view a request asks for", () => {
  it("reads a view named in the URL", () => {
    expect(gatewayViewFor("upstreams")).toBe("upstreams");
    expect(gatewayViewFor("virtual-keys")).toBe("virtual-keys");
  });

  it("opens on the first view when the URL names none", () => {
    expect(gatewayViewFor(null)).toBe("request-log");
  });

  it("opens on the first view rather than nothing when the URL names one that does not exist", () => {
    // A stale bookmark or a typo would otherwise land on a blank tab, which reads exactly like an
    // outage.
    expect(gatewayViewFor("upstream")).toBe("request-log");
    expect(gatewayViewFor("")).toBe("request-log");
  });
});

describe("a link to one view from elsewhere in the product", () => {
  it("names the view, so the reader lands on the screen the link promised", () => {
    // Three places in the product link here, all of them to the upstreams view. Without the view
    // in the address they land on the request log and have to find it.
    expect(gatewayViewHref("upstreams")).toContain("view=upstreams");
    expect(gatewayViewHref("virtual-keys")).toContain("view=virtual-keys");
  });

  it("points at the Gateway tab's own address", () => {
    expect(gatewayViewHref("upstreams")).toContain("data-sources/gateway");
  });
});
