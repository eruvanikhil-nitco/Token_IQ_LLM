const plural = (count: number, unit: string): string => `${count} ${unit}${count === 1 ? "" : "s"}`;

export const describeCadence = (seconds: number): string => {
  if (seconds >= 3600) {
    const hours = Math.round(seconds / 3600);
    return hours === 1 ? "Every hour" : `Every ${plural(hours, "hour")}`;
  }
  if (seconds >= 60) {
    return `Every ${plural(Math.round(seconds / 60), "minute")}`;
  }
  return `Every ${plural(seconds, "second")}`;
};

export const describeWindow = (hours: number): string =>
  hours >= 24 ? `The last ${plural(Math.round(hours / 24), "day")}` : `The last ${plural(hours, "hour")}`;
