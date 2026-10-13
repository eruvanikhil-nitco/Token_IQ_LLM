"use client";

import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  AREAS,
  BLUEPRINT_ROLES,
  GRANTABLE,
  grantableNow,
  matrixValue,
  roleLabel,
  whyNotGrantable,
  type Area,
} from "@/app/(dashboard)/_access/roles";

const AREA_LABELS: Readonly<Record<Area, string>> = {
  "cost-data": "See cost data",
  "invoice-reconciliation": "Invoice reconciliation and month-end close",
  budgets: "Budgets",
  recommendations: "Recommendations",
  "savings-simulator": "Savings Simulator",
  anomalies: "Anomalies and alert rules",
  reports: "Reports and exports",
  "data-sources": "Data sources and connections",
  organization: "Organization (teams, cost centres)",
  pricing: "Cost allocation and pricing",
  "users-and-roles": "Users, roles and sign-on",
  settings: "Integrations and settings",
  "projects-and-keys": "Projects and virtual keys",
  "team-home": "Team Home",
  "audit-log": "Audit log",
};

const NOT_HELD = "—";

/**
 * Administration > Access Control > Roles & Permissions.
 *
 * What the eight roles mean and, for each, whether this installation can actually create a person
 * who holds it. Four of them cannot be created yet, and a screen that offered them would be
 * offering an account nobody can sign in as, which is the kind of promise a customer discovers
 * after inviting somebody.
 *
 * Nothing here grants anything. Roles are assigned on the Users tab, through the roles that exist.
 */
export default function RolesPanel() {
  const waiting = BLUEPRINT_ROLES.filter((role) => !grantableNow(role));

  return (
    <div className="flex flex-col gap-6">
      <p className="max-w-3xl text-sm text-muted-foreground">
        A role decides which pages and actions a person has. What data they see is their scope, which is their
        organisation, one team, or only themselves. The two are separate: an Org Viewer sees the whole organisation
        read-only, and a Team Lead manages one team
      </p>

      <div className="flex flex-col gap-3">
        <h3 className="text-base font-medium">The eight roles</h3>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Role</TableHead>
              <TableHead>Can be assigned</TableHead>
              <TableHead>Notes</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {BLUEPRINT_ROLES.map((role) => (
              <TableRow key={role}>
                <TableCell className="font-medium">{roleLabel(role)}</TableCell>
                <TableCell>
                  {grantableNow(role) ? (
                    <Badge variant="secondary">Yes</Badge>
                  ) : (
                    <Badge variant="outline">Not yet</Badge>
                  )}
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {whyNotGrantable(role) ?? `Assigned as ${GRANTABLE[role]} on the Users tab`}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        {waiting.length > 0 ? (
          <p className="max-w-3xl text-sm text-muted-foreground">
            {waiting.map(roleLabel).join(", ")} cannot be assigned in this installation yet. They are listed because the
            permissions below describe them, not because somebody can be invited as one today
          </p>
        ) : null}
      </div>

      <div className="flex flex-col gap-3">
        <h3 className="text-base font-medium">What each role may do</h3>
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Permission</TableHead>
                {BLUEPRINT_ROLES.map((role) => (
                  <TableHead key={role} className="whitespace-nowrap">
                    {roleLabel(role)}
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {AREAS.map((area) => (
                <TableRow key={area}>
                  <TableCell className="whitespace-nowrap font-medium">{AREA_LABELS[area]}</TableCell>
                  {BLUEPRINT_ROLES.map((role) => {
                    const value = matrixValue(role, area);
                    return (
                      <TableCell
                        key={role}
                        className={value === NOT_HELD ? "text-muted-foreground" : "whitespace-nowrap text-sm"}
                      >
                        {value}
                      </TableCell>
                    );
                  })}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </div>
    </div>
  );
}
