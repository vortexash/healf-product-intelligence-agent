import type { ConversationTurn } from "@/components/chat/model";
import type { ChatResponse, ProductData, StreamHandlers } from "./types";

const BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export async function getHealth(): Promise<{ status: string; llm_configured: boolean }> {
  const r = await fetch(`${BASE}/health`);
  return r.json();
}

/**
 * POST /api/chat/stream and dispatch SSE events to handlers.
 * Uses fetch streaming (not EventSource) so we can POST a JSON body.
 */
export async function streamChat(
  body: {
    session_id?: string;
    message: string;
    product_url?: string;
    history?: ConversationTurn[];
    shown_suggestions?: string[];
  },
  handlers: StreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  let res: Response;
  try {
    res = await fetch(`${BASE}/api/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    });
  } catch (e) {
    handlers.onError?.("NETWORK_ERROR", "Could not reach the backend. Is it running on port 8000?");
    return;
  }

  if (!res.ok && !res.body) {
    handlers.onError?.("INTERNAL_ERROR", `Request failed (${res.status}).`);
    return;
  }

  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() ?? "";
    for (const chunk of chunks) dispatch(chunk, handlers);
  }
  if (buffer.trim()) dispatch(buffer, handlers);
}

function dispatch(chunk: string, h: StreamHandlers) {
  let event = "message";
  let data = "";
  for (const line of chunk.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) data += line.slice(5).trim();
  }
  if (!data) return;
  let parsed: any;
  try {
    parsed = JSON.parse(data);
  } catch {
    return;
  }
  switch (event) {
    case "status":
      h.onStatus?.(parsed);
      break;
    case "product":
      h.onProduct?.(parsed.product as ProductData);
      break;
    case "token":
      h.onToken?.(parsed.text);
      break;
    case "complete":
      h.onComplete?.(parsed.response as ChatResponse);
      break;
    case "error":
      h.onError?.(parsed.code, parsed.message);
      break;
  }
}
