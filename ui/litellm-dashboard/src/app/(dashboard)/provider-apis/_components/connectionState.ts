export type ConnectionState = "not_connected" | "waiting_for_first_data" | "healthy" | "needs_attention";

export const STATE_LABELS: Record<ConnectionState, string> = {
  not_connected: "Not connected",
  waiting_for_first_data: "Waiting for first data",
  healthy: "Healthy",
  needs_attention: "Needs attention",
};

export const stateBadgeVariant = (state: ConnectionState): "default" | "secondary" | "destructive" | "outline" => {
  switch (state) {
    case "needs_attention":
      return "destructive";
    case "healthy":
      return "default";
    case "waiting_for_first_data":
      return "secondary";
    default:
      return "outline";
  }
};
