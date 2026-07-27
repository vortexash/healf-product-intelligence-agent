import { Star, MessageSquare } from "lucide-react";
import { Card, Badge } from "@/components/ui/primitives";
import type { ReviewSummary } from "@/lib/types";

export function ReviewSummaryCard({ reviews }: { reviews: ReviewSummary }) {
  if (reviews.present == null && reviews.count == null) return null;
  return (
    <Card className="p-4 animate-fade-up">
      <div className="flex items-center gap-2 text-sm font-semibold">
        <MessageSquare size={16} className="text-healf" /> Review summary
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-4">
        <div>
          <div className="text-2xl font-semibold text-ink">{reviews.average_rating ?? "-"}</div>
          <div className="flex text-amber-400">
            {[1, 2, 3, 4, 5].map((n) => (
              <Star key={n} size={14} className={n <= Math.round(reviews.average_rating ?? 0) ? "fill-amber-400" : "text-line"} />
            ))}
          </div>
        </div>
        <div className="text-sm text-muted">
          <div>
            <span className="font-semibold text-ink">{reviews.count?.toLocaleString() ?? "Unknown"}</span> reviews
          </div>
          <Badge tone="neutral" className="mt-1">
            {reviews.full_review_text_ingested ? "Full text ingested" : "Aggregate only"}
          </Badge>
        </div>
      </div>
    </Card>
  );
}
