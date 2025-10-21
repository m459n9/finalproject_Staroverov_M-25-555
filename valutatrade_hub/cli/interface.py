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

def _ok(msg: str):
    print(msg)

def _err(msg: str):
    print(msg)

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
            _ok(
                "Покупка выполнена: "
                f"{Decimal(result['amount']):f} {result['currency']} "
                f"по курсу {result['rate_used']} USD/{result['currency']}\n"
                f"Изменения в портфеле:\n"
                f"- {result['currency']}: было {result['before']} → стало {result['after']}\n"
                f"Оценочная стоимость покупки: {result['estimated_cost_in_base']} {result['base']}"
            )

        elif args.command == "sell":
            result = sell_currency(args.currency, args.amount, base="USD")
            _ok(
                "Продажа выполнена: "
                f"{Decimal(result['amount']):f} {result['currency']} "
                f"по курсу {result['rate_used']} USD/{result['currency']}\n"
                f"Изменения в портфеле:\n"
                f"- {result['currency']}: было {result['before']} → стало {result['after']}\n"
                f"Оценочная выручка: {result['estimated_revenue_in_base']} {result['base']}"
            )

        elif args.command == "get-rate":
            r = get_rate(args.frm, args.to)
            _ok(
                f"Курс {r['from']}→{r['to']}: {r['rate']} (обновлено: {r['updated_at']})\n"
                f"Обратный курс {r['to']}→{r['from']}: {r['inverse']}"
            )

    except InsufficientFundsError as e:
        _err(str(e))
    except PermissionError:
        _err("Сначала выполните login")
    except ValueError as e:
        msg = str(e)
        if "уже занято" in msg:
            _err(msg)  # Username занят
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