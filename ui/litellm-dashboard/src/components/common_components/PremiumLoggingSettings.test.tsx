import React from "react";
import { describe, it, expect, vi } from "vitest";
import { renderWithProviders, screen } from "../../../tests/test-utils";
import PremiumLoggingSettings from "./PremiumLoggingSettings";

describe("PremiumLoggingSettings", () => {
  it("renders nothing at all for a free user, with no Enterprise upsell", () => {
    const { container } = renderWithProviders(<PremiumLoggingSettings value={[]} onChange={vi.fn()} />);

    expect(container).toBeEmptyDOMElement();
    expect(screen.queryByText(/Token IQ Enterprise feature/)).not.toBeInTheDocument();
    expect(screen.queryByText("✨ langfuse-logging")).not.toBeInTheDocument();
    expect(screen.queryByText("Logging Integrations")).not.toBeInTheDocument();
  });

  it("renders the editor for a premium user", () => {
    renderWithProviders(<PremiumLoggingSettings value={[]} onChange={vi.fn()} premiumUser />);

    expect(screen.getByText("Logging Integrations")).toBeInTheDocument();
    expect(screen.queryByText(/Token IQ Enterprise feature/)).not.toBeInTheDocument();
  });
});
