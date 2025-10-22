# valutatrade_hub/parser_service/storage.py
from __future__ import annotations

import json
import os
import tempfile
from typing import Dict, Any, List

from valutatrade_hub.logging_config import setup_logging
from valutatrade_hub.infra.settings import SettingsLoader
from valutatrade_hub.infra.database import DatabaseManager

logger = setup_logging()

class RatesStorage:
    """Хранилище для кэша курсов (rates.json) и истории (exchange_rates.json)."""

    def __init__(self) -> None:
        self.settings = SettingsLoader()
        self.db = DatabaseManager()

    def _atomic_write(self, path: str, payload: Any) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".tmp", dir=os.path.dirname(path))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
        finally:
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except Exception:
                pass

    def write_snapshot(self, pairs: Dict[str, Dict[str, Any]], last_refresh: str) -> None:
        """Снимок текущих курсов в rates.json (формат, который читает Core)."""
        snapshot = {
            "pairs": pairs,  
            "last_refresh": last_refresh,
        }
        logger.info(f"Writing {len(pairs)} pairs to {self.settings.rates_file} ...")
        self._atomic_write(self.settings.rates_file, snapshot)

    def append_history(self, records: List[Dict[str, Any]]) -> None:
        """Добавляет записи в историю exchange_rates.json как список."""
        path = self.settings.exchange_rates_file
        logger.info(f"Appending {len(records)} records to {path} ...")

        try:
            existing = self.db.read_json(path)
        except Exception:
            existing = None

        if not isinstance(existing, list):
            existing = []

        existing.extend(records)
        self._atomic_write(path, existing)