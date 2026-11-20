"""日志：控制台 + 滚动文件（bazaar_config/logs/<name>_YYYYMMDD.log）。"""

from __future__ import annotations

import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

_configured: set[tuple[str, str]] = set()


def get_logger(name: str, log_dir: Path, level: int = logging.INFO) -> logging.Logger:
    key = (name, str(log_dir))
    logger = logging.getLogger(f"sbz.{name}")
    if key in _configured:
        return logger
    log_dir.mkdir(parents=True, exist_ok=True)
    logger.setLevel(level)
    logger.propagate = False
    fmt = logging.Formatter("%(asctime)s.%(msecs)03d %(levelname)-5s %(message)s", "%Y-%m-%d %H:%M:%S")

    stream = logging.StreamHandler()
    stream.setFormatter(fmt)
    logger.addHandler(stream)

    path = log_dir / f"{name}_{datetime.now():%Y%m%d}.log"
    handler = RotatingFileHandler(path, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(fmt)
    logger.addHandler(handler)

    _configured.add(key)
    return logger
