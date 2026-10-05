import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import BillReconciliationView from "./BillReconciliationView";
import type { ReconciliationResponse } from "@/components/networking";

const base: ReconciliationResponse = {
  provider: "openrouter",
  period_start: "2026-09-01",
  period_end: "2026-09-30",
  outcome: "balanced",
  currency: "USD",
  invoice_total: "0.00780515",
  ledger_total: "0.00780515",
  explained: [],
  explained_total: "0",
  unexplained: "0",
  note: "The bill, its adjustments and the ledger agree exactly.",
};

const BALANCED: ReconciliationResponse = base;

const WITH_CREDIT: ReconciliationResponse = {
  ...base,
  invoice_total: "0.00661030",
  explained: [{ kind: "credit", amount: "-0.00119485", note: "goodwill" }],
  explained_total: "-0.00119485",
};

const OVER: ReconciliationResponse = {
  ...base,
  outcome: "unexplained_difference",
  invoice_total: "0.00900000",
  unexplained: "0.00119485",
  note: "Part of the difference is not accounted for by any adjustment on the bill.",
};

const UNDER: ReconciliationResponse = {
  ...base,
  outcome: "unexplained_difference",
  invoice_total: "0.00661030",
  unexplained: "-0.00119485",
  note: "Part of the difference is not accounted for by any adjustment on the bill.",
};

const MISMATCH: ReconciliationResponse = {
  ...base,
  outcome: "currency_mismatch",
  currency: "EUR",
  ledger_total: null,
  note: "The bill is in EUR and the ledger holds USD. No conversion is applied, because a rate nobody chose would look authoritative and not be.",
};

const NO_INVOICE: ReconciliationResponse = {
  ...base,
  outcome: "no_invoice",
  currency: null,
  invoice_total: null,
  ledger_total: null,
  note: "No bill entered for this period yet, so there is nothing to compare the ledger against.",
};

const reconciliationCall = vi.fn();

vi.mock("@/components/networking", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/components/networking")>()),
  reconciliationCall: (...args: unknown[]) => reconciliationCall(...args),
}));

vi.mock("@/app/(dashboard)/hooks/useAuthorized", () => ({
  default: () => ({ accessToken: "sk-test", userRole: "proxy_admin" }),
}));

const renderView = () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <BillReconciliationView provider="openrouter" periodStart="2026-09-01" periodEnd="2026-09-30" />
    </QueryClientProvider>,
  );
};

describe("BillReconciliationView", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    reconciliationCall.mockResolvedValue(BALANCED);
  });

  it("shows the unexplained remainder even when it is zero", async () => {
    renderView();
    expect(await screen.findByText("Unexplained")).toBeInTheDocument();
    expect(screen.getByText("$0")).toBeInTheDocument();
    expect(screen.getByText(/nothing is left over/i)).toBeInTheDocument();
  });

  it("names each thing that accounts for part of the difference", async () => {
    reconciliationCall.mockResolvedValue(WITH_CREDIT);
    renderView();
    expect(await screen.findByText("Credit")).toBeInTheDocument();
    expect(screen.getByText("goodwill")).toBeInTheDocument();
    expect(screen.getByText("Accounted for")).toBeInTheDocument();
  });

  it("says nothing on the bill explains the difference when no adjustment was entered", async () => {
    reconciliationCall.mockResolvedValue(OVER);
    renderView();
    expect(await screen.findByText(/nothing on the bill explains/i)).toBeInTheDocument();
  });

  it("tells being overcharged apart from usage not yet billed", async () => {
    reconciliationCall.mockResolvedValue(OVER);
    renderView();
    expect(await screen.findByText(/bill is larger than the ledger/i)).toBeInTheDocument();
  });

  it("reads a bill smaller than the ledger as usage the provider may not have billed", async () => {
    reconciliationCall.mockResolvedValue(UNDER);
    renderView();
    expect(await screen.findByText(/has not billed yet/i)).toBeInTheDocument();
  });

  it("refuses to compare two currencies and says which two", async () => {
    reconciliationCall.mockResolvedValue(MISMATCH);
    renderView();
    expect(await screen.findByText(/EUR/)).toBeInTheDocument();
    expect(screen.getByText(/USD/)).toBeInTheDocument();
    expect(screen.getByText("Different currencies")).toBeInTheDocument();
  });

  it("shows no figures at all when the currencies do not match, rather than a converted one", async () => {
    reconciliationCall.mockResolvedValue(MISMATCH);
    renderView();
    await screen.findByText("Different currencies");
    expect(screen.queryByText("The bill says")).not.toBeInTheDocument();
    expect(screen.queryByText("Unexplained")).not.toBeInTheDocument();
  });

  it("asks for a bill rather than reporting the whole ledger as unexplained", async () => {
    reconciliationCall.mockResolvedValue(NO_INVOICE);
    renderView();
    expect(await screen.findByText("No bill entered")).toBeInTheDocument();
    expect(screen.queryByText("Unexplained")).not.toBeInTheDocument();
  });

  it("keeps every digit rather than rounding a remainder for display", async () => {
    reconciliationCall.mockResolvedValue(OVER);
    renderView();
    expect(await screen.findByText("$0.00119485")).toBeInTheDocument();
  });

  it("opens by saying what the two figures are, before showing them", async () => {
    reconciliationCall.mockResolvedValue(OVER);
    renderView();

    const claim = await screen.findByText(/What this provider invoiced/);
    expect(claim).toHaveTextContent("never added together");
    const bill = screen.getByText("The bill says");
    // The claim precedes the figures in the document, not in a footnote under them.
    expect(claim.compareDocumentPosition(bill) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("never renders the bill and the ledger as one total", async () => {
    // Two accounts of the same spend. Their sum is the number a reader must never be handed, and a
    // sentence introducing it would read perfectly well.
    reconciliationCall.mockResolvedValue(OVER);
    renderView();
    await screen.findByText("The bill says");

    const sum = Number(OVER.invoice_total) + Number(OVER.ledger_total);
    for (const digits of [2, 4, 6, 8]) {
      expect(screen.queryByText(new RegExp(sum.toFixed(digits).replace(".", "\.")))).not.toBeInTheDocument();
    }
  });
});
