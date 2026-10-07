import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import WhatWeFetchTab from "./WhatWeFetchTab";

const fetches = {
  endpoint: "Organization Costs",
  endpoint_url: "https://api.openai.com/v1/organization/costs",
  grain: "day",
  refresh_seconds: 300,
  window_hours: 24,
  delay_note: "Recent days can still change.",
  history_note: "There is no first-connection backfill yet.",
};

describe("WhatWeFetchTab", () => {
  it("says which endpoint is read and how often", () => {
    render(<WhatWeFetchTab fetches={fetches} />);

    expect(screen.getByText("Organization Costs")).toBeInTheDocument();
    expect(screen.getByText("Every 5 minutes")).toBeInTheDocument();
  });

  it("says how fine the data is, because that limits what can be compared", () => {
    // A customer who reads 'per day' here will not go looking for a per-request breakdown
    // that this provider cannot give.
    render(<WhatWeFetchTab fetches={fetches} />);

    expect(screen.getByText("Per day")).toBeInTheDocument();
  });

  it("repeats the provider's own caveats about delay and history", () => {
    render(<WhatWeFetchTab fetches={fetches} />);

    expect(screen.getByText("Recent days can still change.")).toBeInTheDocument();
    expect(screen.getByText("There is no first-connection backfill yet.")).toBeInTheDocument();
  });
});
