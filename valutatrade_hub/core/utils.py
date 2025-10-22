# valutatrade_hub/core/utils.py
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Tuple

from .exceptions import ValidationError, CurrencyNotFoundError
from .currencies import is_known_code

def now_iso() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")

def normalize_currency(code: str) -> str:
    if not isinstance(code, str):
        raise ValidationError("currency_code должен быть строкой")
    c = code.strip().upper()
    if not c:
        raise ValidationError("Код валюты не должен быть пустым")
    if not is_known_code(c):
        raise CurrencyNotFoundError(f"Неизвестная валюта '{c}'")
    return c

def parse_positive_amount(x) -> Decimal:
    try:
        d = Decimal(str(x))
    except Exception as e:
        raise ValidationError("'amount' должен быть числом") from e
    if d <= 0:
        raise ValidationError("'amount' должен быть положительным числом")
    return d

def pair_key(frm: str, to: str) -> str:
    return f"{frm}_{to}"

def parse_rate_obj(rate_obj: dict) -> Tuple[Decimal, str]:
    rate = Decimal(str(rate_obj["rate"]))
    updated = str(rate_obj.get("updated_at", ""))
    return rate, updated