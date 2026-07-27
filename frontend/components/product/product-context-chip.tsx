import { Package, X } from "lucide-react";
import type { ProductData } from "@/lib/types";

export function ProductContextChip({ product, onClear }: { product: ProductData; onClear?: () => void }) {
  const primary = product.images.find((i) => i.is_primary) ?? product.images[0];
  return (
    <div className="inline-flex items-center gap-2 rounded-full border border-healf-ring/50 bg-healf-soft px-2 py-1 text-xs text-healf">
      {primary ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={primary.url} alt="" className="h-5 w-5 rounded-full object-cover" />
      ) : (
        <Package size={14} />
      )}
      <span className="max-w-[180px] truncate font-medium">{product.title ?? product.handle}</span>
      {onClear && (
        <button onClick={onClear} aria-label="Clear active product" className="rounded-full hover:bg-white/60 p-0.5">
          <X size={12} />
        </button>
      )}
    </div>
  );
}
