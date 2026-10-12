import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
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

  it("has no second form of its own, and sends the reader to the one that enters a bill", async () => {
    // Two forms writing one table drift, and this one knew nothing about the months a provider has
    // billed for with no bill entered, which is the part worth acting on.
    const user = userEvent.setup();
    renderTabs();
    await user.click(screen.getByRole("tab", { name: "Invoices" }));

    expect(await screen.findByRole("button", { name: "Enter a bill on Data Sources" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Save invoice" })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Invoice total")).not.toBeInTheDocument();
  });

  it("takes the provider and month it is looking at to the dialog", async () => {
    // Arriving on an empty dialog from a screen that knows which bill is missing makes the reader
    // choose both again, and choosing the wrong month is the one mistake nothing downstream
    // catches.
    const user = userEvent.setup();
    renderTabs();
    await user.click(screen.getByRole("tab", { name: "Invoices" }));

    const link = await screen.findByRole("button", { name: "Enter a bill on Data Sources" });
    const thisMonth = new Date().toISOString().slice(0, 7);

    expect(link).toHaveAttribute("href", expect.stringContaining("data-sources/uploads"));
    expect(link).toHaveAttribute("href", expect.stringContaining(`month=${thisMonth}`));
    expect(link).toHaveAttribute("href", expect.stringContaining("enter=1"));
  });

  it("follows the provider the reader chose rather than naming a fixed one", async () => {
    const user = userEvent.setup();
    renderTabs();
    await screen.findByText("$0.00774700");
    // The provider picker is a Base UI select: it answers to real clicks, not a change event.
    await user.click(screen.getByRole("combobox", { name: "Provider" }));
    await user.click(await screen.findByRole("option", { name: "Anthropic" }));
    await user.click(screen.getByRole("tab", { name: "Invoices" }));

    expect(await screen.findByRole("button", { name: "Enter a bill on Data Sources" })).toHaveAttribute(
      "href",
      expect.stringContaining("provider=anthropic"),
    );
  });

  it("still lets a wrong bill be removed here, where the difference shows up", async () => {
    invoicesCall.mockResolvedValue({ invoices: [SAVED_INVOICE] });
    const user = userEvent.setup();
    renderTabs();
    await user.click(screen.getByRole("tab", { name: "Invoices" }));

    expect(
      await screen.findByRole("button", { name: "Remove the bill for openai, 2026-09-01" }),
    ).toBeInTheDocument();
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

  it("takes the reader from the reconciliation dead end to the dialog that fills it", async () => {
    // The empty state used to say "No bill entered" and stop. The dialog is on another page now,
    // so the way out carries the provider and the month rather than naming a place to go and find.
    const user = userEvent.setup();
    renderTabs();

    await user.click(screen.getByRole("tab", { name: "Bill Reconciliation" }));
    const link = await screen.findByRole("button", { name: "Enter this bill" });
    const thisMonth = new Date().toISOString().slice(0, 7);

    expect(link).toHaveAttribute("href", expect.stringContaining("data-sources/uploads"));
    expect(link).toHaveAttribute("href", expect.stringContaining(`month=${thisMonth}`));
  });

  it("says what the ledger is before showing its total, not after", async () => {
    // The screen printed the ledger total first and explained underneath why the gateway’s own
    // figure is missing from it. A reader who stops at the first number has already been given a
    // figure they can misread as everything that was spent.
    renderTabs();

    const claim = await screen.findByText(/Every cost line the provider reported/);
    const total = screen.getByText("Ledger total, USD");
    // DOCUMENT_POSITION_FOLLOWING: the claim comes first in the document.
    expect(claim.compareDocumentPosition(total) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });
});
