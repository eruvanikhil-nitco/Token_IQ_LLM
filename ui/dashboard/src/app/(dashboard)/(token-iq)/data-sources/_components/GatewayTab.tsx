"use client";

import { parseAsString, useQueryState } from "nuqs";

import ApiKeysDashboard from "@/app/(dashboard)/api-keys/ApiKeysDashboard";
import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
import CredentialsPanel from "@/components/model_add/CredentialsPanel";
import RequestLogsPanel from "@/components/view_logs/RequestLogsPanel";
import { migratedHref } from "@/utils/migratedPages";

import { GATEWAY_VIEWS, GATEWAY_VIEW_SPECS, gatewayViewFor, type GatewayView } from "./gatewayViews";

/**
 * Data Sources > Gateway: what passes through Token IQ.
 *
 * The blueprint's own four things, as views switched by `?view=` rather than by a second tab strip,
 * because its navigation rule is that a sub-tab never has its own tabs and this tab is already one.
 * The view is in the URL so a link to one of them is a link to what the reader was looking at.
 *
 * Each view renders the component the page it replaced rendered, rather than a copy of it. The
 * request log is the flat panel rather than the whole Logs page, whose other three views are
 * recovery screens rather than gateway traffic and stay where they are.
 *
 * No figure here is added to anything on the other tabs. A gateway figure says who spent, a
 * provider figure says how much, and this is the one page that shows both kinds at once.
 */

interface IdentifiedViewer {
  accessToken: string;
  token: string;
  userRole: string;
  userId: string;
}

/** The four the request log needs. The panel takes them as strings, so it cannot render without. */
function identifiedViewer(viewer: {
  accessToken: string | null;
  token: string | null;
  userRole: string | null;
  userId: string | null;
}): IdentifiedViewer | null {
  const { accessToken, token, userRole, userId } = viewer;
  if (accessToken === null) {
    return null;
  }
  if (token === null) {
    return null;
  }
  if (userRole === null) {
    return null;
  }
  if (userId === null) {
    return null;
  }
  return { accessToken, token, userRole, userId };
}

function RequestLog() {
  const { accessToken, userRole, userId, token } = useAuthorized();
  const identity = { accessToken, token, userRole, userId };
  const viewer = identifiedViewer(identity);

  if (viewer === null) {
    return <p className="text-sm">Loading the request log...</p>;
  }

  return (
    <div className="flex flex-col gap-3">
      <RequestLogsPanel
        accessToken={viewer.accessToken}
        token={viewer.token}
        userRole={viewer.userRole}
        userID={viewer.userId}
        isActive
      />
      {/* The Logs page kept its audit log, deleted keys and deleted teams: those are recovery
          screens rather than traffic, so they are named here instead of being folded in or
          quietly dropped. */}
      <p className="text-sm text-muted-foreground">
        The audit log, deleted keys and deleted teams are still on{" "}
        <a className="text-primary underline-offset-4 hover:underline" href={`${migratedHref("logs")}/`}>
          Logs
        </a>
        , because they record what administrators did rather than what the gateway observed
      </p>
    </div>
  );
}

function Upstreams() {
  return (
    <div className="flex flex-col gap-3">
      <CredentialsPanel />
      <p className="text-sm text-muted-foreground">
        What each upstream serves, and the models and endpoints behind it, are on{" "}
        <a className="text-primary underline-offset-4 hover:underline" href={`${migratedHref("providers")}/`}>
          Providers
        </a>{" "}
        and{" "}
        <a
          className="text-primary underline-offset-4 hover:underline"
          href={`${migratedHref("models-and-endpoints")}/`}
        >
          Models + Endpoints
        </a>
        . Both carry their own tabs, and the blueprint&apos;s rule is that a tab inside a tab stops
        there
      </p>
    </div>
  );
}

function panelFor(view: GatewayView) {
  switch (view) {
    case "request-log":
      return <RequestLog />;
    case "virtual-keys":
      return <ApiKeysDashboard />;
    case "upstreams":
      return <Upstreams />;
  }
}

export default function GatewayTab() {
  const [viewParam, setViewParam] = useQueryState("view", parseAsString);
  const view = gatewayViewFor(viewParam);

  return (
    <div className="flex flex-col gap-4">
      <div role="radiogroup" aria-label="Gateway view" className="flex flex-wrap gap-2">
        {GATEWAY_VIEWS.map((candidate) => (
          <button
            key={candidate}
            type="button"
            role="radio"
            aria-checked={candidate === view}
            onClick={() => {
              void setViewParam(candidate);
            }}
            className={`rounded-md border px-3 py-1 text-sm ${candidate === view ? "bg-accent" : ""}`}
          >
            {GATEWAY_VIEW_SPECS[candidate].label}
          </button>
        ))}
      </div>

      <p className="text-sm text-muted-foreground">{GATEWAY_VIEW_SPECS[view].description}</p>

      {panelFor(view)}
    </div>
  );
}
