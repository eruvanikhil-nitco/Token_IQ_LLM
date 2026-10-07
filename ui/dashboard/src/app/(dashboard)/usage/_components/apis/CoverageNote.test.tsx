import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { ProviderRawFact } from "@/components/networking";
import CoverageNote from "./CoverageNote";

const row = (overrides: Partial<ProviderRawFact> = {}): ProviderRawFact => ({
  bucket_start: "2026-09-16T12:40:50.477000+00:00",
  grain: "request",
  evidence: "reconciled",
  credential_name: "openrouter-billing",
  model: "openai/gpt-4o-mini",
  provider_request_id: "gen-1789562236-kKqVw1BljrOCreiAVfES",
  provider_api_key_id: "acct_123",
  billed_cost: "0.00001365",
  billing_currency: "USD",
  input_tokens: 55,
  output_tokens: 9,
  cached_input_tokens: 12,
  cache_write_tokens: 4,
  raw: null,
  fetched_at: "2026-09-16T12:40:51.847000+00:00",
  ...overrides,
});

describe("CoverageNote", () => {
  it("names the fields this provider did not populate anywhere in the window, without saying 'API key'", () => {
    render(<CoverageNote rows={[row({ provider_api_key_id: null })]} />);

    expect(
      screen.getByText("This provider did not report Provider's own key ID on the rows shown here."),
    ).toBeInTheDocument();
    expect(screen.queryByText(/\bAPI key\b/)).not.toBeInTheDocument();
  });

  it("does not name a field that at least one row in the window did populate", () => {
    render(<CoverageNote rows={[row({ provider_api_key_id: null }), row({ provider_api_key_id: "key-1" })]} />);

    expect(
      screen.queryByText("This provider did not report Provider's own key ID on the rows shown here."),
    ).not.toBeInTheDocument();
  });

  it("joins three or more missing fields with an Oxford comma, matching the not-collected sentence's style", () => {
    render(<CoverageNote rows={[row({ model: null, provider_api_key_id: null, cached_input_tokens: null })]} />);

    expect(
      screen.getByText(
        "This provider did not report Model, Provider's own key ID, and Cached input tokens on the rows shown here.",
      ),
    ).toBeInTheDocument();
  });

  it("joins exactly two missing fields with a plain 'and' and no comma", () => {
    render(<CoverageNote rows={[row({ model: null, provider_api_key_id: null })]} />);

    expect(
      screen.getByText("This provider did not report Model and Provider's own key ID on the rows shown here."),
    ).toBeInTheDocument();
  });

  it("makes no claim about missing fields for an empty window", () => {
    const { container } = render(<CoverageNote rows={[]} />);

    expect(container).not.toHaveTextContent("did not report");
  });

  it("always states that service tier, region and per-user attribution are not collected by this build", () => {
    render(<CoverageNote rows={[]} />);

    expect(
      screen.getByText("Service tier, region, and per-user attribution are not collected by this build, for any provider."),
    ).toBeInTheDocument();
  });

  it("still states the not-collected note alongside a populated window's missing-field sentence", () => {
    render(<CoverageNote rows={[row({ model: null })]} />);

    expect(screen.getByText("This provider did not report Model on the rows shown here.")).toBeInTheDocument();
    expect(
      screen.getByText("Service tier, region, and per-user attribution are not collected by this build, for any provider."),
    ).toBeInTheDocument();
  });
});
