import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { internalUserRoles } from "@/utils/roles";
import { useProjectDetails } from "./useProjectDetails";

vi.mock("@/app/(dashboard)/hooks/useAuthorized", () => ({
  default: () => ({ accessToken: "sk-team-admin", userRole: internalUserRoles[0] }),
}));

vi.mock("@/components/networking", () => ({
  getProxyBaseUrl: () => "",
  getGlobalLitellmHeaderName: () => "Authorization",
  deriveErrorMessage: () => "error",
  handleError: vi.fn(),
}));

describe("useProjectDetails", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads a project for a team admin, not only for proxy admins", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ project_id: "p1" }) });
    vi.stubGlobal("fetch", fetchMock);
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });

    const { result } = renderHook(() => useProjectDetails("p1"), {
      wrapper: ({ children }: { children: React.ReactNode }) => (
        <QueryClientProvider client={client}>{children}</QueryClientProvider>
      ),
    });

    await waitFor(() => expect(result.current.data?.project_id).toBe("p1"));
    expect(fetchMock.mock.calls[0][0]).toBe("/project/info?project_id=p1");
  });
});
