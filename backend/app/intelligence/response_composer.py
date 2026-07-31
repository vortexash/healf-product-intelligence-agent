"""Route intent -> answer/evaluation/content and assemble the response (PRD 8, 21)."""
from __future__ import annotations

import json
import re
from urllib.parse import quote_plus

from ..models import (
    ChatAnswer,
    ContentDraft,
    ProductData,
    ProductEvaluation,
    SourceEvidence,
)
from . import (
    content_generator,
    evaluator,
    factual_answerer as fa,
    image_analyzer,
    llm_client,
    product_search,
)
from .intent_router import IntentResult, classify, classify_all
from .llm_payload import product_facts
from ..prompts import evaluator as eval_prompt
from ..utilities import excerpt

_CONTEXTUAL_REVIEW_FOLLOWUP = re.compile(
    r"^\s*(another(?:\s+one)?|one\s+more|next(?:\s+one)?|more)\s*[?.!]*\s*$",
    re.IGNORECASE,
)

_FACTUAL_INTENTS = {
    "ingredient_lookup",
    "review_lookup",
    "price_lookup",
    "subscription_lookup",
    "availability_lookup",
}
_MULTI_PART_CONNECTOR = re.compile(r"\b(and|also|then|plus|as well as|if so)\b", re.IGNORECASE)
_REVIEW_JUDGMENT = re.compile(
    r"\b(why|matter|persuasi|cautious|trust|rely|reliable|quality|effective|which is more)\w*\b",
    re.IGNORECASE,
)


def _continues_review_conversation(prior_user_messages: list[str]) -> bool:
    """Recognize a review request followed by any number of short follow-ups."""
    for prior in reversed(prior_user_messages):
        if classify(prior).intent == "review_lookup":
            return True
        if not _CONTEXTUAL_REVIEW_FOLLOWUP.match(prior):
            return False
    return False


def suggest_follow_ups(
    product: ProductData,
    current_intent: str,
    asked_intents: frozenset[str] = frozenset(),
    current_message: str = "",
    prior_user_messages: list[str] | None = None,
    shown_suggestions: list[str] | None = None,
) -> list[str]:
    """Build follow-up prompts from what THIS product actually has, skipping any
    action already asked earlier in the conversation. Deterministic, no LLM call."""
    prior = [*(prior_user_messages or []), current_message]
    if current_intent == "product_recommendation":
        topic = product_search.derive_search_query(product, current_message)
        price_cap = _follow_up_price_cap(product)
        return _novel_prompts(
            [
                f"Show me {topic} options under £{price_cap}",
                f"Show me {topic} options from a different brand",
                "What should I compare before choosing?",
                f"Show me more {topic} alternatives",
                "What are this product's main trade-offs?",
            ],
            prior,
            shown_suggestions or [],
        )
    if current_intent == "review_lookup" and product.reviews.items:
        name = _product_prompt_name(product)
        return _novel_prompts([
            f"Show me 3 reviews for {name}",
            f"Show the latest review for {name}",
            f"What is the average rating for {name}?",
        ], prior, shown_suggestions or [])
    if current_intent == "general_product_question" and re.search(
        r"\b(why|matter|useful|cautious|trade-?offs?|choose|choosing)\b",
        current_message,
        re.IGNORECASE,
    ):
        name = _product_prompt_name(product)
        return _novel_prompts(
            [
                f"What evidence on the {name} page supports that?",
                f"What does the {name} page not tell us?",
                f"Summarize the key trade-offs for {name}",
                f"What should I verify before buying {name}?",
            ],
            prior,
            shown_suggestions or [],
        )
    done = set(asked_intents) | {current_intent}
    name = _product_prompt_name(product)
    has_ingredients = bool(product.ingredients_raw or product.ingredient_groups)
    has_reviews = bool(product.reviews.present or product.reviews.count)
    candidates: list[tuple[str, str, bool]]

    if current_intent == "product_summary":
        candidates = [
            (f"What warnings are listed for {name}?", "warning_detail", bool(product.warnings)),
            (f"Are any allergens listed for {name}?", "ingredient_lookup", has_ingredients),
            (f"How strong is the review evidence for {name}?", "review_lookup", has_reviews),
            (f"How much would I save by subscribing to {name}?", "subscription_lookup", bool(product.subscription_price)),
            (f"What should I verify before buying {name}?", "purchase_check", True),
        ]
    elif current_intent == "ingredient_lookup":
        candidates = [
            (f"What warnings are listed for {name}?", "warning_detail", bool(product.warnings)),
            (f"How should I use {name}?", "usage_detail", bool(product.suggested_use)),
            (f"What do buyers say about {name}?", "review_lookup", has_reviews),
            (f"How much does {name} cost?", "price_lookup", bool(product.one_time_price)),
            (f"Is {name} currently in stock?", "availability_lookup", product.available is not None),
            (f"What should I verify before buying {name}?", "purchase_check", True),
        ]
    elif current_intent in {"price_lookup", "subscription_lookup"}:
        candidates = [
            (f"What do buyers say about {name}?", "review_lookup", has_reviews),
            (f"Are any allergens listed for {name}?", "ingredient_lookup", has_ingredients),
            (f"Is {name} currently in stock?", "availability_lookup", product.available is not None),
            (f"What should I compare before choosing {name}?", "purchase_check", True),
        ]
    elif current_intent == "review_lookup":
        candidates = [
            (f"What should I be cautious about with {name}?", "purchase_check", True),
            (f"Are any allergens listed for {name}?", "ingredient_lookup", has_ingredients),
            (f"How much would I save by subscribing to {name}?", "subscription_lookup", bool(product.subscription_price)),
            (f"What warnings are listed for {name}?", "warning_detail", bool(product.warnings)),
        ]
    elif current_intent in {"page_evaluation", "seo_evaluation", "image_evaluation"}:
        candidates = [
            (f"Rewrite the description for {name}", "content_rewrite", bool(product.description_text)),
            (f"Improve the SEO title for {name}", "seo_evaluation", current_intent != "seo_evaluation"),
            (f"Review the product images for {name}", "image_evaluation", bool(product.images) and current_intent != "image_evaluation"),
            (f"Create a customer FAQ for {name}", "faq_generation", True),
        ]
    elif current_intent in {"content_rewrite", "faq_generation"}:
        candidates = [
            (f"Rewrite a shorter description for {name}", "short_rewrite", current_intent == "content_rewrite"),
            (f"Create a customer FAQ for {name}", "faq_generation", current_intent != "faq_generation"),
            (f"Improve the SEO title for {name}", "seo_evaluation", True),
            (f"Review the product images for {name}", "image_evaluation", bool(product.images)),
        ]
    elif current_intent == "availability_lookup":
        candidates = [
            (f"How much does {name} cost?", "price_lookup", bool(product.one_time_price)),
            (f"What do buyers say about {name}?", "review_lookup", has_reviews),
            (f"Are any allergens listed for {name}?", "ingredient_lookup", has_ingredients),
            (f"What should I verify before buying {name}?", "purchase_check", True),
        ]
    else:
        candidates = [
            (f"What does the {name} page not tell us?", "missing_detail", True),
            (f"What warnings are listed for {name}?", "warning_detail", bool(product.warnings)),
            (f"What do buyers say about {name}?", "review_lookup", has_reviews),
            (f"Are any allergens listed for {name}?", "ingredient_lookup", has_ingredients),
            (f"How much does {name} cost?", "price_lookup", bool(product.one_time_price)),
        ]
    out: list[str] = []
    for prompt, ikey, relevant in candidates:
        if relevant and ikey not in done:
            out.append(prompt)
            done.add(ikey)  # don't offer two prompts for the same intent
        if len(out) == 3:
            break
    return _novel_prompts(out, prior, shown_suggestions or [])


def _product_prompt_name(product: ProductData) -> str:
    name = (product.title or "this product").split(" - ", 1)[0].strip()
    return name if len(name) <= 42 else name[:39].rstrip() + "..."


def _follow_up_price_cap(product: ProductData) -> int:
    amount = product.one_time_price.amount if product.one_time_price else None
    if amount is None:
        return 50
    for threshold in (20, 30, 50, 75, 100, 150, 200, 300, 500):
        if amount <= threshold:
            return threshold
    return int(((amount + 99) // 100) * 100)


def _novel_prompts(
    candidates: list[str],
    prior_messages: list[str],
    shown_suggestions: list[str] | None = None,
) -> list[str]:
    prior_tokens = [_prompt_tokens(message) for message in prior_messages if message]
    shown = [message for message in (shown_suggestions or []) if message]
    selected: list[str] = []
    for candidate in candidates:
        tokens = _prompt_tokens(candidate)
        if any(_prompts_overlap(tokens, old) for old in prior_tokens):
            continue
        topics = _prompt_topics(candidate)
        if any(
            _prompts_overlap(tokens, _prompt_tokens(old))
            or bool(topics & _prompt_topics(old))
            for old in shown
        ):
            continue
        if any(_prompts_overlap(tokens, _prompt_tokens(old)) for old in selected):
            continue
        selected.append(candidate)
        if len(selected) == 3:
            break
    return selected


def _prompt_tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", value.lower())
        if token not in {"a", "an", "the", "me", "this", "that", "is", "are", "from"}
    }


def _prompts_overlap(left: set[str], right: set[str]) -> bool:
    if not left or not right:
        return False
    return len(left & right) / min(len(left), len(right)) >= 0.8


def _prompt_topics(value: str) -> set[str]:
    text = value.lower()
    patterns = {
        "safety": r"\b(warnings?|cautious|verify|before buying)\b",
        "ingredients": r"\b(ingredients?|allergens?|contains?)\b",
        "reviews": r"\b(reviews?|ratings?|buyers?)\b",
        "subscription": r"\b(subscription|subscrib|saving|save)\w*\b",
        "price": r"\b(price|cost|under £|under \d)\b",
        "usage": r"\b(use|take|dosage|serving)\w*\b",
        "availability": r"\b(stock|available|availability)\b",
        "content": r"\b(rewrite|description|copy)\b",
        "seo": r"\bseo\b|meta description|page title",
        "images": r"\b(images?|photos?|pictures?)\b",
        "faq": r"\bfaq\b|frequently asked",
        "decision": r"\b(compare|choosing|trade-?offs?|alternatives?)\b",
    }
    return {topic for topic, pattern in patterns.items() if re.search(pattern, text)}


class Composed:
    def __init__(self):
        self.answer: ChatAnswer | None = None
        self.evaluation: ProductEvaluation | None = None
        self.content_draft: ContentDraft | None = None
        self.evidence: list[SourceEvidence] = []
        self.suggested_actions: list[str] = []


async def compose_without_product(message: str, conversation_history: list[dict] | None = None) -> Composed:
    """Reply conversationally before a product has been selected.

    This intentionally stays inside the product-intelligence scope rather than
    turning the app into an ungrounded general-health chatbot.
    """
    out = Composed()
    normalized = message.strip().lower()
    if classify(message).intent == "product_recommendation":
        try:
            text, suggestions, evidence, query = await product_search.discover(message)
            out.answer = ChatAnswer(
                text=text,
                intent="product_recommendation",
                confidence="high" if evidence else "low",
                limitations=(
                    ["Catalogue matches are not personalised medical recommendations."]
                    if evidence
                    else ["No matching in-stock catalogue products were returned."]
                ),
            )
            out.evidence = evidence
            if suggestions:
                out.suggested_actions = [
                    "Tell me about the first one",
                    f"Show me {query} options under £30",
                ]
            return out
        except Exception:  # noqa: BLE001
            query = product_search.derive_discovery_query(message)
            search_url = f"https://healf.com/en-uk/search?q={quote_plus(query)}"
            out.answer = ChatAnswer(
                text=(
                    "I couldn't retrieve the live Healf catalogue just now. "
                    f"[Search Healf for {query}]({search_url})."
                ),
                intent="product_recommendation",
                confidence="low",
                limitations=["The live Healf catalogue search was temporarily unavailable."],
            )
            return out
    if re.match(r"^(?:hi|hello|hey|good (?:morning|afternoon|evening))\b", normalized):
        opening = "Hi — happy to help."
    elif re.search(r"\b(thanks|thank you)\b", normalized):
        opening = "You're welcome."
    else:
        opening = "I can help with that once I have the product context."
    out.answer = ChatAnswer(
        text=(
            f"{opening} Send me a public **Healf product URL**, then ask naturally — you can "
            "request facts, compare price and reviews, ask follow-up questions, evaluate the page, "
            "or draft improved content without repeating the URL."
        ),
        intent="product_onboarding",
        confidence="high",
    )
    return out


def _evidence_for(product: ProductData, fields: list[str]) -> list[SourceEvidence]:
    if not fields:
        return product.evidence
    return [e for e in product.evidence if e.field in fields] or product.evidence


async def compose(
    product: ProductData,
    message: str,
    conversation_history: list[dict] | None = None,
    previous_suggestions: list[str] | None = None,
) -> Composed:
    history = conversation_history or []
    prior_user_messages = [
        str(turn.get("text", ""))
        for turn in history
        if turn.get("role") == "user" and turn.get("text")
    ]
    matches = classify_all(message)
    intent = matches[0] if matches else classify(message)
    if (
        intent.intent == "general_product_question"
        and _CONTEXTUAL_REVIEW_FOLLOWUP.match(message)
        and prior_user_messages
        and _continues_review_conversation(prior_user_messages)
    ):
        intent = IntentResult(
            intent="review_lookup",
            requires_llm=False,
            confidence=0.95,
        )
        matches = [intent]
    out = Composed()
    asked = frozenset(classify(m).intent for m in prior_user_messages)
    out.suggested_actions = suggest_follow_ups(
        product,
        intent.intent,
        asked,
        current_message=message,
        prior_user_messages=prior_user_messages,
        shown_suggestions=previous_suggestions,
    )

    # Ambiguous follow-ups and multi-part questions go through one grounded
    # conversational pass.  Simple factual lookups remain deterministic.
    if _needs_conversational_response(message, matches):
        await _handle_conversation(product, message, history, matches, prior_user_messages, out)
        return out

    i = intent.intent
    if i == "product_recommendation":
        await _handle_product_recommendation(product, message, out)
    elif i == "ingredient_lookup":
        out.answer = fa.answer_ingredient(product, intent.target_entity, message)
        out.evidence = _evidence_for(product, ["ingredients_raw", "ingredient_groups"])
    elif i == "review_lookup":
        out.answer = fa.answer_reviews(product, message, prior_user_messages)
        out.evidence = _evidence_for(product, ["reviews"])
    elif i == "price_lookup":
        out.answer = fa.answer_price(product)
        out.evidence = _evidence_for(product, ["one_time_price", "compare_at_price", "subscription_price"])
    elif i == "subscription_lookup":
        out.answer = fa.answer_subscription(product)
        out.evidence = _evidence_for(product, ["subscription_price", "selling_plans", "one_time_price"])
    elif i == "availability_lookup":
        out.answer = fa.answer_availability(product)
        out.evidence = _evidence_for(product, ["available"])
    elif i == "image_evaluation":
        out.answer = await image_analyzer.analyze_images(product, message)
        out.evidence = _evidence_for(product, ["images"])
    elif i in ("page_evaluation", "seo_evaluation"):
        await _handle_evaluation(product, message, i, out)
    elif i in ("content_rewrite", "faq_generation"):
        await _handle_content(product, message, i, out)
    elif i == "product_summary":
        await _handle_summary(product, message, out)
    else:  # general_product_question (normally handled above)
        await _handle_conversation(product, message, history, matches, prior_user_messages, out)

    return out


async def _handle_product_recommendation(
    product: ProductData, message: str, out: Composed
) -> None:
    try:
        text, _, evidence = await product_search.recommend(product, message)
        out.answer = ChatAnswer(
            text=text,
            intent="product_recommendation",
            confidence="high" if evidence else "low",
            limitations=(
                ["Catalog similarity is not a personalised health recommendation."]
                if evidence
                else ["The live Healf catalog search was temporarily unavailable."]
            ),
        )
        out.evidence = evidence
    except Exception:  # noqa: BLE001
        query = product_search.derive_search_query(product, message)
        search_url = f"https://healf.com/en-uk/search?q={quote_plus(query)}"
        out.answer = ChatAnswer(
            text=(
                "I couldn't retrieve live alternatives just now. "
                f"[Search Healf for {query}]({search_url}) and send me any product link you want to analyse."
            ),
            intent="product_recommendation",
            confidence="low",
            limitations=["The live Healf catalog search was temporarily unavailable."],
        )


async def _handle_evaluation(product, message, intent, out: Composed) -> None:
    out.evaluation = await evaluator.evaluate(product, message)
    ev = out.evaluation
    cats = sorted(ev.categories, key=lambda c: c.score)
    lines = [ev.summary, "", f"**Overall score: {ev.overall_score}/100** (a heuristic, not an exact grade)."]
    if cats:
        strongest, weakest = cats[-1], cats[0]
        lines.append(
            f"Strongest area: **{strongest.label}** ({strongest.score}/100). "
            f"Weakest: **{weakest.label}** ({weakest.score}/100)."
        )
    if ev.recommendations:
        lines.append(f"\nThe {min(len(ev.recommendations), 3)} highest-impact fixes are in the card below.")
    conf = "medium" if ev.provisional else "high"
    out.answer = ChatAnswer(text="\n".join(lines), intent=intent, confidence=conf, limitations=ev.limitations)
    out.evidence = product.evidence


async def _handle_content(product, message, intent, out: Composed) -> None:
    if not llm_client.is_configured():
        out.answer = ChatAnswer(
            text="I can answer factual questions, but content generation is unavailable because no LLM is configured.",
            intent=intent,
            confidence="low",
            limitations=["Set an ANTHROPIC_API_KEY or OPENAI_API_KEY to enable content generation."],
        )
        return
    draft = await content_generator.generate(product, intent, message)
    out.content_draft = draft
    out.answer = ChatAnswer(
        text=f"Here is a draft: **{draft.title}**. See the draft card below - it lists which facts were used and which claims were deliberately not introduced.",
        intent=intent,
        confidence="medium",
        limitations=["Generated from extracted facts only; review before publishing."],
    )
    out.evidence = product.evidence


async def _handle_summary(product, message, out: Composed) -> None:
    if not llm_client.is_configured():
        out.answer = _rule_summary(product)
        return
    try:
        user = json.dumps({"task": "Summarize this product in 3-4 sentences for a shopper.", "product": product_facts(product)}, default=str)
        data = await llm_client.complete_json(
            eval_prompt.SYSTEM + '\nReturn ONLY JSON: {"summary": "..."}', user, max_tokens=500
        )
        out.answer = ChatAnswer(text=str(data.get("summary", "")) or _rule_summary(product).text, intent="product_summary", confidence="medium")
    except Exception:  # noqa: BLE001
        out.answer = _rule_summary(product)
    out.evidence = product.evidence


_CONVERSATION_SYSTEM = """You are Healf's product intelligence assistant. Continue the
conversation naturally and answer every part of the user's latest message.

You are given recent conversation turns, structured facts extracted from the current live product
page, and zero or more deterministic tool results.

Rules:
1. Deterministic tool results are authoritative. Do not contradict or embellish them.
2. For facts about THIS product, use only the supplied current-product facts and tool results. If
   they do not contain a fact, say the page does not show it.
3. Conversation history helps resolve references such as "that", "why?", and "what about it?",
   but it is not a source of new product facts and may refer to an older product.
4. For general knowledge, give a brief explanation and clearly distinguish it from a claim about
   this product.
5. Never invent product facts, customer sentiment, prices, certifications, allergens, suitability,
   medical claims, or review quotations. Do not imply that sample reviews represent the full archive.
6. Aggregate review count/rating can be called strong review evidence, but does not prove quality,
   reliability, effectiveness, representativeness, or that every customer is satisfied.
7. Price may be compared exactly, but do not call it affordable, competitive, or good value without
   a supplied benchmark.
8. Address compound requests in a coherent answer instead of choosing only one part.
9. Do not give medical advice or make disease-treatment claims. Be friendly, direct, and concise.

Return ONLY JSON: {"answer": "..."}"""


def _needs_conversational_response(message: str, matches: list[IntentResult]) -> bool:
    if not matches:
        return True
    if len(matches) > 1:
        return True
    return matches[0].intent in _FACTUAL_INTENTS and bool(_MULTI_PART_CONNECTOR.search(message))


def _recent_history(history: list[dict]) -> list[dict[str, str]]:
    recent: list[dict[str, str]] = []
    for turn in history[-10:]:
        role = turn.get("role")
        text = str(turn.get("text", "")).strip()
        if role in {"user", "assistant"} and text:
            recent.append({"role": role, "text": excerpt(text, 900)})
    return recent


def _grounded_tool_results(
    product: ProductData,
    message: str,
    matches: list[IntentResult],
    prior_user_messages: list[str],
) -> list[dict]:
    results: list[dict] = []
    seen: set[str] = set()
    for match in matches:
        if match.intent in seen:
            continue
        seen.add(match.intent)
        answer: ChatAnswer | None = None
        if match.intent == "ingredient_lookup":
            answer = fa.answer_ingredient(product, match.target_entity, message)
        elif match.intent == "review_lookup":
            answer = fa.answer_reviews(product, message, prior_user_messages)
        elif match.intent == "price_lookup":
            answer = fa.answer_price(product)
        elif match.intent == "subscription_lookup":
            answer = fa.answer_subscription(product)
        elif match.intent == "availability_lookup":
            answer = fa.answer_availability(product)
        if answer:
            results.append(
                {
                    "intent": match.intent,
                    "answer": answer.text,
                    "confidence": answer.confidence,
                    "limitations": answer.limitations,
                }
            )
    return results


def _conversation_fallback(product: ProductData, tool_results: list[dict]) -> ChatAnswer:
    if tool_results:
        text = "\n\n".join(str(result["answer"]) for result in tool_results)
        confidence = "high" if all(result["confidence"] == "high" for result in tool_results) else "medium"
        limitations = [
            limitation
            for result in tool_results
            for limitation in result.get("limitations", [])
        ]
        return ChatAnswer(
            text=text,
            intent="conversational_product_question",
            confidence=confidence,
            limitations=list(dict.fromkeys(limitations)),
        )
    summary = _rule_summary(product)
    summary.intent = "conversational_product_question"
    return summary


_CONVERSATION_INFERENCE_REPLACEMENTS: tuple[tuple[re.Pattern, str], ...] = (
    (re.compile(r"\b(?:a )?high level of customer satisfaction and reliability\b", re.I), "strong aggregate review results"),
    (re.compile(r"\bcustomer satisfaction and reliability\b", re.I), "positive aggregate review results"),
    (re.compile(r"\b(?:a )?high level of customer satisfaction\b", re.I), "a strong aggregate rating signal"),
    (re.compile(r"\b(?:strong|high) customer satisfaction\b", re.I), "strong aggregate review results"),
    (re.compile(r"\bcustomer satisfaction is high\b", re.I), "the aggregate rating is strong"),
    (re.compile(r"\bmany users are satisfied with the product(?:'s effectiveness and quality)?\b", re.I), "many reviewers rated the product positively"),
    (re.compile(r"\bproduct reliability\b", re.I), "positive aggregate review results"),
    (re.compile(r"\bhigh quality and worth purchasing\b", re.I), "rated positively by reviewers"),
    (re.compile(r"\bmany users have had positive experiences with the product\b", re.I), "many reviewers gave the product positive ratings"),
    (re.compile(r"\bthe quality and effectiveness of the product\b", re.I), "your purchase decision"),
    (re.compile(r"\bproduct effectiveness and user satisfaction\b", re.I), "review evidence"),
    (re.compile(r"\bquality and reliability\b", re.I), "review evidence"),
    (re.compile(r"\bcustomer satisfaction\b", re.I), "positive aggregate ratings"),
    (re.compile(r"\b(?:a )?focus on affordability\b", re.I), "a lower subscription price"),
    (re.compile(r"\bconfidence that the product will meet expectations\b", re.I), "additional evidence for a purchase decision"),
)


def _sanitize_conversation_answer(text: str) -> str:
    for pattern, replacement in _CONVERSATION_INFERENCE_REPLACEMENTS:
        text = pattern.sub(replacement, text)
    return text


def _grounded_review_judgment(
    product: ProductData,
    message: str,
    matches: list[IntentResult],
) -> ChatAnswer | None:
    intents = {match.intent for match in matches}
    if "review_lookup" not in intents or not _REVIEW_JUDGMENT.search(message):
        return None

    lines: list[str] = []
    if "price_lookup" in intents or "subscription_lookup" in intents:
        price_parts = []
        if product.one_time_price:
            price_parts.append(f"a one-time price of **{product.one_time_price.formatted}**")
        if product.subscription_price:
            saving = (
                f" with a **{product.subscription_savings_percent:g}% saving**"
                if product.subscription_savings_percent is not None
                else ""
            )
            price_parts.append(f"a subscription price of **{product.subscription_price.formatted}**{saving}")
        if price_parts:
            lines.append("The page offers " + " and ".join(price_parts) + ".")

    if product.reviews.count is not None:
        rating = (
            f" with an average rating of **{product.reviews.average_rating}/5**"
            if product.reviews.average_rating is not None
            else ""
        )
        lines.append(f"It reports **{product.reviews.count:,} reviews**{rating}.")
    else:
        lines.append("The page does not expose a confirmed aggregate review count.")

    if "price_lookup" in intents or "subscription_lookup" in intents:
        lines.append(
            "For merchandising, the review count and rating may be the stronger **social-proof signal**, "
            "while the subscription saving is the clearer **financial incentive**. That is a judgment, "
            "not measured conversion evidence."
        )
    else:
        lines.append(
            "Those aggregates are useful social proof because they show how many ratings the page has "
            "and their average; they do not establish why reviewers chose their scores."
        )

    lines.append(
        "Be cautious: aggregate ratings do **not** prove product quality, effectiveness, reliability, "
        "or that the available written samples represent every customer. Read a range of original "
        "reviews and assess the product facts separately."
    )
    return ChatAnswer(
        text="\n\n".join(lines),
        intent="conversational_product_question",
        confidence="high",
        limitations=["Persuasiveness is a merchandising judgment; no conversion data was supplied."],
    )


async def _handle_conversation(
    product: ProductData,
    message: str,
    history: list[dict],
    matches: list[IntentResult],
    prior_user_messages: list[str],
    out: Composed,
) -> None:
    tool_results = _grounded_tool_results(product, message, matches, prior_user_messages)
    fallback = _conversation_fallback(product, tool_results)
    out.evidence = product.evidence
    review_judgment = _grounded_review_judgment(product, message, matches)
    if review_judgment:
        out.answer = review_judgment
        return
    if not llm_client.is_configured():
        out.answer = fallback
        return
    try:
        user = json.dumps(
            {
                "recent_conversation": _recent_history(history),
                "current_question": message,
                "current_product_facts": product_facts(product),
                "grounded_tool_results": tool_results,
            },
            default=str,
        )
        data = await llm_client.complete_json(_CONVERSATION_SYSTEM, user, max_tokens=1000)
        out.answer = ChatAnswer(
            text=_sanitize_conversation_answer(str(data.get("answer", "")).strip()) or fallback.text,
            intent="conversational_product_question",
            confidence="medium",
            limitations=fallback.limitations,
        )
    except Exception:  # noqa: BLE001
        out.answer = fallback


def _rule_summary(product: ProductData) -> ChatAnswer:
    parts = []
    if product.title:
        parts.append(f"**{product.title}**" + (f" by {product.vendor}" if product.vendor else ""))
    if product.one_time_price:
        parts.append(f"priced at {product.one_time_price.formatted}")
    if product.reviews.count:
        parts.append(f"with {product.reviews.count:,} reviews ({product.reviews.average_rating}/5)")
    if product.benefits:
        parts.append("Key benefits: " + "; ".join(product.benefits[:3]))
    text = ". ".join(parts) + "." if parts else "I have the product loaded but limited details to summarize."
    return ChatAnswer(text=text, intent="product_summary", confidence="medium")
