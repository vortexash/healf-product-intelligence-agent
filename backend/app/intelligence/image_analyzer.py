"""Vision analysis of product images (extracts information from the image content).

Sends the live product image URLs to a multimodal model and returns, per image, its
role (hero / lifestyle / supplement-facts / ingredients / usage / packaging / other),
any prominent visible text, and a quality note, plus an overall assessment of what the
image set covers and what's missing. Falls back to the deterministic count answer when
no LLM is configured.
"""
from __future__ import annotations

import json
import re

from ..models import ChatAnswer, ProductData
from ..utilities import excerpt
from . import factual_answerer as fa, llm_client

MAX_IMAGES = 4

# "does the label match the description", "compare image ingredients to the page", etc.
_COMPARE_RE = re.compile(r"\b(match|matches|matching|compare|same|differ|discrepan|consistent|agree|align)\b", re.I)
_LABEL_RE = re.compile(r"\b(ingredient|nutrition|label|supplement facts|panel|description|packaging)\b", re.I)

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

    # "Do the ingredients on the label match the description?" -> read the label at
    # high detail and cross-check against the extracted page ingredients.
    if _COMPARE_RE.search(question) and _LABEL_RE.search(question):
        return await _compare_label_to_page(product, question)

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


_COMPARE_SYSTEM = """You compare a product's on-page ingredient text against what is actually printed
on its product images (labels / supplement-facts panels / packaging).

You are shown the product images. Read any ingredients or nutrition text visible on them as
accurately as you can. The user message also contains the ingredient text extracted from the product
PAGE. Compare the two.

Rules:
1. Only report what you can actually read from the images. Do not invent or complete text.
2. If the label text is too small, blurry, or not present, set verdict to "unreadable" and say so.
3. Ingredient names may be worded slightly differently (e.g. "Salt" vs "Sodium Chloride"); treat
   clear synonyms as matching but call out genuine differences.

Return ONLY JSON:
{
  "image_ingredients": "the ingredient/nutrition text you can read from the images, or empty",
  "label_found": true,
  "verdict": "match" | "partial" | "mismatch" | "unreadable",
  "matches": ["items found in both"],
  "only_on_image": ["items on the label but not in the page text"],
  "only_on_page": ["items in the page text but not visible on the label"],
  "summary": "2-3 sentence plain-language comparison"
}"""


async def _compare_label_to_page(product: ProductData, question: str) -> ChatAnswer:
    images = product.images[:MAX_IMAGES]
    page_ingredients = product.ingredients_raw or ""
    user = json.dumps(
        {
            "question": question,
            "page_ingredients_text": page_ingredients or "(the page did not list ingredients as text)",
        }
    )
    try:
        data = await llm_client.complete_json_vision(
            _COMPARE_SYSTEM, user, [i.url for i in images], max_tokens=1600, detail="high"
        )
    except Exception:  # noqa: BLE001
        ans = fa.answer_image_count(product)
        ans.limitations = (ans.limitations or []) + ["Could not visually read the label to compare it."]
        return ans

    verdict = str(data.get("verdict", "unreadable")).lower()
    img_ing = str(data.get("image_ingredients", "")).strip()
    summary = str(data.get("summary", "")).strip()
    matches = [str(x) for x in (data.get("matches") or [])]
    only_img = [str(x) for x in (data.get("only_on_image") or [])]
    only_page = [str(x) for x in (data.get("only_on_page") or [])]

    verdict_line = {
        "match": "**They match.** The label and the page ingredient text agree.",
        "partial": "**Partial match.** Most items line up, with some differences.",
        "mismatch": "**They do not match.** The label and the page differ.",
        "unreadable": "**I could not read the label clearly enough to compare.**",
    }.get(verdict, f"**Verdict: {verdict}.**")

    lines = ["I read the product image(s) and compared them with the page's ingredient text.", "", verdict_line]
    if summary:
        lines.append(summary)
    lines.append("")
    lines.append(f"**On the label image:** {img_ing or 'no legible ingredient text found'}")
    lines.append(f"**On the page:** {excerpt(page_ingredients, 400) or 'no ingredient text extracted'}")
    if matches:
        lines.append(f"\n**Matching:** {', '.join(matches[:20])}")
    if only_page:
        lines.append(f"**Only in the page text:** {', '.join(only_page[:20])}")
    if only_img:
        lines.append(f"**Only visible on the label:** {', '.join(only_img[:20])}")

    return ChatAnswer(
        text="\n".join(lines),
        intent="image_evaluation",
        confidence="medium" if verdict != "unreadable" else "low",
        limitations=[
            "Based on an automated visual reading of the label; small or stylised text can be misread.",
            "Wording can differ between a label and a page (for example 'Salt' vs 'Sodium Chloride').",
        ],
    )
