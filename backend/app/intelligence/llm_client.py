"""Provider-agnostic LLM JSON client (Anthropic or OpenAI). PRD 20, 31."""
from __future__ import annotations

import json

from ..config import get_settings
from ..models import AppError
from ..utilities.logging import get_logger

log = get_logger("llm")


def is_configured() -> bool:
    return get_settings().llm_configured


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise AppError("LLM_INVALID_RESPONSE", "The model did not return valid JSON.", 502)
    try:
        return json.loads(text[start : end + 1])
    except (ValueError, TypeError):
        raise AppError("LLM_INVALID_RESPONSE", "The model returned malformed JSON.", 502)


async def complete_json(system: str, user: str, *, max_tokens: int = 1500) -> dict:
    """Call the configured provider and return parsed JSON. Raises AppError."""
    s = get_settings()
    if not s.llm_configured:
        raise AppError("LLM_NOT_CONFIGURED", "The evaluation model is not configured.", 503)
    try:
        if s.resolved_provider == "anthropic":
            text = await _anthropic(system, user, max_tokens)
        else:
            text = await _openai(system, user, max_tokens)
    except AppError:
        raise
    except Exception as e:  # noqa: BLE001
        log.warning("LLM call failed: %s", e)
        raise AppError("LLM_TIMEOUT", "The evaluation model did not respond in time.", 504)
    return _extract_json(text)


async def _anthropic(system: str, user: str, max_tokens: int) -> str:
    from anthropic import AsyncAnthropic

    s = get_settings()
    client = AsyncAnthropic(api_key=s.anthropic_api_key, timeout=20.0)
    msg = await client.messages.create(
        model=s.anthropic_model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")


async def _openai(system: str, user: str, max_tokens: int) -> str:
    from openai import AsyncOpenAI

    s = get_settings()
    client = AsyncOpenAI(api_key=s.openai_api_key, timeout=20.0)
    resp = await client.chat.completions.create(
        model=s.openai_model,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return resp.choices[0].message.content or ""
