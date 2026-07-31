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

export interface ConversationTurn {
  role: "user" | "assistant";
  text: string;
}

/** Product context attached to every request. This keeps a follow-up anchored
 * to the product visible in the browser if the backend session has expired. */
export function productContextUrl(
  activeProduct: ProductData | null,
  pendingProductUrl: string | null,
): string | undefined {
  return pendingProductUrl ?? activeProduct?.source_url ?? undefined;
}

/** Recover the product from the newest assistant response. Older saved threads
 * may contain a stale thread-level product even though the latest card is
 * correct. */
export function latestThreadProduct(messages: ThreadMessage[]): ProductData | null {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index];
    if (message.role === "assistant" && message.product) return message.product;
  }
  return null;
}

/** Compact, completed turns sent with each request so browser-saved threads
 * keep their meaning after the backend's in-memory session expires. */
export function conversationHistory(messages: ThreadMessage[], limit = 10): ConversationTurn[] {
  return messages
    .filter((message) => !message.streaming && !message.error && message.text.trim())
    .slice(-limit)
    .map(({ role, text }) => ({ role, text: text.trim().slice(0, 4000) }));
}

/** Suggestions already displayed in a saved thread, sent back so a restarted
 * backend does not offer the same chip again. */
export function shownSuggestions(messages: ThreadMessage[], limit = 24): string[] {
  const unique = new Set<string>();
  for (const message of messages) {
    if (message.role !== "assistant" || message.streaming || message.error) continue;
    for (const suggestion of message.suggested ?? []) {
      const value = suggestion.trim();
      if (value) unique.add(value.slice(0, 300));
    }
  }
  return [...unique].slice(-limit);
}
