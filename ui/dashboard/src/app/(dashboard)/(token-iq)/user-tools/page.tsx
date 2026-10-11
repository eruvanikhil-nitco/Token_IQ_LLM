"use client";

import { useEffect } from "react";

import { migratedHref } from "@/utils/migratedPages";

/**
 * This page is the Accounts tab of Data Sources now. The route stays so a bookmark or a link to
 * /user-tools still arrives somewhere, rather than hitting a route that no longer exists.
 */
export default function UserToolsRedirect() {
  useEffect(() => {
    window.location.replace(`${migratedHref("data-sources/accounts")}/`);
  }, []);
  return null;
}
