"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { Menu, Plus, PanelLeft, PanelLeftClose, Sparkles } from "lucide-react";
import { Logo, LeafMark } from "@/components/ui/logo";
import { ChatSidebar } from "./chat-sidebar";
import { ChatComposer } from "./chat-composer";
import { Message } from "./message";
import { ProductContextChip } from "@/components/product/product-context-chip";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { streamChat, getHealth } from "@/lib/api";
import {
  loadHistory,
  upsertHistory,
  removeHistory,
  saveThread,
  loadThread,
  type HistoryEntry,
} from "@/lib/local-history";
import type { ProductData } from "@/lib/types";
import type { ThreadMessage } from "./model";

const INTRO_PROMPTS = [
  "Does this product have reviews?",
  "Does it contain Vitamin D?",
  "What can I improve?",
  "Summarize the product",
  "Rewrite the description",
];

const COLLAPSE_KEY = "healf.sidebar.collapsed";

let counter = 0;
const uid = () => `m${Date.now()}_${counter++}`;

export function ChatShell() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ThreadMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [activeProduct, setActiveProduct] = useState<ProductData | null>(null);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  // URL of the reopened chat's product, sent with the next message so context is
  // re-established even if the in-memory server session has expired.
  const [pendingProductUrl, setPendingProductUrl] = useState<string | null>(null);
  const [llmConfigured, setLlmConfigured] = useState<boolean | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setHistory(loadHistory());
    setCollapsed(localStorage.getItem(COLLAPSE_KEY) === "1");
  }, []);
  useEffect(() => {
    getHealth()
      .then((h) => setLlmConfigured(h.llm_configured))
      .catch(() => setLlmConfigured(null));
  }, []);
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  // Persist the full thread once a turn finishes, so it can be reopened later.
  useEffect(() => {
    if (sessionId && messages.length > 0 && !busy) {
      saveThread(sessionId, messages, activeProduct);
    }
  }, [sessionId, messages, busy, activeProduct]);

  const openChat = (e: HistoryEntry) => {
    const t = loadThread(e.sessionId);
    setMessages(t?.messages ?? []);
    setActiveProduct(t?.product ?? null);
    setSessionId(e.sessionId);
    setPendingProductUrl(t?.product?.source_url ?? e.productUrl ?? null);
    setInput("");
    setSidebarOpen(false);
  };

  const toggleCollapse = () =>
    setCollapsed((c) => {
      const next = !c;
      try {
        localStorage.setItem(COLLAPSE_KEY, next ? "1" : "0");
      } catch {
        /* ignore */
      }
      return next;
    });

  const patchLast = useCallback((patch: Partial<ThreadMessage>) => {
    setMessages((prev) => {
      const next = [...prev];
      const i = next.length - 1;
      next[i] = { ...next[i], ...patch };
      return next;
    });
  }, []);

  const newChat = () => {
    setSessionId(null);
    setMessages([]);
    setActiveProduct(null);
    setPendingProductUrl(null);
    setInput("");
    setSidebarOpen(false);
  };

  const send = useCallback(
    (rawText?: string) => {
      const text = (rawText ?? input).trim();
      if (!text || busy) return;
      setInput("");
      setBusy(true);
      const resumeUrl = pendingProductUrl;
      setPendingProductUrl(null);

      const userMsg: ThreadMessage = { id: uid(), role: "user", text };
      const assistantMsg: ThreadMessage = { id: uid(), role: "assistant", text: "", streaming: true, status: [] };
      setMessages((prev) => [...prev, userMsg, assistantMsg]);

      let sawProduct: ProductData | null = null;
      const firstProductInSession = !activeProduct;
      const statusLog: typeof assistantMsg.status = [];
      let streamedText = "";

      streamChat(
        { session_id: sessionId ?? undefined, message: text, product_url: resumeUrl ?? undefined },
        {
          onStatus: (s) => {
            statusLog!.push(s);
            patchLast({ status: [...statusLog!] });
          },
          onProduct: (p) => {
            sawProduct = p;
            setActiveProduct(p);
            patchLast({ product: p, showProductCard: firstProductInSession });
          },
          onToken: (t) => {
            streamedText += t;
            patchLast({ text: streamedText });
          },
          onComplete: (r) => {
            setSessionId(r.session_id);
            patchLast({
              streaming: false,
              text: r.answer.text,
              answer: r.answer,
              product: r.product ?? sawProduct,
              evaluation: r.evaluation,
              contentDraft: r.content_draft,
              evidence: r.evidence,
              suggested: r.suggested_actions,
            });
            const prod = r.product ?? sawProduct;
            const primary = prod?.images.find((i) => i.is_primary) ?? prod?.images[0];
            setHistory(
              upsertHistory({
                sessionId: r.session_id,
                productTitle: prod?.title ?? null,
                productThumb: primary?.url ?? null,
                productUrl: prod?.source_url ?? null,
                lastMessage: r.answer.text.replace(/[*#_`]/g, "").slice(0, 80),
                updatedAt: Date.now(),
              }),
            );
            setBusy(false);
          },
          onError: (code, message) => {
            patchLast({ streaming: false, error: { code, message }, status: [] });
            setBusy(false);
          },
        },
      );
    },
    [input, busy, sessionId, activeProduct, pendingProductUrl, patchLast],
  );

  const empty = messages.length === 0;

  return (
    <div className="flex h-[100dvh] overflow-hidden bg-cream">
      <ChatSidebar
        history={history}
        activeSession={sessionId}
        onNewChat={newChat}
        onSelect={openChat}
        onDelete={(id) => {
          setHistory(removeHistory(id));
          if (id === sessionId) newChat();
        }}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        collapsed={collapsed}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="z-10 flex h-14 shrink-0 items-center gap-1.5 border-b border-line/70 bg-cream/70 px-2.5 backdrop-blur-md sm:px-4">
          <button
            onClick={() => setSidebarOpen(true)}
            className="grid h-9 w-9 place-items-center rounded-lg text-muted transition-colors hover:bg-line/60 hover:text-ink md:hidden"
            aria-label="Open menu"
          >
            <Menu size={18} />
          </button>
          <button
            onClick={toggleCollapse}
            className="hidden h-9 w-9 place-items-center rounded-lg text-muted transition-colors hover:bg-line/60 hover:text-ink md:grid"
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {collapsed ? <PanelLeft size={18} /> : <PanelLeftClose size={18} />}
          </button>

          <div className={collapsed ? "md:block" : "md:hidden"}>
            <Logo subtitle={false} />
          </div>

          {activeProduct && (
            <div className="ml-auto hidden min-w-0 sm:block">
              <ProductContextChip product={activeProduct} />
            </div>
          )}
          <div className={`flex items-center gap-1 ${activeProduct ? "" : "ml-auto"}`}>
            <ThemeToggle />
            <button
              onClick={newChat}
              className="grid h-9 w-9 place-items-center rounded-lg text-muted transition-colors hover:bg-healf-soft hover:text-healf"
              aria-label="New chat"
              title="New chat"
            >
              <Plus size={18} />
            </button>
          </div>
        </header>

        {llmConfigured === false && (
          <div className="border-b border-amber-100 bg-amber-50/80 px-4 py-1.5 text-center text-xs text-amber-700 dark:border-amber-900/40 dark:bg-amber-950/40 dark:text-amber-300">
            No LLM key configured. Factual answers work; evaluation and rewrites use a rule-based fallback.
          </div>
        )}

        <main className="scrollbar-thin relative flex-1 overflow-y-auto scroll-smooth">
          <div className="pointer-events-none sticky top-0 z-[1] h-4 bg-gradient-to-b from-cream to-transparent" />
          <div className="mx-auto w-full max-w-3xl px-4 pb-10 pt-2 sm:px-6">
            {empty ? (
              <IntroCard onPick={(p) => setInput(p)} />
            ) : (
              <div className="space-y-7">
                {messages.map((m) => (
                  <Message key={m.id} m={m} onFollowUp={(p) => send(p)} />
                ))}
                <div ref={bottomRef} className="h-1" />
              </div>
            )}
          </div>
        </main>

        <ChatComposer
          value={input}
          onChange={setInput}
          onSend={() => send()}
          busy={busy}
          activeProduct={activeProduct}
          onClearProduct={newChat}
        />
      </div>
    </div>
  );
}

function IntroCard({ onPick }: { onPick: (p: string) => void }) {
  return (
    <div className="mx-auto mt-10 max-w-2xl text-center animate-fade-up sm:mt-16">
      <div
        className="mx-auto mb-5 grid h-16 w-16 place-items-center rounded-xl3 brandmark text-white shadow-lift animate-gradient-pan"
        style={{ backgroundSize: "200% 200%" }}
      >
        <LeafMark className="h-8 w-8" />
      </div>
      <h1 className="text-[2rem] font-bold leading-[1.1] tracking-tight3 sm:text-[2.4rem]">
        The <span className="text-healf-gradient">healf</span> product intelligence agent
      </h1>
      <p className="mx-auto mt-4 max-w-lg text-[15px] leading-relaxed text-muted">
        Paste a public Healf product URL and ask anything: reviews, ingredients, pricing, page quality, or
        rewrites. Every answer is grounded in live product-page data, with a source for each fact.
      </p>

      <div className="mt-8 overflow-hidden rounded-xl3 border border-line bg-card text-left shadow-soft">
        <div className="flex items-center gap-2 border-b border-line bg-healf-soft/60 px-4 py-2.5 text-sm font-medium text-healf">
          <Sparkles size={15} /> Try an example
        </div>
        <code className="block break-all p-4 text-xs leading-relaxed text-muted">
          <span className="text-healf">https://healf.com/en-uk/products/lmnt-recharge-electrolytes-variety-pack</span>
          {"\n"}Does this contain Vitamin D?
        </code>
      </div>

      <div className="mt-6 flex flex-wrap justify-center gap-2">
        {INTRO_PROMPTS.map((p) => (
          <button
            key={p}
            onClick={() => onPick(p)}
            className="rounded-full border border-line bg-card px-3.5 py-1.5 text-sm text-ink shadow-sm transition-all hover:-translate-y-0.5 hover:border-healf-ring hover:bg-healf-soft"
          >
            {p}
          </button>
        ))}
      </div>
    </div>
  );
}
