"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { Menu, Sparkles } from "lucide-react";
import { Logo, LeafMark } from "@/components/ui/logo";
import { ChatSidebar } from "./chat-sidebar";
import { ChatComposer } from "./chat-composer";
import { Message } from "./message";
import { EvidenceDrawer } from "@/components/intelligence/evidence-drawer";
import { streamChat, getHealth } from "@/lib/api";
import { loadHistory, upsertHistory, removeHistory, type HistoryEntry } from "@/lib/local-history";
import type { ProductData, SourceEvidence } from "@/lib/types";
import type { ThreadMessage } from "./model";

const INTRO_PROMPTS = [
  "Does this product have reviews?",
  "Does it contain Vitamin D?",
  "What can I improve?",
  "Summarize the product",
  "Rewrite the description",
];

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
  const [drawer, setDrawer] = useState<{ open: boolean; evidence: SourceEvidence[]; at?: string | null }>({
    open: false,
    evidence: [],
  });
  const [llmConfigured, setLlmConfigured] = useState<boolean | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => setHistory(loadHistory()), []);
  useEffect(() => {
    getHealth()
      .then((h) => setLlmConfigured(h.llm_configured))
      .catch(() => setLlmConfigured(null));
  }, []);
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

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
    setInput("");
    setSidebarOpen(false);
  };

  const send = useCallback(
    (rawText?: string) => {
      const text = (rawText ?? input).trim();
      if (!text || busy) return;
      setInput("");
      setBusy(true);

      const userMsg: ThreadMessage = { id: uid(), role: "user", text };
      const assistantMsg: ThreadMessage = {
        id: uid(),
        role: "assistant",
        text: "",
        streaming: true,
        status: [],
      };
      setMessages((prev) => [...prev, userMsg, assistantMsg]);

      let sawProduct: ProductData | null = null;
      const firstProductInSession = !activeProduct;
      const statusLog: typeof assistantMsg.status = [];
      let streamedText = "";

      streamChat(
        { session_id: sessionId ?? undefined, message: text },
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
    [input, busy, sessionId, activeProduct, patchLast],
  );

  const empty = messages.length === 0;

  return (
    <div className="flex h-[100dvh] overflow-hidden">
      <ChatSidebar
        history={history}
        activeSession={sessionId}
        onNewChat={newChat}
        onSelect={(e) => {
          // Sessions are in-memory server-side; selecting a past chat starts fresh
          // with its product context re-established on the next message.
          setSidebarOpen(false);
        }}
        onDelete={(id) => setHistory(removeHistory(id))}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-2 border-b border-line bg-cream/80 px-3 py-2 backdrop-blur md:hidden">
          <button onClick={() => setSidebarOpen(true)} className="rounded-full p-2 hover:bg-line" aria-label="Open menu">
            <Menu size={18} />
          </button>
          <Logo subtitle={false} />
        </header>

        {llmConfigured === false && (
          <div className="bg-amber-50 px-4 py-1.5 text-center text-xs text-amber-700">
            No LLM key configured. Factual answers work; evaluation &amp; rewrites use a rule-based fallback.
          </div>
        )}

        <main className="scrollbar-thin flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-3xl px-3 py-6 sm:px-4">
            {empty ? (
              <IntroCard onPick={(p) => setInput(p)} />
            ) : (
              <div className="space-y-5">
                {messages.map((m) => (
                  <Message
                    key={m.id}
                    m={m}
                    onOpenEvidence={(msg) =>
                      setDrawer({ open: true, evidence: msg.evidence ?? [], at: msg.product?.retrieved_at })
                    }
                    onFollowUp={(p) => send(p)}
                  />
                ))}
                <div ref={bottomRef} />
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
          suggestions={empty ? [] : []}
        />
      </div>

      <EvidenceDrawer
        open={drawer.open}
        evidence={drawer.evidence}
        retrievedAt={drawer.at}
        onClose={() => setDrawer((d) => ({ ...d, open: false }))}
      />
    </div>
  );
}

function IntroCard({ onPick }: { onPick: (p: string) => void }) {
  return (
    <div className="mx-auto mt-10 max-w-2xl text-center animate-fade-up">
      <div className="mx-auto mb-5 grid h-16 w-16 place-items-center rounded-xl3 brandmark text-white shadow-lift animate-gradient-pan" style={{ backgroundSize: "200% 200%" }}>
        <LeafMark className="h-8 w-8" />
      </div>
      <h1 className="text-[2rem] font-bold leading-tight tracking-tight3">
        The <span className="text-healf-gradient">healf</span> product intelligence agent
      </h1>
      <p className="mx-auto mt-3 max-w-lg text-[15px] leading-relaxed text-muted">
        Paste a public Healf product URL and ask anything: reviews, ingredients, pricing, page quality, or
        rewrites. Every answer is grounded in live product-page data, with a source for each fact.
      </p>

      <div className="mt-7 overflow-hidden rounded-xl2 border border-line bg-card text-left shadow-soft">
        <div className="flex items-center gap-2 border-b border-line bg-healf-soft/60 px-4 py-2 text-sm font-medium text-healf">
          <Sparkles size={15} /> Try an example
        </div>
        <code className="block break-all p-4 text-xs leading-relaxed text-muted">
          <span className="text-healf">https://healf.com/en-uk/products/lmnt-recharge-electrolytes-variety-pack</span>
          {"\n"}Does this contain Vitamin D?
        </code>
      </div>

      <div className="mt-5 flex flex-wrap justify-center gap-2">
        {INTRO_PROMPTS.map((p) => (
          <button
            key={p}
            onClick={() => onPick(p)}
            className="rounded-full border border-line bg-card px-3 py-1.5 text-sm text-ink transition-colors hover:border-healf-ring hover:bg-healf-soft"
          >
            {p}
          </button>
        ))}
      </div>
    </div>
  );
}
