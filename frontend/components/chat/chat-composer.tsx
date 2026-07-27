"use client";
import { useRef, useEffect } from "react";
import { ArrowUp, Link2 } from "lucide-react";
import { Textarea } from "@/components/ui/primitives";
import { Button } from "@/components/ui/button";
import { ProductContextChip } from "@/components/product/product-context-chip";
import { PromptChips } from "./prompt-chips";
import type { ProductData } from "@/lib/types";

export function ChatComposer({
  value,
  onChange,
  onSend,
  busy,
  activeProduct,
  onClearProduct,
  suggestions,
}: {
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
  busy: boolean;
  activeProduct: ProductData | null;
  onClearProduct: () => void;
  suggestions: string[];
}) {
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
    <div className="border-t border-line bg-cream/80 backdrop-blur">
      <div className="mx-auto w-full max-w-3xl p-3 sm:p-4">
        {!activeProduct && suggestions.length > 0 && (
          <div className="mb-2">
            <PromptChips prompts={suggestions} onPick={(p) => onChange(p)} />
          </div>
        )}
        <div className="rounded-xl2 border border-line bg-card p-2 shadow-soft focus-within:border-healf-ring">
          <div className="mb-1 flex items-center justify-between px-1">
            {activeProduct ? (
              <ProductContextChip product={activeProduct} onClear={onClearProduct} />
            ) : (
              <span className="inline-flex items-center gap-1 text-xs text-muted">
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
                  ? "Ask a follow-up… (e.g. What can I improve?)"
                  : "https://healf.com/en-uk/products/…  then your question"
              }
              className="max-h-52 min-h-[24px] px-2 py-1.5 text-sm"
            />
            <Button size="icon" variant="gradient" onClick={onSend} disabled={busy || !value.trim()} aria-label="Send">
              <ArrowUp size={18} />
            </Button>
          </div>
        </div>
        <p className="mt-1.5 text-center text-[11px] text-muted/70">
          Grounded in live Healf data · Enter to send, Shift+Enter for a new line
        </p>
      </div>
    </div>
  );
}
