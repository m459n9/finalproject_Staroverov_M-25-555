# valutatrade_hub/logging_config.py
from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
import os
from datetime import datetime

from valutatrade_hub.infra.settings import SettingsLoader

def _make_formatter(fmt_kind: str):
    if fmt_kind.upper() == "JSON":
        class JsonFormatter(logging.Formatter):
            def format(self, record: logging.LogRecord) -> str:
                payload = {
                    "ts": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"),
                    "level": record.levelname,
                    "logger": record.name,
                    "msg": record.getMessage(),
                }
                return json.dumps(payload, ensure_ascii=False)
        return JsonFormatter()
    else:
        return logging.Formatter(
            fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

def setup_logging() -> logging.Logger:
    """
    Инициализирует:
      - app-логгер: valutatrade_hub -> logs/valutatrade_hub.log
      - actions-логгер: vth.actions -> logs/actions.log
    Строковый формат по умолчанию, уровень INFO (из настроек).
    """
    settings = SettingsLoader()
    os.makedirs(settings.logs_dir, exist_ok=True)

    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    fmt = _make_formatter(settings.log_format)

    app_logger = logging.getLogger("valutatrade_hub")
    if not app_logger.handlers:
        app_logger.setLevel(level)

        sh = logging.StreamHandler()
        sh.setLevel(level)
        sh.setFormatter(fmt)

        fh = RotatingFileHandler(settings.app_log_path, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        fh.setLevel(level)
        fh.setFormatter(fmt)

        app_logger.addHandler(sh)
        app_logger.addHandler(fh)
        app_logger.propagate = False
        app_logger.info("Logging initialized")

    actions = logging.getLogger("vth.actions")
    if not actions.handlers:
        actions.setLevel(level)
        fh2 = RotatingFileHandler(settings.actions_log_path, maxBytes=1_000_000, backupCount=5, encoding="utf-8")
        fh2.setLevel(level)
        fh2.setFormatter(fmt)
        actions.addHandler(fh2)
        actions.propagate = False

    return app_logger