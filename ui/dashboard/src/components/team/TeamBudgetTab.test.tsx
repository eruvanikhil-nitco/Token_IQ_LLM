import { describe, expect, it } from "vitest";
import { renderWithProviders, screen } from "../../../tests/test-utils";
import TeamBudgetTab from "./TeamBudgetTab";

describe("TeamBudgetTab", () => {
  it("shows spend against the limit, when it resets, and that the gateway enforces it", () => {
    renderWithProviders(
      <TeamBudgetTab spend={25} maxBudget={100} budgetDuration="30d" budgetResetAt={null} memberBudget={null} />,
    );

    expect(screen.getByText("$25.00")).toBeInTheDocument();
    expect(screen.getByText("of $100.00 budget")).toBeInTheDocument();
    expect(screen.getByRole("meter")).toHaveAttribute("aria-valuenow", "25");
    expect(screen.getByText("Resets every 30d")).toBeInTheDocument();
    expect(screen.getByText(/the gateway blocks further requests/)).toBeInTheDocument();
    expect(screen.getByText("No per-member budget")).toBeInTheDocument();
  });

  it("says there is no limit and draws no meter for a team without a budget", () => {
    renderWithProviders(
      <TeamBudgetTab spend={25} maxBudget={null} budgetDuration={null} budgetResetAt={null} memberBudget={null} />,
    );

    expect(screen.getByText("No budget limit")).toBeInTheDocument();
    expect(screen.queryByRole("meter")).not.toBeInTheDocument();
    expect(screen.getByText("Never resets")).toBeInTheDocument();
  });

  it("shows the per-member budget when the team sets one", () => {
    renderWithProviders(
      <TeamBudgetTab
        spend={0}
        maxBudget={null}
        budgetDuration={null}
        budgetResetAt={null}
        memberBudget={{ max_budget: 500, budget_duration: "7d" }}
      />,
    );

    expect(screen.getByText("$500.00 per member, resets every 7d")).toBeInTheDocument();
  });
});
