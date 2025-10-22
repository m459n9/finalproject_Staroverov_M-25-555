# valutatrade_hub/core/models.py
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, getcontext, ROUND_HALF_UP
from typing import Callable, Mapping, Optional, Dict, Tuple
import hashlib
import secrets
import re
import copy

__all__ = [
    "User",
    "Wallet",
    "Portfolio",
    "InsufficientFundsError",
    "CurrencyNotFoundError",
    "UserAlreadyExistsError",
]

getcontext().prec = 28
_DEC_FIAT_Q = Decimal("0.01")
_DEC_CRYPTO_Q = Decimal("0.00000001")

CURRENCY_PRECISION: dict[str, Decimal] = {
    "USD": _DEC_FIAT_Q,
    "EUR": _DEC_FIAT_Q,
    "RUB": _DEC_FIAT_Q,
    "USDT": _DEC_CRYPTO_Q,
    "BTC": _DEC_CRYPTO_Q,
    "ETH": _DEC_CRYPTO_Q,
}

_CCY_CODE_RE = re.compile(r"^[A-Z0-9]{2,10}$")

class InsufficientFundsError(RuntimeError):
    """Недостаточно средств на кошельке."""

class CurrencyNotFoundError(RuntimeError):
    """Код валюты не найден в портфеле/курсах."""

class UserAlreadyExistsError(RuntimeError):
    """Пользователь с таким username уже существует."""

def _ensure_upper_currency(code: str) -> str:
    if not isinstance(code, str):
        raise TypeError("currency_code должен быть строкой")
    code = code.strip().upper()
    if not code or not _CCY_CODE_RE.match(code):
        raise ValueError(f"Некорректный код валюты '{code}'")
    return code

def _quantize_for_currency(code: str, amount: Decimal) -> Decimal:
    q = CURRENCY_PRECISION.get(code.upper(), _DEC_FIAT_Q)
    return amount.quantize(q, rounding=ROUND_HALF_UP)

def _to_decimal(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception as e:
        raise TypeError(f"Невозможно привести значение к Decimal: {value!r}") from e

def _hash_password(password: str, salt: str) -> str:
    """
    Односторонний псевдо-хэш: sha256(salt + password)
    """
    if not isinstance(password, str):
        raise TypeError("Пароль должен быть строкой")
    if not isinstance(salt, str):
        raise TypeError("Соль должна быть строкой")
    payload = (salt + password).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()

class User:
    """
    Модель пользователя.
    Хранит приватные поля и безопасно работает с паролем.
    """

    def __init__(
        self,
        user_id: int,
        username: str,
        hashed_password: str,
        salt: str,
        registration_date: datetime,
    ) -> None:
        self._user_id: int = int(user_id)
        self.username = username  
        self._hashed_password: str = str(hashed_password)
        self._salt: str = str(salt)
        if not isinstance(registration_date, datetime):
            raise TypeError("registration_date должен быть datetime")
        self._registration_date: datetime = registration_date.replace(tzinfo=None)

    @property
    def user_id(self) -> int:
        return self._user_id

    @property
    def username(self) -> str:
        return self._username

    @username.setter
    def username(self, value: str) -> None:
        if not isinstance(value, str):
            raise TypeError("username должен быть строкой")
        value = value.strip()
        if not value:
            raise ValueError("Имя пользователя не может быть пустым")
        self._username = value

    @property
    def registration_date(self) -> datetime:
        return self._registration_date

    def change_password(self, new_password: str) -> None:
        if not isinstance(new_password, str):
            raise TypeError("Пароль должен быть строкой")
        if len(new_password) < 4:
            raise ValueError("Пароль должен быть не короче 4 символов")
        self._salt = secrets.token_hex(8)
        self._hashed_password = _hash_password(new_password, self._salt)

    def verify_password(self, password: str) -> bool:
        expected = self._hashed_password
        candidate = _hash_password(password, self._salt)
        return expected == candidate

    def get_user_info(self) -> dict:
        return {
            "user_id": self._user_id,
            "username": self._username,
            "registration_date": self._registration_date.isoformat(timespec="seconds"),
        }

    def to_dict(self) -> dict:
        return {
            "user_id": self._user_id,
            "username": self._username,
            "hashed_password": self._hashed_password,
            "salt": self._salt,
            "registration_date": self._registration_date.isoformat(timespec="seconds"),
        }

    @staticmethod
    def from_dict(d: dict) -> "User":
        try:
            reg_dt = datetime.fromisoformat(str(d["registration_date"]))
        except Exception as e:
            raise ValueError("Некорректный формат registration_date (ожидается ISO)") from e
        return User(
            user_id=int(d["user_id"]),
            username=str(d["username"]),
            hashed_password=str(d["hashed_password"]),
            salt=str(d["salt"]),
            registration_date=reg_dt,
        )

    @staticmethod
    def new(user_id: int, username: str, raw_password: str) -> "User":
        """Фабрика пользователя с генерацией соли/хэша и текущей датой."""
        if len(raw_password) < 4:
            raise ValueError("Пароль должен быть не короче 4 символов")
        salt = secrets.token_hex(8)
        hashed = _hash_password(raw_password, salt)
        return User(
            user_id=user_id,
            username=username,
            hashed_password=hashed,
            salt=salt,
            registration_date=datetime.now(timezone.utc).replace(tzinfo=None),
        )

    def __repr__(self) -> str:
        return f"User(user_id={self._user_id}, username={self._username!r})"

class Wallet:
    """
    Кошелёк для одной валюты.
    Инварианты:
      - currency_code фиксируется при создании;
      - balance >= 0 (Decimal);
      - операции валидируются.
    """

    def __init__(self, currency_code: str, balance: Decimal | int | float | str = Decimal("0")) -> None:
        self._currency_code: str = _ensure_upper_currency(currency_code)
        self._balance: Decimal = Decimal("0")
        self.balance = _to_decimal(balance)

    @property
    def currency_code(self) -> str:
        return self._currency_code

    @property
    def balance(self) -> Decimal:
        return self._balance

    @balance.setter
    def balance(self, value: Decimal | int | float | str) -> None:
        dec = _to_decimal(value)
        if dec < 0:
            raise ValueError("Баланс не может быть отрицательным")
        self._balance = _quantize_for_currency(self._currency_code, dec)

    def deposit(self, amount: Decimal | int | float | str) -> None:
        dec = _to_decimal(amount)
        if dec <= 0:
            raise ValueError("'amount' должен быть положительным числом")
        self.balance = self._balance + dec

    def withdraw(self, amount: Decimal | int | float | str) -> None:
        dec = _to_decimal(amount)
        if dec <= 0:
            raise ValueError("'amount' должен быть положительным числом")
        if dec > self._balance:
            available = self._balance
            code = self._currency_code
            required = dec
            raise InsufficientFundsError(
                f"ыНедостаточно средств: доступно {available} {code}, требуется {required} {code}"
            )
        self.balance = self._balance - dec

    def get_balance_info(self) -> str:
        q = CURRENCY_PRECISION.get(self._currency_code, _DEC_FIAT_Q)
        places = abs(q.as_tuple().exponent)
        fmt = f"{{0:.{places}f}}"
        return f"{self._currency_code}: {fmt.format(self._balance)}"

    def to_dict(self) -> dict:
        return {"currency_code": self._currency_code, "balance": str(self._balance)}

    @staticmethod
    def from_dict(d: dict) -> "Wallet":
        return Wallet(
            currency_code=_ensure_upper_currency(str(d["currency_code"])),
            balance=_to_decimal(d["balance"]),
        )

    def __repr__(self) -> str:
        return f"Wallet({self._currency_code}, balance={self._balance})"

class Portfolio:
    """
    Портфель пользователя: набор кошельков (валют).
    - инкапсулирует Wallet;
    - безопасный доступ (копии);
    - оценка суммарной стоимости через курсы.
    """

    def __init__(self, user_id: int, wallets: Optional[Dict[str, Wallet]] = None) -> None:
        self._user_id: int = int(user_id)
        self._wallets: Dict[str, Wallet] = {}
        if wallets:
            for code, w in wallets.items():
                code_up = _ensure_upper_currency(code)
                if not isinstance(w, Wallet):
                    raise TypeError("wallets должны содержать объекты Wallet")
                if w.currency_code != code_up:
                    raise ValueError("Ключ словаря wallets должен совпадать с Wallet.currency_code")
                if code_up in self._wallets:
                    raise ValueError(f"Дубликат валюты в портфеле: {code_up}")
                self._wallets[code_up] = w

    @property
    def user_id(self) -> int:
        return self._user_id

    @property
    def wallets(self) -> Dict[str, Wallet]:
        return copy.deepcopy(self._wallets)

    def add_currency(self, currency_code: str) -> Wallet:
        code = _ensure_upper_currency(currency_code)
        if code in self._wallets:
            return self._wallets[code]
        w = Wallet(code)
        self._wallets[code] = w
        return w

    def get_wallet(self, currency_code: str) -> Optional[Wallet]:
        return self._wallets.get(_ensure_upper_currency(currency_code))

    def ensure_usd_wallet(self) -> Wallet:
        return self.add_currency("USD")

    def get_total_value(
        self,
        base_currency: str = "USD",
        rate_provider: Optional[Callable[[str, str], Decimal]] = None,
        rate_cache: Optional[Mapping[Tuple[str, str], Decimal]] = None,
    ) -> Decimal:
        """
        Считает суммарную стоимость портфеля в базовой валюте.
        Курсы берёт из:
          - rate_provider(from_code, to_code) -> Decimal, или
          - rate_cache[(from_code, to_code)] -> Decimal.
        Если заданы оба — приоритет у provider.
        """
        base = _ensure_upper_currency(base_currency)
        total = Decimal("0")

        def _get_rate(frm: str, to: str) -> Decimal:
            if frm == to:
                return Decimal("1")
            if rate_provider:
                rate = rate_provider(frm, to)
                if not isinstance(rate, Decimal):
                    rate = _to_decimal(rate)
                return rate
            if rate_cache is not None:
                key = (frm, to)
                if key not in rate_cache:
                    raise CurrencyNotFoundError(f"Нет курса {frm}->{to}")
                rate = rate_cache[key]
                if not isinstance(rate, Decimal):
                    rate = _to_decimal(rate)
                return rate
            raise CurrencyNotFoundError("Не задан источник курсов (rate_provider или rate_cache)")

        for code, wallet in self._wallets.items():
            bal = wallet.balance
            if bal == 0:
                continue
            rate = _get_rate(code, base)
            total += bal * rate

        return _quantize_for_currency(base, total)

    def to_dict(self, compact: bool = True) -> dict:
        """
        compact=True — формат, близкий к примеру из ТЗ:
        {
          "user_id": 1,
          "wallets": {"USD": {"balance": "1500.00"}, "BTC": {"balance": "0.05000000"}}
        }
        compact=False — полный Wallet.to_dict (включая currency_code).
        """
        if compact:
            wallets_payload = {
                code: {"balance": str(w.balance)} for code, w in self._wallets.items()
            }
        else:
            wallets_payload = {code: w.to_dict() for code, w in self._wallets.items()}

        return {"user_id": self._user_id, "wallets": wallets_payload}

    @staticmethod
    def from_dict(d: dict) -> "Portfolio":
        user_id = int(d["user_id"])
        wallets_raw = d.get("wallets", {})
        wallets: Dict[str, Wallet] = {}
        for code, payload in wallets_raw.items():
            code_up = _ensure_upper_currency(code)
            if "currency_code" in payload:
                w = Wallet.from_dict(payload)
            else:
                w = Wallet(currency_code=code_up, balance=_to_decimal(payload["balance"]))
            wallets[code_up] = w
        return Portfolio(user_id=user_id, wallets=wallets)

    def __repr__(self) -> str:
        return f"Portfolio(user_id={self._user_id}, wallets={list(self._wallets.keys())})"