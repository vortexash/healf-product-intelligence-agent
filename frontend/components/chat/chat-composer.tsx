"use client";
import { useRef, useEffect } from "react";
import { ArrowUp, Link2 } from "lucide-react";
import { Textarea } from "@/components/ui/primitives";
import { Button } from "@/components/ui/button";
import { ProductContextChip } from "@/components/product/product-context-chip";
import type { ProductData } from "@/lib/types";

interface ChatComposerProps {
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
  busy: boolean;
  activeProduct: ProductData | null;
  onClearProduct: () => void;
}

export function ChatComposer({ value, onChange, onSend, busy, activeProduct, onClearProduct }: ChatComposerProps) {
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "0px";
    el.style.height = Math.min(el.scrollHeight, 200) + "px";
  }, [value]);

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!busy && value.trim()) onSend();
    }
  };

  return (
    <div className="border-t border-line/70 bg-gradient-to-t from-cream via-cream to-cream/60 backdrop-blur">
      <div className="mx-auto w-full max-w-3xl px-3 pb-3 pt-2.5 sm:px-6 sm:pb-4">
        <div className="rounded-xl3 border border-line bg-card p-2.5 shadow-lift transition-colors focus-within:border-healf-ring focus-within:ring-4 focus-within:ring-healf-ring/15">
          <div className="mb-1.5 flex items-center justify-between px-1.5">
            {activeProduct ? (
              <ProductContextChip product={activeProduct} onClear={onClearProduct} />
            ) : (
              <span className="inline-flex items-center gap-1.5 text-xs text-muted">
                <Link2 size={12} /> Paste a Healf product URL to begin
              </span>
            )}
          </div>
          <div className="flex items-end gap-2">
            <Textarea
              ref={ref}
              value={value}
              onChange={(e) => onChange(e.target.value)}
              onKeyDown={handleKey}
              rows={1}
              aria-label="Message"
              placeholder={
                activeProduct
                  ? "Ask a follow-up, e.g. What can I improve?"
                  : "https://healf.com/en-uk/products/...  then your question"
              }
              className="max-h-52 min-h-[26px] px-2 py-1.5 text-[15px] leading-relaxed"
            />
            <Button
              size="icon"
              variant="gradient"
              onClick={onSend}
              disabled={busy || !value.trim()}
              aria-label="Send"
              className="h-10 w-10 shrink-0"
            >
              <ArrowUp size={18} />
            </Button>
          </div>
        </div>
        <p className="mt-2 text-center text-[11px] text-muted/70">
          Grounded in live Healf data · Enter to send, Shift+Enter for a new line
        </p>
      </div>
    </div>
  );
}
