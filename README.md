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
