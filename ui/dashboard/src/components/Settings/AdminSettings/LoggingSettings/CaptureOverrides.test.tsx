import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import CaptureOverrides from "./CaptureOverrides";

const teams = [
  { team_id: "t-hr", team_alias: "hr" },
  { team_id: "t-sales", team_alias: "sales" },
];

const renderOverrides = (overrides: Partial<React.ComponentProps<typeof CaptureOverrides>> = {}) => {
  const props: React.ComponentProps<typeof CaptureOverrides> = {
    teams,
    providers: ["openrouter", "bedrock"],
    globalDefault: true,
    teamTable: {},
    providerTable: {},
    onTeamTableChange: vi.fn(),
    onProviderTableChange: vi.fn(),
    ...overrides,
  };
  render(<CaptureOverrides {...props} />);
  return props;
};

describe("CaptureOverrides", () => {
  it("lists every team and provider so nothing is silently unruled", () => {
    renderOverrides();

    expect(screen.getByText("hr")).toBeInTheDocument();
    expect(screen.getByText("sales")).toBeInTheDocument();
    expect(screen.getByText("openrouter")).toBeInTheDocument();
    expect(screen.getByText("bedrock")).toBeInTheDocument();
  });

  it("offers three states, because following the default is not the same as never capturing", () => {
    renderOverrides();

    const options = screen.getByLabelText("Capture rule for hr").textContent ?? "";

    expect(options).toContain("Use default");
    expect(options).toContain("Capture");
    expect(options).toContain("Never capture");
  });

  it("shows a team on the default as following the gateway", () => {
    renderOverrides({ globalDefault: true, teamTable: {} });

    expect(screen.getByLabelText("Capture rule for hr")).toHaveValue("default");
    // Effective, not the rule: the gateway captures, so this team is stored.
    expect(screen.getAllByText("Stored").length).toBeGreaterThan(0);
  });

  it("shows an excluded team as not stored even when the gateway captures everything", () => {
    renderOverrides({ globalDefault: true, teamTable: { hr: false } });

    expect(screen.getByLabelText("Capture rule for hr")).toHaveValue("exclude");
    expect(screen.getAllByText("Not stored").length).toBe(1);
  });

  it("writes an exclusion when a team is set to never capture", async () => {
    const user = userEvent.setup();
    const props = renderOverrides({ teamTable: {} });

    await user.selectOptions(screen.getByLabelText("Capture rule for hr"), "exclude");

    expect(props.onTeamTableChange).toHaveBeenCalledWith({ hr: false });
  });

  it("removes the rule when a team goes back to the default", async () => {
    const user = userEvent.setup();
    const props = renderOverrides({ teamTable: { hr: false, sales: true } });

    await user.selectOptions(screen.getByLabelText("Capture rule for hr"), "default");

    // The key goes entirely, so the saved config holds only real decisions.
    expect(props.onTeamTableChange).toHaveBeenCalledWith({ sales: true });
  });

  it("keeps team and provider tables separate", async () => {
    const user = userEvent.setup();
    const props = renderOverrides();

    await user.selectOptions(screen.getByLabelText("Capture rule for bedrock"), "exclude");

    expect(props.onProviderTableChange).toHaveBeenCalledWith({ bedrock: false });
    expect(props.onTeamTableChange).not.toHaveBeenCalled();
  });

  it("says so when there are no teams rather than rendering an empty table", () => {
    renderOverrides({ teams: [] });

    expect(screen.getByText("No teams yet.")).toBeInTheDocument();
  });

  it("tells the operator that provider rules only apply where a team has none", () => {
    renderOverrides();

    // Without this the precedence is invisible and the page looks contradictory.
    expect(screen.getByText(/Applies only where the team above has no rule/)).toBeInTheDocument();
  });
});

const manyTeams = ["hr", "sales", "support", "platform", "finance", "legal"].map((name) => ({
  team_id: `t-${name}`,
  team_alias: name,
}));

describe("CaptureOverrides search", () => {
  it("offers no search box for a handful of rows, where the eye is faster", () => {
    renderOverrides({ teams, providers: ["openrouter"] });

    expect(screen.queryByLabelText("Search teams")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Search providers")).not.toBeInTheDocument();
  });

  it("offers a search box once the list is long enough to be worth searching", () => {
    renderOverrides({ teams: manyTeams });

    expect(screen.getByLabelText("Search teams")).toBeInTheDocument();
  });

  it("narrows the rows as you type, matching anywhere in the name", () => {
    renderOverrides({ teams: manyTeams });

    fireEvent.change(screen.getByLabelText("Search teams"), { target: { value: "port" } });

    expect(screen.getByText("support")).toBeInTheDocument();
    expect(screen.queryByText("finance")).not.toBeInTheDocument();
  });

  it("ignores case", () => {
    renderOverrides({ teams: manyTeams });

    fireEvent.change(screen.getByLabelText("Search teams"), { target: { value: "LEGAL" } });

    expect(screen.getByText("legal")).toBeInTheDocument();
  });

  it("says so when nothing matches rather than showing an empty table", () => {
    renderOverrides({ teams: manyTeams });

    fireEvent.change(screen.getByLabelText("Search teams"), { target: { value: "marketing" } });

    expect(screen.getByText(/No teams match/)).toBeInTheDocument();
  });

  it("keeps rules on rows the search has hidden", async () => {
    const user = userEvent.setup();
    const props = renderOverrides({ teams: manyTeams, teamTable: { hr: false } });

    fireEvent.change(screen.getByLabelText("Search teams"), { target: { value: "sales" } });
    await user.selectOptions(screen.getByLabelText("Capture rule for sales"), "exclude");

    // hr is filtered out of view; its exclusion must survive editing something else.
    expect(props.onTeamTableChange).toHaveBeenCalledWith({ hr: false, sales: false });
  });

  it("searches providers independently of teams", () => {
    renderOverrides({ teams: manyTeams, providers: ["openrouter", "bedrock", "anthropic", "vertex_ai", "azure_ai"] });

    fireEvent.change(screen.getByLabelText("Search providers"), { target: { value: "bed" } });

    expect(screen.getByText("bedrock")).toBeInTheDocument();
    expect(screen.queryByText("anthropic")).not.toBeInTheDocument();
    // The team list is untouched by a provider search.
    expect(screen.getByText("finance")).toBeInTheDocument();
  });
});
