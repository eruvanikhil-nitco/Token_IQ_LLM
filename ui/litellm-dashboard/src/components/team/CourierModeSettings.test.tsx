import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import CourierModeSettings, { ProviderCoverage } from "./CourierModeSettings";

const covered: ProviderCoverage = {
  provider: "openrouter",
  has_route: true,
  reads_usage: true,
  is_covered: true,
  summary: "Supported: the courier route exists and usage is read back for billing.",
};

const billsNothing: ProviderCoverage = {
  provider: "bedrock",
  has_route: true,
  reads_usage: false,
  is_covered: false,
  summary: "Carries traffic but records no cost. Spend for this provider would be missing.",
};

const unavailable: ProviderCoverage = {
  provider: "voyage",
  has_route: false,
  reads_usage: false,
  is_covered: false,
  summary: "No courier route. This provider cannot be used in courier mode.",
};


const renderPanel = (props: Partial<React.ComponentProps<typeof CourierModeSettings>> = {}) =>
  render(
    <CourierModeSettings
      courierMode={true}
      onCourierModeChange={vi.fn()}
      coverage={[covered]}
      unboundKeyCount={0}
      {...props}
    />,
  );

describe("CourierModeSettings", () => {
  it("reflects the team's stored setting", () => {
    renderPanel({ courierMode: false });
    expect(screen.getByRole("switch", { name: /courier mode/i })).not.toBeChecked();
  });

  it("warns that this is not a silent change, because existing apps will break", () => {
    renderPanel();
    expect(screen.getByText(/will be refused until they are updated/i)).toBeInTheDocument();
  });

  it("calls out a provider that carries traffic while recording no cost", () => {
    renderPanel({ coverage: [billsNothing] });
    expect(screen.getByText("Records no cost")).toBeInTheDocument();
    expect(screen.getByText(/spend for this provider would be missing/i)).toBeInTheDocument();
  });

  it("marks a provider with no courier route as unavailable", () => {
    renderPanel({ coverage: [unavailable] });
    expect(screen.getByText("Unavailable")).toBeInTheDocument();
  });

  it("warns when keys on the team do not name the account they spend against", () => {
    renderPanel({ unboundKeyCount: 3 });
    expect(screen.getByText(/3 keys on this team name no account/i)).toBeInTheDocument();
    expect(screen.getByText(/whichever account this gateway finds first/i)).toBeInTheDocument();
  });

  it("stays quiet when every key names its account", () => {
    renderPanel({ unboundKeyCount: 0 });
    expect(screen.queryByText(/name no account/i)).not.toBeInTheDocument();
  });

  it("hides the coverage detail when courier mode is off", () => {
    renderPanel({ courierMode: false, coverage: [billsNothing] });
    expect(screen.queryByText("Records no cost")).not.toBeInTheDocument();
  });
});
