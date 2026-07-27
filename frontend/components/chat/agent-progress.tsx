import { Check, Loader2 } from "lucide-react";
import type { StatusEvent } from "@/lib/types";

export function AgentProgress({ steps, done }: { steps: StatusEvent[]; done: boolean }) {
  if (steps.length === 0) return null;
  return (
    <div className="rounded-xl2 border border-line bg-card/70 p-3 text-sm animate-fade-up" role="status" aria-live="polite">
      <ul className="space-y-1.5">
        {steps.map((s, i) => {
          const isLast = i === steps.length - 1;
          const active = isLast && !done;
          return (
            <li key={i} className="flex items-center gap-2 text-muted">
              {active ? (
                <Loader2 size={14} className="animate-spin text-healf" />
              ) : (
                <Check size={14} className="text-healf" />
              )}
              <span className={active ? "text-ink" : ""}>{s.message}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
