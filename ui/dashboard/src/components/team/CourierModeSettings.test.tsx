import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import CourierModeSettings, { ApiAccessMode, ProviderCoverage } from "./CourierModeSettings";

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
      apiAccessMode={"both" as ApiAccessMode}
      onApiAccessModeChange={vi.fn()}
      coverage={[covered]}
      unboundKeyCount={0}
      {...props}
    />,
  );

describe("CourierModeSettings", () => {
  it("shows the mode the team is actually stored as", () => {
    renderPanel({ apiAccessMode: "courier" });
    expect(screen.getByRole("radio", { name: /courier only/i })).toBeChecked();
    expect(screen.getByRole("radio", { name: /either/i })).not.toBeChecked();
  });

  it("offers all three, because a boolean could not say 'either while we migrate'", () => {
    renderPanel();
    expect(screen.getAllByRole("radio")).toHaveLength(3);
  });

  it("reports the admin's choice", async () => {
    const onChange = vi.fn();
    renderPanel({ onApiAccessModeChange: onChange });

    await userEvent.click(screen.getByRole("radio", { name: /translating only/i }));

    expect(onChange).toHaveBeenCalledWith("translator");
  });

  it("warns that courier only will refuse apps still on the shared address", () => {
    renderPanel({ apiAccessMode: "courier" });
    expect(screen.getByText(/will be refused until they are updated/i)).toBeInTheDocument();
  });

  it("does not warn about breakage for the mode that breaks nothing", () => {
    renderPanel({ apiAccessMode: "both" });
    expect(screen.queryByText(/will be refused until they are updated/i)).not.toBeInTheDocument();
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

  it("hides the provider detail for a team that will never use a provider address", () => {
    renderPanel({ apiAccessMode: "translator", coverage: [billsNothing] });
    expect(screen.queryByText("Records no cost")).not.toBeInTheDocument();
  });
});
