import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { withNuqsTestingAdapter } from "nuqs/adapters/testing";
import { beforeEach, describe, expect, it, vi } from "vitest";

import UploadsTab from "./UploadsTab";
import type { UploadsResponse } from "@/components/networking";

/**
 * Proves the wiring the unit tests cannot reach: that a bill nobody entered reaches the screen as
 * a row to act on, and that the dialog's month and figures reach the save as the period and the
 * digits that were typed.
 *
 * The shaping is asserted in `uploadRows.test.ts` and `invoiceSubmit.test.ts`, which run in
 * milliseconds. Only what needs a real tree is here.
 */

const UPLOADS: UploadsResponse = {
  checked_from: "2026-09-12T00:00:00+00:00",
  checked_to: "2026-10-12T00:00:00+00:00",
  forwarding: { kind: "not_configured", setting: "TOKEN_IQ_INVOICE_FORWARDING_ADDRESS" },
  providers: [
    { provider: "bedrock", display_name: "Amazon Bedrock" },
    { provider: "openrouter", display_name: "OpenRouter" },
  ],
  rows: [
    { kind: "not_entered", provider: "openrouter", display_name: "OpenRouter" },
    {
      kind: "entered",
      invoice_id: "i1",
      provider: "bedrock",
      display_name: "Amazon Bedrock",
      period_start: "2026-09-01",
      period_end: "2026-09-30",
      currency: "USD",
      total: "48210.07",
      note: "from the AWS console",
    },
  ],
};

const SAVED = {
  invoice_id: "i2",
  provider: "openrouter",
  period_start: "2026-09-01",
  period_end: "2026-09-30",
  currency: "USD",
  total: "1250.40",
  adjustments: [],
  note: null,
};

const EXPECTED_PERIOD = {
  provider: "openrouter",
  period_start: "2026-09-01",
  period_end: "2026-09-30",
  total: "1250.40",
};

const uploadsCall = vi.fn();
const upsertInvoiceCall = vi.fn();

vi.mock("@/components/networking", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/components/networking")>()),
  uploadsCall: (...args: unknown[]) => uploadsCall(...args),
  upsertInvoiceCall: (...args: unknown[]) => upsertInvoiceCall(...args),
}));

vi.mock("@/app/(dashboard)/hooks/useAuthorized", () => ({
  default: () => ({ accessToken: "sk-test", userRole: "proxy_admin" }),
}));

const renderTab = (canEnter = true, searchParams = "") => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <UploadsTab canEnter={canEnter} />
    </QueryClientProvider>,
    { wrapper: withNuqsTestingAdapter({ searchParams }) },
  );
};

const openDialog = async () => {
  fireEvent.click(await screen.findByRole("button", { name: "Enter a bill" }));
  return screen.findByRole("dialog");
};

describe("the Uploads tab", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    uploadsCall.mockResolvedValue(UPLOADS);
    upsertInvoiceCall.mockResolvedValue(SAVED);
    renderTab();
  });

  it("lists a provider that billed with no bill entered", async () => {
    const row = await screen.findByRole("row", { name: /OpenRouter/ });

    expect(within(row).getByText("No bill entered")).toBeInTheDocument();
  });

  it("shows no figure at all on the row with no bill", async () => {
    // A zero here reads as a bill of nothing, and the only figure available would be one Token IQ
    // worked out, which is never printed in an invoice column.
    const row = await screen.findByRole("row", { name: /OpenRouter/ });

    expect(within(row).getByText("Not entered")).toBeInTheDocument();
    expect(within(row).queryByText("0")).not.toBeInTheDocument();
    expect(within(row).queryByText("0.00")).not.toBeInTheDocument();
  });

  it("says since when that provider has been billing without one", async () => {
    const row = await screen.findByRole("row", { name: /OpenRouter/ });

    expect(within(row).getByText("Billing since 12 Sep 2026")).toBeInTheDocument();
  });

  it("shows an entered bill with its own figure and month", async () => {
    const row = await screen.findByRole("row", { name: /Amazon Bedrock/ });

    expect(within(row).getByText("48210.07 USD")).toBeInTheDocument();
    expect(within(row).getByText("September 2026")).toBeInTheDocument();
    expect(within(row).getByText("Recorded")).toBeInTheDocument();
  });

  it("names the setting to change when no forwarding address is configured", async () => {
    expect(await screen.findByText(/TOKEN_IQ_INVOICE_FORWARDING_ADDRESS/)).toBeInTheDocument();
  });

  it("says that workspace exports and contracts are not built yet", async () => {
    // Both are on the blueprint's own tab for this and have nowhere to go, so the tab says so
    // rather than offering a field that drops what is typed into it.
    expect(await screen.findByText(/Workspace exports and contracts/)).toBeInTheDocument();
  });

  it("says how many bills are outstanding", async () => {
    expect(await screen.findByText(/1 provider billed in the last 30 days/)).toBeInTheDocument();
  });

  it("offers no way to enter one to a viewer who cannot save it", async () => {
    // The save is refused server side for a read-only admin, so the button would be a dead end.
    // The same rule the page applies to Connect account.
    cleanup();
    renderTab(false);

    expect(await screen.findByText("Amazon Bedrock")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Enter a bill" })).not.toBeInTheDocument();
  });
});

describe("entering a bill", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    uploadsCall.mockResolvedValue(UPLOADS);
    upsertInvoiceCall.mockResolvedValue(SAVED);
    renderTab();
  });

  it("offers only providers whose bill this build can read", async () => {
    const dialog = await openDialog();

    const options = within(dialog)
      .getAllByRole("option")
      .map((option) => option.textContent);

    expect(options).toContain("Amazon Bedrock");
    expect(options).toContain("OpenRouter");
  });

  it("sends the chosen month as the period the bill covers", async () => {
    // The stored period is matched exactly when that month is reconciled, so a period that does
    // not line up with its own month is a bill reconciliation reports as not entered.
    const dialog = await openDialog();

    fireEvent.change(within(dialog).getByLabelText("Provider"), { target: { value: "openrouter" } });
    fireEvent.change(within(dialog).getByLabelText("Billing period"), { target: { value: "2026-09" } });
    fireEvent.change(within(dialog).getByLabelText("Bill total"), { target: { value: "1250.40" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save the bill" }));

    await screen.findByText(/is recorded for/);

    expect(upsertInvoiceCall).toHaveBeenCalledWith(
      "sk-test",
      expect.objectContaining(EXPECTED_PERIOD),
    );
  });

  it("will not save a figure the provider's bill cannot have", async () => {
    const dialog = await openDialog();

    fireEvent.change(within(dialog).getByLabelText("Bill total"), { target: { value: "$48,210.07" } });

    expect(within(dialog).getByRole("button", { name: "Save the bill" })).toBeDisabled();
    expect(within(dialog).getByText(/currency symbol/)).toBeInTheDocument();
  });

  it("sends an adjustment with the bill", async () => {
    const dialog = await openDialog();

    fireEvent.change(within(dialog).getByLabelText("Bill total"), { target: { value: "1250.40" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Add an adjustment" }));
    fireEvent.change(within(dialog).getByLabelText("Adjustment 1 kind"), { target: { value: "credit" } });
    fireEvent.change(within(dialog).getByLabelText("Adjustment 1 amount"), { target: { value: "-400" } });
    fireEvent.change(within(dialog).getByLabelText("Adjustment 1 note"), { target: { value: "goodwill" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save the bill" }));

    await screen.findByText(/is recorded for/);

    expect(upsertInvoiceCall).toHaveBeenCalledWith(
      "sk-test",
      expect.objectContaining({ adjustments: [{ kind: "credit", amount: "-400", note: "goodwill" }] }),
    );
  });

  it("warns when an adjustment is entered the wrong way round", async () => {
    // It does not fail. It moves the unexplained remainder by twice the amount and blames the
    // provider for it, which is why the dialog is where this has to be said.
    const dialog = await openDialog();

    fireEvent.click(within(dialog).getByRole("button", { name: "Add an adjustment" }));
    fireEvent.change(within(dialog).getByLabelText("Adjustment 1 kind"), { target: { value: "credit" } });
    fireEvent.change(within(dialog).getByLabelText("Adjustment 1 amount"), { target: { value: "400" } });

    expect(within(dialog).getByText(/usually negative/)).toBeInTheDocument();
  });

  it("says which period the bill was stored against once it is saved", async () => {
    const dialog = await openDialog();

    fireEvent.change(within(dialog).getByLabelText("Bill total"), { target: { value: "1250.40" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save the bill" }));

    expect(await screen.findByText(/2026-09-01 to 2026-09-30/)).toBeInTheDocument();
  });

  it("shows the server's own refusal rather than a generic failure", async () => {
    upsertInvoiceCall.mockRejectedValue(new Error('{"error":"Unknown provider \'wat\'."}'));
    const dialog = await openDialog();

    fireEvent.change(within(dialog).getByLabelText("Bill total"), { target: { value: "1250.40" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save the bill" }));

    expect(await screen.findByText(/Unknown provider/)).toBeInTheDocument();
  });

  it("says the figures are typed rather than read from the document", async () => {
    // Nothing here parses a PDF or a billing CSV. A file field would leave a customer believing
    // their bill had been understood.
    const dialog = await openDialog();

    expect(within(dialog).getByText(/nothing here parses a PDF or a billing CSV yet/)).toBeInTheDocument();
  });
});

describe("arriving from a screen that knows which bill is missing", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    uploadsCall.mockResolvedValue(UPLOADS);
    upsertInvoiceCall.mockResolvedValue(SAVED);
  });

  it("opens the dialog when the link asked for it", async () => {
    // Invoice Reconciliation links here from a month with no bill. Landing on the tab with the
    // dialog shut makes the reader find the button that the link was already pressing for them.
    cleanup();
    renderTab(true, "?enter=1");

    expect(await screen.findByRole("dialog")).toBeInTheDocument();
  });

  it("stays shut when nothing asked for it", async () => {
    cleanup();
    renderTab();

    await screen.findByText("Amazon Bedrock");

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("opens on the bill the link named", async () => {
    // Choosing the wrong month is the one mistake nothing downstream catches, so a link that knows
    // the month carries it rather than making the reader choose again.
    cleanup();
    renderTab(true, "?enter=1&provider=openrouter&month=2026-09");

    const dialog = await screen.findByRole("dialog");

    expect(within(dialog).getByLabelText("Provider")).toHaveValue("openrouter");
    expect(within(dialog).getByLabelText("Billing period")).toHaveValue("2026-09");
  });

  it("ignores a provider no bill can be entered for", async () => {
    // The value came from a URL, so it is checked against what the server offered rather than
    // trusted. Honoured, it would be a form whose save answers 404.
    cleanup();
    renderTab(true, "?enter=1&provider=not-a-provider");

    const dialog = await screen.findByRole("dialog");

    expect(within(dialog).getByLabelText("Provider")).toHaveValue("bedrock");
  });

  it("ignores a month it does not offer", async () => {
    cleanup();
    renderTab(true, "?enter=1&month=1999-01");

    const dialog = await screen.findByRole("dialog");

    expect(within(dialog).getByLabelText("Billing period")).not.toHaveValue("1999-01");
  });
});
