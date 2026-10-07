import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import TabScroller from "./TabScroller";

/**
 * jsdom performs no layout, so every element reports a width of zero and nothing ever looks
 * scrollable. These stubs stand in for the measurements a real browser would supply.
 */
let scrollLeft = 0;

const stubLayout = (clientWidth: number, scrollWidth: number) => {
  vi.spyOn(HTMLElement.prototype, "clientWidth", "get").mockReturnValue(clientWidth);
  vi.spyOn(HTMLElement.prototype, "scrollWidth", "get").mockReturnValue(scrollWidth);
  vi.spyOn(HTMLElement.prototype, "scrollLeft", "get").mockImplementation(() => scrollLeft);
};

/** Move the strip as a real scroll would, and let the component react to it. */
const scrollTo = (strip: HTMLElement, position: number) => {
  scrollLeft = position;
  act(() => {
    strip.dispatchEvent(new Event("scroll"));
  });
};

/**
 * The scrolling strip carries no role or label of its own, so `data-slot` is the stable handle
 * the dashboard's own guidance points to for exactly this case.
 */
const stripOf = (container: HTMLElement): HTMLElement =>
  // eslint-disable-next-line testing-library/no-node-access -- the strip exposes nothing accessible to query
  container.querySelector('[data-slot="tab-scroll-strip"]') as HTMLElement;

const scrollBy = vi.fn();

const leftArrow = () => screen.getByRole("button", { name: "Scroll tabs left" });
const rightArrow = () => screen.getByRole("button", { name: "Scroll tabs right" });

describe("TabScroller", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    scrollLeft = 0;
    HTMLElement.prototype.scrollBy = scrollBy;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the tabs it wraps", () => {
    stubLayout(600, 600);
    render(
      <TabScroller>
        <span>All Models</span>
      </TabScroller>,
    );

    expect(screen.getByText("All Models")).toBeInTheDocument();
  });

  it("offers no arrows when every tab already fits", () => {
    stubLayout(600, 600);
    render(
      <TabScroller>
        <span>tabs</span>
      </TabScroller>,
    );

    // A strip that fits must look exactly as it did before, with no dead controls.
    expect(leftArrow()).toBeDisabled();
    expect(rightArrow()).toBeDisabled();
  });

  it("offers the right arrow once the tabs overflow", () => {
    stubLayout(600, 1400);
    render(
      <TabScroller>
        <span>tabs</span>
      </TabScroller>,
    );

    expect(rightArrow()).toBeEnabled();
    expect(leftArrow()).toBeDisabled();
  });

  it("scrolls toward the hidden tabs when the right arrow is pressed", async () => {
    const user = userEvent.setup();
    stubLayout(600, 1400);
    render(
      <TabScroller>
        <span>tabs</span>
      </TabScroller>,
    );

    await user.click(rightArrow());

    expect(scrollBy).toHaveBeenCalledWith({ left: 450, behavior: "smooth" });
  });

  it("scrolls back the other way from the left arrow", async () => {
    const user = userEvent.setup();
    stubLayout(600, 1400);
    const { container } = render(
      <TabScroller>
        <span>tabs</span>
      </TabScroller>,
    );

    scrollTo(stripOf(container), 300);

    expect(leftArrow()).toBeEnabled();

    await user.click(leftArrow());

    expect(scrollBy).toHaveBeenCalledWith({ left: -450, behavior: "smooth" });
  });

  it("retires the right arrow once the end is reached", () => {
    stubLayout(600, 1400);
    const { container } = render(
      <TabScroller>
        <span>tabs</span>
      </TabScroller>,
    );

    scrollTo(stripOf(container), 800);

    expect(rightArrow()).toBeDisabled();
    expect(leftArrow()).toBeEnabled();
  });

  it("does not scroll when a disabled arrow is pressed", async () => {
    const user = userEvent.setup();
    stubLayout(600, 600);
    render(
      <TabScroller>
        <span>tabs</span>
      </TabScroller>,
    );

    await user.click(rightArrow());

    expect(scrollBy).not.toHaveBeenCalled();
  });
});
