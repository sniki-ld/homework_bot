import json
import logging
import os
import sys
import time
from logging.handlers import RotatingFileHandler

import requests
import telegram
from dotenv import load_dotenv
from telegram import Bot

from exceptions import ListTypeError, StatusError

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)

logger.setLevel(logging.DEBUG)

c_handler = logging.StreamHandler(sys.stdout)
handler = RotatingFileHandler('my_logger.log',
                              maxBytes=50_000_000,
                              backupCount=5)

logger.addHandler(handler)
logger.addHandler(c_handler)

formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s %(funcName)s- %(message)s'
)
handler.setFormatter(formatter)
c_handler.setFormatter(formatter)


def send_message(bot, message):
    """Отправляет сообщение в Telegram с помощью телеграмм-бота."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info(f'Отправлено сообщение"{message}".')
    except telegram.error.TelegramError as e:
        logger.error(f'Ошибка при отправке'
                     f' сообщения в Telegram : {e}')


def get_api_answer(current_timestamp):
    """Отправляет GET-запрос к эндпоинту url API Практикум.Домашка."""
    timestamp = current_timestamp
    params = {'from_date': timestamp}
    try:
        res_api = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if res_api.status_code != requests.codes.ok:
            res_api.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.critical(f'Ошибка при выполнении запроса: {e}')

    try:
        response = res_api.json()
    except json.JSONDecodeError as e:
        logger.error(f'Десериализованные данные'
                     f' не являются допустимым документом JSON {e}')

    if response:
        logger.info(f'Получен успешный ответ API {response}')
    return response


def check_response(response):
    """Провереряет ответ API на корректность."""
    if type(response) is dict:
        if 'homeworks' in response:
            if not isinstance(response['homeworks'], list):
                raise ListTypeError('Ошибка типа объекта')
            logger.error('Объект не является типом "list"')

    homework = response['homeworks']
    return homework


def parse_status(homework):
    """Вывод статуса конкретной домашней работы."""
    logger.info('Вывод статуса домашней работы')
    homework_name = homework['homework_name']
    homework_status = homework['status']

    if homework_status in HOMEWORK_STATUSES:
        verdict = HOMEWORK_STATUSES[homework_status]
    else:
        raise StatusError('Статус не определен!')

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Провереряет доступность переменных окружения."""
    variables = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
    }

    for key_var, val in variables.items():
        name_variable = val
        if val is None:
            logger.critical(f'Отсутствуют обязательные'
                            f' {name_variable} переменные окружения')
            return False
        else:
            return True


def main():
    """Основная логика работы бота."""
    logger.debug('Запуск бота')
    bot = Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    error_string = None

    while True:
        try:
            response = get_api_answer(current_timestamp)
            if response.get('homeworks'):
                message = parse_status(
                    response.get('homeworks')[0]
                )
                send_message(bot, message)
            current_timestamp = response.get('current_date', current_timestamp)
            time.sleep(RETRY_TIME)

        except Exception as e:
            logger.error(f'Сбой в работе программы: {e}')
            if str(e) != error_string:
                send_message(bot, message=str(e))
                error_string = str(e)
            time.sleep(RETRY_TIME)
        else:
            error_string = None


if __name__ == '__main__':
    main()
