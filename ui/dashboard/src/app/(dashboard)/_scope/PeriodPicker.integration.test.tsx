import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import LedgerTabs from "@/app/(dashboard)/(token-iq)/ledger/_components/LedgerTabs";
import OverviewPanel from "@/app/(dashboard)/(token-iq)/overview/_components/OverviewPanel";
import PeriodPicker from "./PeriodPicker";
import { PeriodProvider } from "./PeriodContext";
import type { LedgerLinesResponse, OverviewResponse } from "@/components/networking";

/**
 * The bar drives the pages, and the pages agree with each other.
 *
 * This is the regression that mattered: the Overview page and the Ledger each had their own copy of
 * a period helper, and the copies disagreed about where a month ends. Both screens worked, both
 * showed a total, and the totals covered different days with nothing saying so.
 */

const LINES: LedgerLinesResponse = {
  lines: [],
  next_cursor: null,
  totals_by_currency: { USD: "0" },
};

const OVERVIEW: OverviewResponse = {
  period_start: "2026-09-01",
  period_end: "2026-09-30",
  currency: "USD",
  total: "0.00780515",
  previous_total: null,
  change: null,
  attributed: "0.00797225",
  unallocated: "0.00774700",
  unallocated_share: "99.3",
  providers: [],
  recommendations: [],
  freshness: [],
};

const NOTHING_TO_COMPARE = {
  provider: "openai",
  outcome: "no_invoice",
  note: "No bill entered for this period yet.",
  currency: null,
  invoice_total: null,
  ledger_total: null,
  unexplained: "0",
  explained: [],
  explained_total: "0",
} as const;

const overviewCall = vi.fn();
const linesCall = vi.fn();
const invoicesCall = vi.fn();
const reconciliationCall = vi.fn();

vi.mock("@/components/networking", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/components/networking")>()),
  overviewCall: (...args: unknown[]) => overviewCall(...args),
  ledgerLinesCall: (...args: unknown[]) => linesCall(...args),
  invoicesCall: (...args: unknown[]) => invoicesCall(...args),
  reconciliationCall: (...args: unknown[]) => reconciliationCall(...args),
}));

vi.mock("@/app/(dashboard)/hooks/useAuthorized", () => ({
  default: () => ({ accessToken: "sk-test", userRole: "proxy_admin" }),
}));

const renderShell = () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <PeriodProvider>
        <PeriodPicker />
        <OverviewPanel />
        <LedgerTabs />
      </PeriodProvider>
    </QueryClientProvider>,
  );
};

const choose = (label: string) => {
  fireEvent.change(screen.getByLabelText("Period"), { target: { value: label } });
};

/** The period a call was made with, as (start, end), whichever argument position they sit in. */
const periodOf = (call: readonly unknown[]): readonly string[] =>
  call.filter((arg): arg is string => typeof arg === "string" && /^\d{4}-\d{2}-\d{2}$/.test(arg));

describe("the period bar", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    overviewCall.mockResolvedValue(OVERVIEW);
    linesCall.mockResolvedValue(LINES);
    invoicesCall.mockResolvedValue({ invoices: [] });
    reconciliationCall.mockResolvedValue(NOTHING_TO_COMPARE);
  });

  it("asks the server for the same period on both pages", async () => {
    renderShell();
    await screen.findByText("Total spend, USD");

    expect(periodOf(overviewCall.mock.calls[0] as readonly unknown[])).toEqual(
      periodOf(linesCall.mock.calls[0] as readonly unknown[]),
    );
  });

  it("moves both pages when the reader changes the period", async () => {
    renderShell();
    await screen.findByText("Total spend, USD");
    overviewCall.mockClear();
    linesCall.mockClear();

    choose("last-month");

    await vi.waitFor(() => {
      expect(overviewCall).toHaveBeenCalled();
    });
    await vi.waitFor(() => {
      expect(linesCall).toHaveBeenCalled();
    });

    const asked = periodOf(overviewCall.mock.calls[0] as readonly unknown[]);
    expect(asked).toEqual(periodOf(linesCall.mock.calls[0] as readonly unknown[]));
    // Last month is a closed month, so it ends on a last day rather than on today.
    expect(asked[0]).toMatch(/-01$/);
  });

  it("tells month to date apart from the whole month, which is what the old copies confused", async () => {
    renderShell();
    await screen.findByText("Total spend, USD");

    choose("month-to-date");
    await vi.waitFor(() => {
      expect(overviewCall).toHaveBeenCalled();
    });
    const toDate = periodOf(overviewCall.mock.calls.at(-1) as readonly unknown[]);

    overviewCall.mockClear();
    choose("this-month");
    await vi.waitFor(() => {
      expect(overviewCall).toHaveBeenCalled();
    });
    const whole = periodOf(overviewCall.mock.calls.at(-1) as readonly unknown[]);

    expect(whole[0]).toBe(toDate[0]);
    expect(whole[1] >= toDate[1]).toBe(true);
  });

  it("reaches a month that closed earlier, which the pages can no longer ask for themselves", async () => {
    renderShell();
    await screen.findByText("Total spend, USD");

    choose("named-month");
    const months = await screen.findByLabelText("Month");
    const options = within(months).getAllByRole("option");
    fireEvent.change(months, { target: { value: (options[3] as HTMLOptionElement).value } });

    await vi.waitFor(() => {
      expect(overviewCall).toHaveBeenCalled();
    });
    const asked = periodOf(overviewCall.mock.calls.at(-1) as readonly unknown[]);
    expect(asked[0]).toBe(`${(options[3] as HTMLOptionElement).value}-01`);
  });

  it("leaves no period controls on the pages themselves", async () => {
    // Two controls for one period is the shape the bug came in: whichever one a reader did not
    // notice kept its own answer.
    renderShell();
    await screen.findByText("Total spend, USD");

    expect(screen.queryByLabelText("Period start")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Period end")).not.toBeInTheDocument();
  });
});
