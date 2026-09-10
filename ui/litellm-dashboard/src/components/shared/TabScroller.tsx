"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "@/lib/cva.config";
import { affordance, stepFor, type ScrollAffordance } from "./tabScroll";

const AT_REST: ScrollAffordance = { canScrollLeft: false, canScrollRight: false };

interface TabScrollerProps {
  readonly children: React.ReactNode;
  readonly className?: string;
}

/**
 * Horizontal scrolling for a tab strip that outgrows its row.
 *
 * The strip already scrolled, but with the scrollbar hidden nothing said so: tabs past the right
 * edge were reachable only by a trackpad swipe you had no reason to guess at. The arrows appear
 * only when there is somewhere to go, so a strip that fits looks exactly as it did before.
 */
const TabScroller: React.FC<TabScrollerProps> = ({ children, className }) => {
  const ref = useRef<HTMLDivElement>(null);
  const [reach, setReach] = useState<ScrollAffordance>(AT_REST);

  const measure = useCallback(() => {
    const el = ref.current;
    if (el) setReach(affordance(el));
  }, []);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    measure();
    el.addEventListener("scroll", measure, { passive: true });

    // Tabs can appear or disappear with permissions, and the row reflows on resize; either
    // changes whether there is anything left to scroll to.
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(measure);
    observer?.observe(el);
    Array.from(el.children).forEach((child) => observer?.observe(child));

    return () => {
      el.removeEventListener("scroll", measure);
      observer?.disconnect();
    };
  }, [measure, children]);

  const nudge = (direction: -1 | 1) => {
    const el = ref.current;
    if (!el) return;
    el.scrollBy({ left: direction * stepFor(el.clientWidth), behavior: "smooth" });
  };

  const arrow = (direction: -1 | 1, enabled: boolean) => {
    const back = direction === -1;
    return (
      <button
        type="button"
        aria-label={back ? "Scroll tabs left" : "Scroll tabs right"}
        disabled={!enabled}
        onClick={() => nudge(direction)}
        className={cn(
          "flex h-7 w-6 shrink-0 items-center justify-center rounded text-muted-foreground transition-opacity",
          "hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
          enabled ? "opacity-100" : "pointer-events-none opacity-0",
        )}
      >
        {back ? <ChevronLeft className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
      </button>
    );
  };

  return (
    <div className={cn("flex min-w-0 flex-nowrap items-center", className)}>
      {arrow(-1, reach.canScrollLeft)}
      <div
        ref={ref}
        data-slot="tab-scroll-strip"
        className="no-scrollbar -mb-1.5 min-w-0 flex-1 overflow-x-auto pb-1.5"
      >
        {children}
      </div>
      {arrow(1, reach.canScrollRight)}
    </div>
  );
};

export default TabScroller;
