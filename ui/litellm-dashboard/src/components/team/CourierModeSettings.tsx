import React from "react";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import { AlertTriangle, CheckCircle2, Info, XCircle } from "lucide-react";

export interface ProviderCoverage {
  provider: string;
  has_route: boolean;
  reads_usage: boolean;
  is_covered: boolean;
  summary: string;
  deployments_ready: string[];
  deployments_needing_opt_in: string[];
}

export interface CourierModeSettingsProps {
  courierMode: boolean;
  onCourierModeChange: (enabled: boolean) => void;
  coverage: ProviderCoverage[];
  /** How many of this team's keys do not name the account they spend against. */
  unboundKeyCount: number;
  disabled?: boolean;
}

const CoverageRow: React.FC<{ entry: ProviderCoverage }> = ({ entry }) => {
  const blocked = !entry.has_route;
  const billingGap = entry.has_route && !entry.reads_usage;

  return (
    <div className="flex flex-col gap-1 py-2">
      <div className="flex items-center gap-2">
        {blocked ? (
          <XCircle className="size-4 shrink-0 text-destructive" />
        ) : billingGap ? (
          <AlertTriangle className="size-4 shrink-0 text-warning" />
        ) : (
          <CheckCircle2 className="size-4 shrink-0 text-success" />
        )}
        <span className="font-medium">{entry.provider}</span>
        {billingGap && <Badge variant="destructive">Records no cost</Badge>}
        {blocked && <Badge variant="secondary">Unavailable</Badge>}
      </div>
      <p className="pl-6 text-sm text-muted-foreground">{entry.summary}</p>
    </div>
  );
};

const CourierModeSettings: React.FC<CourierModeSettingsProps> = ({
  courierMode,
  onCourierModeChange,
  coverage,
  unboundKeyCount,
  disabled = false,
}) => {
  return (
    <Card className="p-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-base font-semibold">Courier mode</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            This team&apos;s requests reach the provider exactly as written, and the provider&apos;s reply is returned
            unchanged. Nothing is repackaged.
          </p>
        </div>
        <Switch
          checked={courierMode}
          onCheckedChange={onCourierModeChange}
          disabled={disabled}
          aria-label="Courier mode"
        />
      </div>

      <div className="mt-3 flex items-start gap-2 rounded-md bg-muted p-3">
        <Info className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
        <p className="text-sm text-muted-foreground">
          This is not a silent change. Courier mode uses different addresses that expect the provider&apos;s own request
          format, so applications written against the standard address will be refused until they are updated.
        </p>
      </div>

      {courierMode && (
        <>
          <Separator className="my-4" />
          <h4 className="text-sm font-semibold">What each provider will do</h4>
          <div className="mt-1 divide-y">
            {coverage.map((entry) => (
              <CoverageRow key={entry.provider} entry={entry} />
            ))}
          </div>

          {unboundKeyCount > 0 && (
            <div className="mt-4 flex items-start gap-2 rounded-md border border-warning p-3">
              <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warning" />
              <div className="text-sm">
                <p className="font-medium">
                  {unboundKeyCount} key{unboundKeyCount === 1 ? "" : "s"} on this team name no account
                </p>
                <p className="mt-1 text-muted-foreground">
                  A key that names the account it spends against is charged to exactly that one, and its spend records
                  say so. A key that names none is charged to whichever account this gateway finds first for the
                  provider, which for a customer holding more than one account at a provider may not be the intended
                  one.
                </p>
              </div>
            </div>
          )}
        </>
      )}
    </Card>
  );
};

export default CourierModeSettings;
