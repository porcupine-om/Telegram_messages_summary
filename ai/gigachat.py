"""
Модуль для работы с GigaChat API.
Реализует получение токена и генерацию выжимок текста.
"""

import requests
import logging
from typing import Optional
from dotenv import load_dotenv
import os
from pathlib import Path
import urllib3

# Отключаем предупреждения о небезопасных SSL запросах
# (GigaChat API использует самоподписанные сертификаты)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Загружаем переменные окружения из .env в текущей директории
env_path = Path(__file__).parent / '.env'
load_dotenv(env_path)

logger = logging.getLogger(__name__)

# URL для GigaChat API
OAUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
CHAT_COMPLETIONS_URL = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"


class GigaChatError(Exception):
    """Базовое исключение для ошибок GigaChat API."""
    pass


class GigaChatAuthError(GigaChatError):
    """Ошибка аутентификации в GigaChat API."""
    pass


class GigaChatAPIError(GigaChatError):
    """Ошибка при выполнении запроса к GigaChat API."""
    pass


def get_access_token() -> str:
    """
    Получение OAuth токена для доступа к GigaChat API.
    
    Returns:
        Access token для использования в API запросах
        
    Raises:
        GigaChatAuthError: Если не удалось получить токен
    """
    # Получаем данные из .env согласно prompt.txt:
    # RqUID = CLIENT_ID из env
    # Authorization = CLIENT_SECRET из env (в формате Basic)
    client_id = os.getenv('CLIENT_ID') or os.getenv('RQUID')
    client_secret = os.getenv('CLIENT_SECRET') or os.getenv('AUTHORIZATION')
    
    if not client_id:
        raise GigaChatAuthError(
            "CLIENT_ID должен быть указан в файле .env"
        )
    
    if not client_secret:
        raise GigaChatAuthError(
            "CLIENT_SECRET должен быть указан в файле .env"
        )
    
    # Формируем Authorization заголовок в формате Basic
    # Если CLIENT_SECRET уже содержит "Basic ", используем как есть
    if client_secret.startswith('Basic '):
        authorization = client_secret
    else:
        authorization = f'Basic {client_secret}'
    
    # Подготовка данных для запроса (form-data, не JSON)
    payload = {
        'scope': 'GIGACHAT_API_PERS'
    }
    
    # Заголовки для запроса
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/json',
        'RqUID': client_id,
        'Authorization': authorization
    }
    
    try:
        logger.info("Запрос токена доступа к GigaChat API...")
        logger.debug(f"URL: {OAUTH_URL}")
        logger.debug(f"RqUID: {client_id}")
        logger.debug(f"Authorization: {authorization[:50]}...")  # Показываем первые 50 символов
        
        # Отключаем проверку SSL для работы с GigaChat API
        response = requests.post(
            OAUTH_URL,
            headers=headers,
            data=payload,  # Используем data, а не json
            timeout=10,
            verify=False  # Отключаем проверку SSL сертификата
        )
        
        # Логируем детали ошибки, если запрос неудачен
        if response.status_code != 200:
            logger.error(f"HTTP {response.status_code}: {response.text}")
        
        response.raise_for_status()
        token_data = response.json()
        
        access_token = token_data.get('access_token')
        if not access_token:
            raise GigaChatAuthError("Токен доступа не найден в ответе API")
        
        logger.info("Токен доступа успешно получен")
        return access_token
        
    except requests.exceptions.HTTPError as e:
        error_msg = f"HTTP {e.response.status_code}: {e.response.text}"
        logger.error(f"Ошибка при запросе токена: {error_msg}")
        raise GigaChatAuthError(f"Не удалось получить токен доступа: {error_msg}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при запросе токена: {e}")
        raise GigaChatAuthError(f"Не удалось получить токен доступа: {e}")
    except Exception as e:
        logger.error(f"Неожиданная ошибка при получении токена: {e}")
        raise GigaChatAuthError(f"Ошибка при получении токена: {e}")


def chat_completion(user_message: str, system_message: Optional[str] = None) -> str:
    """
    Отправка сообщения в GigaChat API и получение ответа.
    
    Args:
        user_message: Сообщение пользователя
        system_message: Опциональное системное сообщение для настройки поведения ассистента
        
    Returns:
        Ответ от GigaChat
        
    Raises:
        GigaChatError: При ошибках работы с API
    """
    if not user_message or not user_message.strip():
        raise ValueError("Сообщение пользователя не может быть пустым")
    
    # Получаем токен доступа
    try:
        access_token = get_access_token()
    except GigaChatAuthError as e:
        raise GigaChatError(f"Ошибка аутентификации: {e}")
    
    # Подготовка запроса
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    # Формируем список сообщений
    messages = []
    if system_message:
        messages.append({
            "role": "system",
            "content": system_message
        })
    messages.append({
        "role": "user",
        "content": user_message
    })
    
    payload = {
        "model": "GigaChat",
        "messages": messages
    }
    
    try:
        logger.info("Отправка запроса в GigaChat API...")
        # Отключаем проверку SSL для работы с GigaChat API
        response = requests.post(
            CHAT_COMPLETIONS_URL,
            json=payload,
            headers=headers,
            timeout=30,
            verify=False  # Отключаем проверку SSL сертификата
        )
        
        response.raise_for_status()
        result = response.json()
        
        # Извлекаем ответ из структуры ответа API
        choices = result.get('choices', [])
        if not choices:
            raise GigaChatAPIError("Ответ API не содержит choices")
        
        message = choices[0].get('message', {})
        content = message.get('content', '')
        
        if not content:
            raise GigaChatAPIError("Ответ API не содержит содержимого")
        
        logger.info("Ответ успешно получен от GigaChat API")
        return content
        
    except requests.exceptions.HTTPError as e:
        error_msg = f"HTTP ошибка: {e.response.status_code}"
        try:
            error_data = e.response.json()
            error_msg += f" - {error_data}"
        except:
            error_msg += f" - {e.response.text}"
        logger.error(error_msg)
        raise GigaChatAPIError(error_msg)
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при запросе к API: {e}")
        raise GigaChatAPIError(f"Ошибка при запросе к API: {e}")
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}")
        raise GigaChatAPIError(f"Неожиданная ошибка: {e}")


def generate_summary(text: str) -> str:
    """
    Генерация краткой выжимки текста через GigaChat API.
    
    Args:
        text: Текст для обработки
        
    Returns:
        Краткая выжимка текста
        
    Raises:
        GigaChatError: При ошибках работы с API
    """
    if not text or not text.strip():
        raise ValueError("Текст не может быть пустым")
    
    # Получаем токен доступа
    try:
        access_token = get_access_token()
    except GigaChatAuthError as e:
        raise GigaChatError(f"Ошибка аутентификации: {e}")
    
    # Подготовка запроса
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "GigaChat",
        "messages": [
            {
                "role": "system",
                "content": "Ты – ассистент, который делает краткие выжимки текста."
            },
            {
                "role": "user",
                "content": text
            }
        ]
    }
    
    try:
        logger.info("Отправка запроса на генерацию выжимки...")
        # Отключаем проверку SSL для работы с GigaChat API
        response = requests.post(
            CHAT_COMPLETIONS_URL,
            json=payload,
            headers=headers,
            timeout=30,
            verify=False  # Отключаем проверку SSL сертификата
        )
        
        response.raise_for_status()
        result = response.json()
        
        # Извлекаем ответ из структуры ответа API
        choices = result.get('choices', [])
        if not choices:
            raise GigaChatAPIError("Ответ API не содержит choices")
        
        message = choices[0].get('message', {})
        summary = message.get('content', '')
        
        if not summary:
            raise GigaChatAPIError("Ответ API не содержит содержимого")
        
        logger.info("Выжимка успешно сгенерирована")
        return summary
        
    except requests.exceptions.HTTPError as e:
        error_msg = f"HTTP ошибка: {e.response.status_code}"
        try:
            error_data = e.response.json()
            error_msg += f" - {error_data}"
        except:
            error_msg += f" - {e.response.text}"
        logger.error(error_msg)
        raise GigaChatAPIError(error_msg)
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при запросе к API: {e}")
        raise GigaChatAPIError(f"Ошибка при запросе к API: {e}")
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}")
        raise GigaChatAPIError(f"Неожиданная ошибка: {e}")

