"use client";

import OrganizationTabs from "../_components/OrganizationTabs";
import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";

export default function OrganizationProjectsPage() {
  useAuthorized();
  return <OrganizationTabs />;
}
