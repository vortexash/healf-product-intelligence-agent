"use client";
import { X, FileSearch } from "lucide-react";
import { Badge } from "@/components/ui/primitives";
import type { SourceEvidence } from "@/lib/types";
import { SOURCE_LABEL, fieldLabel } from "@/lib/utils";

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
        className={`fixed inset-0 z-40 bg-black/40 transition-opacity ${open ? "opacity-100" : "pointer-events-none opacity-0"}`}
        onClick={onClose}
        aria-hidden
      />
      <aside
        role="dialog"
        aria-label="Sources"
        aria-modal="true"
        className={`fixed right-0 top-0 z-50 flex h-full w-full max-w-md flex-col border-l border-line bg-card shadow-soft transition-transform ${
          open ? "translate-x-0" : "translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between border-b border-line p-4">
          <div className="flex items-center gap-2 font-semibold">
            <FileSearch size={18} className="text-healf" /> Sources
          </div>
          <button onClick={onClose} aria-label="Close sources" className="rounded-full p-1 hover:bg-cream">
            <X size={18} />
          </button>
        </div>
        <div className="scrollbar-thin flex-1 overflow-y-auto p-4">
          <p className="mb-3 text-xs text-muted">
            Every fact below is taken from the live Healf product page
            {retrievedAt && `, read ${new Date(retrievedAt).toLocaleString()}`}.
          </p>
          {evidence.length === 0 && <p className="text-sm text-muted">No sources for this answer.</p>}
          <ul className="space-y-3">
            {evidence.map((e, i) => (
              <li key={i} className="rounded-lg border border-line p-3">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-semibold text-ink">{fieldLabel(e.field)}</span>
                  <Badge tone="green">{SOURCE_LABEL[e.source_type] ?? "Product page"}</Badge>
                </div>
                {e.excerpt && <p className="mt-1 text-sm text-muted">“{e.excerpt}”</p>}
                <div className="mt-2 text-xs text-muted/80">Confidence {Math.round(e.confidence * 100)}%</div>
              </li>
            ))}
          </ul>
        </div>
      </aside>
    </>
  );
}
