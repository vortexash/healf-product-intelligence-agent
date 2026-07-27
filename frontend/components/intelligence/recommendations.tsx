import { Lightbulb } from "lucide-react";
import { Card } from "@/components/ui/primitives";
import type { Recommendation } from "@/lib/types";

export function Recommendations({ items }: { items: Recommendation[] }) {
  if (!items.length) return null;
  return (
    <Card className="p-4 animate-fade-up">
      <div className="flex items-center gap-2 text-sm font-semibold">
        <Lightbulb size={16} className="text-healf" /> Recommendations
      </div>
      <ol className="mt-3 space-y-3">
        {items.map((r) => (
          <li key={r.priority} className="flex gap-3">
            <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-healf-soft text-xs font-semibold text-healf">
              {r.priority}
            </span>
            <div>
              <div className="text-sm font-medium text-ink">{r.title}</div>
              {r.rationale && <div className="text-sm text-muted">{r.rationale}</div>}
              <div className="mt-1 text-sm text-healf">→ {r.suggested_action}</div>
              {r.evidence_fields.length > 0 && (
                <div className="mt-1 text-xs text-muted/70">Evidence: {r.evidence_fields.join(", ")}</div>
              )}
            </div>
          </li>
        ))}
      </ol>
    </Card>
  );
}
