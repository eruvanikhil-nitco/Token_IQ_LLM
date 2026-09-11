import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import CourierModeSettings, { ProviderCoverage, modelsThatStopMatching } from "./CourierModeSettings";

const covered: ProviderCoverage = {
  provider: "openrouter",
  has_route: true,
  reads_usage: true,
  is_covered: true,
  summary: "Supported: the courier route exists and usage is read back for billing.",
  deployments_ready: ["openrouter/openai/gpt-4o-mini"],
  deployments_needing_opt_in: [],
};

const billsNothing: ProviderCoverage = {
  provider: "bedrock",
  has_route: true,
  reads_usage: false,
  is_covered: false,
  summary: "Carries traffic but records no cost. Spend for this provider would be missing.",
  deployments_ready: [],
  deployments_needing_opt_in: [],
};

const unavailable: ProviderCoverage = {
  provider: "voyage",
  has_route: false,
  reads_usage: false,
  is_covered: false,
  summary: "No courier route. This provider cannot be used in courier mode.",
  deployments_ready: [],
  deployments_needing_opt_in: [],
};

const needsOptIn: ProviderCoverage = {
  ...covered,
  provider: "anthropic",
  deployments_ready: [],
  deployments_needing_opt_in: ["anthropic-haiku-4-5", "anthropic-sonnet-5"],
};

const renderPanel = (props: Partial<React.ComponentProps<typeof CourierModeSettings>> = {}) =>
  render(
    <CourierModeSettings
      courierMode={true}
      onCourierModeChange={vi.fn()}
      coverage={[covered]}
      teamModels={[]}
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

  it("names the deployments that will fail on credentials, and the fix", () => {
    renderPanel({ coverage: [needsOptIn] });
    expect(screen.getByText(/fail on credentials until pass-through is enabled/i)).toBeInTheDocument();
    expect(screen.getByText(/anthropic-haiku-4-5, anthropic-sonnet-5/)).toBeInTheDocument();
  });

  it("warns which permitted models stop matching once the team is switched", () => {
    renderPanel({ teamModels: ["openrouter/openai/gpt-4o-mini", "some-local-alias"] });
    expect(screen.getByText(/these permitted models will stop matching/i)).toBeInTheDocument();
    expect(screen.getByText(/openrouter\/openai\/gpt-4o-mini/)).toBeInTheDocument();
  });

  it("hides the coverage detail when courier mode is off", () => {
    renderPanel({ courierMode: false, coverage: [billsNothing] });
    expect(screen.queryByText("Records no cost")).not.toBeInTheDocument();
  });
});

describe("modelsThatStopMatching", () => {
  it("flags models whose provider has a courier route", () => {
    expect(modelsThatStopMatching(["openrouter/openai/gpt-4o-mini"], [covered])).toEqual([
      "openrouter/openai/gpt-4o-mini",
    ]);
  });

  it("leaves alone models for providers with no courier route", () => {
    expect(modelsThatStopMatching(["voyage/voyage-4-large"], [unavailable])).toEqual([]);
  });

  it("ignores aliases that name no provider", () => {
    expect(modelsThatStopMatching(["my-alias"], [covered])).toEqual([]);
  });
});
