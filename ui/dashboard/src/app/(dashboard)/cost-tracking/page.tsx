"use client";

import { useEffect } from "react";

import { migratedHref } from "@/utils/migratedPages";

/**
 * Cost Tracking is Administration > Pricing & Rates now, the name section 12's label table gives
 * it. The route stays so a bookmark or a link to /cost-tracking still arrives somewhere, rather
 * than hitting a route that no longer exists.
 */
export default function CostTrackingRedirect() {
  useEffect(() => {
    window.location.replace(`${migratedHref("pricing-and-rates")}/`);
  }, []);
  return null;
}
