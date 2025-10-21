# valutatrade_hub/cli/interface.py
from __future__ import annotations

import argparse
from decimal import Decimal
from prettytable import PrettyTable

from valutatrade_hub.core.usecases import (
    register_user, login_user, show_portfolio,
    buy_currency, sell_currency, get_rate, update_rates_stub
)
from valutatrade_hub.core.exceptions import (
    ValidationError, InsufficientFundsError, NotLoggedInError, CurrencyNotFoundError, ApiRequestError
)
from valutatrade_hub.core.currencies import list_currencies

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

    p_buy = sub.add_parser("buy", help="Купить валюту (количество в штуках)")
    p_buy.add_argument("--currency", required=True)
    p_buy.add_argument("--amount", type=float, required=True)

    p_sell = sub.add_parser("sell", help="Продать валюту (количество в штуках)")
    p_sell.add_argument("--currency", required=True)
    p_sell.add_argument("--amount", type=float, required=True)

    p_rate = sub.add_parser("get-rate", help="Получить курс одной валюты к другой")
    p_rate.add_argument("--from", dest="frm", required=True)
    p_rate.add_argument("--to", dest="to", required=True)

    sub.add_parser("list-currencies", help="Показать реестр валют")
    sub.add_parser("update-rates", help="(DEV) Освежить timestamps в rates.json")

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
            r = buy_currency(args.currency, args.amount, base="USD")
            ch = r["portfolio_changes"]
            _ok(
                "Покупка выполнена: "
                f"{Decimal(r['amount']):f} {r['currency']} по курсу {r['rate_used']} {r['base']}/{r['currency']}\n"
                f"Изменения в портфеле:\n"
                f"- {r['currency']}: было {ch[r['currency']]['before']} → стало {ch[r['currency']]['after']}\n"
                f"- {r['base']}: было {ch[r['base']]['before']} → стало {ch[r['base']]['after']}\n"
                f"Списано: {r['estimated_cost_in_base']} {r['base']}"
            )

        elif args.command == "sell":
            r = sell_currency(args.currency, args.amount, base="USD")
            ch = r["portfolio_changes"]
            _ok(
                "Продажа выполнена: "
                f"{Decimal(r['amount']):f} {r['currency']} по курсу {r['rate_used']} {r['base']}/{r['currency']}\n"
                f"Изменения в портфеле:\n"
                f"- {r['currency']}: было {ch[r['currency']]['before']} → стало {ch[r['currency']]['after']}\n"
                f"- {r['base']}: было {ch[r['base']]['before']} → стало {ch[r['base']]['after']}\n"
                f"Зачислено: {r['estimated_revenue_in_base']} {r['base']}"
            )

        elif args.command == "get-rate":
            r = get_rate(args.frm, args.to)
            _ok(f"Курс {r['from']}→{r['to']}: {r['rate']} (обновлено: {r['updated_at']})\nОбратный курс {r['to']}→{r['from']}: {r['inverse']}")

        elif args.command == "list-currencies":
            t = PrettyTable()
            t.field_names = ["Code", "Info"]
            for c in list_currencies():
                t.add_row([c.code, c.get_display_info()])
            _ok(str(t))

        elif args.command == "update-rates":
            r = update_rates_stub()
            _ok(f"Курсы обновлены (DEV). Обновлено пар: {r['updated']}, last_refresh: {r['last_refresh']}")

    except NotLoggedInError as e:
        _err(str(e))
    except InsufficientFundsError as e:
        _err(str(e))

    except CurrencyNotFoundError as e:
        _err(str(e))
        _err("Подсказка: проверьте код валюты. Посмотреть поддерживаемые коды: `project list-currencies`.")
        _err("Также можно получить помощь: `project get-rate --help`.")

    except ApiRequestError as e:
        _err(str(e))
        _err("Попробуйте повторить позже или проверьте подключение к сети.")

    except ValidationError as e:
        _err(str(e))

    except Exception as e:
        _err(f"Неожиданная ошибка: {e}")

if __name__ == "__main__":
    main()