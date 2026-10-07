import { cn } from "@/lib/cva.config";

export const BRAND_NAME = "Token IQ";

interface BrandLogoProps {
  collapsed?: boolean;
  className?: string;
}

const BrandLogo: React.FC<BrandLogoProps> = ({ collapsed = false, className }) => (
  <span className={cn("flex min-w-0 items-center gap-2 text-foreground", className)}>
    <svg
      viewBox="0 0 32 32"
      className="size-7 flex-none"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <rect x="3" y="3" width="26" height="26" rx="8" className="opacity-40" />
      <circle cx="16" cy="16" r="4.5" />
      <path d="M16 3.5v4" />
      <path d="M16 24.5v4" />
      <path d="M3.5 16h4" />
      <path d="M24.5 16h4" />
    </svg>
    {!collapsed && (
      <span className="truncate text-[15px] font-bold tracking-tight group-data-[collapsed=true]/sidebar:hidden">
        {BRAND_NAME}
      </span>
    )}
  </span>
);

export default BrandLogo;
