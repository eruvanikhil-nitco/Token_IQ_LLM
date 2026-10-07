import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import CreatedKeyDisplay from "./CreatedKeyDisplay";

import { toast } from "@/lib/toast";

describe("CreatedKeyDisplay", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("should render", () => {
    render(<CreatedKeyDisplay apiKey="sk-test-123" />);
    expect(screen.getByText("sk-test-123")).toBeInTheDocument();
  });

  it("should theme the key box with tokens instead of a hardcoded light background", () => {
    render(<CreatedKeyDisplay apiKey="sk-test-123" />);

    const keyBox = screen.getByText("sk-test-123").parentElement as HTMLElement;

    expect(keyBox).not.toHaveAttribute("style");
    expect(keyBox).toHaveClass("bg-muted");
  });

  it("should display the security warning", () => {
    render(<CreatedKeyDisplay apiKey="sk-test-123" />);
    expect(screen.getByText(/you will not be able to view it again/i)).toBeInTheDocument();
  });

  it("should show the copy button with initial label", () => {
    render(<CreatedKeyDisplay apiKey="sk-test-123" />);
    expect(screen.getByRole("button", { name: /copy virtual key/i })).toBeInTheDocument();
  });

  it("should change button text to Copied after clicking copy", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<CreatedKeyDisplay apiKey="sk-test-123" />);

    await user.click(screen.getByRole("button", { name: /copy virtual key/i }));

    expect(screen.getByRole("button", { name: /copied/i })).toBeInTheDocument();
  });

  it("should show a success message when the key is copied", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<CreatedKeyDisplay apiKey="sk-test-123" />);

    await user.click(screen.getByRole("button", { name: /copy virtual key/i }));

    expect(toast.success).toHaveBeenCalledWith("Key copied to clipboard");
  });

  it("should revert button text back after 2 seconds", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<CreatedKeyDisplay apiKey="sk-test-123" />);

    await user.click(screen.getByRole("button", { name: /copy virtual key/i }));
    expect(screen.getByRole("button", { name: /copied/i })).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(2000);
    });

    expect(screen.getByRole("button", { name: /copy virtual key/i })).toBeInTheDocument();
  });

  it("should show the base URL, since the key alone cannot route a request here", () => {
    render(<CreatedKeyDisplay apiKey="sk-test-123" baseUrl="https://gateway.example.com" />);

    expect(screen.getByText("Base URL:")).toBeInTheDocument();
    expect(screen.getByText("https://gateway.example.com")).toBeInTheDocument();
  });

  it("should build an example request carrying both the base URL and the key", () => {
    render(<CreatedKeyDisplay apiKey="sk-test-123" baseUrl="https://gateway.example.com" />);

    const example = screen.getByText(/chat\/completions/);

    expect(example).toHaveTextContent("https://gateway.example.com/v1/chat/completions");
    expect(example).toHaveTextContent("Authorization: Bearer sk-test-123");
  });

  it("should copy the base URL separately from the key", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<CreatedKeyDisplay apiKey="sk-test-123" baseUrl="https://gateway.example.com" />);

    await user.click(screen.getByRole("button", { name: /copy base url/i }));

    expect(toast.success).toHaveBeenCalledWith("Base URL copied to clipboard");
  });

  it("should copy the example without disturbing the key copy state", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<CreatedKeyDisplay apiKey="sk-test-123" baseUrl="https://gateway.example.com" />);

    await user.click(screen.getByRole("button", { name: /copy example/i }));

    expect(toast.success).toHaveBeenCalledWith("Example copied to clipboard");
    expect(screen.getByRole("button", { name: /copy virtual key/i })).toBeInTheDocument();
  });

  it("should omit the base URL and example when no base URL is known", () => {
    render(<CreatedKeyDisplay apiKey="sk-test-123" baseUrl="" />);

    expect(screen.queryByText("Base URL:")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /copy example/i })).not.toBeInTheDocument();
    expect(screen.getByText("sk-test-123")).toBeInTheDocument();
  });
});
