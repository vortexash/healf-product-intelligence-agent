import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ProductCard } from "@/components/product/product-card";
import { AgentProgress } from "@/components/chat/agent-progress";
import { Scorecard } from "@/components/intelligence/scorecard";
import { Message } from "@/components/chat/message";
import {
  conversationHistory,
  latestThreadProduct,
  productContextUrl,
  shownSuggestions,
} from "@/components/chat/model";
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

describe("Conversation history", () => {
  it("sends completed user and assistant turns while excluding errors and in-flight messages", () => {
    const history = conversationHistory([
      { id: "1", role: "user", text: "Tell me about this product" },
      { id: "2", role: "assistant", text: "It has 516 reviews." },
      { id: "3", role: "assistant", text: "", streaming: true },
      { id: "4", role: "assistant", text: "", error: { code: "X", message: "failed" } },
    ]);
    expect(history).toEqual([
      { role: "user", text: "Tell me about this product" },
      { role: "assistant", text: "It has 516 reviews." },
    ]);
  });

  it("sends the product visible in the browser with every follow-up", () => {
    expect(productContextUrl(product, null)).toBe(product.source_url);
    expect(productContextUrl(product, "https://healf.com/products/reopened")).toBe(
      "https://healf.com/products/reopened",
    );
  });

  it("repairs a stale saved header from the latest product response", () => {
    const newerProduct = { ...product, handle: "oshun", title: "Electrolytes Concentrate Mini" };
    expect(
      latestThreadProduct([
        { id: "1", role: "assistant", text: "Sodii", product },
        { id: "2", role: "user", text: "Switch products" },
        { id: "3", role: "assistant", text: "Oshun", product: newerProduct },
      ]),
    ).toEqual(newerProduct);
  });

  it("collects unique suggestions already displayed in a saved thread", () => {
    expect(
      shownSuggestions([
        { id: "1", role: "assistant", text: "Answer", suggested: ["Check price", "Check reviews"] },
        { id: "2", role: "assistant", text: "Next", suggested: ["Check reviews", "Check stock"] },
        { id: "3", role: "assistant", text: "", streaming: true, suggested: ["Ignore me"] },
      ]),
    ).toEqual(["Check price", "Check reviews", "Check stock"]);
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

  it("labels catalog recommendations without pretending they came from one product page", () => {
    render(
      <Citations
        evidence={[
          {
            field: "product_recommendation",
            source_type: "derived",
            source_url: "https://healf.com/products/a",
            confidence: 0.9,
          },
          {
            field: "product_recommendation",
            source_type: "derived",
            source_url: "https://healf.com/products/b",
            confidence: 0.9,
          },
        ]}
      />,
    );
    expect(screen.getByText(/2 live Healf catalog matches linked above/)).toBeInTheDocument();
    expect(screen.queryByText(/the live Healf product page/)).toBeNull();
  });
});

describe("Message", () => {
  it("renders an error message", () => {
    render(
      <Message
        m={{ id: "1", role: "assistant", text: "", error: { code: "UNSUPPORTED_HOST", message: "Only Healf URLs allowed." } }}
        onFollowUp={() => {}}
      />,
    );
    expect(screen.getByText("Only Healf URLs allowed.")).toBeInTheDocument();
  });

  it("shows the plain source line but no confidence badge or internal labels", () => {
    render(
      <Message
        m={{
          id: "2",
          role: "assistant",
          text: "Vitamin D is not listed.",
          answer: { text: "Vitamin D is not listed.", intent: "ingredient_lookup", confidence: "high", limitations: [] },
          evidence: [{ field: "ingredients_raw", source_type: "html", source_url: "https://healf.com/products/x", confidence: 0.8 }],
        }}
        onFollowUp={() => {}}
      />,
    );
    expect(screen.getByText(/the live Healf product page/)).toBeInTheDocument();
    expect(screen.queryByText(/confidence/i)).toBeNull();
    expect(screen.queryByText(/ingredient lookup/i)).toBeNull();
  });

  it("renders assistant replies as open chat text and labels real caveats as notes", () => {
    const { container } = render(
      <Message
        m={{
          id: "3",
          role: "assistant",
          text: "Here is the answer.",
          answer: {
            text: "Here is the answer.",
            intent: "review_lookup",
            confidence: "high",
            limitations: ["Written review text is unavailable."],
          },
        }}
        onFollowUp={() => {}}
      />,
    );
    expect(screen.getByText("Here is the answer.")).toBeInTheDocument();
    expect(screen.getByText(/Written review text is unavailable/)).toBeInTheDocument();
    expect(screen.getByText("Note:")).toBeInTheDocument();
    expect(container.querySelector(".border-line.bg-card.shadow-soft")).toBeNull();
  });

  it("hides stale follow-up chips on older messages", () => {
    render(
      <Message
        m={{ id: "old", role: "assistant", text: "Earlier answer", suggested: ["Old follow-up"] }}
        onFollowUp={() => {}}
        showSuggestions={false}
      />,
    );
    expect(screen.queryByText("Old follow-up")).toBeNull();
  });
});
