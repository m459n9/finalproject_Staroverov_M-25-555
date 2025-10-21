# valutatrade_hub/core/currencies.py
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict

from .exceptions import CurrencyNotFoundError, ValidationError

def _normalize_code(code: str) -> str:
    if not isinstance(code, str):
        raise ValidationError("code должен быть строкой")
    c = code.strip().upper()
    if not (2 <= len(c) <= 5) or " " in c or not c.isalnum():
        raise ValidationError("Некорректный код валюты (верхний регистр, 2–5 символов, без пробелов)")
    return c

def _validate_name(name: str) -> str:
    if not isinstance(name, str):
        raise ValidationError("name должен быть строкой")
    n = name.strip()
    if not n:
        raise ValidationError("name не может быть пустым")
    return n

class Currency(ABC):
    name: str
    code: str

    def __init__(self, name: str, code: str) -> None:
        self.name = _validate_name(name)
        self.code = _normalize_code(code)

    @abstractmethod
    def get_display_info(self) -> str: ...

@dataclass(frozen=True, slots=True)
class FiatCurrency(Currency):
    name: str
    code: str
    issuing_country: str

    def __init__(self, name: str, code: str, issuing_country: str) -> None:
        object.__setattr__(self, "name", _validate_name(name))
        object.__setattr__(self, "code", _normalize_code(code))
        if not isinstance(issuing_country, str) or not issuing_country.strip():
            raise ValidationError("issuing_country не может быть пустым")
        object.__setattr__(self, "issuing_country", issuing_country.strip())

    def get_display_info(self) -> str:
        return f"[FIAT] {self.code} — {self.name} (Issuing: {self.issuing_country})"

@dataclass(frozen=True, slots=True)
class CryptoCurrency(Currency):
    name: str
    code: str
    algorithm: str
    market_cap: float

    def __init__(self, name: str, code: str, algorithm: str, market_cap: float) -> None:
        object.__setattr__(self, "name", _validate_name(name))
        object.__setattr__(self, "code", _normalize_code(code))
        if not isinstance(algorithm, str) or not algorithm.strip():
            raise ValidationError("algorithm не может быть пустым")
        object.__setattr__(self, "algorithm", algorithm.strip())
        try:
            mc = float(market_cap)
        except Exception as e:
            raise ValidationError("market_cap должен быть числом") from e
        if mc < 0:
            raise ValidationError("market_cap не может быть отрицательным")
        object.__setattr__(self, "market_cap", mc)

    def get_display_info(self) -> str:
        return f"[CRYPTO] {self.code} — {self.name} (Algo: {self.algorithm}, MCAP: {self.market_cap:.2e})"


_REG: Dict[str, Currency] = {}

def register_currency(curr: Currency) -> None:
    _REG[curr.code] = curr

def get_currency(code: str) -> Currency:
    key = _normalize_code(code)
    if key not in _REG:
        raise CurrencyNotFoundError(f"Неизвестная валюта '{key}'")
    return _REG[key]

def is_known_code(code: str) -> bool:
    try:
        get_currency(code)
        return True
    except CurrencyNotFoundError:
        return False

def list_currencies() -> list[Currency]:
    return list(_REG.values())

register_currency(FiatCurrency("US Dollar", "USD", "United States"))
register_currency(FiatCurrency("Euro", "EUR", "Eurozone"))
register_currency(FiatCurrency("Russian Ruble", "RUB", "Russia"))

register_currency(CryptoCurrency("Bitcoin", "BTC", "SHA-256", 1.2e12))
register_currency(CryptoCurrency("Ethereum", "ETH", "Ethash", 4.5e11))
register_currency(CryptoCurrency("Tether", "USDT", "n/a", 1.1e11))