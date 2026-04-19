"""Кастомные исключения для бота-ассистента."""


class BotException(Exception):
    """Базовое исключение для бота."""
    pass


class MissingEnvVarError(BotException):
    """Отсутствует обязательная переменная окружения."""
    pass


class APIResponseError(BotException):
    """API вернул неожиданный статус-код или структуру ответа."""
    pass


class APIRequestError(BotException):
    """Ошибка при выполнении запроса к API (сеть, таймаут и т.д.)."""
    pass
