import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import RolesPanel from "./RolesPanel";

/**
 * The screen's job is to be honest about two things: what the eight roles are, and which of them
 * this installation cannot actually create. A list of roles that cannot be assigned, shown without
 * saying so, is discovered by a customer after they invite somebody.
 */

describe("Roles & Permissions", () => {
  it("names all eight roles the way the blueprint does", () => {
    render(<RolesPanel />);

    for (const role of [
      "Org Owner",
      "Org Admin",
      "Finance Admin",
      "Org Viewer",
      "Team Lead (Manage)",
      "Team Lead (Read-only)",
      "Team Member",
      "Service Account",
    ]) {
      expect(screen.getAllByText(role).length).toBeGreaterThan(0);
    }
  });

  it("says which roles cannot be assigned yet, and why", () => {
    render(<RolesPanel />);

    expect(screen.getAllByText("Not yet").length).toBe(4);
    expect(
      screen.getByText(/Finance Admin, Team Lead \(Manage\), Team Lead \(Read-only\), Service Account/),
    ).toBeInTheDocument();
    expect(screen.getByText(/no underlying role is/)).toBeInTheDocument();
  });

  it("says what a role that can be assigned is assigned as", () => {
    render(<RolesPanel />);

    expect(screen.getByText("Assigned as proxy_admin on the Users tab")).toBeInTheDocument();
    expect(screen.getByText("Assigned as internal_user on the Users tab")).toBeInTheDocument();
  });

  it("keeps the blueprint's own words for a permission rather than a level", () => {
    render(<RolesPanel />);

    expect(screen.getByText("View; upload invoices")).toBeInTheDocument();
    expect(screen.getByText("View; request changes")).toBeInTheDocument();
    expect(screen.getByText("Ingest only")).toBeInTheDocument();
  });

  it("separates the role from the scope, which decides different things", () => {
    render(<RolesPanel />);

    expect(screen.getByText(/A role decides which pages/)).toHaveTextContent("scope");
  });

  it("shows a permission a role does not hold as held by nobody rather than leaving the cell out", () => {
    render(<RolesPanel />);

    const settings = screen.getByText("Integrations and settings").closest("tr");
    expect(settings).not.toBeNull();
    // Six of the eight do not have settings at all, and an empty cell would read as unknown.
    expect(within(settings as HTMLElement).getAllByText("—").length).toBe(6);
  });
});
