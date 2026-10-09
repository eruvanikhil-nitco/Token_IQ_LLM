"use client";

import { useEffect } from "react";

import { migratedHref } from "@/utils/migratedPages";

/**
 * Projects moved into Administration > Organization as a tab. This stays so a bookmark or a link
 * to /projects still arrives somewhere, rather than hitting a route that no longer exists.
 */
export default function ProjectsRedirect() {
  useEffect(() => {
    window.location.replace(`${migratedHref("organization/projects")}/`);
  }, []);
  return null;
}
