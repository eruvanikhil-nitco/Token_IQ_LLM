import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import RecommendationTabs from "./RecommendationTabs";
import type { Recommendation, RecommendationsResponse } from "@/components/networking";

const ESCAPED: Recommendation = {
  rule_id: "escaped_spend",
  kind: "business",
  title: "Spend is reaching providers without going through the gateway",
  noticed: "Provider bills are higher than what the gateway saw.",
  evidence: [
    { label: "Unallocated", value: "$412.90" },
    { label: "Accounts", value: "openai-prod" },
  ],
  figure: "412.90",
  figure_kind: "already_spent_unwatched",
  currency: "USD",
  who_should_act: "Whoever owns the openai-prod key",
  state: null,
};

const FAILURES: Recommendation = {
  rule_id: "failed_requests",
  kind: "technical",
  title: "A large share of requests are failing",
  noticed: "103 of 165 requests failed in this period.",
  evidence: [{ label: "Failure rate", value: "62.4%" }],
  figure: null,
  figure_kind: "none",
  currency: null,
  who_should_act: "The team that owns the failing keys",
  state: null,
};

const DECIDED: Recommendation = {
  ...FAILURES,
  rule_id: "stale_budget",
  title: "A budget is barely used",
  state: "dismissed",
};

const RESPONSE: RecommendationsResponse = {
  period_start: "2026-09-01",
  period_end: "2026-09-29",
  open: [ESCAPED, FAILURES],
  decided: [DECIDED],
};

const recommendationsCall = vi.fn();
const decideCall = vi.fn();
const undoCall = vi.fn();

vi.mock("@/components/networking", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/components/networking")>()),
  recommendationsCall: (...args: unknown[]) => recommendationsCall(...args),
  decideRecommendationCall: (...args: unknown[]) => decideCall(...args),
  undoRecommendationCall: (...args: unknown[]) => undoCall(...args),
}));

vi.mock("@/app/(dashboard)/hooks/useAuthorized", () => ({
  default: () => ({ accessToken: "sk-test", userRole: "proxy_admin" }),
}));

const renderTabs = () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <RecommendationTabs />
    </QueryClientProvider>,
  );
};

describe("RecommendationTabs", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    recommendationsCall.mockResolvedValue(RESPONSE);
    decideCall.mockResolvedValue(undefined);
    undoCall.mockResolvedValue(undefined);
  });

  it("shows money that escaped the gateway as already being spent, never as a saving", async () => {
    renderTabs();
    const card = (await screen.findByText(ESCAPED.title)).closest("div[data-slot='card']");

    expect(card).toHaveTextContent("$412.90");
    expect(card).toHaveTextContent("Already being spent, unwatched");
    expect(card).not.toHaveTextContent(/saving|save/i);
  });

  it("shows no figure at all on a card that has nothing honest to quantify, rather than a zero", async () => {
    renderTabs();
    const failures = (await screen.findByText(FAILURES.title)).closest("div[data-slot='card']");

    expect(failures).not.toBeNull();
    expect(failures).not.toHaveTextContent("$");
    expect(failures).not.toHaveTextContent("0.00");
  });

  it("keeps a decided card out of the open list but still reachable, so a dismissal leaves a trace", async () => {
    const user = userEvent.setup();
    renderTabs();

    expect(await screen.findByText(ESCAPED.title)).toBeInTheDocument();
    expect(screen.queryByText(DECIDED.title)).not.toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "Done & Dismissed" }));
    expect(await screen.findByText(DECIDED.title)).toBeInTheDocument();
    expect(screen.getByText("Dismissed")).toBeInTheDocument();
  });

  it("separates the business cards from the technical ones", async () => {
    const user = userEvent.setup();
    renderTabs();

    await user.click(await screen.findByRole("tab", { name: "Business" }));
    expect(await screen.findByText(ESCAPED.title)).toBeInTheDocument();
    expect(screen.queryByText(FAILURES.title)).not.toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "Technical" }));
    expect(await screen.findByText(FAILURES.title)).toBeInTheDocument();
    expect(screen.queryByText(ESCAPED.title)).not.toBeInTheDocument();
  });

  it("sends the decision an admin made for the card they made it on", async () => {
    const user = userEvent.setup();
    renderTabs();

    await user.click(await screen.findByRole("button", { name: `Dismiss: ${FAILURES.title}` }));
    expect(decideCall).toHaveBeenCalledWith("sk-test", "failed_requests", "dismissed");
  });

  it("brings a decided card back when an admin undoes the decision", async () => {
    const user = userEvent.setup();
    renderTabs();

    await user.click(await screen.findByRole("tab", { name: "Done & Dismissed" }));
    await user.click(await screen.findByRole("button", { name: `Bring back: ${DECIDED.title}` }));
    expect(undoCall).toHaveBeenCalledWith("sk-test", "stale_budget");
  });

  it("asks for the period the reader chose, so a card is always about a stated window", async () => {
    renderTabs();
    await screen.findByText(ESCAPED.title);

    expect(recommendationsCall).toHaveBeenCalledWith("sk-test", expect.any(String), expect.any(String));
    const [, start, end] = recommendationsCall.mock.calls[0];
    expect(start).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(end).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });
});
