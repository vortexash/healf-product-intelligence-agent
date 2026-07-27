"use client";
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Copy, Check, FileText, ShieldCheck, ShieldOff } from "lucide-react";
import { Card, Badge } from "@/components/ui/primitives";
import { Button } from "@/components/ui/button";
import type { ContentDraft } from "@/lib/types";

export function ContentDraftCard({ draft }: { draft: ContentDraft }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    await navigator.clipboard.writeText(draft.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  return (
    <Card className="p-4 animate-fade-up">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm font-semibold">
          <FileText size={16} className="text-healf" /> {draft.title}
        </div>
        <Button size="sm" variant="outline" onClick={copy}>
          {copied ? <Check size={14} /> : <Copy size={14} />} {copied ? "Copied" : "Copy"}
        </Button>
      </div>
      <div className="prose-chat mt-3 rounded-lg bg-cream/70 p-3 text-sm">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{draft.content}</ReactMarkdown>
      </div>
      {(draft.claims_preserved.length > 0 || draft.claims_not_introduced.length > 0) && (
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          {draft.claims_preserved.length > 0 && (
            <div>
              <div className="mb-1 flex items-center gap-1 text-xs font-semibold text-healf">
                <ShieldCheck size={13} /> Claims preserved
              </div>
              <ul className="space-y-1 text-xs text-muted">
                {draft.claims_preserved.map((c, i) => (
                  <li key={i}>• {c}</li>
                ))}
              </ul>
            </div>
          )}
          {draft.claims_not_introduced.length > 0 && (
            <div>
              <div className="mb-1 flex items-center gap-1 text-xs font-semibold text-amber-700">
                <ShieldOff size={13} /> Claims not introduced
              </div>
              <ul className="space-y-1 text-xs text-muted">
                {draft.claims_not_introduced.map((c, i) => (
                  <li key={i}>• {c}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
      {draft.facts_used.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1">
          {draft.facts_used.slice(0, 8).map((f, i) => (
            <Badge key={i} tone="neutral">
              {f}
            </Badge>
          ))}
        </div>
      )}
    </Card>
  );
}
