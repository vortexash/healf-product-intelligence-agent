import { ExternalLink, Star, Images, Check, X } from "lucide-react";
import { Card, Badge } from "@/components/ui/primitives";
import type { ProductData } from "@/lib/types";

export function ProductCard({ product }: { product: ProductData }) {
  const primary = product.images.find((i) => i.is_primary) ?? product.images[0];
  const price = product.one_time_price?.formatted;
  const sub = product.subscription_price?.formatted;
  return (
    <Card className="overflow-hidden animate-fade-up">
      <div className="flex gap-4 p-4">
        {primary && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={primary.url}
            alt={primary.alt_text || product.title || "Product image"}
            className="h-24 w-24 shrink-0 rounded-lg border border-line object-cover bg-cream"
          />
        )}
        <div className="min-w-0 flex-1">
          {product.vendor && <div className="text-xs font-medium uppercase tracking-wide text-healf">{product.vendor}</div>}
          <h3 className="truncate text-base font-semibold text-ink">{product.title}</h3>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-sm">
            {price && <span className="font-semibold">{price}</span>}
            {sub && (
              <Badge tone="green">
                Sub {sub}
                {product.subscription_savings_percent ? ` · -${Math.round(product.subscription_savings_percent)}%` : ""}
              </Badge>
            )}
            {product.available === true && (
              <Badge tone="green">
                <Check size={12} /> In stock
              </Badge>
            )}
            {product.available === false && (
              <Badge tone="red">
                <X size={12} /> Out of stock
              </Badge>
            )}
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-muted">
            {product.reviews.count != null && (
              <span className="inline-flex items-center gap-1">
                <Star size={12} className="fill-amber-400 text-amber-400" />
                {product.reviews.average_rating ?? "-"} · {product.reviews.count.toLocaleString()} reviews
              </span>
            )}
            <span className="inline-flex items-center gap-1">
              <Images size={12} /> {product.images.length} image{product.images.length !== 1 ? "s" : ""}
            </span>
            <a
              href={product.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-healf hover:underline"
            >
              View on Healf <ExternalLink size={12} />
            </a>
          </div>
        </div>
      </div>
      {product.extraction_warnings.length > 0 && (
        <div className="border-t border-line bg-cream/60 px-4 py-2 text-xs text-muted">
          {product.extraction_warnings[0]}
        </div>
      )}
    </Card>
  );
}
