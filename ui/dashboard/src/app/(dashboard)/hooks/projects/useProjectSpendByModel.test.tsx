import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { DailyData, SpendMetrics } from "@/components/UsagePage/types";
import { internalUserRoles } from "@/utils/roles";
import { useProjectSpendByModel } from "./useProjectSpendByModel";

const mockUseAuthorized = vi.fn();
vi.mock("@/app/(dashboard)/hooks/useAuthorized", () => ({
  default: () => mockUseAuthorized(),
}));

const mockProjectDailyActivityCall = vi.fn();
vi.mock("@/components/networking", () => ({
  projectDailyActivityCall: (...args: unknown[]) => mockProjectDailyActivityCall(...args),
}));

const metrics = (spend: number): SpendMetrics => ({
  spend,
  prompt_tokens: 0,
  completion_tokens: 0,
  total_tokens: 0,
  api_requests: 0,
  successful_requests: 0,
  failed_requests: 0,
  cache_read_input_tokens: 0,
  cache_creation_input_tokens: 0,
});

const day = (date: string, model: string, spend: number): DailyData => ({
  date,
  metrics: metrics(spend),
  breakdown: {
    models: { [model]: { metrics: metrics(spend), metadata: {}, api_key_breakdown: {} } },
    model_groups: {},
    mcp_servers: {},
    providers: {},
    api_keys: {},
    entities: {},
  },
});

const page = (results: DailyData[], totalPages: number) => ({
  results,
  metadata: { total_pages: totalPages, page: 1, has_more: totalPages > 1 },
});

const NOW = new Date("2026-09-15T12:00:00Z");
const DAY_MS = 24 * 60 * 60 * 1000;

const renderSpendByModel = () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return renderHook(() => useProjectSpendByModel("p1"), {
    wrapper: ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    ),
  });
};

describe("useProjectSpendByModel", () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(NOW);
    mockProjectDailyActivityCall.mockReset();
    mockUseAuthorized.mockReturnValue({ accessToken: "sk-team-admin", userRole: internalUserRoles[0] });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("adds up every page of the report, so a busy project keeps its oldest days", async () => {
    mockProjectDailyActivityCall.mockImplementation(
      async (_token: string, _start: Date, _end: Date, pageNumber: number) =>
        pageNumber === 1
          ? page([day("2026-09-14", "gpt-5.2", 2)], 2)
          : page([day("2026-08-17", "gpt-5.2", 1), day("2026-08-17", "claude-sonnet-5", 5)], 2),
    );

    const { result } = renderSpendByModel();

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockProjectDailyActivityCall.mock.calls.map((call) => call[3])).toEqual([1, 2]);
    expect(result.current.data).toEqual([
      { model: "claude-sonnet-5", spend: 5 },
      { model: "gpt-5.2", spend: 3 },
    ]);
  });

  it("asks for the last 30 days of this project, ending now", async () => {
    mockProjectDailyActivityCall.mockResolvedValue(page([], 1));

    const { result } = renderSpendByModel();

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockProjectDailyActivityCall).toHaveBeenCalledTimes(1);
    const [token, start, end, pageNumber, projectIds] = mockProjectDailyActivityCall.mock.calls[0];
    expect(token).toBe("sk-team-admin");
    expect((end as Date).getTime()).toBe(NOW.getTime());
    expect((start as Date).getTime()).toBe(NOW.getTime() - 30 * DAY_MS);
    expect(pageNumber).toBe(1);
    expect(projectIds).toEqual(["p1"]);
  });

  it("does not ask for the report for a role that cannot read projects", () => {
    mockUseAuthorized.mockReturnValue({ accessToken: "sk-customer", userRole: "Customer" });

    const { result } = renderSpendByModel();

    expect(result.current.fetchStatus).toBe("idle");
    expect(mockProjectDailyActivityCall).not.toHaveBeenCalled();
  });
});
