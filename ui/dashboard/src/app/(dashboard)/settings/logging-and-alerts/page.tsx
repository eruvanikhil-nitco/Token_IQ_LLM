"use client";

import SettingsTabs from "../_components/SettingsTabs";
import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";

export default function SettingsLoggingAndAlertsPage() {
  useAuthorized();
  return <SettingsTabs />;
}
