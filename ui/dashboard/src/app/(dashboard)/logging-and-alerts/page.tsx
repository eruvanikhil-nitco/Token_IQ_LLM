"use client";

import { useEffect } from "react";

import { migratedHref } from "@/utils/migratedPages";

/**
 * Logging & Alerts moved into Administration > Settings as a tab. This stays so a bookmark or a link to
 * /logging-and-alerts still arrives somewhere, rather than hitting a route that no longer exists.
 */
export default function LoggingAndAlerts() {
  useEffect(() => {
    window.location.replace(`${migratedHref("settings/logging-and-alerts")}/`);
  }, []);
  return null;
}
