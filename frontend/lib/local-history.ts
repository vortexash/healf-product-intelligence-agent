// Lightweight recent-conversation history in localStorage (PRD 22.2).

export interface HistoryEntry {
  sessionId: string;
  productTitle: string | null;
  productThumb: string | null;
  lastMessage: string;
  updatedAt: number;
}

const KEY = "healf.chats.v1";
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
  localStorage.setItem(KEY, JSON.stringify(trimmed));
  return trimmed;
}

export function removeHistory(sessionId: string): HistoryEntry[] {
  const list = loadHistory().filter((e) => e.sessionId !== sessionId);
  localStorage.setItem(KEY, JSON.stringify(list));
  return list;
}
