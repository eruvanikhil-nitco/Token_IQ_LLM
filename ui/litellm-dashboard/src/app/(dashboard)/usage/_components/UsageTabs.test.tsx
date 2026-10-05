import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import UsageTabs from "./UsageTabs";

function StatefulGatewayFilter() {
  const [filter, setFilter] = useState("");
  return <input aria-label="date range filter" value={filter} onChange={(e) => setFilter(e.target.value)} />;
}

describe("UsageTabs", () => {
  it("opens on Combined, the only view that reconciles the sources against each other", () => {
    render(
      <UsageTabs gateway={() => <p>gateway content</p>} apis={<p>apis content</p>} combined={() => <p>combined content</p>} />,
    );
    expect(screen.getByText("combined content")).toBeInTheDocument();
  });

  it("still reaches the Gateway view, which is unchanged", async () => {
    const user = userEvent.setup();
    render(
      <UsageTabs gateway={() => <p>gateway content</p>} apis={<p>apis content</p>} combined={() => <p>combined content</p>} />,
    );
    await user.click(screen.getByRole("tab", { name: "Gateway" }));
    expect(await screen.findByText("gateway content")).toBeInTheDocument();
  });

  it("shows the APIs view when that tab is chosen", async () => {
    const user = userEvent.setup();
    render(
      <UsageTabs gateway={() => <p>gateway content</p>} apis={<p>apis content</p>} combined={() => <p>combined content</p>} />,
    );
    await user.click(screen.getByRole("tab", { name: "APIs" }));
    expect(await screen.findByText("apis content")).toBeInTheDocument();
  });

  it("keeps Gateway filters set after visiting APIs and coming back", async () => {
    const user = userEvent.setup();
    render(
      <UsageTabs gateway={() => <StatefulGatewayFilter />} apis={<p>apis content</p>} combined={() => <p>combined content</p>} />,
    );

    await user.click(screen.getByRole("tab", { name: "Gateway" }));
    fireEvent.change(await screen.findByLabelText("date range filter"), { target: { value: "last 7 days" } });

    await user.click(screen.getByRole("tab", { name: "APIs" }));
    await screen.findByText("apis content");
    await user.click(screen.getByRole("tab", { name: "Gateway" }));

    expect(await screen.findByLabelText("date range filter")).toHaveValue("last 7 days");
  });

  it("gives every tab the same period, so switching tab cannot change the window", async () => {
    // The page used to hold two periods: a 7/30/90 dropdown inside Combined defaulting to 30 days,
    // and a separate picker inside Gateway defaulting to 7. Both panels stay mounted, so moving
    // from Combined to Gateway took the reader from thirty days to seven with nothing saying so.
    const user = userEvent.setup();
    const seen: Record<string, number> = {};
    // Plain render props rather than components, so each records the period it was handed.
    const showCombined = (period: { from?: Date; to?: Date }) => {
      seen.combined = period.from?.getTime() ?? 0;
      return <p>combined content</p>;
    };
    const showGateway = (period: { from?: Date; to?: Date }) => {
      seen.gateway = period.from?.getTime() ?? 0;
      return <p>gateway content</p>;
    };

    render(<UsageTabs gateway={showGateway} apis={<p>apis content</p>} combined={showCombined} />);
    await user.click(screen.getByRole("tab", { name: "Gateway" }));
    await screen.findByText("gateway content");

    expect(seen.gateway).toBe(seen.combined);
  });

  it("puts the period control above the tabs, where it governs all three", () => {
    render(<UsageTabs gateway={() => <p>g</p>} apis={<p>a</p>} combined={() => <p>c</p>} />);

    // One control on the page, not one per tab. `data-slot` is what the primitive sets
    // deliberately and treats as stable; the trigger exposes no role or label to query.
    expect(document.querySelectorAll('[data-slot="advanced-date-picker-trigger"]')).toHaveLength(1);
  });
});
