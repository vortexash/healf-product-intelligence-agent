// Mirrors backend Pydantic models (PRD 12).

export interface Money {
  amount: number;
  currency: string;
  formatted?: string | null;
}

export interface ProductImage {
  url: string;
  alt_text?: string | null;
  is_primary?: boolean;
  position?: number | null;
}

export interface SellingPlan {
  id?: string | null;
  name?: string | null;
  discount_percent?: number | null;
}

export interface ProductVariant {
  id?: string | null;
  title?: string | null;
  available?: boolean | null;
  price?: Money | null;
  options?: Record<string, string>;
}

export interface ReviewSummary {
  present?: boolean | null;
  count?: number | null;
  average_rating?: number | null;
  provider?: string | null;
  full_review_text_ingested?: boolean;
}

export interface SeoData {
  title?: string | null;
  description?: string | null;
  canonical_url?: string | null;
}

export interface SourceEvidence {
  field: string;
  source_type: string;
  source_url: string;
  excerpt?: string | null;
  selector?: string | null;
  confidence: number;
}

export interface ProductData {
  source_url: string;
  canonical_url?: string | null;
  retrieved_at: string;
  handle: string;
  title?: string | null;
  vendor?: string | null;
  product_type?: string | null;
  description_text?: string | null;
  benefits: string[];
  ingredients_raw?: string | null;
  ingredient_groups: Record<string, string[]>;
  suggested_use?: string | null;
  warnings: string[];
  one_time_price?: Money | null;
  compare_at_price?: Money | null;
  subscription_price?: Money | null;
  subscription_savings_percent?: number | null;
  available?: boolean | null;
  selected_variant_id?: string | null;
  variants: ProductVariant[];
  selling_plans: SellingPlan[];
  reviews: ReviewSummary;
  images: ProductImage[];
  seo: SeoData;
  evidence: SourceEvidence[];
  extraction_warnings: string[];
}

export interface EvaluationCategory {
  key: string;
  label: string;
  score: number;
  status: "strong" | "good" | "moderate" | "weak" | "unknown";
  findings: string[];
  evidence_fields: string[];
}

export interface Recommendation {
  priority: number;
  title: string;
  rationale: string;
  suggested_action: string;
  evidence_fields: string[];
}

export interface ProductEvaluation {
  overall_score: number;
  summary: string;
  categories: EvaluationCategory[];
  recommendations: Recommendation[];
  limitations: string[];
  provisional: boolean;
}

export interface ContentDraft {
  title: string;
  content: string;
  facts_used: string[];
  claims_preserved: string[];
  claims_not_introduced: string[];
}

export interface ChatAnswer {
  text: string;
  intent: string;
  confidence: "high" | "medium" | "low";
  limitations: string[];
}

export interface ChatResponse {
  session_id: string;
  answer: ChatAnswer;
  product?: ProductData | null;
  evaluation?: ProductEvaluation | null;
  content_draft?: ContentDraft | null;
  evidence: SourceEvidence[];
  suggested_actions: string[];
}

export interface StatusEvent {
  step: string;
  message: string;
}

export type StreamHandlers = {
  onStatus?: (s: StatusEvent) => void;
  onProduct?: (p: ProductData) => void;
  onToken?: (t: string) => void;
  onComplete?: (r: ChatResponse) => void;
  onError?: (code: string, message: string) => void;
};
