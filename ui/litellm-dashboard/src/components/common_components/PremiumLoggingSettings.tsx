import React from "react";
import LoggingSettings from "../team/LoggingSettings";

interface PremiumLoggingSettingsProps {
  value: any[];
  onChange: (settings: any[]) => void;
  premiumUser?: boolean;
  disabledCallbacks?: string[];
  onDisabledCallbacksChange?: (disabledCallbacks: string[]) => void;
}

export function PremiumLoggingSettings({
  value,
  onChange,
  premiumUser = false,
  disabledCallbacks = [],
  onDisabledCallbacksChange,
}: PremiumLoggingSettingsProps) {
  if (!premiumUser) {
    return null;
  }

  return (
    <LoggingSettings
      value={value}
      onChange={onChange}
      disabledCallbacks={disabledCallbacks}
      onDisabledCallbacksChange={onDisabledCallbacksChange}
    />
  );
}

export default PremiumLoggingSettings;
