"""Capture REAL example outputs from the live backend into examples/example_outputs.md.

Run with backend up on :8000. Produces grounded, non-invented outputs.
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

BASE = os.environ.get("CAPTURE_BASE", "http://127.0.0.1:8000")
URL = "https://healf.com/en-uk/products/lmnt-recharge-electrolytes-variety-pack"


def post(path, payload):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=150) as r:
        return json.loads(r.read())


def main():
    health = json.loads(urllib.request.urlopen(BASE + "/health").read())
    scenarios = [
        ("Scenario 1 - Reviews", f"{URL}\nDoes this product have any reviews?", None),
        ("Scenario 2 - Ingredient lookup (Vitamin D)", "Does this product have Vitamin D in it?", "session"),
        ("Scenario 3 - Ingredient present (Magnesium)", "Does it contain magnesium?", "session"),
        ("Scenario 4 - Pricing & subscription", "Compare one-time and subscription pricing.", "session"),
        ("Scenario 5 - Availability", "Is it in stock?", "session"),
        ("Scenario 6 - List all ingredients", "What are the ingredients?", "session"),
        ("Scenario 7 - Open-ended page evaluation", "What can I improve on this page?", "session"),
        ("Scenario 8 - Vision: read the product images", "What do the product images show?", "session"),
        ("Scenario 9 - Follow-up: rewrite the top section", "Rewrite the product description.", "session"),
        (
            "Scenario 10 - Compound conversational request",
            "Compare the price and reviews, and tell me which is more persuasive.",
            "session",
        ),
        (
            "Scenario 11 - Contextual follow-up",
            "Why do the reviews matter more here, and what should I be cautious about?",
            "session",
        ),
        (
            "Scenario 12 - Catalogue discovery without a product URL",
            "Do you have any protein bars?",
            None,
        ),
    ]

    out = ["# Example Outputs - Healf Product Intelligence Agent", ""]
    out.append(
        f"_Generated {datetime.now(timezone.utc).isoformat()} from **live** Healf data "
        f"(`{URL}`). LLM configured: **{health['llm_configured']}**._"
    )
    out.append("")
    out.append(
        "> These are real, unedited API responses captured against the running backend. "
        "With no LLM key set, factual answers and the deterministic scorecard are fully live; "
        "LLM-dependent narrative/rewrites fall back to a rule-based response (shown honestly below)."
    )
    out.append("")

    session_id = None
    for title, message, mode in scenarios:
        payload = {"message": message}
        if mode == "session" and session_id:
            payload["session_id"] = session_id
        try:
            resp = post("/api/chat", payload)
        except Exception as e:  # noqa: BLE001
            out.append(f"## {title}\n\n_Request failed: {e}_\n")
            continue
        session_id = resp.get("session_id", session_id)
        out.append(f"## {title}")
        out.append(f"\n**User:** `{message.replace(chr(10), ' [new line] ')}`\n")
        ans = resp["answer"]
        out.append(f"**Intent:** `{ans['intent']}` | **Confidence:** `{ans['confidence']}`\n")
        out.append("**Answer:**\n")
        out.append("> " + ans["text"].replace("\n", "\n> "))
        out.append("")
        if ans.get("limitations"):
            out.append("**Limitations:** " + "; ".join(ans["limitations"]) + "\n")
        if resp.get("evaluation"):
            ev = resp["evaluation"]
            out.append(f"**Overall score:** {ev['overall_score']}/100 (heuristic)\n")
            out.append("| Category | Score | Status |")
            out.append("|---|---:|---|")
            for c in ev["categories"]:
                out.append(f"| {c['label']} | {c['score']} | {c['status']} |")
            out.append("")
            out.append("**Top recommendations:**")
            for r in ev["recommendations"][:3]:
                out.append(f"- **{r['title']}** - {r['suggested_action']}")
            out.append("")
        if resp.get("content_draft"):
            cd = resp["content_draft"]
            out.append(f"**Draft - {cd['title']}:**\n")
            out.append(cd["content"])
            out.append("")
            if cd.get("claims_not_introduced"):
                out.append("**Claims not introduced:** " + "; ".join(cd["claims_not_introduced"]) + "\n")
        if resp.get("evidence"):
            out.append(f"**Evidence ({len(resp['evidence'])} fields):**\n")
            for e in resp["evidence"][:5]:
                ex = (e.get("excerpt") or "").replace("\n", " ")[:120]
                out.append(f"- `{e['field']}` <- {e['source_type']} (conf {e['confidence']}) {('"'+ex+'"') if ex else ''}")
            out.append("")
        out.append("**Suggested follow-ups:** " + ", ".join(resp.get("suggested_actions", [])))
        out.append("\n---\n")

    dest = sys.argv[1] if len(sys.argv) > 1 else "../examples/example_outputs.md"
    rendered = "\n".join(out)
    rendered = "\n".join(line.rstrip() for line in rendered.splitlines()) + "\n"
    with open(dest, "w", encoding="utf-8") as f:
        f.write(rendered)
    print("wrote", dest)


if __name__ == "__main__":
    main()
