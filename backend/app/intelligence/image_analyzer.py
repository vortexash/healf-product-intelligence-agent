"""Vision analysis of product images (extracts information from the image content).

Sends the live product image URLs to a multimodal model and returns, per image, its
role (hero / lifestyle / supplement-facts / ingredients / usage / packaging / other),
any prominent visible text, and a quality note, plus an overall assessment of what the
image set covers and what's missing. Falls back to the deterministic count answer when
no LLM is configured.
"""
from __future__ import annotations

import json

from ..models import ChatAnswer, ProductData
from . import factual_answerer as fa, llm_client

MAX_IMAGES = 4

_SYSTEM = """You are a product-imagery analyst for a health and wellness marketplace. You are shown
the actual product images from one listing, in order. For each image, identify what it is and read
any prominent text you can see.

Rules:
1. Only describe what is actually visible in the images. Do not invent text, ingredients, or claims.
2. Classify each image's role as one of: hero, lifestyle, supplement_facts, ingredients, usage,
   packaging, comparison, other.
3. If a supplement-facts / nutrition panel or an ingredients list is visible, say so and quote the
   key legible text (do not guess unreadable values).
4. Keep it concise and factual.

Return ONLY JSON:
{
  "images": [
    {"index": 1, "role": "hero", "visible_text": "short quote or empty", "note": "one short line"}
  ],
  "covers": ["hero", "supplement_facts"],
  "missing": ["a clear usage/directions image"],
  "summary": "2-3 sentences on what the image set shows and its gaps"
}"""


async def analyze_images(product: ProductData, question: str) -> ChatAnswer:
    images = product.images[:MAX_IMAGES]
    if not images:
        return ChatAnswer(
            text="This product page has no images I could analyze.",
            intent="image_evaluation",
            confidence="low",
        )
    if not llm_client.is_configured():
        # No vision available: fall back to the deterministic count/alt answer.
        return fa.answer_image_count(product)

    urls = [i.url for i in images]
    user = json.dumps({"question": question, "image_count_total": len(product.images), "images_shown": len(urls)})
    try:
        data = await llm_client.complete_json_vision(_SYSTEM, user, urls, max_tokens=1400)
    except Exception:  # noqa: BLE001 - degrade gracefully to the deterministic answer
        ans = fa.answer_image_count(product)
        ans.limitations = (ans.limitations or []) + ["Visual analysis was unavailable, so this is metadata only."]
        return ans

    entries = data.get("images", []) if isinstance(data, dict) else []
    lines: list[str] = []
    total = len(product.images)
    shown = len(urls)
    header = f"I looked at {shown} of this product's {total} image{'s' if total != 1 else ''}:"
    lines.append(header)
    lines.append("")
    for i, img in enumerate(images):
        meta = entries[i] if i < len(entries) else {}
        role = str(meta.get("role", "image")).replace("_", " ")
        note = str(meta.get("note", "")).strip()
        visible = str(meta.get("visible_text", "")).strip()
        lines.append(f"![image {i + 1}]({img.url})")
        bits = [f"**{role.title()}**"]
        if note:
            bits.append(note)
        line = " - ".join(bits)
        if visible:
            line += f'  \nVisible text: "{visible[:200]}"'
        lines.append(line)
        lines.append("")

    summary = str(data.get("summary", "")).strip()
    if summary:
        lines.append(f"**Overall:** {summary}")
    missing = [str(m) for m in (data.get("missing") or [])]
    if missing:
        lines.append(f"**Missing / would help:** {', '.join(missing)}.")

    alt = sum(1 for i in product.images if i.alt_text)
    return ChatAnswer(
        text="\n".join(lines),
        intent="image_evaluation",
        confidence="medium",
        limitations=[
            "Based on an automated visual reading of the images; it can misread small or stylised text.",
            f"Alt text is present on {alt}/{total} images (affects accessibility and SEO).",
        ],
    )
