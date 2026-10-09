"use client";

import OrganizationTabs from "./_components/OrganizationTabs";
import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";

export default function OrganizationPage() {
  useAuthorized();
  return <OrganizationTabs />;
}
