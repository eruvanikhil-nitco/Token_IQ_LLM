import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import GatewayBaseUrl from "./GatewayBaseUrl";

describe("GatewayBaseUrl", () => {
  it("shows the address a client has to be pointed at", () => {
    render(<GatewayBaseUrl baseUrl="https://gateway.example.com" />);

    expect(screen.getByText("https://gateway.example.com")).toBeInTheDocument();
  });

  it("renders nothing when the address is unknown, rather than an empty box", () => {
    const { container } = render(<GatewayBaseUrl baseUrl="" />);

    expect(container).toBeEmptyDOMElement();
  });

  it("copies the address to the clipboard", async () => {
    const user = userEvent.setup();

    render(<GatewayBaseUrl baseUrl="https://gateway.example.com" />);
    await user.click(screen.getByRole("button", { name: "Copy Base URL" }));

    await expect(navigator.clipboard.readText()).resolves.toBe("https://gateway.example.com");
  });
});
