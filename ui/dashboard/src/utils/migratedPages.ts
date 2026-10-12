import { serverRootPath } from "@/components/networking";

/**
 * Single source of truth for pages cut over from the legacy `?page=` switch in
 * app/page.tsx to path-based routes under app/(dashboard)/.
 *
 * Key = legacy page id emitted by the sidebar. Value = route segment under (dashboard)/.
 * Add an entry to route the sidebar and deep links to the new path and redirect the
 * legacy `?page=` URL; remove it to roll back.
 */
export const MIGRATED_PAGES: Record<string, string> = {
  "api-keys": "api-keys",
  providers: "providers",
  models: "models-and-endpoints",
  api_ref: "api-reference",
  // Legacy alias: older bookmarks used the hyphenated ?page=api-reference form.
  "api-reference": "api-reference",
  "llm-playground": "playground",
  chat: "chat",
  budgets: "budgets",
  attribution: "attribution",
  ledger: "ledger",
  recommendations: "recommendations",
  overview: "overview",
  workflows: "workflows",
  "guardrails-monitor": "guardrails-monitor",
  "mcp-servers": "mcp-servers",
  "search-tools": "search-tools",
  "tag-management": "tag-management",
  "vector-stores": "vector-stores",
  memory: "memory",
  policies: "policies",
  guardrails: "guardrails",
  prompts: "prompts",
  "tool-policies": "tool-policies",
  skills: "skills",
  // Legacy alias: the old switch matched ?page=claude-code-plugins for the same panel.
  "claude-code-plugins": "skills",
  caching: "caching",
  "cost-tracking": "cost-tracking",
  "transform-request": "transform-request",
  logs: "logs",
  "model-hub-table": "model-hub-table",
  // The modern usage dashboard; the legacy ?page=usage report routes to /old-usage.
  new_usage: "usage",
  usage: "old-usage",
  "cost-optimization": "cost-optimization",
  agents: "agents",
  "router-settings": "router-settings",
  // Administration > Access Control, which merged Users, Access Groups and the audit log. The
  // merged id comes first, for the same reason as Organization above.
  "access-control": "access-control",
  users: "access-control",
  "access-groups": "access-control/access-groups",
  // Administration > Settings, which merged Admin Settings, Logging & Alerts and UI Theme.
  // Data > Data Sources. Both legacy ids point at the Accounts sub-route rather than the page,
  // so they keep landing on the tab they were when the Overview tab arrives and becomes first.
  "data-sources": "data-sources",
  "provider-apis": "data-sources/accounts",
  "user-tools": "data-sources/accounts",
  // Forwarding credentials are the Gateway tab's Upstreams view. The request log and virtual keys
  // moved into the same tab for an admin and keep their own routes, because every non-admin role
  // still reaches them there and cannot open Data Sources at all.
  "llm-provider-credentials": "data-sources/gateway",
  settings: "settings",
  "admin-panel": "settings",
  "logging-and-alerts": "settings/logging-and-alerts",
  "ui-theme": "settings/ui-theme",
  // Administration > Organization, which merged Teams and Projects. The merged id comes first:
  // legacyKeyForPathname returns the first key whose segment matches, and the sidebar uses it to
  // decide which entry is highlighted.
  organization: "organization",
  // Legacy aliases, so a ?page=teams or ?page=projects link still lands on the right tab.
  teams: "organization",
  projects: "organization/projects",
  organizations: "organizations",
};

function uiBase(): string {
  // next dev serves the app at the root; only the proxy mounts the static export under /ui
  // (and optionally under server_root_path). Inlined at build time, so production is unaffected.
  if (process.env.NODE_ENV === "development") {
    return "";
  }
  const root = serverRootPath && serverRootPath !== "/" ? `/${serverRootPath.replace(/^\/+|\/+$/g, "")}` : "";
  return `${root}/ui`;
}

/** Absolute (same-origin) href for a migrated route segment, e.g. "api-reference" -> "/ui/api-reference". */
export function migratedHref(routeSegment: string): string {
  return `${uiBase()}/${routeSegment.replace(/^\/+/, "")}`;
}

/** Href for a not-yet-migrated page, served by the legacy `?page=` switch at the UI root. */
export function legacyPageHref(pageKey: string): string {
  return `${uiBase()}/?page=${pageKey}`;
}

/** Reverse-maps a path-routed location back to its legacy page id, e.g. "/ui/api-reference" -> "api_ref". */
export function legacyKeyForPathname(pathname: string): string | null {
  const base = uiBase();
  const rel = (pathname.startsWith(base) ? pathname.slice(base.length) : pathname).replace(/^\/+|\/+$/g, "");
  for (const [key, segment] of Object.entries(MIGRATED_PAGES)) {
    if (rel === segment) return key;
  }
  return null;
}

/**
 * Href for a page id, or null when this build routes nowhere for it.
 *
 * For links built from data the backend supplies, where the page id is a string in a response
 * rather than something written at the call site. A link to a page that does not exist is worse
 * than no link, so the caller can decide to state the problem without offering a dead end.
 */
export function migratedHrefIfRouted(pageKey: string): string | null {
  const segment = MIGRATED_PAGES[pageKey];
  return segment === undefined ? null : migratedHref(segment);
}
