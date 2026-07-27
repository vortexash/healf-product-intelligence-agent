"use client";
import { X, FileSearch } from "lucide-react";
import { Badge } from "@/components/ui/primitives";
import type { SourceEvidence } from "@/lib/types";
import { SOURCE_LABEL } from "@/lib/utils";

export function EvidenceDrawer({
  open,
  evidence,
  retrievedAt,
  onClose,
}: {
  open: boolean;
  evidence: SourceEvidence[];
  retrievedAt?: string | null;
  onClose: () => void;
}) {
  return (
    <>
      <div
        className={`fixed inset-0 z-40 bg-ink/20 transition-opacity ${open ? "opacity-100" : "pointer-events-none opacity-0"}`}
        onClick={onClose}
        aria-hidden
      />
      <aside
        role="dialog"
        aria-label="Evidence"
        aria-modal="true"
        className={`fixed right-0 top-0 z-50 flex h-full w-full max-w-md flex-col border-l border-line bg-card shadow-soft transition-transform ${
          open ? "translate-x-0" : "translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between border-b border-line p-4">
          <div className="flex items-center gap-2 font-semibold">
            <FileSearch size={18} className="text-healf" /> Evidence
          </div>
          <button onClick={onClose} aria-label="Close evidence" className="rounded-full p-1 hover:bg-cream">
            <X size={18} />
          </button>
        </div>
        <div className="scrollbar-thin flex-1 overflow-y-auto p-4">
          {retrievedAt && (
            <p className="mb-3 text-xs text-muted">Retrieved {new Date(retrievedAt).toLocaleString()}</p>
          )}
          {evidence.length === 0 && <p className="text-sm text-muted">No evidence for this answer.</p>}
          <ul className="space-y-3">
            {evidence.map((e, i) => (
              <li key={i} className="rounded-lg border border-line p-3">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs font-semibold text-ink">{e.field}</span>
                  <Badge tone="green">{SOURCE_LABEL[e.source_type] ?? e.source_type}</Badge>
                </div>
                {e.excerpt && <p className="mt-1 text-sm text-muted">“{e.excerpt}”</p>}
                <div className="mt-2 flex items-center justify-between text-xs text-muted/80">
                  <span>Confidence {Math.round(e.confidence * 100)}%</span>
                  {e.selector && <span className="truncate font-mono">{e.selector}</span>}
                </div>
              </li>
            ))}
          </ul>
        </div>
      </aside>
    </>
  );
}
