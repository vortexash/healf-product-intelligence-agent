import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const HEALF_URL = /https?:\/\/(?:www\.)?healf\.com\/[^\s]*\/?products\/[^\s]+/i;

export function findHealfUrl(text: string): string | null {
  const m = text.match(HEALF_URL);
  return m ? m[0] : null;
}

// Human labels for extraction sources (used by citations + evidence drawer).
export const SOURCE_LABEL: Record<string, string> = {
  shopify_json: "Shopify JSON",
  embedded_json: "Embedded product JSON",
  json_ld: "JSON-LD",
  html: "Product page HTML",
  review_widget: "Review widget",
  derived: "Derived",
};

export function timeAgo(iso: number): string {
  const s = Math.floor((Date.now() - iso) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}
