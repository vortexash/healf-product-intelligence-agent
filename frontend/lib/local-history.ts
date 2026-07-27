// Lightweight recent-conversation history in localStorage.
// We store two things: a small index of recent chats (for the sidebar), and the
// full message thread per session so a chat can be reopened.

import type { ThreadMessage } from "@/components/chat/model";
import type { ProductData } from "./types";

export interface HistoryEntry {
  sessionId: string;
  productTitle: string | null;
  productThumb: string | null;
  productUrl: string | null;
  lastMessage: string;
  updatedAt: number;
}

const KEY = "healf.chats.v1";
const THREAD_PREFIX = "healf.thread.";
const MAX = 15;

export function loadHistory(): HistoryEntry[] {
  if (typeof window === "undefined") return [];
  try {
    return JSON.parse(localStorage.getItem(KEY) || "[]");
  } catch {
    return [];
  }
}

export function upsertHistory(entry: HistoryEntry): HistoryEntry[] {
  const list = loadHistory().filter((e) => e.sessionId !== entry.sessionId);
  list.unshift(entry);
  const trimmed = list.slice(0, MAX);
  try {
    localStorage.setItem(KEY, JSON.stringify(trimmed));
  } catch {
    /* quota */
  }
  pruneThreads(trimmed.map((e) => e.sessionId));
  return trimmed;
}

export function removeHistory(sessionId: string): HistoryEntry[] {
  const list = loadHistory().filter((e) => e.sessionId !== sessionId);
  try {
    localStorage.setItem(KEY, JSON.stringify(list));
  } catch {
    /* quota */
  }
  removeThread(sessionId);
  return list;
}

// --- Full thread persistence (so a chat can be reopened) ---

interface StoredThread {
  messages: ThreadMessage[];
  product: ProductData | null;
}

export function saveThread(sessionId: string, messages: ThreadMessage[], product: ProductData | null): void {
  try {
    localStorage.setItem(THREAD_PREFIX + sessionId, JSON.stringify({ messages, product } satisfies StoredThread));
  } catch {
    /* quota exceeded — the chat just won't be reopenable, no crash */
  }
}

export function loadThread(sessionId: string): StoredThread | null {
  try {
    const raw = localStorage.getItem(THREAD_PREFIX + sessionId);
    return raw ? (JSON.parse(raw) as StoredThread) : null;
  } catch {
    return null;
  }
}

export function removeThread(sessionId: string): void {
  try {
    localStorage.removeItem(THREAD_PREFIX + sessionId);
  } catch {
    /* ignore */
  }
}

// Drop stored threads that are no longer in the recent index.
function pruneThreads(keep: string[]): void {
  try {
    const keepKeys = new Set(keep.map((s) => THREAD_PREFIX + s));
    for (let i = localStorage.length - 1; i >= 0; i--) {
      const k = localStorage.key(i);
      if (k && k.startsWith(THREAD_PREFIX) && !keepKeys.has(k)) localStorage.removeItem(k);
    }
  } catch {
    /* ignore */
  }
}
