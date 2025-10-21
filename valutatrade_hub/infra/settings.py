# valutatrade_hub/infra/settings.py
from __future__ import annotations

import os
import json
from typing import Any, ClassVar, Optional

class SettingsLoader:
    """
    Синглтон конфигурации приложения.

    Источники:
    1) env-переменные (имеют приоритет)
    2) файл конфигурации (tool.valutatrade / config.json)
    3) дефолты

    Публичные методы:
      - get(key: str, default=...) -> Any
      - reload() -> None  (перечитать конфигурацию)
    """
    _instance: ClassVar[Optional["SettingsLoader"]] = None

    _DEFAULTS = {
        "DATA_DIR": "data",
        "LOGS_DIR": "logs",
        "RATES_TTL_SECONDS": 300,
        "DEFAULT_BASE": "USD",
        "USERS_FILE": "users.json",
        "PORTFOLIOS_FILE": "portfolios.json",
        "RATES_FILE": "rates.json",
        "SESSION_FILE": "session.json",
        "LOG_FORMAT": "STRING", 
        "LOG_LEVEL": "INFO",
        "ACTIONS_LOG": "actions.log",
        "APP_LOG": "valutatrade_hub.log",
    }

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
        self._cfg: dict[str, Any] = {}
        self._load()
        self._initialized = True

    def get(self, key: str, default: Any = None) -> Any:
        return self._cfg.get(key, default)

    def reload(self) -> None:
        self._load()

    def _load(self) -> None:
        root = os.getcwd()

        cfg = dict(self._DEFAULTS)

        cfg_path = os.getenv("VTH_CONFIG", os.path.join(root, "config.json"))
        if os.path.exists(cfg_path):
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    user_cfg = json.load(f) or {}
                for k, v in user_cfg.items():
                    cfg[k.upper()] = v
            except Exception:
                pass

        for k in list(cfg.keys()):
            env_key = f"VTH_{k}"
            if env_key in os.environ:
                val = os.environ[env_key]
                if k.endswith("_SECONDS"):
                    try:
                        val = int(val)
                    except Exception:
                        pass
                cfg[k] = val

        data_dir = cfg["DATA_DIR"] if os.path.isabs(cfg["DATA_DIR"]) else os.path.join(root, cfg["DATA_DIR"])
        logs_dir = cfg["LOGS_DIR"] if os.path.isabs(cfg["LOGS_DIR"]) else os.path.join(root, cfg["LOGS_DIR"])

        cfg["DATA_DIR"] = data_dir
        cfg["LOGS_DIR"] = logs_dir
        cfg["USERS_FILE_FULL"] = os.path.join(data_dir, cfg["USERS_FILE"])
        cfg["PORTFOLIOS_FILE_FULL"] = os.path.join(data_dir, cfg["PORTFOLIOS_FILE"])
        cfg["RATES_FILE_FULL"] = os.path.join(data_dir, cfg["RATES_FILE"])
        cfg["SESSION_FILE_FULL"] = os.path.join(data_dir, cfg["SESSION_FILE"])
        cfg["APP_LOG_FULL"] = os.path.join(logs_dir, cfg["APP_LOG"])
        cfg["ACTIONS_LOG_FULL"] = os.path.join(logs_dir, cfg["ACTIONS_LOG"])

        self._cfg = cfg

    @property
    def data_dir(self) -> str: return self._cfg["DATA_DIR"]
    @property
    def logs_dir(self) -> str: return self._cfg["LOGS_DIR"]
    @property
    def ttl_seconds(self) -> int: return int(self._cfg["RATES_TTL_SECONDS"])
    @property
    def default_base(self) -> str: return self._cfg["DEFAULT_BASE"]
    @property
    def users_file(self) -> str: return self._cfg["USERS_FILE_FULL"]
    @property
    def portfolios_file(self) -> str: return self._cfg["PORTFOLIOS_FILE_FULL"]
    @property
    def rates_file(self) -> str: return self._cfg["RATES_FILE_FULL"]
    @property
    def session_file(self) -> str: return self._cfg["SESSION_FILE_FULL"]
    @property
    def app_log_path(self) -> str: return self._cfg["APP_LOG_FULL"]
    @property
    def actions_log_path(self) -> str: return self._cfg["ACTIONS_LOG_FULL"]
    @property
    def log_format(self) -> str: return self._cfg["LOG_FORMAT"]
    @property
    def log_level(self) -> str: return self._cfg["LOG_LEVEL"]