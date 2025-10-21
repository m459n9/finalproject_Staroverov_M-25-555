# valutatrade_hub/core/usecases.py
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, Tuple, Optional
import json
import os
import tempfile
import shutil

from valutatrade_hub.core.models import (
    User,
    Wallet,
    Portfolio,
    InsufficientFundsError,
    CurrencyNotFoundError,
)

DATA_DIR = os.path.join(os.getcwd(), "data")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
PORTFOLIOS_FILE = os.path.join(DATA_DIR, "portfolios.json")
RATES_FILE = os.path.join(DATA_DIR, "rates.json")
SESSION_FILE = os.path.join(DATA_DIR, "session.json")

DEFAULT_TTL_SECONDS = 300  

def _ensure_data_files():
    os.makedirs(DATA_DIR, exist_ok=True)
    for path, default in [
        (USERS_FILE, []),
        (PORTFOLIOS_FILE, []),
        (RATES_FILE, {"source": "LocalCache", "last_refresh": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")}),
        (SESSION_FILE, {"current_user": None}),
    ]:
        if not os.path.exists(path):
            _atomic_write_json(path, default)

def _read_json(path: str):
    _ensure_data_files()
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _atomic_write_json(path: str, payload):
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

def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")

def _get_logged_in_username() -> Optional[str]:
    sess = _read_json(SESSION_FILE)
    return sess.get("current_user")

def _set_logged_in_username(username: Optional[str]) -> None:
    _atomic_write_json(SESSION_FILE, {"current_user": username})

def _load_users() -> Dict[str, User]:
    raw = _read_json(USERS_FILE)
    users: Dict[str, User] = {}
    for row in raw:
        u = User.from_dict(row)
        users[u.username] = u
    return users

def _save_users(users: Dict[str, User]) -> None:
    as_list = [u.to_dict() for u in users.values()]
    _atomic_write_json(USERS_FILE, as_list)

def _next_user_id(users: Dict[str, User]) -> int:
    if not users:
        return 1
    return max(u.user_id for u in users.values()) + 1

def _load_portfolios() -> Dict[int, Portfolio]:
    raw = _read_json(PORTFOLIOS_FILE)
    result: Dict[int, Portfolio] = {}
    for row in raw:
        p = Portfolio.from_dict(row)
        result[p.user_id] = p
    return result

def _save_portfolios(portfolios: Dict[int, Portfolio]) -> None:
    as_list = [p.to_dict(compact=True) for p in portfolios.values()]
    _atomic_write_json(PORTFOLIOS_FILE, as_list)

def _load_rates():
    return _read_json(RATES_FILE)

def _is_fresh(iso_ts: str, ttl_seconds: int) -> bool:
    try:
        dt = datetime.fromisoformat(iso_ts)
    except Exception:
        return False
    return datetime.now(timezone.utc).replace(tzinfo=None) - dt <= timedelta(seconds=ttl_seconds)

def _pair_key(frm: str, to: str) -> str:
    return f"{frm.upper()}_{to.upper()}"

def _get_rate_from_cache(frm: str, to: str, ttl_seconds: int) -> Tuple[Decimal, str]:
    """
    Пытается вернуть прямой курс, иначе обратный (1 / to_from).
    Бросает CurrencyNotFoundError, если ничего нет.
    """
    rates = _load_rates()
    direct_key = _pair_key(frm, to)
    inv_key = _pair_key(to, frm)

    if direct_key in rates:
        rate_obj = rates[direct_key]
        updated = rate_obj.get("updated_at")
        if updated and _is_fresh(updated, ttl_seconds):
            return Decimal(str(rate_obj["rate"])), updated

    if inv_key in rates:
        rate_obj = rates[inv_key]
        updated = rate_obj.get("updated_at")
        if updated and _is_fresh(updated, ttl_seconds):
            r = Decimal("1") / Decimal(str(rate_obj["rate"]))
            return r, updated

    raise CurrencyNotFoundError(f"Курс {frm}->{to} недоступен или устарел")

def register_user(username: str, password: str) -> User:
    username = (username or "").strip()
    if not username:
        raise ValueError("Имя пользователя не может быть пустым")
    if not isinstance(password, str) or len(password) < 4:
        raise ValueError("Пароль должен быть не короче 4 символов")

    users = _load_users()
    if username in users:
        raise ValueError(f"Имя пользователя '{username}' уже занято")

    uid = _next_user_id(users)
    user = User.new(uid, username, password)
    users[username] = user
    _save_users(users)

    portfolios = _load_portfolios()
    if uid not in portfolios:
        portfolios[uid] = Portfolio(user_id=uid)  
        _save_portfolios(portfolios)

    return user

def login_user(username: str, password: str) -> None:
    users = _load_users()
    user = users.get(username or "")
    if not user:
        raise ValueError(f"Пользователь '{username}' не найден")
    if not user.verify_password(password):
        raise ValueError("Неверный пароль")
    _set_logged_in_username(user.username)

def current_user() -> User:
    users = _load_users()
    uname = _get_logged_in_username()
    if not uname:
        raise PermissionError("Сначала выполните login")
    user = users.get(uname)
    if not user:
        _set_logged_in_username(None)
        raise PermissionError("Сначала выполните login")
    return user

def get_portfolio(user: User) -> Portfolio:
    portfolios = _load_portfolios()
    p = portfolios.get(user.user_id)
    if not p:
        p = Portfolio(user.user_id)
        portfolios[user.user_id] = p
        _save_portfolios(portfolios)
    return p

def show_portfolio(base: str = "USD", ttl_seconds: int = DEFAULT_TTL_SECONDS) -> Dict:
    user = current_user()
    portfolio = get_portfolio(user)
    rates_raw = _load_rates()
    rate_cache: Dict[Tuple[str, str], Decimal] = {}
    for key, obj in rates_raw.items():
        if key in ("source", "last_refresh"):
            continue
        frm, to = key.split("_", 1)
        if not _is_fresh(obj.get("updated_at", ""), ttl_seconds):
            continue
        rate_cache[(frm, to)] = Decimal(str(obj["rate"]))

    total = portfolio.get_total_value(base_currency=base, rate_cache=rate_cache if rate_cache else None)

    rows = []
    for code, w in portfolio.wallets.items():
        if code == base:
            rate = Decimal("1")
        else:
            try:
                rate, updated = _get_rate_from_cache(code, base, ttl_seconds)
            except CurrencyNotFoundError:
                rate, updated = None, None
        rows.append({
            "currency": code,
            "balance": str(w.balance),
            "rate_to_base": str(rate) if rate is not None else "N/A",
        })

    return {
        "username": user.username,
        "base": base,
        "rows": rows,
        "total_in_base": str(total),
    }

def buy_currency(currency: str, amount: float, base: str = "USD") -> Dict:
    if not isinstance(amount, (int, float)) or amount <= 0:
        raise ValueError("'amount' должен быть положительным числом")
    currency = (currency or "").upper().strip()
    if not currency:
        raise ValueError("Некорректный код валюты")

    user = current_user()
    portfolios = _load_portfolios()
    portfolio = portfolios.get(user.user_id) or Portfolio(user.user_id)

    target = portfolio.add_currency(currency)
    before = target.balance
    target.deposit(Decimal(str(amount)))
    after = target.balance

    rate, updated = None, None
    try:
        rate, updated = _get_rate_from_cache(currency, base, DEFAULT_TTL_SECONDS)
    except CurrencyNotFoundError:
        pass

    portfolios[user.user_id] = portfolio
    _save_portfolios(portfolios)

    return {
        "currency": currency,
        "amount": str(Decimal(str(amount))),
        "before": str(before),
        "after": str(after),
        "rate_used": str(rate) if rate is not None else "N/A",
        "estimated_cost_in_base": str((Decimal(str(amount)) * rate).quantize(Decimal("0.01"))) if rate is not None else "N/A",
        "base": base,
    }

def sell_currency(currency: str, amount: float, base: str = "USD") -> Dict:
    if not isinstance(amount, (int, float)) or amount <= 0:
        raise ValueError("'amount' должен быть положительным числом")
    currency = (currency or "").upper().strip()
    if not currency:
        raise ValueError("Некорректный код валюты")

    user = current_user()
    portfolios = _load_portfolios()
    portfolio = portfolios.get(user.user_id) or Portfolio(user.user_id)

    wallet = portfolio.get_wallet(currency)
    if not wallet:
        raise ValueError(f"У вас нет кошелька '{currency}'. Добавьте валюту: она создаётся автоматически при первой покупке.")

    before = wallet.balance
    wallet.withdraw(Decimal(str(amount)))
    after = wallet.balance

    rate, updated = None, None
    try:
        rate, updated = _get_rate_from_cache(currency, base, DEFAULT_TTL_SECONDS)
    except CurrencyNotFoundError:
        pass

    portfolios[user.user_id] = portfolio
    _save_portfolios(portfolios)

    return {
        "currency": currency,
        "amount": str(Decimal(str(amount))),
        "before": str(before),
        "after": str(after),
        "rate_used": str(rate) if rate is not None else "N/A",
        "estimated_revenue_in_base": str((Decimal(str(amount)) * rate).quantize(Decimal("0.01"))) if rate is not None else "N/A",
        "base": base,
    }

def get_rate(frm: str, to: str, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> Dict:
    frm, to = (frm or "").upper().strip(), (to or "").upper().strip()
    if not frm or not to:
        raise ValueError("Коды валют не должны быть пустыми")
    rate, updated = _get_rate_from_cache(frm, to, ttl_seconds)
    inverse = None
    try:
        inverse = (Decimal("1") / rate)
    except Exception:
        pass
    return {
        "from": frm,
        "to": to,
        "rate": str(rate),
        "updated_at": updated,
        "inverse": str(inverse) if inverse is not None else "N/A",
    }