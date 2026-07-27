import { Card, Badge } from "@/components/ui/primitives";
import type { ProductEvaluation } from "@/lib/types";
import { cn } from "@/lib/utils";

const STATUS_TONE = {
  strong: "green",
  good: "green",
  moderate: "amber",
  weak: "red",
  unknown: "neutral",
} as const;

function ring(score: number) {
  if (score >= 85) return "#3B5D4F";
  if (score >= 70) return "#5E8B79";
  if (score >= 50) return "#C08A3E";
  return "#C05B4D";
}

export function Scorecard({ evaluation }: { evaluation: ProductEvaluation }) {
  const e = evaluation;
  return (
    <Card className="p-4 animate-fade-up">
      <div className="flex items-center justify-between">
        <div className="text-sm font-semibold">Page evaluation</div>
        <Badge tone="neutral">Heuristic{e.provisional ? " · provisional" : ""}</Badge>
      </div>

      <div className="mt-3 flex items-center gap-4">
        <div
          className="grid h-16 w-16 shrink-0 place-items-center rounded-full text-lg font-semibold text-white"
          style={{ background: ring(e.overall_score) }}
          aria-label={`Overall score ${e.overall_score} out of 100`}
        >
          {e.overall_score}
        </div>
        <p className="text-sm text-muted">{e.summary}</p>
      </div>

      <div className="mt-4 space-y-2">
        {e.categories.map((c) => (
          <div key={c.key} className="flex items-center gap-3">
            <div className="w-40 shrink-0 text-sm text-ink">{c.label}</div>
            <div className="h-2 flex-1 overflow-hidden rounded-full bg-cream">
              <div className="h-full rounded-full" style={{ width: `${c.score}%`, background: ring(c.score) }} />
            </div>
            <div className="w-8 text-right text-xs tabular-nums text-muted">{c.score}</div>
            <Badge tone={STATUS_TONE[c.status]} className={cn("w-16 justify-center")}>
              {c.status}
            </Badge>
          </div>
        ))}
      </div>
    </Card>
  );
}
