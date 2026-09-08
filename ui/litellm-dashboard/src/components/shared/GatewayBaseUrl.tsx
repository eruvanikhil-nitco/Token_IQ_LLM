import React from "react";
import CopyButton from "@/components/shared/CopyButton";
import { getProxyBaseUrl } from "@/components/networking";

interface GatewayBaseUrlProps {
  baseUrl?: string;
}

/**
 * The gateway address a client must be pointed at.
 *
 * A virtual key authenticates a caller but carries no routing information, so an
 * application given only the key never reaches this proxy. The address is fixed per
 * deployment and does not depend on the key, so it is shown while a key is being made
 * rather than only once one exists.
 */
const GatewayBaseUrl: React.FC<GatewayBaseUrlProps> = ({ baseUrl = getProxyBaseUrl() }) => {
  if (!baseUrl) return null;

  return (
    <div className="flex items-center gap-2 text-sm text-muted-foreground">
      <span>Base URL:</span>
      <code className="rounded bg-muted px-1.5 py-0.5 text-foreground break-all">{baseUrl}</code>
      <CopyButton value={baseUrl} label="Copy Base URL" />
    </div>
  );
};

export default GatewayBaseUrl;
