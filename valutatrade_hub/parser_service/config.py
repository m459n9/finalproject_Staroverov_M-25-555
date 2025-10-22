from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Tuple, Dict, Optional
from valutatrade_hub.infra.settings import SettingsLoader

@dataclass(frozen=True)
class ParserConfig:
    """
    Конфигурация Parser Service.

    Поля:
      EXCHANGERATE_API_KEY: ключ ExchangeRate-API (env EXCHANGERATE_API_KEY)
      COINGECKO_URL: базовый URL CoinGecko simple/price
      EXCHANGERATE_API_URL: базовый URL ExchangeRate-API v6
      BASE_FIAT_CURRENCY: базовая валюта (обычно USD)
      FIAT_CURRENCIES: список фиатных кодов для запроса
      CRYPTO_ID_MAP: соответствие тикеров CoinGecko id
      REQUEST_TIMEOUT: таймаут HTTP-запросов (сек)
      RATES_FILE_PATH: путь к текущему срезу курсов (совпадает с Core)
      HISTORY_FILE_PATH: путь к журналу истории измерений
    """
    EXCHANGERATE_API_KEY: Optional[str] = None
    COINGECKO_URL: Optional[str] = None
    EXCHANGERATE_API_URL: Optional[str] = None

    BASE_FIAT_CURRENCY: Optional[str] = None
    FIAT_CURRENCIES: Optional[Tuple[str, ...]] = None
    CRYPTO_ID_MAP: Optional[Dict[str, str]] = None

    REQUEST_TIMEOUT: Optional[int] = None
    RATES_FILE_PATH: Optional[str] = None
    HISTORY_FILE_PATH: Optional[str] = None

    def __post_init__(self) -> None:
        if all([
            self.EXCHANGERATE_API_KEY is not None,
            self.COINGECKO_URL is not None,
            self.EXCHANGERATE_API_URL is not None,
            self.BASE_FIAT_CURRENCY is not None,
            self.FIAT_CURRENCIES is not None,
            self.CRYPTO_ID_MAP is not None,
            self.REQUEST_TIMEOUT is not None,
            self.RATES_FILE_PATH is not None,
            self.HISTORY_FILE_PATH is not None,
        ]):
            return

        object.__setattr__(self, "_ParserConfig__loaded", True)  
        settings = SettingsLoader()

        base_currency = (os.getenv("PARSER_BASE_CURRENCY") or settings.default_base).upper()

        fiat_env = os.getenv("PARSER_FIAT_CURRENCIES", "")
        if fiat_env.strip():
            fiat_tuple: Tuple[str, ...] = tuple(
                c.strip().upper() for c in fiat_env.split(",") if c.strip()
            )
        else:
            fiat_tuple = ("EUR", "GBP", "RUB")

        crypto_id_map: Dict[str, str] = {
            "BTC": "bitcoin",
            "ETH": "ethereum",
            "SOL": "solana",
        }

        rates_file = settings.rates_file
        history_file = os.path.join(settings.data_dir, "exchange_rates.json")

        object.__setattr__(self, "EXCHANGERATE_API_KEY", os.getenv("EXCHANGERATE_API_KEY"))
        object.__setattr__(self, "COINGECKO_URL", "https://api.coingecko.com/api/v3/simple/price")
        object.__setattr__(self, "EXCHANGERATE_API_URL", "https://v6.exchangerate-api.com/v6")

        object.__setattr__(self, "BASE_FIAT_CURRENCY", base_currency)
        object.__setattr__(self, "FIAT_CURRENCIES", fiat_tuple)
        object.__setattr__(self, "CRYPTO_ID_MAP", crypto_id_map)

        object.__setattr__(self, "REQUEST_TIMEOUT", int(os.getenv("PARSER_REQUEST_TIMEOUT", "10")))
        object.__setattr__(self, "RATES_FILE_PATH", rates_file)
        object.__setattr__(self, "HISTORY_FILE_PATH", history_file)


def _build_config() -> ParserConfig:
    return ParserConfig() 

CONFIG: ParserConfig = _build_config()

__all__ = ["ParserConfig", "CONFIG"]