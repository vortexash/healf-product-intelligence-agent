"""Build a live Healf listing benchmark (PRD 19).

Ingests 5-10 live Healf product pages, computes aggregate metrics, and writes
backend/data/benchmark.json. Non-product / failing URLs are skipped. No values
are invented — every metric comes from live pages, and sample_size is recorded.

Usage:
    python scripts/build_benchmark.py handle1 handle2 ...
    python scripts/build_benchmark.py --file candidates.txt --target 8
"""
from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ingestion import ingest_product  # noqa: E402
from app.models import AppError  # noqa: E402
from app.navigation import parse_and_validate  # noqa: E402
from app.utilities import word_count  # noqa: E402

DATA = Path(__file__).resolve().parents[1] / "data"


async def _ingest(handle: str):
    url = f"https://healf.com/en-uk/products/{handle}"
    try:
        parsed = parse_and_validate(url)
        p = await asyncio.wait_for(ingest_product(parsed), timeout=25)
    except (AppError, asyncio.TimeoutError, Exception):  # noqa: BLE001
        return None
    # Require it to look like a real product.
    if not p.title or not p.one_time_price:
        return None
    return p


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("handles", nargs="*")
    ap.add_argument("--file")
    ap.add_argument("--target", type=int, default=8)
    args = ap.parse_args()

    candidates = list(args.handles)
    if args.file:
        candidates += [h.strip() for h in Path(args.file).read_text().splitlines() if h.strip()]

    products = []
    headings_counter: dict[str, int] = {}
    for h in candidates:
        if len(products) >= args.target:
            break
        p = await _ingest(h)
        if not p:
            print(f"  skip {h}")
            continue
        products.append(p)
        print(f"  ok {h} - {p.title}")
        # Count which normalized sections were present, not flavour-group names.
        present_sections = {
            "Product Description": bool(p.description_text),
            "Key Benefits": bool(p.benefits),
            "Ingredients": bool(p.ingredients_raw),
            "Suggested Use": bool(p.suggested_use),
            "Warnings": bool(p.warnings),
        }
        for name, present in present_sections.items():
            if present:
                headings_counter[name] = headings_counter.get(name, 0) + 1

    if len(products) < 3:
        print(f"Only {len(products)} products ingested — too few for a benchmark. Aborting.")
        sys.exit(1)

    n = len(products)
    desc_words = [word_count(p.description_text) for p in products]
    img_counts = [len(p.images) for p in products]
    alt_cov = [
        (sum(1 for i in p.images if i.alt_text) / len(p.images)) if p.images else 0.0 for p in products
    ]
    common_sections = sorted(headings_counter, key=headings_counter.get, reverse=True)[:8]

    bench = {
        "sample_size": n,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "median_description_words": int(statistics.median(desc_words)),
        "median_image_count": int(statistics.median(img_counts)),
        "alt_text_coverage": round(statistics.mean(alt_cov), 3),
        "ingredient_section_rate": round(sum(1 for p in products if p.ingredients_raw) / n, 3),
        "suggested_use_rate": round(sum(1 for p in products if p.suggested_use) / n, 3),
        "review_presence_rate": round(sum(1 for p in products if p.reviews.present) / n, 3),
        "subscription_rate": round(sum(1 for p in products if p.subscription_price) / n, 3),
        "common_sections": common_sections,
        "sampled_handles": [p.handle for p in products],
    }
    DATA.mkdir(exist_ok=True)
    (DATA / "benchmark.json").write_text(json.dumps(bench, indent=2), encoding="utf-8")
    print(f"\nWrote {DATA / 'benchmark.json'} (sample_size={n})")


if __name__ == "__main__":
    asyncio.run(main())
