import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import UsageTabs from "./UsageTabs";

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
});
