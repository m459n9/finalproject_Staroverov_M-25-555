# valutatrade_hub/infra/database.py
from __future__ import annotations

import json
import os
import shutil
import tempfile
from typing import Any

from .settings import SettingsLoader

class DatabaseManager:
    """Singleton менеджер файловой БД."""
    _instance: "DatabaseManager" = None  

    def __new__(cls, *args, **kwargs):
        if cls._instance is not None:
            return cls._instance
        inst = super().__new__(cls)
        cls._instance = inst
        return inst

    def __init__(self) -> None:
        self.settings = SettingsLoader()
        os.makedirs(self.settings.data_dir, exist_ok=True)

    def _atomic_write(self, path: str, payload: Any) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".tmp_", dir=os.path.dirname(path))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            shutil.move(tmp, path)
        finally:
            try:
                if os.path.exists(tmp):
                    os.unlink(tmp)
            except Exception:
                pass

    def read_json(self, path: str) -> Any:
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            if path.endswith("users.json") or path.endswith("portfolios.json"):
                self._atomic_write(path, [])
            elif path.endswith("rates.json"):
                self._atomic_write(path, {"source": "LocalCache"})
            elif path.endswith("session.json"):
                self._atomic_write(path, {"current_user": None})
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def write_json(self, path: str, payload: Any) -> None:
        self._atomic_write(path, payload)