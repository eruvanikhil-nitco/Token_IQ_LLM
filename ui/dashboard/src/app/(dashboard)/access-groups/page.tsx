"use client";

import { useEffect } from "react";

import { migratedHref } from "@/utils/migratedPages";

/**
 * Access Groups moved into Administration > Access Control as a tab. This stays so a bookmark or a
 * link to /access-groups still arrives somewhere, rather than hitting a route that no longer exists.
 */
export default function AccessGroupsPage() {
  useEffect(() => {
    window.location.replace(`${migratedHref("access-control/access-groups")}/`);
  }, []);
  return null;
}
