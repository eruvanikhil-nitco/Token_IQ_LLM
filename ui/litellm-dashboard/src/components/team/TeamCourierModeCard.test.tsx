// @vitest-environment jsdom
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const teamCourierCoverageCall = vi.fn();
const teamUpdateCall = vi.fn();

vi.mock("@/components/networking", () => ({
  teamCourierCoverageCall: (...args: unknown[]) => teamCourierCoverageCall(...args),
  teamUpdateCall: (...args: unknown[]) => teamUpdateCall(...args),
}));

const toastError = vi.fn();
vi.mock("@/lib/toast", () => ({
  toast: {
    success: vi.fn(),
    fromError: (...args: unknown[]) => toastError(...args),
  },
}));

import TeamCourierModeCard from "./TeamCourierModeCard";

const coverage = (overrides: Record<string, unknown> = {}) => ({
  team_id: "t1",
  courier_mode: false,
  unbound_key_count: 0,
  providers: [
    {
      provider: "openrouter",
      has_route: true,
      reads_usage: true,
      is_covered: true,
      summary: "Supported: the courier route exists and usage is read back for billing.",
    },
  ],
  ...overrides,
});

const renderCard = (props: Partial<React.ComponentProps<typeof TeamCourierModeCard>> = {}) => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <TeamCourierModeCard accessToken="sk-1" teamId="t1" canEditTeam={true} {...props} />
    </QueryClientProvider>,
  );
};

describe("TeamCourierModeCard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    teamCourierCoverageCall.mockResolvedValue(coverage());
    teamUpdateCall.mockResolvedValue({});
  });

  it("shows the switch set to what is actually stored for the team", async () => {
    teamCourierCoverageCall.mockResolvedValue(coverage({ courier_mode: true }));
    renderCard();

    expect(await screen.findByRole("switch", { name: /courier mode/i })).toBeChecked();
  });

  it("saves the change against this team rather than a default", async () => {
    renderCard();

    await userEvent.click(await screen.findByRole("switch", { name: /courier mode/i }));

    await waitFor(() =>
      expect(teamUpdateCall).toHaveBeenCalledWith("sk-1", { team_id: "t1", courier_mode: true }),
    );
  });

  it("re-reads the team after saving, so the panel shows the stored value and not the attempt", async () => {
    renderCard();
    await screen.findByRole("switch", { name: /courier mode/i });
    teamCourierCoverageCall.mockResolvedValue(coverage({ courier_mode: true }));

    await userEvent.click(screen.getByRole("switch", { name: /courier mode/i }));

    await waitFor(() => expect(screen.getByRole("switch", { name: /courier mode/i })).toBeChecked());
  });

  it("leaves the switch showing the stored value when the save is rejected", async () => {
    teamUpdateCall.mockRejectedValue(new Error("nope"));
    renderCard();

    await userEvent.click(await screen.findByRole("switch", { name: /courier mode/i }));

    await waitFor(() => expect(toastError).toHaveBeenCalled());
    expect(screen.getByRole("switch", { name: /courier mode/i })).not.toBeChecked();
  });

  it("does not let a member without edit rights change the team's mode", async () => {
    renderCard({ canEditTeam: false });

    await userEvent.click(await screen.findByRole("switch", { name: /courier mode/i }));

    expect(teamUpdateCall).not.toHaveBeenCalled();
  });

  it("surfaces the count of keys that name no provider account", async () => {
    teamCourierCoverageCall.mockResolvedValue(coverage({ courier_mode: true, unbound_key_count: 2 }));
    renderCard();

    expect(await screen.findByText(/2 keys on this team name no account/i)).toBeInTheDocument();
  });

  it("says so plainly when the settings cannot be read, rather than showing a switch it cannot honour", async () => {
    teamCourierCoverageCall.mockRejectedValue(new Error("boom"));
    renderCard();

    expect(await screen.findByText(/could not read this team's courier mode settings/i)).toBeInTheDocument();
    expect(screen.queryByRole("switch", { name: /courier mode/i })).not.toBeInTheDocument();
  });
});
