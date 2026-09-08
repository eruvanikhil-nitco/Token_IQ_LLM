import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders, screen } from "../../../../tests/test-utils";
import { CommunityEngagementButtons } from "./CommunityEngagementButtons";

let mockUseDisableShowPromptsImpl = () => false;

vi.mock("@/app/(dashboard)/hooks/useDisableShowPrompts", () => ({
  useDisableShowPrompts: () => mockUseDisableShowPromptsImpl(),
}));

describe("CommunityEngagementButtons", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseDisableShowPromptsImpl = () => false;
  });

  it("should still render both icons", () => {
    renderWithProviders(<CommunityEngagementButtons />);

    expect(screen.getByTestId("community-icon-slack")).toBeInTheDocument();
    expect(screen.getByTestId("community-icon-github")).toBeInTheDocument();
  });

  it("should render no links at all, so nothing navigates away", () => {
    const { container } = renderWithProviders(<CommunityEngagementButtons />);

    expect(container.querySelectorAll("a")).toHaveLength(0);
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it("should not point anywhere near litellm.ai or the upstream repo", () => {
    const { container } = renderWithProviders(<CommunityEngagementButtons />);

    expect(container.innerHTML).not.toContain("litellm.ai");
    expect(container.innerHTML).not.toContain("github.com/BerriAI");
  });

  it("should not be clickable", () => {
    renderWithProviders(<CommunityEngagementButtons />);

    // pointer-events-none is what makes them inert; without it a bare span
    // still takes hover and focus styling and reads as interactive.
    expect(screen.getByTestId("community-icon-slack")).toHaveClass("pointer-events-none");
    expect(screen.getByTestId("community-icon-github")).toHaveClass("pointer-events-none");
  });

  it("should not render at all when prompts are disabled", () => {
    mockUseDisableShowPromptsImpl = () => true;

    renderWithProviders(<CommunityEngagementButtons />);

    expect(screen.queryByTestId("community-icon-slack")).not.toBeInTheDocument();
    expect(screen.queryByTestId("community-icon-github")).not.toBeInTheDocument();
  });
});
