"""
Модуль для создания саммари (выжимки) из новых сообщений.
"""

import logging
from typing import List, Dict, Optional, Tuple
from telegram_bot.db_utils import MessagesDB
from ai.gigachat import chat_completion, GigaChatError

logger = logging.getLogger(__name__)


def format_messages_for_summary(messages: List[Dict]) -> str:
    """
    Форматирование списка сообщений в текст для суммаризации.
    Объединяет сообщения из всех чатов в один текст.
    
    Args:
        messages: Список словарей с информацией о сообщениях
        
    Returns:
        Отформатированный текст для суммаризации
    """
    if not messages:
        return ""
    
    # Группируем сообщения по чатам для лучшей структуры
    chats = {}
    for msg in messages:
        chat_id = msg['chat_id']
        if chat_id not in chats:
            chats[chat_id] = []
        chats[chat_id].append(msg)
    
    # Формируем текст - объединяем все сообщения из всех чатов
    text_parts = []
    
    # Сначала добавляем информацию о количестве чатов
    text_parts.append(f"Сообщения из {len(chats)} чатов:\n")
    
    # Проходим по всем чатам и добавляем все сообщения
    for chat_id, chat_messages in chats.items():
        # Определяем название чата (берем наиболее часто встречающееся имя отправителя)
        senders = [msg.get('sender', '') for msg in chat_messages if msg.get('sender')]
        if senders:
            # Берем первое непустое имя отправителя как название чата
            chat_name = senders[0] if senders[0] else f"Чат {chat_id}"
        else:
            chat_name = f"Чат {chat_id}"
        
        text_parts.append(f"\n--- {chat_name} (чат ID: {chat_id}) ---")
        
        # Добавляем все сообщения из этого чата
        for msg in chat_messages:
            sender = msg.get('sender', 'Неизвестный')
            text = msg.get('text', '').strip()
            
            if text:
                # Ограничиваем длину текста для каждого сообщения
                if len(text) > 300:
                    text = text[:300] + "..."
                text_parts.append(f"{sender}: {text}")
    
    return "\n".join(text_parts)


def create_summary(messages: List[Dict]) -> Optional[str]:
    """
    Создание саммари из списка сообщений через GigaChat.
    
    Args:
        messages: Список словарей с информацией о сообщениях
        
    Returns:
        Текст саммари или None в случае ошибки
    """
    if not messages:
        return None
    
    try:
        # Форматируем сообщения для суммаризации
        formatted_text = format_messages_for_summary(messages)
        
        if not formatted_text or not formatted_text.strip():
            logger.warning("Нет текста для суммаризации")
            return None
        
        # Ограничиваем общий размер текста (GigaChat имеет лимиты)
        max_length = 10000  # Примерный лимит
        if len(formatted_text) > max_length:
            logger.warning(f"Текст слишком длинный ({len(formatted_text)} символов), обрезаем до {max_length}")
            formatted_text = formatted_text[:max_length] + "\n\n[... текст обрезан ...]"
        
        # Системное сообщение для суммаризации
        system_message = """Ты – ассистент, который создает краткие и информативные выжимки (саммари) из множества сообщений из разных чатов Telegram.

Твоя задача:
1. Проанализировать ВСЕ сообщения из ВСЕХ чатов
2. Выделить основные темы и события, объединив информацию из разных чатов
3. Создать единую структурированную выжимку с ключевыми моментами
4. Объединить похожие темы из разных чатов в одну тему
5. Указать важные детали, но без лишних подробностей
6. Если тема обсуждается в нескольких чатах, объединить это в одну тему

ВАЖНО: Не пересказывай сообщения по отдельности и не группируй по чатам. Создай ОБЩУЮ выжимку, объединяя информацию из всех чатов.

Формат ответа:
- Краткое введение (1-2 предложения о том, что происходило в целом)
- Основные темы/события (объединенные из всех чатов)
- Важные детали и выводы

Будь кратким, но информативным. Выделяй общее и важное из ВСЕХ сообщений."""
        
        user_message = f"""Создай краткую общую выжимку из следующих сообщений из разных чатов Telegram. 
Проанализируй ВСЕ сообщения из ВСЕХ чатов и создай единое саммари, объединяя похожие темы:

{formatted_text}

Сделай структурированную выжимку, выделив основные темы и важные моменты из ВСЕХ чатов. Не группируй по чатам, а объединяй информацию."""
        
        logger.info(f"Создание саммари из {len(messages)} сообщений...")
        summary = chat_completion(user_message, system_message)
        
        logger.info("Саммари успешно создано")
        return summary
        
    except GigaChatError as e:
        logger.error(f"Ошибка GigaChat при создании саммари: {e}")
        return None
    except Exception as e:
        logger.error(f"Неожиданная ошибка при создании саммари: {e}")
        return None


def generate_summary_from_db() -> Tuple[Optional[str], int]:
    """
    Получение новых сообщений из БД и создание саммари.
    
    Returns:
        Кортеж (саммари, количество обработанных сообщений)
        Если новых сообщений нет, возвращает (None, 0)
    """
    db = MessagesDB()
    
    # Получаем новые сообщения
    new_messages = db.get_new_messages()
    
    if not new_messages:
        logger.info("Нет новых сообщений для суммаризации")
        return None, 0
    
    logger.info(f"Найдено {len(new_messages)} новых сообщений")
    
    # Подсчитываем количество уникальных чатов
    unique_chats = set(msg['chat_id'] for msg in new_messages)
    logger.info(f"Сообщения из {len(unique_chats)} чатов: {unique_chats}")
    
    # Создаем саммари
    summary = create_summary(new_messages)
    
    if summary:
        # Помечаем все обработанные сообщения как summarised
        message_ids = [(msg['id'], msg['chat_id']) for msg in new_messages]
        db.mark_messages_as_summarised(message_ids)
        
        # Также обновляем состояние для обратной совместимости
        last_message = new_messages[-1]
        db.update_last_processed(
            last_date=last_message['date'],
            last_id=last_message['id'],
            last_chat_id=last_message['chat_id']
        )
        logger.info(f"Саммари создано, обработано {len(new_messages)} сообщений")
        return summary, len(new_messages)
    else:
        logger.error("Не удалось создать саммари")
        return None, len(new_messages)

