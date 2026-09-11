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
  /** The team's permitted models, which are named differently on a courier route. */
  teamModels: string[];
  disabled?: boolean;
}

const providerOf = (model: string): string => (model.includes("/") ? model.split("/")[0] : "");

/**
 * Models a courier request will not match.
 *
 * A team's permitted models are the gateway's deployment names. A courier request
 * carries the provider's own model name, because the body is the provider's own, so
 * these entries stop matching the moment the team is switched and every call is refused
 * naming a model the admin believes they granted.
 */
export const modelsThatStopMatching = (teamModels: string[], coverage: ProviderCoverage[]): string[] => {
  const courierProviders = new Set(coverage.filter((c) => c.has_route).map((c) => c.provider));
  return teamModels.filter((model) => courierProviders.has(providerOf(model)));
};

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
      {entry.deployments_needing_opt_in.length > 0 && (
        <p className="pl-6 text-sm text-muted-foreground">
          {entry.deployments_needing_opt_in.length} model
          {entry.deployments_needing_opt_in.length === 1 ? "" : "s"} will fail on credentials until pass-through is
          enabled on {entry.deployments_needing_opt_in.length === 1 ? "it" : "them"}:{" "}
          {entry.deployments_needing_opt_in.join(", ")}
        </p>
      )}
    </div>
  );
};

const CourierModeSettings: React.FC<CourierModeSettingsProps> = ({
  courierMode,
  onCourierModeChange,
  coverage,
  teamModels,
  disabled = false,
}) => {
  const losingModels = modelsThatStopMatching(teamModels, coverage);

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

          {losingModels.length > 0 && (
            <div className="mt-4 flex items-start gap-2 rounded-md border border-warning p-3">
              <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warning" />
              <div className="text-sm">
                <p className="font-medium">These permitted models will stop matching</p>
                <p className="mt-1 text-muted-foreground">
                  Courier requests name the provider&apos;s model, not this gateway&apos;s. Until this team&apos;s
                  permitted models are updated, its calls will be refused as not allowed even though the models appear
                  granted: {losingModels.join(", ")}
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
