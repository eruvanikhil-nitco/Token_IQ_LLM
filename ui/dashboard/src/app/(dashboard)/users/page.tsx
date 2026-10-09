"use client";

import { useEffect } from "react";

import { migratedHref } from "@/utils/migratedPages";

/**
 * Users moved into Administration > Access Control as its first tab. This stays so a bookmark or a
 * link to /users still arrives somewhere, rather than hitting a route that no longer exists.
 */
export default function UsersPage() {
  useEffect(() => {
    window.location.replace(`${migratedHref("access-control")}/`);
  }, []);
  return null;
}
