"use client";

import { useEffect } from "react";

import { gatewayViewHref } from "@/app/(dashboard)/(token-iq)/data-sources/_components/gatewayViews";

/**
 * Forwarding credentials are the Upstreams view of Data Sources > Gateway now, which is where the
 * blueprint puts them. The route stays so a bookmark or a link to /llm-provider-credentials still
 * arrives somewhere, rather than hitting a route that no longer exists.
 */
export default function LlmProviderCredentialsRedirect() {
  useEffect(() => {
    window.location.replace(gatewayViewHref("upstreams"));
  }, []);
  return null;
}
