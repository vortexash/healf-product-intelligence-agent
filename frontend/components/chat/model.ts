import type { ChatAnswer, ContentDraft, ProductData, ProductEvaluation, SourceEvidence, StatusEvent } from "@/lib/types";

export interface ThreadMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  // assistant-only fields
  streaming?: boolean;
  status?: StatusEvent[];
  answer?: ChatAnswer;
  product?: ProductData | null;
  evaluation?: ProductEvaluation | null;
  contentDraft?: ContentDraft | null;
  evidence?: SourceEvidence[];
  suggested?: string[];
  error?: { code: string; message: string };
  showProductCard?: boolean;
}
