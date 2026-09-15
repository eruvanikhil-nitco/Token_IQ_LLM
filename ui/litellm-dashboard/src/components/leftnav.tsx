import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
import useIsOrgAdmin from "@/app/(dashboard)/hooks/useIsOrgAdmin";
import { useTeams } from "@/app/(dashboard)/hooks/teams/useTeams";
import { useHealthReadinessDetails } from "@/app/(dashboard)/hooks/healthReadiness/useHealthReadinessDetails";
import { useLogout } from "@/app/(dashboard)/hooks/useLogout";
import { getProxyBaseUrl } from "@/components/networking";
import { useTheme } from "@/contexts/ThemeContext";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Sidebar,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuItem,
  SidebarSeparator,
  sidebarMenuButtonVariants,
} from "@/components/shared/Sidebar";
import {
  Activity,
  BarChart3,
  Bell,
  Blocks,
  Boxes,
  Code2,
  ExternalLink,
  FileText,
  Folder,
  HeartPulse,
  KeyRound,
  LayoutGrid,
  Network,
  Palette,
  PanelLeftClose,
  PanelLeftOpen,
  PiggyBank,
  PlayCircle,
  Route,
  ScrollText,
  Server,
  Settings as SettingsIcon,
  Shield,
  Tags,
  Terminal,
  User,
  Users,
  Wallet,
} from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { cn } from "@/lib/cva.config";
import { rolesWithCapability } from "../utils/capabilities";
import {
  all_admin_roles,
  internalUserRoles,
  isAdminRole,
  isUserTeamAdminForAnyTeam,
  rolesAllowedToViewWriteScopedPages,
  rolesWithWriteAccess,
} from "../utils/roles";
import BetaBadge from "./BetaBadge";
import BrandLogo, { BRAND_NAME } from "./BrandLogo";
import SidebarAccountMenu from "./SidebarAccountMenu/SidebarAccountMenu";
import SidebarUsageCard from "./SidebarUsageCard";
import { MIGRATED_PAGES, migratedHref, legacyPageHref } from "@/utils/migratedPages";

const ICON = { strokeWidth: 1.75 } as const;

const LOGO_CLASS_NAME = "h-7 w-auto max-w-[150px] object-contain group-data-[collapsed=true]/sidebar:w-7";

interface SidebarProps {
  setPage: (page: string) => void;
  defaultSelectedKey: string;
  collapsed?: boolean;
  onToggleCollapsed?: () => void;
  enabledPagesInternalUsers?: string[] | null;
  enableProjectsUI?: boolean;
  disableAgentsForInternalUsers?: boolean;
  allowAgentsForTeamAdmins?: boolean;
  disableVectorStoresForInternalUsers?: boolean;
  allowVectorStoresForTeamAdmins?: boolean;
}

interface MenuItem {
  key: string;
  page: string;
  label: string | React.ReactNode;
  roles?: string[];
  icon?: React.ReactNode;
  external_url?: string;
}

interface MenuGroup {
  groupLabel: string;
  items: MenuItem[];
  roles?: string[];
}

// Menu groups organized by category - defined outside component for export.
// Shape (key/page/label/roles/children) is consumed by page_utils.ts; only the
// icons changed to lucide as part of the sidebar redesign.
const menuGroups: MenuGroup[] = [
  {
    groupLabel: "ANALYTICS",
    items: [
      {
        key: "new_usage",
        page: "new_usage",
        icon: <BarChart3 {...ICON} />,
        roles: [...all_admin_roles, ...internalUserRoles],
        label: "Usage",
      },
      {
        key: "4",
        page: "usage",
        label: "Classic Usage",
        icon: <BarChart3 {...ICON} />,
        roles: rolesWithCapability("viewGlobalSpend"),
      },
      {
        key: "cost-optimization",
        page: "cost-optimization",
        icon: <PiggyBank {...ICON} />,
        roles: [...all_admin_roles, ...internalUserRoles],
        label: (
          <span className="flex items-center gap-2">
            Cost Optimization <BetaBadge />
          </span>
        ),
      },
      { key: "logs", page: "logs", label: "Logs", icon: <Activity {...ICON} /> },
    ],
  },
  {
    groupLabel: "ORGANISATION",
    items: [
      { key: "teams", page: "teams", label: "Teams", icon: <Users {...ICON} /> },
      {
        key: "projects",
        page: "projects",
        label: "Projects",
        icon: <Folder {...ICON} />,
        roles: [...all_admin_roles, ...internalUserRoles],
      },
      { key: "users", page: "users", label: "Users", icon: <User {...ICON} />, roles: all_admin_roles },
      {
        key: "access-groups",
        page: "access-groups",
        label: "Access Groups",
        icon: <Boxes {...ICON} />,
        roles: all_admin_roles,
      },
      { key: "budgets", page: "budgets", label: "Budgets", icon: <Wallet {...ICON} />, roles: all_admin_roles },
    ],
  },
  {
    groupLabel: "GATEWAY",
    items: [
      { key: "api-keys", page: "api-keys", label: "Virtual Keys", icon: <KeyRound {...ICON} /> },
      { key: "providers", page: "providers", label: "Providers", icon: <Boxes {...ICON} />, roles: all_admin_roles },
      {
        key: "models",
        page: "models",
        label: "Models + Endpoints",
        icon: <Network {...ICON} />,
        roles: rolesAllowedToViewWriteScopedPages,
      },
      {
        key: "llm-playground",
        page: "llm-playground",
        label: "Playground",
        icon: <PlayCircle {...ICON} />,
        roles: rolesWithWriteAccess,
      },
      {
        key: "transform-request",
        page: "transform-request",
        label: "API Playground",
        icon: <Terminal {...ICON} />,
        roles: [...all_admin_roles, ...internalUserRoles],
      },
    ],
  },
  {
    groupLabel: "SAFETY",
    items: [
      { key: "guardrails", page: "guardrails", label: "Guardrails", icon: <Shield {...ICON} /> },
      {
        key: "guardrails-monitor",
        page: "guardrails-monitor",
        label: "Guardrails Monitor",
        icon: <HeartPulse {...ICON} />,
        roles: rolesWithCapability("viewGuardrailUsage"),
      },
      {
        key: "policies",
        page: "policies",
        label: "Policies",
        icon: <ScrollText {...ICON} />,
        roles: rolesWithCapability("viewPolicies"),
      },
    ],
  },
  {
    groupLabel: "BUILD",
    items: [
      { key: "mcp-servers", page: "mcp-servers", label: "MCP Servers", icon: <Server {...ICON} /> },
      { key: "skills", page: "skills", label: "Skills", icon: <Blocks {...ICON} />, roles: all_admin_roles },
      {
        key: "prompts",
        page: "prompts",
        label: "Prompts",
        icon: <FileText {...ICON} />,
        roles: rolesWithCapability("viewPrompts"),
      },
      {
        key: "tag-management",
        page: "tag-management",
        label: "Tag Management",
        icon: <Tags {...ICON} />,
        roles: all_admin_roles,
      },
      { key: "model-hub-table", page: "model-hub-table", label: "AI Hub", icon: <LayoutGrid {...ICON} /> },
      { key: "api_ref", page: "api_ref", label: "API Reference", icon: <Code2 {...ICON} /> },
    ],
  },
  {
    groupLabel: "SETTINGS",
    roles: all_admin_roles,
    items: [
      {
        key: "admin-panel",
        page: "admin-panel",
        label: "Admin Settings",
        icon: <SettingsIcon {...ICON} />,
        roles: all_admin_roles,
      },
      {
        key: "router-settings",
        page: "router-settings",
        label: "Router Settings",
        icon: <Route {...ICON} />,
        roles: all_admin_roles,
      },
      {
        key: "logging-and-alerts",
        page: "logging-and-alerts",
        label: "Logging & Alerts",
        icon: <Bell {...ICON} />,
        roles: all_admin_roles,
      },
      {
        key: "cost-tracking",
        page: "cost-tracking",
        label: "Cost Tracking",
        icon: <BarChart3 {...ICON} />,
        roles: all_admin_roles,
      },
      { key: "ui-theme", page: "ui-theme", label: "UI Theme", icon: <Palette {...ICON} />, roles: all_admin_roles },
    ],
  },
];

const findMenuItemKey = (page: string): string => {
  for (const group of menuGroups) {
    for (const item of group.items) {
      if (item.page === page) return item.key;
    }
  }
  return "api-keys";
};

const SECTION_DISPLAY: Record<string, string> = {
  ANALYTICS: "Analytics",
  ORGANISATION: "Organisation",
  GATEWAY: "Gateway",
  SAFETY: "Safety",
  BUILD: "Build",
  SETTINGS: "Settings",
};

const prettify = (key: string): string =>
  key
    .split(/[-_]/)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");

const labelText = (item: MenuItem): string => (typeof item.label === "string" ? item.label : prettify(item.key));

// Breadcrumb ("Section" / "Page") for the top bar, derived from the same nav config.
export const getBreadcrumb = (page: string): { section: string | null; title: string } => {
  for (const group of menuGroups) {
    for (const item of group.items) {
      const section = SECTION_DISPLAY[group.groupLabel] ?? group.groupLabel;
      if (item.page === page)
        return { section, title: typeof item.label === "string" ? item.label : prettify(item.key) };
    }
  }
  return { section: null, title: prettify(page) };
};

const Sidebar_: React.FC<SidebarProps> = ({
  setPage,
  defaultSelectedKey,
  collapsed = false,
  onToggleCollapsed,
  enabledPagesInternalUsers,
  enableProjectsUI,
  disableAgentsForInternalUsers,
  allowAgentsForTeamAdmins,
  disableVectorStoresForInternalUsers,
  allowVectorStoresForTeamAdmins,
}) => {
  const { userId, accessToken, userRole, isViewOnly } = useAuthorized();
  const isOrgAdmin = useIsOrgAdmin();
  const { data: teams } = useTeams();
  const { logoUrl, logoUrlDark } = useTheme();
  const [erroredDarkLogo, setErroredDarkLogo] = useState<string | null>(null);
  const { data: healthData } = useHealthReadinessDetails(accessToken);
  const logout = useLogout(accessToken);

  const baseUrl = getProxyBaseUrl();
  const version = healthData?.litellm_version;
  const selectedKey = findMenuItemKey(defaultSelectedKey);

  const filterItemsByRole = (items: MenuItem[]): MenuItem[] => {
    const isAdmin = isAdminRole(userRole);
    return items.filter((item) => {
      if (item.key === "llm-playground" && isViewOnly) return false;
      if (item.key === "organizations" || item.key === "users") {
        const hasRoleAccess = !item.roles || item.roles.includes(userRole) || isOrgAdmin;
        if (!hasRoleAccess) return false;
        if (!isAdmin && enabledPagesInternalUsers != null) return enabledPagesInternalUsers.includes(item.page);
        return true;
      }
      if (item.key === "projects") {
        if (!enableProjectsUI) return false;
        if (!isAdmin && !isUserTeamAdminForAnyTeam(teams ?? null, userId ?? "")) return false;
      }
      if (item.roles && !item.roles.includes(userRole)) return false;
      if (!isAdmin && enabledPagesInternalUsers != null) {
        return enabledPagesInternalUsers.includes(item.page);
      }
      return true;
    });
  };

  const visibleGroups = menuGroups
    .filter((group) => !group.roles || group.roles.includes(userRole))
    .map((group) => ({ groupLabel: group.groupLabel, items: filterItemsByRole(group.items) }))
    .filter((group) => group.items.length > 0);

  const handleLeafClick = (e: React.MouseEvent, item: MenuItem) => {
    if (item.external_url) return;
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.button === 1) return;
    e.preventDefault();
    setPage(item.page);
  };

  const renderLeaf = (item: MenuItem, isChild: boolean) => {
    const active = selectedKey === item.key;
    const size = isChild ? "sub" : "default";
    const label = <span className="flex-1 truncate group-data-[collapsed=true]/sidebar:hidden">{item.label}</span>;

    if (item.external_url) {
      return (
        <a
          key={item.key}
          href={item.external_url}
          target="_blank"
          rel="noopener noreferrer"
          title={collapsed ? labelText(item) : undefined}
          data-active={active || undefined}
          className={cn(sidebarMenuButtonVariants({ isActive: active, size }))}
        >
          {item.icon}
          {label}
          <ExternalLink className="size-3.5 shrink-0 opacity-70 group-data-[collapsed=true]/sidebar:hidden" />
        </a>
      );
    }

    const href = MIGRATED_PAGES[item.page] ? migratedHref(MIGRATED_PAGES[item.page]) : legacyPageHref(item.page);
    return (
      <a
        key={item.key}
        href={href}
        onClick={(e) => handleLeafClick(e, item)}
        title={collapsed ? labelText(item) : undefined}
        data-active={active || undefined}
        className={cn(sidebarMenuButtonVariants({ isActive: active, size }))}
      >
        {item.icon}
        {label}
      </a>
    );
  };

  const renderItem = (item: MenuItem) => <SidebarMenuItem key={item.key}>{renderLeaf(item, false)}</SidebarMenuItem>;

  const logoSrc = logoUrl || `${baseUrl}/get_image`;
  const reachableDarkLogo = logoUrlDark === erroredDarkLogo ? null : logoUrlDark;
  const darkLogoSrc = reachableDarkLogo || logoUrl || `${baseUrl}/get_image?theme=dark`;

  return (
    <Sidebar collapsed={collapsed}>
      <SidebarHeader className="h-14 border-b border-border group-data-[collapsed=true]/sidebar:h-auto">
        <div className="flex items-center justify-between gap-2 group-data-[collapsed=true]/sidebar:flex-col">
          <div className="flex min-w-0 items-center gap-2">
            <Link href={migratedHref("")} className="flex min-w-0 items-center" aria-label={`${BRAND_NAME} home`}>
              {logoUrl ? (
                <>
                  <img src={logoSrc} alt={BRAND_NAME} className={cn(LOGO_CLASS_NAME, "dark:hidden")} />
                  <img
                    src={darkLogoSrc}
                    alt=""
                    aria-hidden
                    onError={() => setErroredDarkLogo(logoUrlDark)}
                    className={cn(LOGO_CLASS_NAME, "hidden dark:block")}
                  />
                </>
              ) : (
                <BrandLogo collapsed={collapsed} />
              )}
            </Link>
            {version && (
              <Badge
                variant="outline"
                render={<a href="https://docs.litellm.ai/release_notes" target="_blank" rel="noopener noreferrer" />}
                className="px-1.5 py-0 font-mono text-[10px] font-medium text-muted-foreground group-data-[collapsed=true]/sidebar:hidden"
              >
                v{version}
              </Badge>
            )}
          </div>
          {onToggleCollapsed && (
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={onToggleCollapsed}
              aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
              className="flex-none text-muted-foreground"
            >
              {collapsed ? <PanelLeftOpen /> : <PanelLeftClose />}
            </Button>
          )}
        </div>
      </SidebarHeader>

      <ScrollArea className="min-h-0 flex-1">
        <nav className="flex flex-col gap-0.5 px-3 pb-3">
          {visibleGroups.map((group, gi) => (
            <SidebarGroup key={group.groupLabel}>
              {gi > 0 && <SidebarSeparator className="hidden group-data-[collapsed=true]/sidebar:block" />}
              <SidebarGroupLabel>{group.groupLabel}</SidebarGroupLabel>
              <SidebarMenu>{group.items.map((item) => renderItem(item))}</SidebarMenu>
            </SidebarGroup>
          ))}
        </nav>
      </ScrollArea>

      <SidebarFooter>
        {isAdminRole(userRole) && (
          <SidebarUsageCard
            accessToken={accessToken}
            collapsed={collapsed}
            onExpandRail={() => onToggleCollapsed?.()}
          />
        )}
        <SidebarAccountMenu onLogout={logout} collapsed={collapsed} />
      </SidebarFooter>
    </Sidebar>
  );
};

export default Sidebar_;

export { menuGroups };
