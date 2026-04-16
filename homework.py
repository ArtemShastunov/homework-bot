import logging
import os
import sys
import time

import requests
import telebot
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

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
            logging.critical(
                f'Отсутствует переменная окружения: \'{name}\''
            )
            return False
    return True


def send_message(bot, message):
    """Отправляет сообщение в Telegram-чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logging.debug(f'Бот отправил сообщение "{message}"')
    except Exception as error:
        logging.error(f'Сбой при отправке сообщения: {error}')


def get_api_answer(timestamp):
    """Делает запрос к API Практикум Домашка."""
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp}
        )
        if response.status_code != 200:
            logging.error(
                f'Эндпоинт {ENDPOINT} недоступен. '
                f'Код ответа: {response.status_code}'
            )
            raise ValueError(
                f'API вернул код состояния {response.status_code}'
            )
        return response.json()
    except requests.RequestException as error:
        logging.error(f'Сбой при запросе к {ENDPOINT}: {error}')
        raise Exception(f'Ошибка соединения с API: {error}')


def check_response(response):
    """Проверяет ответ API на соответствие структуре."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API должен быть словарём')
    if 'homeworks' not in response:
        raise KeyError('В ответе нет ключа \'homeworks\'')
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError('Ключ \'homeworks\' должен содержать список')
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


def _handle_homeworks(bot, homeworks, last_error):
    """Обрабатывает список домашних работ."""
    for homework in homeworks:
        try:
            message = parse_status(homework)
            send_message(bot, message)
            last_error = None
        except KeyError as error:
            error_msg = f'Ошибка парсинга: {error}'
            logging.error(error_msg)
            if error_msg != last_error:
                send_message(bot, f'Сбой в программе: {error_msg}')
                last_error = error_msg
    return last_error


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical('Программа остановлена.')
        sys.exit(1)

    bot = telebot.TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_error_message = None

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            timestamp = response.get('current_date', timestamp)

            if homeworks:
                last_error_message = _handle_homeworks(
                    bot, homeworks, last_error_message
                )
            else:
                logging.debug('Нет новых статусов')
                last_error_message = None
        except Exception as error:
            message = f'Сбой в программе: {error}'
            logging.error(message)
            if message != last_error_message:
                send_message(bot, message)
                last_error_message = message

        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
