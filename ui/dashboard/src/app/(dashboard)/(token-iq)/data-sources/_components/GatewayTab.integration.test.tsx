/* @vitest-environment jsdom */
import { fireEvent, render, screen } from "@testing-library/react";
import { withNuqsTestingAdapter } from "nuqs/adapters/testing";
import { describe, expect, it, vi } from "vitest";

import GatewayTab from "./GatewayTab";

/**
 * Proves the wiring the unit tests on `gatewayViews` cannot reach: that the view named in the URL
 * decides which of the three screens renders, and that each one is the component the page it
 * replaced rendered rather than a copy of it.
 *
 * The three panels are stubbed at the module boundary. Each is a whole page with its own tests and
 * its own network calls, and what is under test here is which one this tab mounts.
 */

vi.mock("@/components/view_logs/RequestLogsPanel", () => ({
  default: () => <div data-testid="request-logs-panel" />,
}));
vi.mock("@/app/(dashboard)/api-keys/ApiKeysDashboard", () => ({
  default: () => <div data-testid="api-keys-dashboard" />,
}));
vi.mock("@/components/model_add/CredentialsPanel", () => ({
  default: () => <div data-testid="credentials-panel" />,
}));

vi.mock("@/app/(dashboard)/hooks/useAuthorized", () => ({
  default: () => ({
    accessToken: "sk-test",
    userRole: "proxy_admin",
    userId: "u1",
    token: "jwt",
    premiumUser: false,
  }),
}));

const renderTab = (searchParams = "") =>
  render(<GatewayTab />, { wrapper: withNuqsTestingAdapter({ searchParams }) });

describe("the Gateway tab", () => {
  it("opens on the request log, which is what observed traffic looks like", () => {
    renderTab();

    expect(screen.getByTestId("request-logs-panel")).toBeInTheDocument();
  });

  it("shows the view the URL names, so a link to one of them is a link to it", () => {
    // The blueprint writes this address itself: /data-sources/gateway?view=upstreams
    renderTab("?view=upstreams");

    expect(screen.getByTestId("credentials-panel")).toBeInTheDocument();
    expect(screen.queryByTestId("request-logs-panel")).not.toBeInTheDocument();
  });

  it("shows virtual keys when the URL names them", () => {
    renderTab("?view=virtual-keys");

    expect(screen.getByTestId("api-keys-dashboard")).toBeInTheDocument();
  });

  it("falls back to the first view rather than a blank tab when the URL names nothing real", () => {
    // A stale bookmark would otherwise land on an empty tab, which reads exactly like an outage.
    renderTab("?view=upstream");

    expect(screen.getByTestId("request-logs-panel")).toBeInTheDocument();
  });

  it("swaps the screen when a view is chosen", () => {
    renderTab();

    fireEvent.click(screen.getByRole("radio", { name: "Upstreams" }));

    expect(screen.getByTestId("credentials-panel")).toBeInTheDocument();
  });

  it("marks the view being read, so the switcher says where you are", () => {
    renderTab("?view=virtual-keys");

    expect(screen.getByRole("radio", { name: "Virtual keys" })).toBeChecked();
    expect(screen.getByRole("radio", { name: "Upstreams" })).not.toBeChecked();
  });

  it("offers all three views whichever one is open", () => {
    renderTab("?view=upstreams");

    for (const label of ["Request log", "Virtual keys", "Upstreams"]) {
      expect(screen.getByRole("radio", { name: label })).toBeInTheDocument();
    }
  });

  it("says what the view is, in a sentence", () => {
    renderTab("?view=upstreams");

    expect(screen.getByText(/credentials the gateway forwards with/)).toBeInTheDocument();
  });

  it("names where the audit log and the deleted keys went", () => {
    // The Logs page kept three views that record what administrators did rather than what the
    // gateway observed. Folded in they would be gateway traffic; unnamed they would be lost.
    renderTab();

    expect(screen.getByText(/audit log, deleted keys and deleted teams/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Logs" })).toHaveAttribute("href", "/ui/logs/");
  });

  it("links to the configuration behind an upstream rather than nesting it here", () => {
    // Both pages carry their own tabs, and the blueprint's rule is that a tab inside a tab stops
    // there.
    renderTab("?view=upstreams");

    expect(screen.getByText(/What each upstream serves/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Providers" })).toHaveAttribute("href", "/ui/providers/");
    expect(screen.getByRole("link", { name: "Models + Endpoints" })).toHaveAttribute(
      "href",
      "/ui/models-and-endpoints/",
    );
  });
});
