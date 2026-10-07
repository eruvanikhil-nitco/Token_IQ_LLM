"use client";
import { useDeletedTeams } from "@/app/(dashboard)/hooks/teams/useTeams";
import { DeletedTeamsTable } from "./DeletedTeamsTable/DeletedTeamsTable";

export default function DeletedTeamsPage() {
  const { data: teamsData, isLoading } = useDeletedTeams(1, 100);

  return (
    <div className="flex flex-col gap-4">
      <DeletedTeamsTable teams={teamsData || []} isLoading={isLoading} />
    </div>
  );
}
