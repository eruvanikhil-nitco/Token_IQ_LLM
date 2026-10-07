import type { ProviderRawFact } from "@/components/networking";
import { fieldsNotReported, joinWithAnd } from "./coverage";

const NOT_COLLECTED_NOTE =
  "Service tier, region, and per-user attribution are not collected by this build, for any provider.";

export default function CoverageNote({ rows }: { rows: readonly ProviderRawFact[] }) {
  const missing = fieldsNotReported(rows);

  return (
    <div className="flex flex-col gap-1 text-sm text-muted-foreground">
      {missing.length > 0 && <p>This provider did not report {joinWithAnd(missing)} on the rows shown here.</p>}
      <p>{NOT_COLLECTED_NOTE}</p>
    </div>
  );
}
