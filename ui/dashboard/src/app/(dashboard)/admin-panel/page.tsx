"use client";

import { useEffect } from "react";

import { migratedHref } from "@/utils/migratedPages";

/**
 * Admin Settings moved into Administration > Settings as a tab. This stays so a bookmark or a link to
 * /admin-panel still arrives somewhere, rather than hitting a route that no longer exists.
 */
export default function AdminPanelPage() {
  useEffect(() => {
    window.location.replace(`${migratedHref("settings")}/`);
  }, []);
  return null;
}
