/**
 * The views inside Data Sources > Gateway, and which page each one used to be.
 *
 * Views rather than tabs, selected by `?view=`, which is the blueprint's own mechanism for this
 * tab: it names `/data-sources/gateway?view=upstreams` directly. The reason is its navigation
 * rule, that a page has sub-tabs and a sub-tab never has its own tabs. The Gateway tab is already
 * a sub-tab, so a second tab strip inside it would be three deep.
 *
 * `movedFrom` is the legacy page id each view was reachable as. None of those addresses stops
 * resolving: the view is where the sidebar now leads, and the old id still routes.
 */

import { migratedHref } from "@/utils/migratedPages";

export const GATEWAY_VIEWS = ["request-log", "virtual-keys", "upstreams"] as const;

export type GatewayView = (typeof GATEWAY_VIEWS)[number];

/** The blueprint lists traffic first, and the request log is what observed traffic looks like. */
export const GATEWAY_BASE_VIEW: GatewayView = "request-log";

export interface GatewayViewSpec {
  label: string;
  description: string;
  /** The legacy `?page=` id this view was a page of, or null if it never was one. */
  movedFrom: string | null;
}

export const GATEWAY_VIEW_SPECS: Readonly<Record<GatewayView, GatewayViewSpec>> = {
  "request-log": {
    label: "Request log",
    description:
      "Every request the gateway observed, as it observed it. The gateway never changes a request, so this is traffic rather than a second source of cost.",
    movedFrom: "logs",
  },
  "virtual-keys": {
    label: "Virtual keys",
    description:
      "The keys callers use to reach the gateway. A key is how a request gets attributed to a team or project, which is what makes gateway figures answer who rather than how much.",
    movedFrom: "api-keys",
  },
  upstreams: {
    label: "Upstreams",
    description:
      "The credentials the gateway forwards with. Different job and different risk from the read-only billing credentials on Accounts, which is why they are not in the same list.",
    movedFrom: "llm-provider-credentials",
  },
};

/**
 * Which view a `?view=` value asks for.
 *
 * An unknown value falls back to the first view rather than rendering nothing, because a stale
 * bookmark or a typo would otherwise land on a blank tab with no way to tell it from an outage.
 */
export function gatewayViewFor(param: string | null): GatewayView {
  const found = GATEWAY_VIEWS.find((view) => view === param);
  return found ?? GATEWAY_BASE_VIEW;
}

/** The address of one view, for a link from elsewhere in the product. */
export function gatewayViewHref(view: GatewayView): string {
  return `${migratedHref("data-sources/gateway")}/?view=${view}`;
}

/** The legacy page ids this tab now answers for, which is what has to keep resolving. */
export function gatewayMovedPages(): readonly string[] {
  return GATEWAY_VIEWS.map((view) => GATEWAY_VIEW_SPECS[view].movedFrom).filter(
    (page): page is string => page !== null,
  );
}
