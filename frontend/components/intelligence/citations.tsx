import { ExternalLink } from "lucide-react";
import type { SourceEvidence } from "@/lib/types";

// A single, plain-English "Source" line under each answer: it says the answer came
// from the live Healf product page and links to it. No field names or internal
// source jargon are shown to the user.
export function Citations({ evidence }: { evidence: SourceEvidence[] }) {
  if (!evidence || evidence.length === 0) return null;

  // Everything is read from the same live product page, so link to it once.
  const url = evidence[0].source_url;

  return (
    <div className="mt-3">
      <a
        href={url}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-1.5 text-xs text-muted transition-colors hover:text-healf"
      >
        <span className="font-medium">Source:</span>
        <span>the live Healf product page</span>
        <ExternalLink size={11} />
      </a>
    </div>
  );
}
