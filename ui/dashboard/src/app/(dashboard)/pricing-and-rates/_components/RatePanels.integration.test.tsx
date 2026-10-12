/* @vitest-environment jsdom */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ContractedRatesPanel from "./ContractedRatesPanel";
import CurrencyRatesPanel from "./CurrencyRatesPanel";

/**
 * Proves the wiring the unit tests on `rateSubmit` cannot reach: that a figure typed into the form
 * reaches the server as the string that was typed, that a rate the server would refuse cannot be
 * sent at all, and that a recorded rate reads on the screen as what a customer pays.
 */

const providerRatesCall = vi.fn();
const addProviderRateCall = vi.fn();
const deleteProviderRateCall = vi.fn();
const currencyRatesCall = vi.fn();
const addCurrencyRateCall = vi.fn();
const deleteCurrencyRateCall = vi.fn();

vi.mock("@/components/networking", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/components/networking")>()),
  providerRatesCall: (...args: unknown[]) => providerRatesCall(...args),
  addProviderRateCall: (...args: unknown[]) => addProviderRateCall(...args),
  deleteProviderRateCall: (...args: unknown[]) => deleteProviderRateCall(...args),
  currencyRatesCall: (...args: unknown[]) => currencyRatesCall(...args),
  addCurrencyRateCall: (...args: unknown[]) => addCurrencyRateCall(...args),
  deleteCurrencyRateCall: (...args: unknown[]) => deleteCurrencyRateCall(...args),
}));

vi.mock("@/app/(dashboard)/hooks/useAuthorized", () => ({
  default: () => ({ accessToken: "sk-test", userRole: "proxy_admin", userId: "u1" }),
}));

const A_DISCOUNT = {
  rate_id: "r1",
  provider: "anthropic",
  model: null,
  field: null,
  basis: "discount",
  percent_off: "13.5",
  per_million: null,
  effective_from: "2026-09-01",
  effective_to: null,
  source: "the enterprise agreement signed in August",
};

const A_BOOKED_RATE = {
  rate_id: "c1",
  source_currency: "EUR",
  target_currency: "USD",
  rate: "1.0823",
  effective_from: "2026-09-01",
  effective_to: null,
  source: "the rate finance booked September at",
};

const EXPECTED_DISCOUNT = { basis: "discount", percent_off: "13.5", model: null, field: null };

const renderPanel = (panel: "rates" | "currency") => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      {panel === "rates" ? <ContractedRatesPanel /> : <CurrencyRatesPanel />}
    </QueryClientProvider>,
  );
};

const fill = (label: string, value: string) => {
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
};

describe("the contracted rates panel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    providerRatesCall.mockResolvedValue([]);
    addProviderRateCall.mockResolvedValue(A_DISCOUNT);
  });

  it("says what the figures mean when nothing is recorded", async () => {
    // The honest default. Every figure the product works out for itself is list price, which for a
    // customer with a negotiated discount is wrong by exactly what they negotiated.
    renderPanel("rates");

    expect(await screen.findByText(/wrong by exactly what you negotiated/)).toBeInTheDocument();
  });

  it("sends a discount as the digits that were typed", async () => {
    renderPanel("rates");

    fill("Provider", "anthropic");
    fill("Per cent off", "13.5");
    fill("First day it applies", "2026-09-01");
    fill("Where it came from", "the enterprise agreement signed in August");
    fireEvent.click(screen.getByRole("button", { name: "Record this rate" }));

    await vi.waitFor(() =>
      expect(addProviderRateCall).toHaveBeenCalledWith("sk-test", expect.objectContaining(EXPECTED_DISCOUNT)),
    );
  });

  it("will not send a committed price without a model, and says why", async () => {
    renderPanel("rates");

    fill("Provider", "anthropic");
    fill("What the contract says", "unit_price");
    fill("Price per million", "2.50");
    fill("First day it applies", "2026-09-01");
    fill("Where it came from", "committed use");

    expect(screen.getByText(/prices a small model like a large one/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Record this rate" })).toBeDisabled();
    expect(addProviderRateCall).not.toHaveBeenCalled();
  });

  it("will not send a rate nobody can trace", async () => {
    // The source is how a figure gets corrected later. Without it the row is a number with no
    // provenance, which nobody will touch and everybody will doubt.
    renderPanel("rates");

    fill("Provider", "anthropic");
    fill("Per cent off", "20");
    fill("First day it applies", "2026-09-01");

    expect(screen.getByText(/so somebody can check it later/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Record this rate" })).toBeDisabled();
  });

  it("will not send a period that ends before it starts", async () => {
    renderPanel("rates");

    fill("Provider", "anthropic");
    fill("Per cent off", "20");
    fill("First day it applies", "2026-09-01");
    fill("Last day it applies", "2026-08-01");
    fill("Where it came from", "x");

    expect(screen.getByText(/ends before it starts/)).toBeInTheDocument();
  });

  it("reads a recorded discount as what the customer pays, with its period and source", async () => {
    cleanup();
    providerRatesCall.mockResolvedValue([A_DISCOUNT]);
    renderPanel("rates");

    const row = await screen.findByRole("row", { name: /anthropic/ });

    expect(within(row).getByText("13.5% off list")).toBeInTheDocument();
    expect(within(row).getByText("from 2026-09-01")).toBeInTheDocument();
    expect(within(row).getByText("the enterprise agreement signed in August")).toBeInTheDocument();
    expect(within(row).getByText("every model")).toBeInTheDocument();
  });

  it("shows the server's own refusal rather than a generic failure", async () => {
    addProviderRateCall.mockRejectedValue(new Error('{"error":"A discount over a hundred per cent would make spend negative."}'));
    renderPanel("rates");

    fill("Provider", "anthropic");
    fill("Per cent off", "20");
    fill("First day it applies", "2026-09-01");
    fill("Where it came from", "x");
    fireEvent.click(screen.getByRole("button", { name: "Record this rate" }));

    expect(await screen.findByText(/would make spend negative/)).toBeInTheDocument();
  });
});

describe("the currency rates panel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    currencyRatesCall.mockResolvedValue([]);
    addCurrencyRateCall.mockResolvedValue(A_BOOKED_RATE);
  });

  it("says that a rate is never inverted", async () => {
    // So nobody records one direction and wonders why the other does not convert.
    renderPanel("currency");

    expect(await screen.findByText(/never inverted/)).toBeInTheDocument();
  });

  it("sends both currencies upper case and the rate as typed", async () => {
    renderPanel("currency");

    fill("Convert from", "eur");
    fill("Report in", "usd");
    fill("Rate", "1.0823");
    fill("First day", "2026-09-01");
    fill("Where it came from", "the rate finance booked September at");
    fireEvent.click(screen.getByRole("button", { name: "Record this rate" }));

    await vi.waitFor(() =>
      expect(addCurrencyRateCall).toHaveBeenCalledWith(
        "sk-test",
        expect.objectContaining({ source_currency: "EUR", target_currency: "USD", rate: "1.0823" }),
      ),
    );
  });

  it("will not send a currency converting to itself", async () => {
    renderPanel("currency");

    fill("Convert from", "usd");
    fill("Report in", "usd");
    fill("Rate", "1");
    fill("First day", "2026-09-01");
    fill("Where it came from", "x");

    expect(screen.getByText(/converts to itself/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Record this rate" })).toBeDisabled();
  });

  it("will not send a rate of zero, which would report every euro as nothing", async () => {
    renderPanel("currency");

    fill("Convert from", "EUR");
    fill("Report in", "USD");
    fill("Rate", "0");
    fill("First day", "2026-09-01");
    fill("Where it came from", "x");

    expect(screen.getByRole("button", { name: "Record this rate" })).toBeDisabled();
  });

  it("reads a recorded rate with its pair, period and source", async () => {
    cleanup();
    currencyRatesCall.mockResolvedValue([A_BOOKED_RATE]);
    renderPanel("currency");

    const row = await screen.findByRole("row", { name: /EUR/ });

    expect(within(row).getByText("1.0823")).toBeInTheDocument();
    expect(within(row).getByText("the rate finance booked September at")).toBeInTheDocument();
  });
});
