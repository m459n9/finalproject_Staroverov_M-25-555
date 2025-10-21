# valutatrade_hub/core/usecases.py
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, Tuple, Optional

from valutatrade_hub.logging_config import setup_logging
from valutatrade_hub.decorators import log_action
from valutatrade_hub.infra.settings import SettingsLoader
from valutatrade_hub.infra.database import DatabaseManager

from valutatrade_hub.core.models import User, Portfolio
from valutatrade_hub.core.currencies import get_currency
from valutatrade_hub.core.exceptions import (
    CurrencyNotFoundError,
    ValidationError,
    NotLoggedInError,
    UserAlreadyExistsError,
    InsufficientFundsError,
    ApiRequestError,
)
from valutatrade_hub.core.utils import (
    now_iso,
    normalize_currency,
    parse_positive_amount,
    pair_key,
    parse_rate_obj,
)

logger = setup_logging()
settings = SettingsLoader()
db = DatabaseManager()

def _is_fresh(iso: str) -> bool:
    if not iso:
        return False
    try:
        dt = datetime.fromisoformat(iso)
    except Exception:
        return False
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    return (now - dt) <= timedelta(seconds=settings.ttl_seconds)

def _get_rate_from_cache(frm: str, to: str) -> Tuple[Decimal, str]:
    rates = db.read_json(settings.rates_file)
    direct = pair_key(frm, to)
    inverse = pair_key(to, frm)

    if direct in rates:
        r, upd = parse_rate_obj(rates[direct])
        if _is_fresh(upd):
            return r, upd

    if inverse in rates:
        r, upd = parse_rate_obj(rates[inverse])
        if _is_fresh(upd):
            return (Decimal("1") / r), upd
    raise CurrencyNotFoundError(f"Неизвестная валюта '{frm}'")

def _get_rate_via_external_api(frm: str, to: str) -> Tuple[Decimal, str]:
    raise ApiRequestError(f"Ошибка при обращении к внешнему API: пара {frm}->{to} недоступна (Parser Service не подключён)")

def _get_rate_with_fallback(frm: str, to: str) -> Tuple[Decimal, str]:
    try:
        return _get_rate_from_cache(frm, to)
    except CurrencyNotFoundError:
        return _get_rate_via_external_api(frm, to)

def _load_users() -> Dict[str, User]:
    raw = db.read_json(settings.users_file)
    res: Dict[str, User] = {}
    for row in raw:
        u = User.from_dict(row)
        res[u.username] = u
    return res

def _save_users(users: Dict[str, User]) -> None:
    db.write_json(settings.users_file, [u.to_dict() for u in users.values()])

def _load_portfolios() -> Dict[int, Portfolio]:
    raw = db.read_json(settings.portfolios_file)
    res: Dict[int, Portfolio] = {}
    for row in raw:
        p = Portfolio.from_dict(row)
        res[p.user_id] = p
    return res

def _save_portfolios(portfolios: Dict[int, Portfolio]) -> None:
    db.write_json(settings.portfolios_file, [p.to_dict(compact=True) for p in portfolios.values()])

def _get_session_user() -> Optional[str]:
    sess = db.read_json(settings.session_file)
    return sess.get("current_user")

def _set_session_user(username: Optional[str]) -> None:
    db.write_json(settings.session_file, {"current_user": username})

def _next_user_id(users: Dict[str, User]) -> int:
    return (max((u.user_id for u in users.values()), default=0) + 1)

@log_action("REGISTER")
def register_user(username: str, password: str) -> User:
    username = (username or "").strip()
    if not username:
        raise ValidationError("Имя пользователя не может быть пустым")
    if not isinstance(password, str) or len(password) < 4:
        raise ValidationError("Пароль должен быть не короче 4 символов")

    users = _load_users()
    if username in users:
        raise UserAlreadyExistsError(f"Имя пользователя '{username}' уже занято")

    uid = _next_user_id(users)
    user = User.new(uid, username, password)
    users[username] = user
    _save_users(users)

    portfolios = _load_portfolios()
    if uid not in portfolios:
        portfolios[uid] = Portfolio(user_id=uid)
        _save_portfolios(portfolios)

    return user

@log_action("LOGIN")
def login_user(username: str, password: str) -> None:
    users = _load_users()
    u = users.get((username or "").strip())
    if not u:
        raise ValidationError(f"Пользователь '{username}' не найден")
    if not u.verify_password(password):
        raise ValidationError("Неверный пароль")
    _set_session_user(u.username)

def current_user() -> User:
    uname = _get_session_user()
    if not uname:
        raise NotLoggedInError("Сначала выполните login")
    users = _load_users()
    u = users.get(uname)
    if not u:
        _set_session_user(None)
        raise NotLoggedInError("Сначала выполните login")
    return u

def get_portfolio_for(u: User) -> Portfolio:
    portfolios = _load_portfolios()
    p = portfolios.get(u.user_id)
    if not p:
        p = Portfolio(u.user_id)
        portfolios[u.user_id] = p
        _save_portfolios(portfolios)
    return p

@log_action("SHOW_PORTFOLIO")
def show_portfolio(base: str = None) -> dict:
    u = current_user()
    p = get_portfolio_for(u)
    base = normalize_currency(base or settings.default_base)

    rows = []
    total = Decimal("0")

    for code, w in p.wallets.items():
        if w.balance == 0:
            rows.append({"currency": code, "balance": str(w.balance), "rate_to_base": "N/A"})
            continue
        if code == base:
            rows.append({"currency": code, "balance": str(w.balance), "rate_to_base": "1"})
            total += w.balance
            continue
        try:
            r, _ = _get_rate_from_cache(code, base)
            rows.append({"currency": code, "balance": str(w.balance), "rate_to_base": str(r)})
            total += w.balance * r
        except CurrencyNotFoundError:
            rows.append({"currency": code, "balance": str(w.balance), "rate_to_base": "N/A"})

    from valutatrade_hub.core.models import _quantize_for_currency
    total_q = _quantize_for_currency(base, total)
    return {"username": u.username, "base": base, "rows": rows, "total_in_base": str(total_q)}

@log_action("BUY", verbose=True)
def buy_currency(currency: str, amount: float, base: str = None) -> dict:
    u = current_user()
    base = normalize_currency(base or settings.default_base)
    qty = parse_positive_amount(amount)

    get_currency(currency)
    currency = normalize_currency(currency)

    r, _ = _get_rate_with_fallback(currency, base) 
    cost = qty * r

    portfolios = _load_portfolios()
    p = portfolios.get(u.user_id) or Portfolio(u.user_id)

    usd = p.add_currency(base)
    if usd.balance < cost:
        raise InsufficientFundsError(
            f"Недостаточно средств: доступно {usd.balance} {base}, требуется {cost} {base}"
        )

    target = p.add_currency(currency)
    before_target = target.balance
    before_usd = usd.balance

    target.deposit(qty)
    usd.withdraw(cost)

    portfolios[u.user_id] = p
    _save_portfolios(portfolios)

    return {
        "currency": currency,
        "amount": str(qty),
        "rate_used": str(r),
        "base": base,
        "portfolio_changes": {
            currency: {"before": str(before_target), "after": str(target.balance)},
            base: {"before": str(before_usd), "after": str(usd.balance)},
        },
        "estimated_cost_in_base": str(cost),
    }

@log_action("SELL", verbose=True)
def sell_currency(currency: str, amount: float, base: str = None) -> dict:
    u = current_user()
    base = normalize_currency(base or settings.default_base)
    qty = parse_positive_amount(amount)

    get_currency(currency)
    currency = normalize_currency(currency)

    r, _ = _get_rate_with_fallback(currency, base)
    revenue = qty * r

    portfolios = _load_portfolios()
    p = portfolios.get(u.user_id) or Portfolio(u.user_id)

    wallet = p.get_wallet(currency)
    if not wallet:
        raise ValidationError(
            f"У вас нет кошелька '{currency}'. Добавьте валюту: она создаётся автоматически при первой покупке."
        )
    before_cur = wallet.balance
    wallet.withdraw(qty)

    usd = p.add_currency(base)
    before_usd = usd.balance
    usd.deposit(revenue)

    portfolios[u.user_id] = p
    _save_portfolios(portfolios)

    return {
        "currency": currency,
        "amount": str(qty),
        "rate_used": str(r),
        "base": base,
        "portfolio_changes": {
            currency: {"before": str(before_cur), "after": str(wallet.balance)},
            base: {"before": str(before_usd), "after": str(usd.balance)},
        },
        "estimated_revenue_in_base": str(revenue),
    }

@log_action("GET_RATE")
def get_rate(frm: str, to: str) -> dict:
    get_currency(frm)
    get_currency(to)
    frm = normalize_currency(frm)
    to = normalize_currency(to)

    r, upd = _get_rate_with_fallback(frm, to)
    inv = (Decimal("1") / r) if r != 0 else None
    return {
        "from": frm, "to": to, "rate": str(r),
        "updated_at": upd, "inverse": str(inv) if inv is not None else "N/A"
    }

@log_action("UPDATE_RATES_STUB")
def update_rates_stub() -> dict:
    payload = db.read_json(settings.rates_file)
    now = now_iso()
    changed = 0
    for k, v in list(payload.items()):
        if isinstance(v, dict) and "rate" in v:
            v["updated_at"] = now
            changed += 1
    payload["last_refresh"] = now
    payload.setdefault("source", "LocalDevStub")
    db.write_json(settings.rates_file, payload)
    return {"updated": changed, "last_refresh": now}