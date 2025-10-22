# valutatrade_hub/cli/interface.py
from __future__ import annotations

import argparse
from decimal import Decimal
from prettytable import PrettyTable

from valutatrade_hub.core.usecases import (
    register_user,
    login_user,
    show_portfolio,
    buy_currency,
    sell_currency,
    get_rate,
    InsufficientFundsError,
)
# ⬇️ ДОБАВЬ этот импорт, чтобы использовать правильный апдейтер
from valutatrade_hub.parser_service.updater import RatesUpdater
from valutatrade_hub.core.exceptions import ApiRequestError, CurrencyNotFoundError

def _print_portfolio(model: dict):
    username = model["username"]
    base = model["base"]
    total = model["total_in_base"]

    table = PrettyTable()
    table.field_names = ["Currency", "Balance", f"Rate → {base}"]
    for row in model["rows"]:
        table.add_row([row["currency"], row["balance"], row["rate_to_base"]])

    print(f"Портфель пользователя '{username}' (база: {base}):")
    print(table)
    print("-" * 33)
    print(f"ИТОГО: {Decimal(total):,.2f} {base}".replace(",", " "))

def _ok(msg: str): print(msg)
def _err(msg: str): print(msg)

def main():
    parser = argparse.ArgumentParser(prog="ValutaTrade Hub CLI", description="Консольный интерфейс управления портфелем")
    sub = parser.add_subparsers(dest="command", required=True)

    p_reg = sub.add_parser("register", help="Зарегистрировать нового пользователя")
    p_reg.add_argument("--username", required=True)
    p_reg.add_argument("--password", required=True)

    p_login = sub.add_parser("login", help="Войти в систему")
    p_login.add_argument("--username", required=True)
    p_login.add_argument("--password", required=True)

    p_show = sub.add_parser("show-portfolio", help="Показать портфель")
    p_show.add_argument("--base", default="USD")

    p_buy = sub.add_parser("buy", help="Купить валюту (количество в штуках, не в долларах)")
    p_buy.add_argument("--currency", required=True)
    p_buy.add_argument("--amount", type=float, required=True)

    p_sell = sub.add_parser("sell", help="Продать валюту (количество в штуках)")
    p_sell.add_argument("--currency", required=True)
    p_sell.add_argument("--amount", type=float, required=True)

    p_rate = sub.add_parser("get-rate", help="Получить курс одной валюты к другой")
    p_rate.add_argument("--from", dest="frm", required=True)
    p_rate.add_argument("--to", dest="to", required=True)

    # ⬇️ Команда обновления курсов парсера
    p_update = sub.add_parser("update-rates", help="Запустить обновление курсов (parser service)")
    p_update.add_argument("--source", choices=["coingecko", "exchangerate"], help="Ограничить источником")

    # ⬇️ Показ кэша курсов (улучшенная версия get-rate)
    p_showrates = sub.add_parser("show-rates", help="Показать курсы из локального кэша")
    p_showrates.add_argument("--currency", help="Фильтр по коду валюты (например, BTC)")
    p_showrates.add_argument("--top", type=int, help="Показать N самых дорогих криптовалют")
    p_showrates.add_argument("--base", help="Базовая валюта отображения (по умолчанию USD)")

    args = parser.parse_args()

    try:
        if args.command == "register":
            u = register_user(args.username, args.password)
            _ok(f"Пользователь '{u.username}' зарегистрирован (id={u.user_id}). Войдите: login --username {u.username} --password ****")

        elif args.command == "login":
            login_user(args.username, args.password)
            _ok(f"Вы вошли как '{args.username}'")

        elif args.command == "show-portfolio":
            model = show_portfolio(base=args.base)
            _print_portfolio(model)

        elif args.command == "buy":
            result = buy_currency(args.currency, args.amount, base="USD")
            ch = result["portfolio_changes"]
            _ok(
                "Покупка выполнена: "
                f"{Decimal(result['amount']):f} {result['currency']} "
                f"по курсу {result['rate_used']} USD/{result['currency']}\n"
                f"Изменения в портфеле:\n"
                f"- {result['currency']}: было {ch[args.currency]['before']} → стало {ch[args.currency]['after']}\n"
                f"- USD: было {ch['USD']['before']} → стало {ch['USD']['after']}\n"
                f"Оценочная стоимость покупки: {result['estimated_cost_in_base']} {result['base']}"
            )

        elif args.command == "sell":
            result = sell_currency(args.currency, args.amount, base="USD")
            ch = result["portfolio_changes"]
            _ok(
                "Продажа выполнена: "
                f"{Decimal(result['amount']):f} {result['currency']} "
                f"по курсу {result['rate_used']} USD/{result['currency']}\n"
                f"Изменения в портфеле:\n"
                f"- {result['currency']}: было {ch[args.currency]['before']} → стало {ch[args.currency]['after']}\n"
                f"- USD: было {ch['USD']['before']} → стало {ch['USD']['after']}\n"
                f"Зачислено: {result['estimated_revenue_in_base']} {result['base']}"
            )

        elif args.command == "get-rate":
            r = get_rate(args.frm, args.to)
            _ok(
                f"Курс {r['from']}→{r['to']}: {r['rate']} (обновлено: {r['updated_at']})\n"
                f"Обратный курс {r['to']}→{r['from']}: {r['inverse']}"
            )

        elif args.command == "update-rates":
            updater = RatesUpdater()  # ⬅️ больше НЕ передаём clients=...
            res = updater.run_update(only=args.source)
            # res — обычный dict; аккуратно печатаем статус
            ok_sources = res.get("ok_sources", 0)
            errors = res.get("errors", [])
            pairs_count = res.get("pairs_count", 0)
            last_refresh = res.get("last_refresh", "-")
            if errors:
                _ok(f"Update completed with errors. Sources OK: {ok_sources}, pairs: {pairs_count}. Last refresh: {last_refresh}")
                for e in errors:
                    print(f"- {e}")
            else:
                _ok(f"Update success. Pairs={pairs_count} ok={ok_sources} errors=0 Last refresh: {last_refresh}")

        elif args.command == "show-rates":
            # лёгкая реализация поверх локального кэша из usecases.get_rate не нужна;
            # читаем файл через RatesUpdater.CONFIG
            from valutatrade_hub.parser_service.config import CONFIG
            import json
            import os
            path = CONFIG.RATES_FILE_PATH
            if not os.path.exists(path):
                _err("Локальный кеш курсов пуст. Выполните 'update-rates', чтобы загрузить данные.")
                return
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f) or {}
            pairs = payload.get("pairs", {})
            if not pairs:
                _err("Локальный кеш курсов пуст. Выполните 'update-rates', чтобы загрузить данные.")
                return

            rows = []
            flt = (args.currency or "").strip().upper()
            for k, v in pairs.items():
                if flt and not k.startswith(flt + "_"):
                    continue
                rows.append((k, v.get("rate"), v.get("updated_at"), v.get("source")))
            if not rows:
                _err(f"Курс для '{flt}' не найден в кеше.")
                return

            rows.sort(key=lambda r: r[0])
            tbl = PrettyTable()
            tbl.field_names = ["PAIR", "RATE", "UPDATED_AT", "SOURCE"]
            for r in rows:
                tbl.add_row(r)
            print(f"Rates from cache (updated at {payload.get('last_refresh','-')}):")
            print(tbl)

    except InsufficientFundsError as e:
        _err(str(e))
    except CurrencyNotFoundError as e:
        _err(str(e))
        _ok("Подсказка: используйте 'show-rates' или 'update-rates', чтобы увидеть поддерживаемые коды.")
    except ApiRequestError as e:
        _err(str(e))
        _ok("Попробуйте позже или проверьте сеть/ключ EXCHANGERATE_API_KEY.")
    except PermissionError:
        _err("Сначала выполните login")
    except ValueError as e:
        msg = str(e)
        if "уже занято" in msg:
            _err(msg)
        elif "Пароль" in msg:
            _err("Пароль должен быть не короче 4 символов")
        elif "не найден" in msg:
            _err(msg)
        else:
            _err(msg)
    except Exception as e:
        _err(f"Неожиданная ошибка: {e}")

if __name__ == "__main__":
    main()