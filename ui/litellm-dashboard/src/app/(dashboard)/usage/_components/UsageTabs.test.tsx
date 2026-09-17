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
  it("opens on Gateway so today's view is what a returning user still sees first", () => {
    render(<UsageTabs gateway={<p>gateway content</p>} apis={<p>apis content</p>} />);
    expect(screen.getByText("gateway content")).toBeInTheDocument();
  });

  it("shows the APIs view when that tab is chosen", async () => {
    const user = userEvent.setup();
    render(<UsageTabs gateway={<p>gateway content</p>} apis={<p>apis content</p>} />);
    await user.click(screen.getByRole("tab", { name: "APIs" }));
    expect(await screen.findByText("apis content")).toBeInTheDocument();
  });

  it("keeps Gateway filters set after visiting APIs and coming back", async () => {
    const user = userEvent.setup();
    render(<UsageTabs gateway={<StatefulGatewayFilter />} apis={<p>apis content</p>} />);

    fireEvent.change(screen.getByLabelText("date range filter"), { target: { value: "last 7 days" } });

    await user.click(screen.getByRole("tab", { name: "APIs" }));
    await screen.findByText("apis content");
    await user.click(screen.getByRole("tab", { name: "Gateway" }));

    expect(await screen.findByLabelText("date range filter")).toHaveValue("last 7 days");
  });
});
