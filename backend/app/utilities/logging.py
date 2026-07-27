"""Minimal structured logging setup."""
from __future__ import annotations

import logging

from ..config import get_settings


def configure() -> None:
    logging.basicConfig(
        level=get_settings().log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
