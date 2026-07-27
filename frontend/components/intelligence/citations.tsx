import { ExternalLink } from "lucide-react";
import type { SourceEvidence } from "@/lib/types";
import { SOURCE_LABEL } from "@/lib/utils";

// Inline "Sources" row derived from the answer's extraction evidence.
// Each citation groups the fields that came from one source type, links to the
// live page it was read from, and is numbered so answers can be traced. This is
// deterministic (from tracked evidence), never LLM-invented.
export function Citations({
  evidence,
  onOpenAll,
}: {
  evidence: SourceEvidence[];
  onOpenAll?: () => void;
}) {
  if (!evidence || evidence.length === 0) return null;

  const groups = new Map<string, { fields: Set<string>; url: string }>();
  for (const e of evidence) {
    const g = groups.get(e.source_type) ?? { fields: new Set<string>(), url: e.source_url };
    e.field.split(",").forEach((f) => g.fields.add(f.trim()));
    groups.set(e.source_type, g);
  }
  const items = [...groups.entries()];

  return (
    <div className="mt-3 border-t border-line pt-2">
      <div className="flex flex-wrap items-center gap-1.5 text-xs text-muted">
        <span className="font-medium text-ink">Sources:</span>
        {items.map(([type, g], i) => {
          const fields = [...g.fields];
          const label = SOURCE_LABEL[type] ?? type;
          return (
            <a
              key={type}
              href={g.url}
              target="_blank"
              rel="noopener noreferrer"
              title={`${label} · fields: ${fields.join(", ")}`}
              className="inline-flex items-center gap-1 rounded-full border border-line bg-cream px-2 py-0.5 transition-colors hover:border-healf-ring hover:bg-healf-soft"
            >
              <span className="font-semibold text-healf">[{i + 1}]</span>
              <span>{label}</span>
              <span className="text-muted/70">· {fields.slice(0, 3).join(", ")}{fields.length > 3 ? "…" : ""}</span>
              <ExternalLink size={11} className="text-muted/70" />
            </a>
          );
        })}
        {onOpenAll && (
          <button onClick={onOpenAll} className="rounded-full px-2 py-0.5 text-healf underline underline-offset-2 hover:bg-healf-soft">
            details
          </button>
        )}
      </div>
    </div>
  );
}
