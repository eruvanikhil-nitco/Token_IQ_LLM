import React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Card } from "@/components/ui/card";
import { toast } from "@/lib/toast";
import { teamCourierCoverageCall, teamUpdateCall } from "@/components/networking";
import CourierModeSettings, { TeamCourierCoverage } from "./CourierModeSettings";

export interface TeamCourierModeCardProps {
  accessToken: string | null;
  teamId: string;
  canEditTeam: boolean;
  /** Called after a successful save so the surrounding view reflects the new setting. */
  onSaved?: () => void;
}

const TeamCourierModeCard: React.FC<TeamCourierModeCardProps> = ({ accessToken, teamId, canEditTeam, onSaved }) => {
  const queryClient = useQueryClient();
  const queryKey = ["team", teamId, "courier-coverage"];

  const { data: coverage, error } = useQuery<TeamCourierCoverage>({
    queryKey,
    queryFn: () => teamCourierCoverageCall(accessToken!, teamId),
    enabled: Boolean(accessToken),
  });

  const { mutate: setCourierMode, isPending } = useMutation({
    mutationFn: (enabled: boolean) => teamUpdateCall(accessToken!, { team_id: teamId, courier_mode: enabled }),
    onSuccess: async (_result, enabled) => {
      toast.success(enabled ? "Courier mode enabled" : "Courier mode disabled");
      onSaved?.();
    },
    onError: (error: unknown) => toast.fromError(error),
    // Re-read either way, so the switch shows what is stored rather than what was attempted.
    onSettled: () => queryClient.invalidateQueries({ queryKey }),
  });

  if (error) {
    return (
      <Card className="mt-4 block p-6">
        <h3 className="text-base font-semibold">Courier mode</h3>
        <p className="mt-1 text-sm text-destructive">
          Could not read this team&apos;s courier mode settings, so the switch is not shown. Reload to try again.
        </p>
      </Card>
    );
  }

  if (coverage === undefined) {
    return (
      <Card className="mt-4 block p-6">
        <p className="text-sm text-muted-foreground">Loading courier mode settings...</p>
      </Card>
    );
  }

  return (
    <div className="mt-4">
      <CourierModeSettings
        courierMode={coverage.courier_mode}
        onCourierModeChange={setCourierMode}
        coverage={coverage.providers}
        unboundKeyCount={coverage.unbound_key_count}
        disabled={!canEditTeam || isPending}
      />
    </div>
  );
};

export default TeamCourierModeCard;
