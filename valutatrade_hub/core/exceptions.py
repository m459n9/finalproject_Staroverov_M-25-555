# valutatrade_hub/core/exceptions.py

class InsufficientFundsError(RuntimeError):
    """
    Недостаточно средств.
    Сообщение:
    "Недостаточно средств: доступно {available} {code}, требуется {required} {code}"
    """

class CurrencyNotFoundError(RuntimeError):
    """
    Неизвестная валюта.
    Сообщение:
    "Неизвестная валюта '{code}'"
    """

class ApiRequestError(RuntimeError):
    """
    Сбой внешнего API.
    Сообщение:
    "Ошибка при обращении к внешнему API: {reason}"
    """

class ValidationError(ValueError):
    """Общая ошибка валидации."""

class NotLoggedInError(PermissionError):
    """Требуется авторизация."""

class UserAlreadyExistsError(RuntimeError):
    """Пользователь уже существует."""