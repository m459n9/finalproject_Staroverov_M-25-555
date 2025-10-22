from __future__ import annotations

import time
from typing import Dict, Any, Tuple, List, Optional
from datetime import datetime, timezone

import requests

from valutatrade_hub.logging_config import setup_logging
from valutatrade_hub.core.exceptions import ApiRequestError
from .config import CONFIG, ParserConfig

logger = setup_logging()

def _iso_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

class BaseApiClient:
    """
    Базовый контракт для клиентов внешних API.

    fetch() -> (pairs, history)
      pairs: dict для актуального кэша rates.json:
        {
          "BTC_USD": {"rate": 59337.21, "updated_at": "2025-10-10T12:00:00Z", "source": "CoinGecko"},
          ...
        }
      history: list записей для exchange_rates.json:
        [
          {
            "id": "BTC_USD_2025-10-10T12:00:00Z",
            "from_currency": "BTC",
            "to_currency": "USD",
            "rate": 59337.21,
            "timestamp": "2025-10-10T12:00:00Z",
            "source": "CoinGecko",
            "meta": {...}
          },
          ...
        ]
    """
    source_name: str = "Base"

    def fetch(self) -> Tuple[Dict[str, Dict[str, Any]], List[Dict[str, Any]]]:
        raise NotImplementedError

class CoinGeckoClient(BaseApiClient):
    source_name = "CoinGecko"

    def __init__(self, config: Optional[ParserConfig] = None) -> None:
        self.config = config or CONFIG
        self.base = self.config.BASE_FIAT_CURRENCY.lower()
        self.ids = ",".join(self.config.CRYPTO_ID_MAP.values())

    def fetch(self) -> Tuple[Dict[str, Dict[str, Any]], List[Dict[str, Any]]]:
        if not self.ids:
            return {}, []

        url = f"{self.config.COINGECKO_URL}?ids={self.ids}&vs_currencies={self.base}"
        t0 = time.perf_counter()
        try:
            resp = requests.get(url, timeout=self.config.REQUEST_TIMEOUT)
        except requests.RequestException as e:
            raise ApiRequestError(f"Ошибка при обращении к внешнему API: {e}") from e

        ms = int((time.perf_counter() - t0) * 1000)
        etag = resp.headers.get("ETag", "")

        if resp.status_code == 429:
            raise ApiRequestError("Ошибка при обращении к внешнему API: 429 Too Many Requests (CoinGecko)")
        if not resp.ok:
            raise ApiRequestError(f"Ошибка при обращении к внешнему API: HTTP {resp.status_code} (CoinGecko)")

        try:
            data = resp.json()
        except Exception as e:
            raise ApiRequestError(f"Ошибка при обращении к внешнему API: некорректный JSON ({e})") from e

        updated_at_z = _iso_now_z()
        pairs: Dict[str, Dict[str, Any]] = {}
        history: List[Dict[str, Any]] = []

        for code, raw_id in self.config.CRYPTO_ID_MAP.items():
            entry = data.get(raw_id) or {}
            rate = entry.get(self.base)
            if not isinstance(rate, (int, float)):
                continue

            pair_key = f"{code.upper()}_{self.config.BASE_FIAT_CURRENCY.upper()}"
            pairs[pair_key] = {"rate": float(rate), "updated_at": updated_at_z, "source": self.source_name}

            rec_id = f"{code.upper()}_{self.config.BASE_FIAT_CURRENCY.upper()}_{updated_at_z}"
            history.append({
                "id": rec_id,
                "from_currency": code.upper(),
                "to_currency": self.config.BASE_FIAT_CURRENCY.upper(),
                "rate": float(rate),
                "timestamp": updated_at_z,
                "source": self.source_name,
                "meta": {
                    "raw_id": raw_id,
                    "request_ms": ms,
                    "status_code": resp.status_code,
                    "etag": etag,
                }
            })

        return pairs, history

class ExchangeRateApiClient(BaseApiClient):
    source_name = "ExchangeRate-API"

    def __init__(self, config: Optional[ParserConfig] = None) -> None:
        self.config = config or CONFIG
        self.key = self.config.EXCHANGERATE_API_KEY
        self.base = self.config.BASE_FIAT_CURRENCY.upper()

    def fetch(self) -> Tuple[Dict[str, Dict[str, Any]], List[Dict[str, Any]]]:
        if not self.key:
            raise ApiRequestError("Ошибка при обращении к внешнему API: отсутствует EXCHANGERATE_API_KEY")

        url = f"{self.config.EXCHANGERATE_API_URL}/{self.key}/latest/{self.base}"
        t0 = time.perf_counter()
        try:
            resp = requests.get(url, timeout=self.config.REQUEST_TIMEOUT)
        except requests.RequestException as e:
            raise ApiRequestError(f"Ошибка при обращении к внешнему API: {e}") from e

        ms = int((time.perf_counter() - t0) * 1000)
        etag = resp.headers.get("ETag", "")

        if resp.status_code == 401:
            raise ApiRequestError("Ошибка при обращении к внешнему API: 401 Unauthorized (проверьте ключ)")
        if resp.status_code == 429:
            raise ApiRequestError("Ошибка при обращении к внешнему API: 429 Too Many Requests")
        if not resp.ok:
            raise ApiRequestError(f"Ошибка при обращении к внешнему API: HTTP {resp.status_code}")

        try:
            data = resp.json()
        except Exception as e:
            raise ApiRequestError(f"Ошибка при обращении к внешнему API: некорректный JSON ({e})") from e

        if data.get("result") != "success":
            raise ApiRequestError("Ошибка при обращении к внешнему API: статус не success")

        rates = data.get("rates", {}) or {}
        updated_at_z = _iso_now_z()

        pairs: Dict[str, Dict[str, Any]] = {}
        history: List[Dict[str, Any]] = []

        for code in self.config.FIAT_CURRENCIES:
            rate = rates.get(code)
            if not isinstance(rate, (int, float)):
                continue

            pair_key = f"{code.upper()}_{self.base}"
            pairs[pair_key] = {"rate": float(rate), "updated_at": updated_at_z, "source": self.source_name}

            rec_id = f"{code.upper()}_{self.base}_{updated_at_z}"
            history.append({
                "id": rec_id,
                "from_currency": code.upper(),
                "to_currency": self.base,
                "rate": float(rate),
                "timestamp": updated_at_z,
                "source": self.source_name,
                "meta": {
                    "raw_id": code.upper(),
                    "request_ms": ms,
                    "status_code": resp.status_code,
                    "etag": etag,
                }
            })

        return pairs, history