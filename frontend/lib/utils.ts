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

// Plain-English labels for sources (no technical jargon shown to users).
export const SOURCE_LABEL: Record<string, string> = {
  shopify_json: "Product data",
  embedded_json: "Product data",
  json_ld: "Product listing",
  html: "Product page",
  review_widget: "Reviews",
  derived: "Derived",
};

// Plain-English labels for the data fields (hide internal field names).
const FIELD_LABEL: Record<string, string> = {
  title: "Product name",
  vendor: "Brand",
  product_type: "Category",
  description_text: "Description",
  description_html: "Description",
  benefits: "Key benefits",
  ingredients_raw: "Ingredients",
  ingredient_groups: "Ingredients",
  suggested_use: "How to use",
  warnings: "Warnings",
  one_time_price: "Price",
  compare_at_price: "Original price",
  subscription_price: "Subscription price",
  subscription_savings_percent: "Subscription saving",
  selling_plans: "Subscription plans",
  available: "Availability",
  variants: "Options",
  selected_variant_id: "Selected option",
  reviews: "Reviews",
  images: "Images",
  seo: "Page title & description",
  canonical_url: "Page address",
};

export function fieldLabel(field: string): string {
  if (FIELD_LABEL[field]) return FIELD_LABEL[field];
  return field.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function timeAgo(iso: number): string {
  const s = Math.floor((Date.now() - iso) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}
