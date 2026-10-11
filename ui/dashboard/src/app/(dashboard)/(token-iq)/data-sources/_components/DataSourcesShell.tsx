"use client";

import { Database } from "lucide-react";

import { PageHeader } from "@/components/shared/PageHeader";
import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
import { all_admin_roles } from "@/utils/roles";

import { dataSourcesAccess } from "../dataSourcesTabs";
import ConnectAccountDialog from "./ConnectAccountDialog";
import DataSourcesTabs from "./DataSourcesTabs";

/**
 * The page every Data Sources route renders.
 *
 * Shared rather than copied per route because the one thing that differs between them is which tab
 * opens, which `DataSourcesTabs` works out from the URL. The primary action is the blueprint's
 * only one, and it appears for a role that may change connections: a read-only admin sees the tabs
 * and not the button, which is the same rule `dataSourcesAccess` applies to everything else here.
 */
export default function DataSourcesShell() {
  const { userRole } = useAuthorized();
  const access = dataSourcesAccess({ userRole, adminRoles: all_admin_roles });

  return (
    <main className="flex h-full flex-col gap-6 p-8">
      <PageHeader
        icon={<Database />}
        title="Data Sources"
        subtitle="Every place Token IQ gets usage and cost data from, whether it is arriving, and the records exactly as received."
        primaryAction={access === "manage" ? <ConnectAccountDialog /> : undefined}
      />
      <DataSourcesTabs />
    </main>
  );
}
