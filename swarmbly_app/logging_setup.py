"""Logging setup: rotating file in the data directory + console."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

_configured = False


def configure(data_dir: Path, level: int = logging.INFO) -> logging.Logger:
    global _configured
    logger = logging.getLogger("swarmbly")
    if _configured:
        return logger
    logger.setLevel(level)
    data_dir.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        data_dir / "swarmbly.log", maxBytes=2_000_000, backupCount=3,
        encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s"))
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    logger.addHandler(file_handler)
    logger.addHandler(console)
    _configured = True
    return logger


def get_logger(name: str = "swarmbly") -> logging.Logger:
    return logging.getLogger(name)
