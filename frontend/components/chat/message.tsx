"use client";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { AlertTriangle, FileSearch } from "lucide-react";
import { LeafMark } from "@/components/ui/logo";
import { Badge } from "@/components/ui/primitives";
import { Button } from "@/components/ui/button";
import { AgentProgress } from "./agent-progress";
import { PromptChips } from "./prompt-chips";
import { ProductCard } from "@/components/product/product-card";
import { ReviewSummaryCard } from "@/components/product/review-summary-card";
import { Scorecard } from "@/components/intelligence/scorecard";
import { Recommendations } from "@/components/intelligence/recommendations";
import { ContentDraftCard } from "@/components/intelligence/content-draft";
import { Citations } from "@/components/intelligence/citations";
import type { ThreadMessage } from "./model";

const CONF_TONE = { high: "green", medium: "amber", low: "red" } as const;

export function Message({
  m,
  onOpenEvidence,
  onFollowUp,
}: {
  m: ThreadMessage;
  onOpenEvidence: (m: ThreadMessage) => void;
  onFollowUp: (prompt: string) => void;
}) {
  if (m.role === "user") {
    return (
      <div className="flex justify-end animate-fade-up">
        <div className="max-w-[85%] whitespace-pre-wrap break-words rounded-xl3 rounded-br-md bg-healf px-4 py-2.5 text-[15px] leading-relaxed text-white shadow-soft">
          {m.text}
        </div>
      </div>
    );
  }

  const intent = m.answer?.intent;
  return (
    <div className="flex flex-col gap-3 animate-fade-up">
      <div className="flex items-start gap-3">
        <div className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-full brandmark text-white shadow-soft">
          <LeafMark className="h-4 w-4" />
        </div>
        <div className="min-w-0 flex-1 space-y-3">
          {m.status && m.status.length > 0 && (!m.text || m.streaming) && <AgentProgress steps={m.status} done={!m.streaming} />}

          {m.error && (
            <div className="flex items-start gap-2 rounded-xl3 border border-red-200 bg-red-50 p-3.5 text-sm text-red-700 dark:border-red-900/40 dark:bg-red-950/40 dark:text-red-300">
              <AlertTriangle size={16} className="mt-0.5 shrink-0" />
              <span>{m.error.message}</span>
            </div>
          )}

          {m.showProductCard && m.product && <ProductCard product={m.product} />}

          {m.text && (
            <div className="rounded-xl3 rounded-tl-md border border-line bg-card px-4 py-3.5 shadow-soft sm:px-5">
              <div className="prose-chat text-[15px] text-ink">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.text}</ReactMarkdown>
                {m.streaming && (
                  <span className="ml-0.5 inline-block h-4 w-[3px] translate-y-0.5 animate-pulse-dot rounded-full bg-healf align-middle" />
                )}
              </div>

              {m.answer && !m.streaming && (
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  {intent && <Badge tone="neutral">{intent.replace(/_/g, " ")}</Badge>}
                  {m.answer.confidence && (
                    <Badge tone={CONF_TONE[m.answer.confidence]}>{m.answer.confidence} confidence</Badge>
                  )}
                  {m.evidence && m.evidence.length > 0 && (
                    <Button size="sm" variant="outline" onClick={() => onOpenEvidence(m)}>
                      <FileSearch size={14} /> Evidence ({m.evidence.length})
                    </Button>
                  )}
                </div>
              )}

              {m.answer?.limitations && m.answer.limitations.length > 0 && !m.streaming && (
                <ul className="mt-2 space-y-0.5 text-xs text-muted">
                  {m.answer.limitations.map((l, i) => (
                    <li key={i}>· {l}</li>
                  ))}
                </ul>
              )}

              {m.evidence && m.evidence.length > 0 && !m.streaming && <Citations evidence={m.evidence} />}
            </div>
          )}

          {/* Specialized response blocks */}
          {!m.streaming && intent === "review_lookup" && m.product && <ReviewSummaryCard reviews={m.product.reviews} />}
          {!m.streaming && m.evaluation && (
            <>
              <Scorecard evaluation={m.evaluation} />
              <Recommendations items={m.evaluation.recommendations} />
            </>
          )}
          {!m.streaming && m.contentDraft && <ContentDraftCard draft={m.contentDraft} />}

          {!m.streaming && m.suggested && m.suggested.length > 0 && (
            <PromptChips prompts={m.suggested} onPick={onFollowUp} />
          )}
        </div>
      </div>
    </div>
  );
}
