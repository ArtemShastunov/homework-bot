import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telebot
from dotenv import load_dotenv

from exceptions import (
    APIRequestError,
    APIResponseError,
    MissingEnvVarError,
)

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = (
    'https://practicum.yandex.ru/api/user_api/homework_statuses/'
)
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверяет наличие обязательных переменных окружения."""
    required_vars = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
    }
    for name, value in required_vars.items():
        if not value:
            raise MissingEnvVarError(
                f'Отсутствует переменная окружения: \'{name}\''
            )


def send_message(bot, message):
    """Отправляет сообщение в Telegram-чат."""
    logging.debug(f'Начало отправки: "{message}"')
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logging.debug(f'Бот отправил сообщение "{message}"')
        return True
    except (telebot.apihelper.ApiException, requests.RequestException):
        logging.error('Сбой при отправке сообщения')
        return False


def get_api_answer(timestamp):
    """Делает запрос к API Практикум Домашка."""
    request_params = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': {'from_date': timestamp}
    }
    logging.debug(
        f'Запрос к API: {request_params["url"]}, '
        f'headers: {request_params["headers"]}, '
        f'params: {request_params["params"]}'
    )

    try:
        response = requests.get(**request_params)
    except requests.RequestException as error:
        raise APIRequestError(f'Сбой запроса к API: {error}')

    if response.status_code != HTTPStatus.OK:
        raise APIResponseError(
            f'API вернул код {response.status_code}'
        )

    return response.json()


def check_response(response):
    """Проверяет ответ API на соответствие структуре."""
    if not isinstance(response, dict):
        raise TypeError(
            f'Ожидался dict, получен {type(response).__name__}'
        )
    if 'homeworks' not in response:
        raise KeyError('В ответе нет ключа \'homeworks\'')
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError(
            f'Ожидался list для \'homeworks\', '
            f'получен {type(homeworks).__name__}'
        )
    return homeworks


def parse_status(homework):
    """Извлекает статус домашки и формирует сообщение."""
    if 'homework_name' not in homework:
        raise KeyError('В ответе нет ключа \'homework_name\'')
    homework_name = homework['homework_name']
    if 'status' not in homework:
        raise KeyError('В ответе нет ключа \'status\'')
    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        raise KeyError(f'Неизвестный статус: \'{status}\'')
    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def _handle_homeworks(bot, homeworks):
    """Обрабатывает список домашних работ."""
    all_sent = True
    for homework in homeworks:
        try:
            message = parse_status(homework)
            if not send_message(bot, message):
                all_sent = False
        except KeyError as error:
            logging.error(f'Ошибка парсинга: {error}')
            all_sent = False
    return all_sent


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = telebot.TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if homeworks:
                if _handle_homeworks(bot, homeworks):
                    timestamp = response.get('current_date', timestamp)
            else:
                logging.debug('Нет новых статусов')
        except Exception as error:
            message = f'Сбой в программе: {error}'
            logging.error(message)
            send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    try:
        main()
    except MissingEnvVarError as error:
        logging.critical(error)
        sys.exit(1)
