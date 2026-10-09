"use client";

import { useEffect } from "react";

import { migratedHref } from "@/utils/migratedPages";

/**
 * UI Theme moved into Administration > Settings as a tab. This stays so a bookmark or a link to
 * /ui-theme still arrives somewhere, rather than hitting a route that no longer exists.
 */
export default function UITheme() {
  useEffect(() => {
    window.location.replace(`${migratedHref("settings/ui-theme")}/`);
  }, []);
  return null;
}
