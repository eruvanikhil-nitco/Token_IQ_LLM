import { describe, expect, it } from "vitest";

import {
  ADJUSTMENT_KINDS,
  amountProblem,
  canSaveInvoice,
  defaultMonth,
  enterBillHref,
  invoicePayload,
  invoiceSavedMessage,
  monthOfPeriod,
  monthOptions,
  periodForMonth,
  prefilledMonth,
  prefilledProvider,
  signHint,
  type InvoiceFormDraft,
} from "./invoiceSubmit";
import type { Invoice } from "@/components/networking";

/**
 * What leaves the enter-a-bill dialog.
 *
 * The period is the part that fails silently. A bill stored against a period that does not line up
 * with the month it covers is still a bill: the save succeeds, the row appears, and reconciliation
 * for that month reports no bill entered or compares it against usage it has nothing to do with.
 */

const OCTOBER = new Date(Date.UTC(2026, 9, 12));

const DRAFT: InvoiceFormDraft = {
  provider: "bedrock",
  month: "2026-09",
  currency: "USD",
  total: "48210.07",
  note: "",
  adjustments: [],
};

describe("the month a bill is entered for", () => {
  it("offers a year of months, newest first", () => {
    const months = monthOptions(OCTOBER);

    expect(months).toHaveLength(12);
    expect(months[0]).toEqual({ value: "2026-10", label: "October 2026" });
    expect(months[11]).toEqual({ value: "2025-11", label: "November 2025" });
  });

  it("crosses back over a year boundary without inventing a month thirteen", () => {
    const months = monthOptions(new Date(Date.UTC(2027, 0, 5)));

    expect(months[0].value).toBe("2027-01");
    expect(months[1]).toEqual({ value: "2026-12", label: "December 2026" });
  });

  it("opens on the month that has finished rather than the one in progress", () => {
    // A bill for the current month does not exist yet, so opening on it would have somebody
    // correct the field every time before they could use the dialog.
    expect(defaultMonth(OCTOBER)).toBe("2026-09");
  });
});

describe("the period that month becomes", () => {
  it("runs from the first day to the last day of the month", () => {
    expect(periodForMonth("2026-09")).toEqual({ period_start: "2026-09-01", period_end: "2026-09-30" });
  });

  it("knows how long each month is", () => {
    expect(periodForMonth("2026-02")?.period_end).toBe("2026-02-28");
    expect(periodForMonth("2024-02")?.period_end).toBe("2024-02-29");
    expect(periodForMonth("2026-12")?.period_end).toBe("2026-12-31");
  });

  it("refuses a month it cannot read rather than guessing one", () => {
    // Guessed, the bill is stored against a period nobody chose and the month it was meant for
    // still reports no bill entered.
    expect(periodForMonth("September")).toBeNull();
    expect(periodForMonth("2026-13")).toBeNull();
    expect(periodForMonth("2026-00")).toBeNull();
    expect(periodForMonth("")).toBeNull();
  });
});

describe("the figures on the bill", () => {
  it("passes a plain amount", () => {
    expect(amountProblem("48210.07")).toBeNull();
  });

  it("passes a negative amount, because an adjustment can come off the bill", () => {
    expect(amountProblem("-400.00")).toBeNull();
  });

  it("catches a pasted figure with its currency symbol and separators", () => {
    // The save answers this with "not an amount", which is true and says nothing about the dollar
    // sign that caused it.
    const problem = amountProblem("$48,210.07");

    expect(problem).toBeTruthy();
    expect(problem).toContain("currency symbol");
  });

  it("catches letters", () => {
    expect(amountProblem("about 48k")).toBeTruthy();
  });

  it("says nothing about a field nobody has filled yet", () => {
    expect(amountProblem("")).toBeNull();
    expect(amountProblem("  ")).toBeNull();
  });
});

describe("the direction an adjustment moves the bill", () => {
  it("explains every kind, including which way its sign goes", () => {
    for (const spec of ADJUSTMENT_KINDS) {
      expect(spec.explanation, spec.kind).toBeTruthy();
    }
  });

  it("notes a credit entered as a positive amount", () => {
    // Entered the wrong way round it does not fail. It moves the unexplained remainder by twice
    // the amount and blames the provider for it.
    expect(signHint("credit", "400")).toContain("negative");
  });

  it("notes a commitment entered as a negative amount", () => {
    expect(signHint("commitment", "-1200")).toContain("positive");
  });

  it("says nothing when the sign matches the kind", () => {
    expect(signHint("credit", "-400")).toBeNull();
    expect(signHint("commitment", "1200")).toBeNull();
  });

  it("says nothing about a figure that is not an amount yet", () => {
    expect(signHint("credit", "")).toBeNull();
    expect(signHint("credit", "$4")).toBeNull();
  });

  it("is a note and not a refusal, because a reversed credit is real", () => {
    expect(canSaveInvoice({ ...DRAFT, adjustments: [{ kind: "credit", amount: "400", note: "" }] })).toBe(true);
  });
});

describe("the request the dialog sends", () => {
  it("sends the month as the period it covers", () => {
    expect(invoicePayload(DRAFT)).toMatchObject({ period_start: "2026-09-01", period_end: "2026-09-30" });
  });

  it("sends the figure as typed, with no rounding", () => {
    expect(invoicePayload({ ...DRAFT, total: " 48210.07 " })?.total).toBe("48210.07");
  });

  it("drops an adjustment row nobody filled in", () => {
    // An empty row is not an adjustment of zero. Sent, it would explain nothing and still appear
    // on the reconciliation as a reason.
    const payload = invoicePayload({
      ...DRAFT,
      adjustments: [
        { kind: "credit", amount: "", note: "" },
        { kind: "tax", amount: "120.50", note: "GST" },
      ],
    });

    expect(payload?.adjustments).toEqual([{ kind: "tax", amount: "120.50", note: "GST" }]);
  });

  it("sends no note rather than an empty one", () => {
    expect(invoicePayload(DRAFT)?.note).toBeNull();
  });

  it("sends nothing at all when the month cannot be read", () => {
    expect(invoicePayload({ ...DRAFT, month: "whenever" })).toBeNull();
  });
});

describe("whether there is a bill to save yet", () => {
  it("is ready once a provider, a month and a total are in", () => {
    expect(canSaveInvoice(DRAFT)).toBe(true);
  });

  it("is not ready with no total", () => {
    expect(canSaveInvoice({ ...DRAFT, total: "   " })).toBe(false);
  });

  it("is not ready with a total the save would refuse", () => {
    expect(canSaveInvoice({ ...DRAFT, total: "$48,210" })).toBe(false);
  });

  it("is not ready with an adjustment the save would refuse", () => {
    expect(canSaveInvoice({ ...DRAFT, adjustments: [{ kind: "credit", amount: "-$400", note: "" }] })).toBe(false);
  });

  it("is not ready with no provider chosen", () => {
    expect(canSaveInvoice({ ...DRAFT, provider: "" })).toBe(false);
  });
});

describe("what it says once the bill is saved", () => {
  it("names the period the bill was stored against", () => {
    // Entering the wrong month is the mistake this dialog makes easiest and the one nothing
    // downstream can detect, so the confirmation is where it can still be caught.
    const stored: Invoice = {
      invoice_id: "i1",
      provider: "bedrock",
      period_start: "2026-09-01",
      period_end: "2026-09-30",
      currency: "USD",
      total: "48210.07",
      adjustments: [],
      note: null,
    };

    const message = invoiceSavedMessage(stored, "Amazon Bedrock");

    expect(message).toContain("Amazon Bedrock");
    expect(message).toContain("2026-09-01");
    expect(message).toContain("2026-09-30");
    expect(message).toContain("48210.07");
  });
});

describe("a link to this dialog from another screen", () => {
  it("carries the provider and month, and asks for the dialog to be open", () => {
    // Invoice Reconciliation links here from a month with no bill. Without the provider and the
    // month, the reader chooses both again on a screen that already knew them.
    const href = enterBillHref({ provider: "bedrock", month: "2026-09" });

    expect(href).toContain("data-sources/uploads");
    expect(href).toContain("provider=bedrock");
    expect(href).toContain("month=2026-09");
    expect(href).toContain("enter=1");
  });

  it("still opens the dialog when the linking screen knows neither", () => {
    const href = enterBillHref();

    expect(href).toContain("enter=1");
    expect(href).not.toContain("provider=");
    expect(href).not.toContain("month=");
  });

  it("reads the month off the period a screen is looking at", () => {
    expect(monthOfPeriod("2026-09-01")).toBe("2026-09");
    expect(monthOfPeriod("2026-09-15")).toBe("2026-09");
  });

  it("names no month for a period that is not a date", () => {
    expect(monthOfPeriod("September")).toBeNull();
    expect(monthOfPeriod("2026-13-01")).toBeNull();
    expect(monthOfPeriod("")).toBeNull();
  });
});

describe("what the dialog opens on when a link named it", () => {
  const providers = [
    { provider: "bedrock", display_name: "Amazon Bedrock" },
    { provider: "openrouter", display_name: "OpenRouter" },
  ];

  it("opens on the provider the link named", () => {
    expect(prefilledProvider("openrouter", providers)).toBe("openrouter");
  });

  it("ignores a provider the save would refuse", () => {
    // The value came from a URL, so it is checked against what the server offered rather than
    // trusted. Honoured, it would be a form whose save answers 404.
    expect(prefilledProvider("not-a-provider", providers)).toBe("bedrock");
  });

  it("opens on the first provider when the link named none", () => {
    expect(prefilledProvider(null, providers)).toBe("bedrock");
  });

  it("opens on nothing when this build can read no provider's bill at all", () => {
    expect(prefilledProvider("bedrock", [])).toBe("");
  });

  it("opens on the month the link named", () => {
    expect(prefilledMonth("2026-09", OCTOBER)).toBe("2026-09");
  });

  it("ignores a month it does not offer", () => {
    expect(prefilledMonth("1999-01", OCTOBER)).toBe(defaultMonth(OCTOBER));
    expect(prefilledMonth("whenever", OCTOBER)).toBe(defaultMonth(OCTOBER));
  });

  it("opens on the month that has finished when the link named none", () => {
    expect(prefilledMonth(null, OCTOBER)).toBe("2026-09");
  });
});
