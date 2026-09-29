"use client";

import type { ToolConnection } from "@/app/(dashboard)/hooks/userTools/useToolConnections";

const Row = ({ label, children }: { label: string; children: React.ReactNode }) => (
  <div className="flex flex-col gap-1">
    <p className="text-xs uppercase text-muted-foreground">{label}</p>
    <p className="text-sm">{children}</p>
  </div>
);

export default function ToolWhatWeFetchTab({ connection }: { connection: ToolConnection }) {
  return (
    <div className="flex max-w-3xl flex-col gap-5">
      <Row label="Endpoint">
        {connection.fetches.endpoint}
        <span className="block text-xs text-muted-foreground">{connection.fetches.endpoint_url}</span>
      </Row>
      <Row label="What it gives">{connection.fetches.what_it_gives}</Row>
      <Row label="What it cannot give">{connection.fetches.what_it_cannot_give}</Row>
      <Row label="History">{connection.fetches.backfill_note}</Row>
      <Row label="How far this has been proved">{connection.fetches.verification_note}</Row>
    </div>
  );
}
