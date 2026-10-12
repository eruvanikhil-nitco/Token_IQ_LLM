import { describe, expect, it } from "vitest";

import { billsMissing, dayLabel, forwardingMessage, periodLabel, uploadRowView, uploadRowViews } from "./uploadRows";
import type { InvoiceForwarding, UploadRow } from "@/components/networking";

/**
 * The Uploads tab's shaping.
 *
 * Two things here go wrong quietly. A missing bill shown as a figure of zero reads as a bill of
 * nothing rather than as work to do, and a forwarding address that cannot receive mail shown as
 * though it worked sends a finance team's invoices nowhere for a month.
 */

const CHECKED_FROM = "2026-09-12T00:00:00+00:00";

const ENTERED: UploadRow = {
  kind: "entered",
  invoice_id: "i1",
  provider: "bedrock",
  display_name: "Amazon Bedrock",
  period_start: "2026-09-01",
  period_end: "2026-09-30",
  currency: "USD",
  total: "48210.07",
  note: "from the AWS console",
};

const MISSING: UploadRow = {
  kind: "not_entered",
  provider: "openrouter",
  display_name: "OpenRouter",
};

describe("a bill somebody entered", () => {
  it("shows the figure exactly as it was entered, with its currency", () => {
    // Formatted through a locale it would be rounded, and a rounded bill manufactures a
    // difference from the ledger that does not exist.
    expect(uploadRowView(ENTERED, CHECKED_FROM).total).toBe("48210.07 USD");
  });

  it("names the month when the period is a whole one", () => {
    expect(uploadRowView(ENTERED, CHECKED_FROM).period).toBe("September 2026");
  });

  it("keeps the note the person typed", () => {
    expect(uploadRowView(ENTERED, CHECKED_FROM).note).toBe("from the AWS console");
  });

  it("reads as recorded, with nothing to do about it", () => {
    const view = uploadRowView(ENTERED, CHECKED_FROM);

    expect(view.status).toBe("recorded");
    expect(view.detail).toBeNull();
  });
});

describe("a bill nobody entered", () => {
  it("carries no total at all rather than a zero", () => {
    // A zero reads as a bill of nothing. There is no bill, and the only figure available would be
    // one Token IQ worked out, which is never printed in an invoice column.
    expect(uploadRowView(MISSING, CHECKED_FROM).total).toBeNull();
  });

  it("says since when the provider has been billing without one", () => {
    const view = uploadRowView(MISSING, CHECKED_FROM);

    expect(view.status).toBe("missing");
    expect(view.period).toBe("Billing since 12 Sep 2026");
    expect(view.detail).toBeTruthy();
  });

  it("names the provider as a reader knows it rather than as the database does", () => {
    expect(uploadRowView(MISSING, CHECKED_FROM).provider).toBe("OpenRouter");
  });

  it("is counted so the tab can say how much is outstanding", () => {
    expect(billsMissing([MISSING, ENTERED, { ...MISSING, provider: "azure" }])).toBe(2);
  });

  it("counts nothing when every bill is in", () => {
    expect(billsMissing([ENTERED])).toBe(0);
  });
});

describe("the period a bill covers", () => {
  it("names a whole calendar month", () => {
    expect(periodLabel("2026-09-01", "2026-09-30")).toBe("September 2026");
  });

  it("names a whole February without needing to know how long it is", () => {
    expect(periodLabel("2024-02-01", "2024-02-29")).toBe("February 2024");
  });

  it("gives both days when the period is not a whole month", () => {
    // Rounded to "September 2026" it would claim a month the bill does not cover, and the
    // difference against a full month of usage would be blamed on the provider.
    expect(periodLabel("2026-09-01", "2026-09-15")).toBe("1 Sep 2026 to 15 Sep 2026");
  });

  it("gives both days when a period spans two months", () => {
    expect(periodLabel("2026-09-15", "2026-10-14")).toBe("15 Sep 2026 to 14 Oct 2026");
  });

  it("does not call two whole months one of them", () => {
    // The first of one month to the last of another is the case that reads as a single month if
    // only the days are checked, and it would name a month the bill does not cover.
    expect(periodLabel("2026-09-01", "2026-10-31")).toBe("1 Sep 2026 to 31 Oct 2026");
  });

  it("does not call the same month of a different year one period", () => {
    expect(periodLabel("2025-09-01", "2026-09-30")).toBe("1 Sep 2025 to 30 Sep 2026");
  });

  it("shows the day that was written rather than shifting it into a timezone", () => {
    // `new Date("2026-09-01")` is UTC midnight, which renders as 31 August for any reader west of
    // Greenwich. A billing period is a set of days on a bill, so it has no timezone to shift into.
    expect(dayLabel("2026-09-01T00:00:00+00:00")).toBe("1 Sep 2026");
  });

  it("shows a date it cannot read as it arrived rather than as Invalid Date", () => {
    expect(dayLabel("not-a-date")).toBe("not-a-date");
    expect(periodLabel("not-a-date", "nor-this")).toBe("not-a-date to nor-this");
  });
});

describe("what the tab says about forwarding bills by email", () => {
  it("shows a configured address as something to copy", () => {
    const configured: InvoiceForwarding = { kind: "configured", address: "invoices@example.com" };

    const message = forwardingMessage(configured);

    expect(message.tone).toBe("configured");
    expect(message.address).toBe("invoices@example.com");
  });

  it("says plainly that nothing reads the mailbox yet", () => {
    // Presented as automatic, a customer forwards bills for a month and then asks why none of
    // them arrived.
    const configured: InvoiceForwarding = { kind: "configured", address: "invoices@example.com" };

    expect(forwardingMessage(configured).text).toMatch(/not read this mailbox automatically|administrator/i);
  });

  it("names the setting to change when no address is configured", () => {
    const unset: InvoiceForwarding = { kind: "not_configured", setting: "TOKEN_IQ_INVOICE_FORWARDING_ADDRESS" };

    const message = forwardingMessage(unset);

    expect(message.tone).toBe("unset");
    expect(message.address).toBeNull();
    expect(message.text).toContain("TOKEN_IQ_INVOICE_FORWARDING_ADDRESS");
  });

  it("says an unusable address is losing mail, and why", () => {
    const unusable: InvoiceForwarding = {
      kind: "unusable",
      setting: "TOKEN_IQ_INVOICE_FORWARDING_ADDRESS",
      value: "invoices",
      problem: "'invoices' is not an email address: it has no @.",
    };

    const message = forwardingMessage(unusable);

    expect(message.tone).toBe("unusable");
    expect(message.text).toContain("lost");
    expect(message.text).toContain("no @");
  });

  it("does not report an unusable address as one nobody configured", () => {
    // Collapsed into "not configured" it reads as nobody having tried, and the next administrator
    // sets it a second time instead of fixing the typo.
    const unusable: InvoiceForwarding = {
      kind: "unusable",
      setting: "S",
      value: "invoices@localhost",
      problem: "no dot.",
    };

    expect(forwardingMessage(unusable).tone).not.toBe("unset");
  });
});

describe("every row together", () => {
  it("keeps the order the server put them in", () => {
    // The server puts the bills needing action first, and re-sorting here would mean two orders
    // to keep in step with each other.
    const views = uploadRowViews([MISSING, ENTERED], CHECKED_FROM);

    expect(views.map((view) => view.status)).toEqual(["missing", "recorded"]);
  });

  it("gives every row a key of its own, including two missing ones", () => {
    const views = uploadRowViews([MISSING, { ...MISSING, provider: "azure" }, ENTERED], CHECKED_FROM);

    expect(new Set(views.map((view) => view.id)).size).toBe(3);
  });
});
