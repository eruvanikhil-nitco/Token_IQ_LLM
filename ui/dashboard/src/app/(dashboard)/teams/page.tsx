"use client";

import { useEffect } from "react";

import { migratedHref } from "@/utils/migratedPages";

/**
 * Teams moved into Administration > Organization as its first tab. This stays so a bookmark or a
 * link to /teams still arrives somewhere, rather than hitting a route that no longer exists.
 */
export default function TeamsPage() {
  useEffect(() => {
    window.location.replace(`${migratedHref("organization")}/`);
  }, []);
  return null;
}
