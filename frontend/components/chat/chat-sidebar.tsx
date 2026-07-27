"use client";
import { Plus, MessageSquare, Trash2, X, PanelLeftClose } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Logo } from "@/components/ui/logo";
import { timeAgo } from "@/lib/utils";
import type { HistoryEntry } from "@/lib/local-history";

interface ChatSidebarProps {
  history: HistoryEntry[];
  activeSession: string | null;
  onNewChat: () => void;
  onSelect: (e: HistoryEntry) => void;
  onDelete: (id: string) => void;
  open: boolean;
  onClose: () => void;
  collapsed: boolean;
  onCollapse: () => void;
}

export function ChatSidebar({
  history,
  activeSession,
  onNewChat,
  onSelect,
  onDelete,
  open,
  onClose,
  collapsed,
  onCollapse,
}: ChatSidebarProps) {
  return (
    <>
      {/* Mobile scrim */}
      <div
        className={`fixed inset-0 z-30 bg-ink/25 backdrop-blur-sm transition-opacity duration-300 md:hidden ${
          open ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
        onClick={onClose}
        aria-hidden
      />
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-72 flex-col border-r border-line bg-cream/95 transition-transform duration-300 ease-out md:static md:z-auto md:translate-x-0 md:bg-cream md:transition-[width,opacity] ${
          open ? "translate-x-0" : "-translate-x-full"
        } ${collapsed ? "md:w-0 md:overflow-hidden md:border-r-0 md:opacity-0" : "md:w-72 md:opacity-100"}`}
      >
        <div className="flex w-72 flex-1 flex-col">
          <div className="flex items-center justify-between p-4">
            <Logo />
            <button
              onClick={onCollapse}
              className="hidden h-8 w-8 place-items-center rounded-lg text-muted transition-colors hover:bg-line/60 hover:text-ink md:grid"
              aria-label="Collapse sidebar"
              title="Collapse sidebar"
            >
              <PanelLeftClose size={17} />
            </button>
            <button
              onClick={onClose}
              className="grid h-8 w-8 place-items-center rounded-lg text-muted hover:bg-line/60 md:hidden"
              aria-label="Close menu"
            >
              <X size={18} />
            </button>
          </div>

          <div className="px-3">
            <Button variant="outline" className="w-full justify-start shadow-sm" onClick={onNewChat}>
              <Plus size={16} /> New chat
            </Button>
          </div>

          <div className="scrollbar-thin mt-5 flex-1 overflow-y-auto px-2.5">
            <div className="px-2 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted/80">
              Recent
            </div>
            {history.length === 0 && (
              <p className="px-2 py-3 text-sm leading-relaxed text-muted/80">
                Your conversations will show up here.
              </p>
            )}
            <ul className="space-y-0.5">
              {history.map((e) => {
                const active = activeSession === e.sessionId;
                return (
                  <li key={e.sessionId}>
                    <div
                      className={`group relative flex cursor-pointer items-center gap-2.5 rounded-xl2 px-2 py-2 text-sm transition-colors ${
                        active ? "bg-healf-soft" : "hover:bg-line/40"
                      }`}
                      onClick={() => onSelect(e)}
                    >
                      {active && (
                        <span className="absolute left-0 top-1/2 h-5 w-1 -translate-y-1/2 rounded-r-full bg-healf" />
                      )}
                      {e.productThumb ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          src={e.productThumb}
                          alt=""
                          className="h-9 w-9 shrink-0 rounded-lg border border-line/60 object-cover"
                        />
                      ) : (
                        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-line/70 text-muted">
                          <MessageSquare size={15} />
                        </span>
                      )}
                      <div className="min-w-0 flex-1">
                        <div className="truncate font-medium text-ink">{e.productTitle ?? "New conversation"}</div>
                        <div className="flex items-center gap-1 truncate text-xs text-muted">
                          <span className="truncate">{e.lastMessage}</span>
                        </div>
                      </div>
                      <div className="flex shrink-0 items-center gap-1">
                        <span className="text-[10px] text-muted/60 group-hover:hidden">{timeAgo(e.updatedAt)}</span>
                        <button
                          onClick={(ev) => {
                            ev.stopPropagation();
                            onDelete(e.sessionId);
                          }}
                          className="hidden rounded-md p-1 text-muted transition-colors hover:bg-white hover:text-red-500 group-hover:block"
                          aria-label="Delete conversation"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </div>
                  </li>
                );
              })}
            </ul>
          </div>

          <div className="border-t border-line/70 p-3.5 text-[11px] leading-relaxed text-muted/70">
            Grounded in live Healf data. Sessions are in-memory for this MVP.
          </div>
        </div>
      </aside>
    </>
  );
}
