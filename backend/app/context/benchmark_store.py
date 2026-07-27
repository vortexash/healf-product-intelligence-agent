"""Load an optional, generated Healf listing benchmark (PRD 19).

The benchmark is produced by scripts/build_benchmark.py from live pages. If no
benchmark file exists, evaluation stays product-specific and is labelled as such
(no invented values, no whole-catalogue claims).
"""
from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

_BENCH_PATH = Path(__file__).resolve().parents[2] / "data" / "benchmark.json"


class Benchmark(BaseModel):
    sample_size: int
    generated_at: str
    median_description_words: int | None = None
    median_image_count: int | None = None
    alt_text_coverage: float | None = None
    ingredient_section_rate: float | None = None
    suggested_use_rate: float | None = None
    review_presence_rate: float | None = None
    subscription_rate: float | None = None
    common_sections: list[str] = []


_cache: Benchmark | None = None
_loaded = False


def load_benchmark() -> Benchmark | None:
    global _cache, _loaded
    if _loaded:
        return _cache
    _loaded = True
    if _BENCH_PATH.exists():
        try:
            _cache = Benchmark(**json.loads(_BENCH_PATH.read_text(encoding="utf-8")))
        except (ValueError, TypeError):
            _cache = None
    return _cache
