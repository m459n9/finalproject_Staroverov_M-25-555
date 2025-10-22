from __future__ import annotations

import json
import os
from typing import Dict, List, Optional
from datetime import datetime, timezone

from valutatrade_hub.logging_config import setup_logging
from valutatrade_hub.core.exceptions import ApiRequestError
from .config import CONFIG, ParserConfig
from .api_clients import BaseApiClient, CoinGeckoClient, ExchangeRateApiClient

logger = setup_logging()

def _iso_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _read_json(path: str):
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def _write_atomic_json(path: str, payload) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

class RatesUpdater:
    """
    Координатор обновления курсов: опрашивает клиентов,
    объединяет пары, пишет кэш (rates.json) и историю (exchange_rates.json).
    """

    def __init__(self, config: Optional[ParserConfig] = None) -> None:
        self.config = config or CONFIG
        self.rates_file = self.config.RATES_FILE_PATH
        self.history_file = self.config.HISTORY_FILE_PATH

    def _make_clients(self, only: Optional[str]) -> List[BaseApiClient]:
        only_norm = (only or "").strip().lower()
        clients: List[BaseApiClient] = []
        if not only_norm or only_norm == "coingecko":
            clients.append(CoinGeckoClient(self.config))
        if not only_norm or only_norm == "exchangerate":
            clients.append(ExchangeRateApiClient(self.config))
        if only_norm and not clients:
            raise ValueError("Неизвестный источник. Используйте coingecko или exchangerate.")
        return clients

    def run_update(self, only: Optional[str] = None) -> Dict[str, object]:
        logger.info("Starting rates update...")
        clients = self._make_clients(only)

        merged_pairs: Dict[str, Dict[str, object]] = {}
        history_records: List[Dict[str, object]] = []
        errors: List[str] = []
        ok_sources = 0

        for client in clients:
            try:
                logger.info("Fetching from %s...", client.source_name)
                pairs, hist = client.fetch()
                logger.info("OK: %s returned %d pairs", client.source_name, len(pairs))
                ok_sources += 1

                for k, v in pairs.items():
                    prev = merged_pairs.get(k)
                    if prev is None:
                        merged_pairs[k] = dict(v)
                    else:
                        prev_ts = str(prev.get("updated_at", ""))
                        cur_ts = str(v.get("updated_at", ""))
                        if cur_ts > prev_ts:
                            merged_pairs[k] = dict(v)

                history_records.extend(hist)

            except ApiRequestError as e:
                logger.error("Failed to fetch from %s: %s", client.source_name, e)
                errors.append(f"{client.source_name}: {e}")

        last_refresh = _iso_now_z()

        cache_payload = {"pairs": merged_pairs, "last_refresh": last_refresh}
        logger.info("Writing %d pairs to %s ...", len(merged_pairs), self.rates_file)
        _write_atomic_json(self.rates_file, cache_payload)

        logger.info("Appending %d records to %s ...", len(history_records), self.history_file)
        existing = _read_json(self.history_file)
        if not isinstance(existing, list):
            existing = []
        existing.extend(history_records)
        _write_atomic_json(self.history_file, existing)

        status = "success" if ok_sources > 0 and not errors else ("partial" if ok_sources > 0 else "failed")
        logger.info("Update finished: status=%s ok=%d err=%d last_refresh=%s", status, ok_sources, len(errors), last_refresh)

        return {
            "status": status,
            "ok_sources": ok_sources,
            "errors": errors,
            "pairs_count": len(merged_pairs),
            "last_refresh": last_refresh,
        }