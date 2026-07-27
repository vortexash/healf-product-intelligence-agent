"""Application configuration loaded from environment."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel

# Load backend/.env if present so `cp .env.example .env` + a key just works.
load_dotenv(Path(__file__).resolve().parents[1] / ".env")


class Settings(BaseModel):
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    frontend_origin: str = "http://localhost:3000"

    llm_provider: str = "anthropic"  # "anthropic" | "openai"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-opus-4-8"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o"

    http_user_agent: str = "HealfProductIntelligenceMVP/1.0"
    product_cache_ttl_seconds: int = 600
    session_ttl_seconds: int = 3600
    request_timeout_seconds: int = 20
    log_level: str = "INFO"

    @property
    def resolved_provider(self) -> str:
        """The provider actually usable at runtime.

        Honors LLM_PROVIDER (case-insensitive) when that provider's key is set;
        otherwise infers from whichever key IS present. This means setting just
        OPENAI_API_KEY (or just ANTHROPIC_API_KEY) is enough — no need to also
        remember LLM_PROVIDER.
        """
        p = (self.llm_provider or "").strip().lower()
        if p == "openai" and self.openai_api_key:
            return "openai"
        if p == "anthropic" and self.anthropic_api_key:
            return "anthropic"
        if self.openai_api_key:
            return "openai"
        if self.anthropic_api_key:
            return "anthropic"
        return p or "anthropic"

    @property
    def llm_configured(self) -> bool:
        rp = self.resolved_provider
        if rp == "openai":
            return bool(self.openai_api_key)
        if rp == "anthropic":
            return bool(self.anthropic_api_key)
        return False


@lru_cache
def get_settings() -> Settings:
    e = os.environ.get
    return Settings(
        app_env=e("APP_ENV", "development"),
        app_host=e("APP_HOST", "0.0.0.0"),
        app_port=int(e("APP_PORT", "8000")),
        frontend_origin=e("FRONTEND_ORIGIN", "http://localhost:3000"),
        llm_provider=e("LLM_PROVIDER", "anthropic"),
        anthropic_api_key=e("ANTHROPIC_API_KEY") or None,
        anthropic_model=e("ANTHROPIC_MODEL") or "claude-opus-4-8",
        openai_api_key=e("OPENAI_API_KEY") or None,
        openai_model=e("OPENAI_MODEL") or "gpt-4o",
        http_user_agent=e("HTTP_USER_AGENT", "HealfProductIntelligenceMVP/1.0"),
        product_cache_ttl_seconds=int(e("PRODUCT_CACHE_TTL_SECONDS", "600")),
        session_ttl_seconds=int(e("SESSION_TTL_SECONDS", "3600")),
        request_timeout_seconds=int(e("REQUEST_TIMEOUT_SECONDS", "20")),
        log_level=e("LOG_LEVEL", "INFO"),
    )
