import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ProductCard } from "@/components/product/product-card";
import { EvidenceDrawer } from "@/components/intelligence/evidence-drawer";
import { AgentProgress } from "@/components/chat/agent-progress";
import { Scorecard } from "@/components/intelligence/scorecard";
import { Message } from "@/components/chat/message";
import { Citations } from "@/components/intelligence/citations";
import { findHealfUrl } from "@/lib/utils";
import type { ProductData, ProductEvaluation } from "@/lib/types";

const product: ProductData = {
  source_url: "https://healf.com/en-uk/products/lmnt",
  retrieved_at: "2026-07-27T00:00:00Z",
  handle: "lmnt",
  title: "Recharge Electrolytes",
  vendor: "LMNT",
  benefits: [],
  ingredient_groups: {},
  warnings: [],
  one_time_price: { amount: 18.99, currency: "GBP", formatted: "£18.99" },
  variants: [],
  selling_plans: [],
  reviews: { present: true, count: 516, average_rating: 4.9, full_review_text_ingested: false },
  images: [{ url: "https://cdn.shopify.com/a.png", is_primary: true }],
  seo: {},
  evidence: [],
  extraction_warnings: [],
  available: true,
};

describe("URL extraction (composer logic)", () => {
  it("extracts a Healf product URL from a message", () => {
    expect(findHealfUrl("https://healf.com/en-uk/products/lmnt does it have vitamin d?")).toContain("/products/lmnt");
  });
  it("returns null when a follow-up omits the URL", () => {
    expect(findHealfUrl("what can I improve?")).toBeNull();
  });
});

describe("ProductCard", () => {
  it("renders title, price and reviews", () => {
    render(<ProductCard product={product} />);
    expect(screen.getByText("Recharge Electrolytes")).toBeInTheDocument();
    expect(screen.getByText("£18.99")).toBeInTheDocument();
    expect(screen.getByText(/516 reviews/)).toBeInTheDocument();
    expect(screen.getByText(/In stock/)).toBeInTheDocument();
  });
});

describe("AgentProgress", () => {
  it("renders progress steps", () => {
    render(<AgentProgress steps={[{ step: "validate_url", message: "Validating Healf URL" }]} done={false} />);
    expect(screen.getByText("Validating Healf URL")).toBeInTheDocument();
  });
});

describe("EvidenceDrawer", () => {
  it("opens and lists evidence, closes on button", () => {
    const onClose = vi.fn();
    render(
      <EvidenceDrawer
        open
        evidence={[{ field: "reviews", source_type: "json_ld", source_url: "u", excerpt: "rating=4.9", confidence: 0.9 }]}
        onClose={onClose}
      />,
    );
    expect(screen.getByText("Reviews")).toBeInTheDocument();
    expect(screen.getByText(/rating=4.9/)).toBeInTheDocument();
    expect(screen.queryByText("reviews")).toBeNull(); // raw field name hidden
    fireEvent.click(screen.getByLabelText("Close sources"));
    expect(onClose).toHaveBeenCalled();
  });
});

describe("Scorecard", () => {
  it("renders categories and overall score", () => {
    const evaluation: ProductEvaluation = {
      overall_score: 89,
      summary: "Strong page.",
      categories: [{ key: "images", label: "Image coverage", score: 46, status: "weak", findings: [], evidence_fields: [] }],
      recommendations: [],
      limitations: [],
      provisional: false,
    };
    render(<Scorecard evaluation={evaluation} />);
    expect(screen.getByText("89")).toBeInTheDocument();
    expect(screen.getByText("Image coverage")).toBeInTheDocument();
  });
});

describe("Citations", () => {
  it("shows a single plain-English source line linking to the live page (no jargon)", () => {
    render(
      <Citations
        evidence={[
          { field: "reviews", source_type: "json_ld", source_url: "https://healf.com/products/x", confidence: 0.9 },
          { field: "ingredients_raw", source_type: "html", source_url: "https://healf.com/products/x", confidence: 0.85 },
        ]}
      />,
    );
    expect(screen.getByText(/the live Healf product page/)).toBeInTheDocument();
    const link = screen.getByRole("link");
    expect(link).toHaveAttribute("href", "https://healf.com/products/x");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
    // Internal identifiers must not leak to the user.
    expect(screen.queryByText("JSON-LD")).toBeNull();
    expect(screen.queryByText(/ingredients_raw/)).toBeNull();
  });
});

describe("Message error rendering + evidence button", () => {
  it("renders an error message", () => {
    render(
      <Message
        m={{ id: "1", role: "assistant", text: "", error: { code: "UNSUPPORTED_HOST", message: "Only Healf URLs allowed." } }}
        onOpenEvidence={() => {}}
        onFollowUp={() => {}}
      />,
    );
    expect(screen.getByText("Only Healf URLs allowed.")).toBeInTheDocument();
  });

  it("shows an Evidence button and fires the callback", () => {
    const onOpen = vi.fn();
    render(
      <Message
        m={{
          id: "2",
          role: "assistant",
          text: "Vitamin D is not listed.",
          answer: { text: "Vitamin D is not listed.", intent: "ingredient_lookup", confidence: "high", limitations: [] },
          evidence: [{ field: "ingredients_raw", source_type: "html", source_url: "u", confidence: 0.8 }],
        }}
        onOpenEvidence={onOpen}
        onFollowUp={() => {}}
      />,
    );
    fireEvent.click(screen.getByText(/View sources/));
    expect(onOpen).toHaveBeenCalled();
  });
});
