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
