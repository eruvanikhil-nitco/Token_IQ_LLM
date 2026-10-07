import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { within } from "@testing-library/react";
import { renderWithProviders, screen, testQueryClient } from "../../../../../tests/test-utils";
import AuditLogView from "./AuditLogView";

const mockAuditListCall = vi.hoisted(() => vi.fn());

vi.mock("@/components/networking", () => ({
  auditListCall: mockAuditListCall,
}));

vi.mock("@/app/(dashboard)/hooks/useAuthorized", () => ({
  default: () => ({ accessToken: "tok", userRole: "Admin", userId: "u1" }),
}));

const teamUpdate = {
  id: "a1",
  changed_at: "2026-09-10T10:31:20",
  action: "updated",
  table_name: "LiteLLM_TeamTable",
  object_id: "cd4318d5-f2f7-4182-992d-46fad28beb9b",
  changed_by: "nikhil",
  summary: "max_budget",
  changes: [{ field: "max_budget", before: "5.0", after: "12.5" }],
};

const keyCreated = {
  id: "a2",
  changed_at: "2026-09-10T10:07:08",
  action: "created",
  table_name: "LiteLLM_VerificationToken",
  object_id: "2806b95f53c9e68b036872197c314aaa",
  changed_by: "default_user_id",
  summary: "key_alias, models",
  changes: [{ field: "key_alias", before: null, after: "sales-app" }],
};

const response = (entries: object[] = [teamUpdate, keyCreated], total = entries.length) => ({
  entries,
  total,
  page: 1,
  size: 25,
});

/** The results table only. Filter dropdowns repeat the same labels, so bare text queries
 *  match twice and prove nothing about what was rendered as a row. */
const rows = () => within(screen.getAllByRole("table")[0]);

describe("AuditLogView", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    testQueryClient.clear();
    mockAuditListCall.mockResolvedValue(response());
  });

  it("names objects the way a person would, not by table name", async () => {
    renderWithProviders(<AuditLogView />);

    await screen.findByText("nikhil");

    // "LiteLLM_VerificationToken" means nothing to someone asking who deleted a key.
    expect(rows().getByText("Team")).toBeInTheDocument();
    expect(rows().getByText("Virtual key")).toBeInTheDocument();
  });

  it("shows who made each change", async () => {
    renderWithProviders(<AuditLogView />);

    expect(await screen.findByText("nikhil")).toBeInTheDocument();
  });

  it("summarises what changed without needing the row expanded", async () => {
    renderWithProviders(<AuditLogView />);

    expect(await screen.findByText("max_budget")).toBeInTheDocument();
  });

  it("reveals the before and after only when asked", async () => {
    const user = userEvent.setup();
    renderWithProviders(<AuditLogView />);

    await screen.findByText("nikhil");
    expect(screen.queryByText("12.5")).not.toBeInTheDocument();

    await user.click(screen.getAllByRole("button", { name: "Details" })[0]);

    expect(screen.getByText("5.0")).toBeInTheDocument();
    expect(screen.getByText("12.5")).toBeInTheDocument();
  });

  it("reads a missing before on a creation as not set, rather than as a deletion", async () => {
    const user = userEvent.setup();
    renderWithProviders(<AuditLogView />);

    await screen.findByText("nikhil");
    await user.click(screen.getAllByRole("button", { name: "Details" })[1]);

    expect(screen.getByText("not set")).toBeInTheDocument();
    expect(screen.queryByText("removed")).not.toBeInTheDocument();
  });

  it("asks the proxy for the chosen action rather than filtering in the browser", async () => {
    const user = userEvent.setup();
    renderWithProviders(<AuditLogView />);

    await screen.findByText("nikhil");
    await user.selectOptions(screen.getByLabelText("Filter by action"), "deleted");

    // Filtering client-side would only ever search the current page.
    expect(mockAuditListCall).toHaveBeenLastCalledWith("tok", expect.objectContaining({ action: "deleted" }));
  });

  it("returns to the first page when a filter changes", async () => {
    const user = userEvent.setup();
    mockAuditListCall.mockResolvedValue(response([teamUpdate, keyCreated], 200));
    renderWithProviders(<AuditLogView />);

    await screen.findByText("nikhil");
    await user.click(screen.getByRole("button", { name: "Next" }));
    await user.selectOptions(screen.getByLabelText("Filter by action"), "created");

    // Staying on page 4 of a different filter shows an empty page for no reason.
    expect(mockAuditListCall).toHaveBeenLastCalledWith("tok", expect.objectContaining({ page: 1 }));
  });

  it("offers only the object kinds actually present", async () => {
    renderWithProviders(<AuditLogView />);

    await screen.findByText("nikhil");
    const options = screen.getByLabelText("Filter by object").textContent ?? "";

    expect(options).toContain("Team");
    expect(options).toContain("Virtual key");
    expect(options).not.toContain("Organization");
  });

  it("explains an empty trail instead of showing a blank table", async () => {
    mockAuditListCall.mockResolvedValue(response([], 0));

    renderWithProviders(<AuditLogView />);

    // Recording being off and nothing having happened look identical from here.
    expect(await screen.findByText(/Nothing recorded yet/)).toBeInTheDocument();
  });

  it("says so when the trail cannot be loaded, rather than looking empty", async () => {
    mockAuditListCall.mockRejectedValue(new Error("boom"));

    renderWithProviders(<AuditLogView />);

    expect(await screen.findByText("Could not load the audit trail.")).toBeInTheDocument();
  });

  it("hides paging when everything fits on one page", async () => {
    renderWithProviders(<AuditLogView />);

    await screen.findByText("nikhil");
    expect(screen.queryByRole("button", { name: "Next" })).not.toBeInTheDocument();
  });
});
