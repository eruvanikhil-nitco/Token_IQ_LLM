"use client";

import AccessControlTabs from "../_components/AccessControlTabs";
import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";

export default function AccessControlAccessGroupsPage() {
  useAuthorized();
  return <AccessControlTabs />;
}
