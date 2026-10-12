import { useQuery } from "@tanstack/react-query";

import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
import { uploadsCall } from "@/components/networking";
import { all_admin_roles } from "@/utils/roles";
import type { UploadsResponse } from "@/components/networking";

export const UPLOADS_KEY = ["ledger-uploads"];

/**
 * Every bill entered, every bill missing, and where a bill may be forwarded instead.
 *
 * One call rather than a list plus a coverage check, because the missing rows and the entered rows
 * have to describe the same window: two calls would let the tab say a bill is missing beside the
 * bill that covers it.
 */
export const useUploads = () => {
  const { accessToken, userRole } = useAuthorized();

  return useQuery<UploadsResponse>({
    queryKey: UPLOADS_KEY,
    queryFn: async () => uploadsCall(accessToken!),
    enabled: Boolean(accessToken) && all_admin_roles.includes(userRole ?? ""),
  });
};
