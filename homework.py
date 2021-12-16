import logging
import os
import sys
import time

import requests
import telegram
from dotenv import load_dotenv
from telegram import Bot

from exceptions import IncorrectApi, NoEnvVariables

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

logger_homework = logging.getLogger(__name__)
logger_homework.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
logger_homework.addHandler(handler)

formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s %(funcName)s- %(message)s'
)

handler.setFormatter(formatter)


def send_message(bot, message):
    """Отправляет сообщение в Telegram с помощью телеграмм-бота."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger_homework.info(f'Отправлено сообщение"{message}".')
    except telegram.error.TelegramError as e:
        logger_homework.error(f'Ошибка при отправке'
                              f' сообщения в Telegram : {e}')


def get_api_answer(current_timestamp):
    """Отправляет GET-запрос к эндпоинту url API Практикум.Домашка."""
    timestamp = current_timestamp
    params = {'from_date': timestamp}
    logger_homework.info('Отправка запроса к API')
    response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    try:
        if response.status_code != requests.codes.ok:
            raise IncorrectApi('Эндпоинт'
                               ' https://practicum.yandex.ru/api/'
                               'user_api/homework_statuses/111'
                               ' недоступен.')
    except requests.exceptions.RequestException as e:
        logger_homework.critical(f'Ошибка при выполнении запроса: {e}')

    response = response.json()
    if response:
        logger_homework.info(f'Получен успешный ответ API {response}')

    return response


def check_response(response):
    """Провереряет доступность переменных окружения."""
    if 'homeworks' in response:
        try:
            if not isinstance(response['homeworks'], list):
                raise Exception('Не верный тип значения')
        except TypeError as e:
            logger_homework.error(f'{e}')

    homework = response['homeworks']
    return homework


def parse_status(homework):
    """Вывод статуса конкретной домашней работы."""
    logger_homework.info('Вывод статуса домашней работы')
    homework_name = homework['homework_name']
    homework_status = homework['status']

    if homework_status in HOMEWORK_STATUSES:
        verdict = HOMEWORK_STATUSES[homework_status]
    else:
        raise Exception(logger_homework.error('Статус не определен!'))

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Провереряет доступность переменных окружения."""
    variables = {
        PRACTICUM_TOKEN: 'PRACTICUM_TOKEN',
        TELEGRAM_TOKEN: 'TELEGRAM_TOKEN',
        TELEGRAM_CHAT_ID: 'TELEGRAM_CHAT_ID'
    }
    for key_var in variables.keys():
        name_variable = variables[key_var]
        try:
            if key_var is None:
                raise NoEnvVariables(f'Отсутствуют обязательные'
                                     f' {name_variable}'
                                     f' переменные окружения')
        except NoEnvVariables as e:
            logger_homework.critical(f'Отсутствуют'
                                     f' обязательные'
                                     f' {name_variable}'
                                     f' переменные окружения {e}')
            return False

        return True


def main():
    """Основная логика работы бота."""
    logger_homework.debug('Запуск бота.')
    try:
        if TELEGRAM_TOKEN is None:
            raise NoEnvVariables('Отсутствует'
                                 ' обязательная'
                                 ' переменная окружения: "TELEGRAM_TOKEN".'
                                 'Программа принудительно остановлена.')
    except NoEnvVariables as e:
        logger_homework.critical(f'{e}')

    bot = Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time()) - 30*24*60*60
    is_error_shown = False

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
            logger_homework.error(f'Сбой в работе программы: {e}')
            if not is_error_shown:
                send_message(bot, message=f'{e}')
                is_error_shown = True
            time.sleep(RETRY_TIME)
        else:
            is_error_shown = False


if __name__ == '__main__':
    main()
