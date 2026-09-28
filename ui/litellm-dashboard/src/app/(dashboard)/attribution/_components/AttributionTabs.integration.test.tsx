import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AttributionTabs from "./AttributionTabs";
import type { UnallocatedResponse } from "@/components/networking";

const UNALLOCATED: UnallocatedResponse = {
  provider: "openrouter",
  days: 30,
  total_unallocated: "0.00774700",
  total_owned: "0",
  lines: [
    {
      day: "2026-09-15",
      provider: "openrouter",
      credential_name: "openrouter-billing",
      provider_cost: "0.00774700",
      gateway_cost: "0",
      gap: "0.00774700",
      state: "unallocated",
      owner_type: null,
      owner_id: null,
      rule_id: null,
    },
    {
      day: "2026-09-14",
      provider: "openrouter",
      credential_name: "openrouter-billing",
      provider_cost: null,
      gateway_cost: "0.5",
      gap: "0",
      state: "no_provider_data",
      owner_type: null,
      owner_id: null,
      rule_id: null,
    },
  ],
};

const rulesCall = vi.fn();
const unallocatedCall = vi.fn();
const upsertCall = vi.fn();

vi.mock("@/components/networking", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/components/networking")>()),
  attributionRulesCall: (...args: unknown[]) => rulesCall(...args),
  attributionUnallocatedCall: (...args: unknown[]) => unallocatedCall(...args),
  upsertAttributionRuleCall: (...args: unknown[]) => upsertCall(...args),
  deleteAttributionRuleCall: vi.fn(),
}));

vi.mock("@/app/(dashboard)/hooks/useAuthorized", () => ({
  default: () => ({ accessToken: "sk-test", userRole: "proxy_admin" }),
}));

const renderTabs = () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <AttributionTabs />
    </QueryClientProvider>,
  );
};

describe("AttributionTabs", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    rulesCall.mockResolvedValue({ rules: [] });
    unallocatedCall.mockResolvedValue(UNALLOCATED);
    upsertCall.mockResolvedValue({
      rule_id: "r1",
      provider: "openrouter",
      match_type: "cloud_account",
      match_value: "openrouter-billing",
      owner_type: "team",
      owner_id: "platform-team",
      note: null,
    });
  });

  it("shows unclaimed spend as money with no owner rather than as zero", async () => {
    const user = userEvent.setup();
    renderTabs();
    await user.click(screen.getByRole("tab", { name: "Unmatched" }));

    // Three places, and all three are the same figure for a reason: the gateway recorded nothing
    // that day, so the headline total, what the provider billed, and the difference all coincide.
    // Counting them catches a total that disagrees with the line it is meant to sum.
    const shown = await screen.findAllByText("$0.00774700");
    expect(shown).toHaveLength(3);
    expect(screen.getByText("No rule matches")).toBeInTheDocument();
  });

  it("does not claim the sources agree on a day the provider reported nothing", async () => {
    const user = userEvent.setup();
    renderTabs();
    await user.click(screen.getByRole("tab", { name: "Unmatched" }));

    expect(await screen.findByText("Provider reported nothing")).toBeInTheDocument();
    expect(screen.queryByText("Matched")).not.toBeInTheDocument();
  });

  it("keeps the chosen provider when moving between tabs", async () => {
    const user = userEvent.setup();
    renderTabs();

    fireEvent.change(screen.getByLabelText("Provider"), { target: { value: "anthropic" } });
    await user.click(screen.getByRole("tab", { name: "Unmatched" }));
    await user.click(screen.getByRole("tab", { name: "Cloud Accounts" }));

    expect(screen.getByLabelText("Provider")).toHaveValue("anthropic");
  });

  it("keeps a half-typed rule when the reader checks the other tab", async () => {
    const user = userEvent.setup();
    renderTabs();

    fireEvent.change(screen.getByLabelText("Provider account"), { target: { value: "finance-openrouter" } });
    await user.click(screen.getByRole("tab", { name: "Unmatched" }));
    await user.click(screen.getByRole("tab", { name: "Cloud Accounts" }));

    expect(screen.getByLabelText("Provider account")).toHaveValue("finance-openrouter");
  });

  it("sends the account and owner an admin typed, for the provider they chose", async () => {
    const user = userEvent.setup();
    renderTabs();

    fireEvent.change(screen.getByLabelText("Provider"), { target: { value: "openai" } });
    fireEvent.change(screen.getByLabelText("Provider account"), { target: { value: " finance-openai " } });
    fireEvent.change(screen.getByLabelText("Owner"), { target: { value: " t-7 " } });
    await user.click(screen.getByRole("button", { name: "Save rule" }));

    expect(upsertCall).toHaveBeenCalledWith("sk-test", {
      provider: "openai",
      match_type: "cloud_account",
      match_value: "finance-openai",
      owner_type: "team",
      owner_id: "t-7",
    });
  });

  it("will not save a rule with no account or no owner", async () => {
    renderTabs();
    expect(screen.getByRole("button", { name: "Save rule" })).toBeDisabled();

    fireEvent.change(screen.getByLabelText("Provider account"), { target: { value: "acct" } });
    expect(screen.getByRole("button", { name: "Save rule" })).toBeDisabled();
  });
});
