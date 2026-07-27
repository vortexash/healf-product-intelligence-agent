"use client";
import { Plus, MessageSquare, Trash2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Logo } from "@/components/ui/logo";
import { timeAgo } from "@/lib/utils";
import type { HistoryEntry } from "@/lib/local-history";

export function ChatSidebar({
  history,
  activeSession,
  onNewChat,
  onSelect,
  onDelete,
  open,
  onClose,
}: {
  history: HistoryEntry[];
  activeSession: string | null;
  onNewChat: () => void;
  onSelect: (e: HistoryEntry) => void;
  onDelete: (id: string) => void;
  open: boolean;
  onClose: () => void;
}) {
  return (
    <>
      <div
        className={`fixed inset-0 z-30 bg-ink/20 md:hidden ${open ? "" : "pointer-events-none opacity-0"}`}
        onClick={onClose}
      />
      <aside
        className={`fixed z-30 flex h-full w-72 shrink-0 flex-col border-r border-line bg-cream transition-transform md:static md:translate-x-0 ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between p-4">
          <Logo />
          <button onClick={onClose} className="rounded-full p-1 hover:bg-line md:hidden" aria-label="Close menu">
            <X size={18} />
          </button>
        </div>

        <div className="px-3">
          <Button variant="outline" className="w-full justify-start" onClick={onNewChat}>
            <Plus size={16} /> New chat
          </Button>
        </div>

        <div className="scrollbar-thin mt-4 flex-1 overflow-y-auto px-2">
          <div className="px-2 pb-1 text-xs font-medium uppercase tracking-wide text-muted">Recent</div>
          {history.length === 0 && <p className="px-2 py-3 text-sm text-muted">No conversations yet.</p>}
          <ul className="space-y-1">
            {history.map((e) => (
              <li key={e.sessionId}>
                <div
                  className={`group flex cursor-pointer items-center gap-2 rounded-lg px-2 py-2 text-sm transition-colors ${
                    activeSession === e.sessionId ? "bg-healf-soft" : "hover:bg-line/50"
                  }`}
                  onClick={() => onSelect(e)}
                >
                  {e.productThumb ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={e.productThumb} alt="" className="h-8 w-8 shrink-0 rounded object-cover" />
                  ) : (
                    <span className="grid h-8 w-8 shrink-0 place-items-center rounded bg-line text-muted">
                      <MessageSquare size={14} />
                    </span>
                  )}
                  <div className="min-w-0 flex-1">
                    <div className="truncate font-medium text-ink">{e.productTitle ?? "New conversation"}</div>
                    <div className="truncate text-xs text-muted">{e.lastMessage}</div>
                  </div>
                  <button
                    onClick={(ev) => {
                      ev.stopPropagation();
                      onDelete(e.sessionId);
                    }}
                    className="opacity-0 transition-opacity group-hover:opacity-100"
                    aria-label="Delete conversation"
                  >
                    <Trash2 size={14} className="text-muted hover:text-red-500" />
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </div>
        <div className="p-3 text-[11px] text-muted/70">MVP · in-memory sessions · live Healf data</div>
      </aside>
    </>
  );
}
