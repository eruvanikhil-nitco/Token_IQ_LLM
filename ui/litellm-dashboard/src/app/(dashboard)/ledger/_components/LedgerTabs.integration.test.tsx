import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import LedgerTabs from "./LedgerTabs";
import type { InvoiceListResponse, LedgerLinesResponse } from "@/components/networking";

const LINES: LedgerLinesResponse = {
  lines: [
    {
      day: "2026-09-15",
      provider: "openrouter",
      display_name: "OpenRouter",
      credential_name: "openrouter-billing",
      model: "openai/gpt-4o",
      evidence: "reconciled",
      currency: "USD",
      amount: "0.00774700",
      owner_type: "team",
      owner_id: "platform-team",
    },
    {
      day: "2026-09-14",
      provider: "openrouter",
      display_name: "OpenRouter",
      credential_name: "openrouter-billing",
      model: null,
      evidence: "allocated",
      currency: "USD",
      amount: "0.00005815",
      owner_type: null,
      owner_id: null,
    },
  ],
  next_cursor: null,
  totals_by_currency: { USD: "0.00780515" },
};

const NO_INVOICES: InvoiceListResponse = { invoices: [] };

const SAVED_INVOICE = {
  invoice_id: "i1",
  provider: "openai",
  period_start: "2026-09-01",
  period_end: "2026-09-30",
  currency: "USD",
  total: "1234.56",
  adjustments: [],
  note: null,
} as const;

const NOTHING_TO_COMPARE = {
  provider: "openrouter",
  outcome: "no_invoice",
  note: "No bill entered for this period yet, so there is nothing to compare the ledger against.",
  currency: "USD",
  invoice_total: null,
  ledger_total: null,
  unexplained: "0",
  explained: [],
  explained_total: "0",
} as const;

const linesCall = vi.fn();
const invoicesCall = vi.fn();
const upsertCall = vi.fn();
const deleteCall = vi.fn();
const reconciliationCall = vi.fn();

vi.mock("@/components/networking", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/components/networking")>()),
  ledgerLinesCall: (...args: unknown[]) => linesCall(...args),
  invoicesCall: (...args: unknown[]) => invoicesCall(...args),
  upsertInvoiceCall: (...args: unknown[]) => upsertCall(...args),
  deleteInvoiceCall: (...args: unknown[]) => deleteCall(...args),
  reconciliationCall: (...args: unknown[]) => reconciliationCall(...args),
}));

vi.mock("@/app/(dashboard)/hooks/useAuthorized", () => ({
  default: () => ({ accessToken: "sk-test", userRole: "proxy_admin" }),
}));

const renderTabs = () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <LedgerTabs />
    </QueryClientProvider>,
  );
};

describe("LedgerTabs", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    linesCall.mockResolvedValue(LINES);
    invoicesCall.mockResolvedValue(NO_INVOICES);
    upsertCall.mockResolvedValue(SAVED_INVOICE);
    reconciliationCall.mockResolvedValue(NOTHING_TO_COMPARE);
  });

  it("shows a ledger line with its amount, evidence and owner", async () => {
    renderTabs();
    expect(await screen.findByText("$0.00774700")).toBeInTheDocument();
    expect(screen.getAllByText("OpenRouter").length).toBeGreaterThan(0);
    expect(screen.getByText("team: platform-team")).toBeInTheDocument();
  });

  it("keeps every digit of the ledger total rather than rounding it", async () => {
    renderTabs();
    expect(await screen.findByText("$0.00780515")).toBeInTheDocument();
  });

  it("does not list the gateway's own records, which would count the same money twice", async () => {
    renderTabs();
    await screen.findByText("$0.00774700");
    expect(screen.getByText(/would count it twice/i)).toBeInTheDocument();
  });

  it("will not save a bill with no total", async () => {
    const user = userEvent.setup();
    renderTabs();
    await user.click(screen.getByRole("tab", { name: "Invoices" }));
    expect(await screen.findByRole("button", { name: "Save invoice" })).toBeDisabled();
  });

  it("sends the bill an admin typed, for the provider and period they chose", async () => {
    const user = userEvent.setup();
    renderTabs();
    await user.click(screen.getByRole("tab", { name: "Invoices" }));

    fireEvent.change(await screen.findByLabelText("Invoice total"), { target: { value: " 1234.56 " } });
    fireEvent.change(screen.getByLabelText("Period start"), { target: { value: "2026-09-01" } });
    fireEvent.change(screen.getByLabelText("Period end"), { target: { value: "2026-09-30" } });
    await user.click(screen.getByRole("button", { name: "Save invoice" }));

    const expected = {
      total: "1234.56",
      period_start: "2026-09-01",
      period_end: "2026-09-30",
      currency: "USD",
      adjustments: [],
    };
    expect(upsertCall).toHaveBeenCalledWith("sk-test", expect.objectContaining(expected));
  });

  it("sends an adjustment when one is entered, so the bill can explain itself", async () => {
    const user = userEvent.setup();
    renderTabs();
    await user.click(screen.getByRole("tab", { name: "Invoices" }));

    fireEvent.change(await screen.findByLabelText("Invoice total"), { target: { value: "100" } });
    fireEvent.change(screen.getByLabelText("Adjustment kind"), { target: { value: "tax" } });
    fireEvent.change(screen.getByLabelText("Adjustment amount"), { target: { value: "15" } });
    await user.click(screen.getByRole("button", { name: "Save invoice" }));

    expect(upsertCall).toHaveBeenCalledWith(
      "sk-test",
      expect.objectContaining({ adjustments: [{ kind: "tax", amount: "15", note: null }] }),
    );
  });

  it("keeps a half-typed bill when the reader checks the ledger tab", async () => {
    const user = userEvent.setup();
    renderTabs();
    await user.click(screen.getByRole("tab", { name: "Invoices" }));
    fireEvent.change(await screen.findByLabelText("Invoice total"), { target: { value: "1234.56" } });

    await user.click(screen.getByRole("tab", { name: "Cost Ledger" }));
    await user.click(screen.getByRole("tab", { name: "Invoices" }));

    expect(screen.getByLabelText("Invoice total")).toHaveValue("1234.56");
  });

  it("says no bills are entered rather than leaving the tab blank", async () => {
    const user = userEvent.setup();
    renderTabs();
    await user.click(screen.getByRole("tab", { name: "Invoices" }));
    expect(await screen.findByText(/no bills entered yet/i)).toBeInTheDocument();
  });

  it("asks the server for the provider and period the reader chose", async () => {
    const user = userEvent.setup();
    renderTabs();
    await screen.findByText("$0.00774700");
    // The provider picker is a Base UI select: it answers to real clicks, not a change event.
    await user.click(screen.getByRole("combobox", { name: "Provider" }));
    await user.click(await screen.findByRole("option", { name: "Anthropic" }));
    await screen.findByText("$0.00774700");
    expect(linesCall).toHaveBeenLastCalledWith("sk-test", "anthropic", expect.any(String), expect.any(String));
  });

  it("takes the reader from the reconciliation dead end to the form that fills it", async () => {
    // The empty state used to say "No bill entered" and stop. The form sits in another tab, so the
    // way out has to move the reader there rather than naming a place for them to go and find.
    const user = userEvent.setup();
    renderTabs();

    await user.click(screen.getByRole("tab", { name: "Bill Reconciliation" }));
    await user.click(await screen.findByRole("button", { name: "Enter this bill" }));

    expect(await screen.findByRole("tab", { name: "Invoices", selected: true })).toBeInTheDocument();
  });
});
