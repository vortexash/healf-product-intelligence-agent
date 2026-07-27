import { cn } from "@/lib/utils";

/**
 * Healf-style wordmark: lowercase "healf" in the signature green→blue→bronze
 * gradient, with a "Product Intelligence" descriptor. Adapted from healf.com's
 * brand language (gradient + Avenir), not a copy of their logo asset.
 */
export function Logo({ className, subtitle = true }: { className?: string; subtitle?: boolean }) {
  return (
    <div className={cn("flex items-center gap-2", className)}>
      <span className="grid h-8 w-8 place-items-center rounded-xl2 brandmark text-white shadow-soft">
        <LeafMark className="h-4 w-4" />
      </span>
      <div className="leading-none">
        <span className="text-lg font-bold tracking-tight2 text-healf-gradient">healf</span>
        {subtitle && <div className="mt-0.5 text-[10px] font-medium uppercase tracking-wide text-muted">Product Intelligence</div>}
      </div>
    </div>
  );
}

export function LeafMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className} aria-hidden>
      <path
        d="M12 3c-4.5 0-8 3.2-8 7.5 0 3.4 2.2 6.3 5.4 7.3-.2-2.6.6-5.1 2.4-7 1.2-1.3 2.9-2.3 4.7-2.9-2 .3-3.9 1.3-5.3 2.8-.9 1-1.5 2.2-1.8 3.5C10.9 13.4 13 9 20 8.3 19.4 5.2 16 3 12 3Z"
        fill="currentColor"
      />
    </svg>
  );
}
