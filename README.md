# 💱 ValutaTrade Hub

**ValutaTrade Hub** — это консольное приложение для управления портфелем валют и криптовалют.  
Проект объединяет функциональность Core (регистрация пользователей, операции с валютами), Parser Service (обновление курсов из API CoinGecko и ExchangeRate), а также систему логирования и кэширования курсов.

## Возможности

- Регистрация и вход пользователей  
- Управление портфелем (купить / продать валюту)  
- Отображение актуальных балансов с пересчётом в базовую валюту (по умолчанию — USD)  
- Получение текущих курсов валют и криптовалют  
- Обновление курсов из внешних источников (CoinGecko, ExchangeRate API)  
- Локальное кэширование с TTL  
- Подробное логирование действий и операций

## Демо

[![asciicast](https://asciinema.org/a/KbLAQX4SqjrtgiMdYEwoeGIMa.svg)](https://asciinema.org/a/KbLAQX4SqjrtgiMdYEwoeGIMa)

Полный цикл работы приложения:
- Регистрация → вход пользователя  
- Обновление курсов → просмотр курсов  
- Покупка / продажа валюты → просмотр портфеля  
- Получение курса → демонстрация обработки ошибок 

| Слой | Назначение |
|------|-------------|
| **Core** | Логика пользователей, кошельков и операций (buy, sell, get-rate) |
| **Infra** | Настройки, база данных, загрузка конфигураций |
| **Parser Service** | Получение курсов из CoinGecko и ExchangeRate API |
| **CLI** | Интерфейс командной строки для взаимодействия с пользователем |
| **Data** | JSON-файлы для хранения данных пользователей, портфелей и курсов |

---

## Структура проекта

```bash
valutatrade_hub/
├── core/
│   ├── models.py
│   ├── usecases.py
│   ├── currencies.py
│   ├── exceptions.py
│   ├── utils.py
├── infra/
│   ├── settings.py
│   ├── database.py
├── parser_service/
│   ├── api_clients.py
│   ├── updater.py
│   ├── config.py
│   ├── scheduler.py
├── cli/
│   ├── interface.py
├── decorators.py
├── logging_config.py
├── data/
│   ├── users.json
│   ├── portfolios.json
│   ├── rates.json
│   ├── exchange_rates.json
├── logs/
│   ├── valutatrade_hub.log
│   ├── actions.log
```

## Установка и запуск

```bash
# Клонирование репозитория
git clone https://github.com/<your_username>/valutatrade-hub.git
cd valutatrade-hub

# Установка зависимостей через Poetry
make install

# Проверка линтера
make lint

# Запуск CLI
poetry run project
```

## Примеры использования CLI

### Регистрация и вход

```bash
poetry run project register --username maksim --password 1234
poetry run project login --username maksim --password 1234
```

### Просмотр портфеля

```bash
poetry run project show-portfolio

# Пример вывода:
# Портфель пользователя 'maksim' (база: USD):
# +----------+------------+------------+
# | Currency |  Balance   | Rate → USD |
# +----------+------------+------------+
# |   USD    |  9457.59   |     1      |
# |   BTC    | 0.00500000 |  108399.0  |
# +----------+------------+------------+
# ---------------------------------
# ИТОГО: 9 999.59 USD
```

### Купить или продать валюту

``` bash
poetry run project buy --currency BTC --amount 0.01
poetry run project sell --currency BTC --amount 0.003
```

### Обновить курс валют

``` bash
# Из CoinGecko
poetry run project update-rates --source coingecko

# Из ExchangeRate API
export EXCHANGERATE_API_KEY="ваш_api_ключ"
poetry run project update-rates --source exchangerate
```

### Получить курс валют

``` bash
poetry run project get-rate --from BTC --to USD

# Пример вывода:
# Курс BTC→USD: 108593.0 (обновлено: 2025-10-22T15:49:00Z)
# Обратный курс USD→BTC: 0.0000092087
```

### Просмотр кэша курсов

``` bash
poetry run project show-rates --currency BTC

# Пример:
# Rates from cache (updated at 2025-10-22T15:49:00Z):
# +---------+----------+----------------------+-----------+
# |   PAIR  |   RATE   |      UPDATED_AT      |   SOURCE  |
# +---------+----------+----------------------+-----------+
# | BTC_USD | 108593.0 | 2025-10-22T15:49:00Z | CoinGecko |
# +---------+----------+----------------------+-----------+
```
