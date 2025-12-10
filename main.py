"""
Основной файл Telegram-скрипта на базе Telethon.
Реализует подключение, получение чатов, сбор сообщений и live-слушатель.
"""

import asyncio
import logging
from datetime import datetime
from typing import List, Optional

from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError, FloodWaitError
from telethon.tl.types import User, Channel, Chat, PeerChannel, PeerChat, PeerUser

from config import API_ID, API_HASH, SESSION_NAME
from db import Database

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('telegram_bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Инициализация базы данных
db = Database()


class TelegramBot:
    """Основной класс для работы с Telegram через Telethon."""
    
    def __init__(self):
        """Инициализация клиента Telethon."""
        self.client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
        self.db = db
        logger.info("TelegramBot инициализирован")
    
    @staticmethod
    def _extract_chat_id(peer_id) -> Optional[int]:
        """
        Извлечение ID чата из различных типов peer_id.
        
        Args:
            peer_id: Объект peer_id из сообщения
            
        Returns:
            ID чата или None
        """
        if hasattr(peer_id, 'channel_id'):
            return peer_id.channel_id
        elif hasattr(peer_id, 'chat_id'):
            return peer_id.chat_id
        elif hasattr(peer_id, 'user_id'):
            return peer_id.user_id
        elif isinstance(peer_id, PeerChannel):
            return peer_id.channel_id
        elif isinstance(peer_id, PeerChat):
            return peer_id.chat_id
        elif isinstance(peer_id, PeerUser):
            return peer_id.user_id
        return None
    
    @staticmethod
    def _get_chat_type(chat, peer_id=None) -> str:
        """
        Определение типа чата (Channel или Chat).
        
        Args:
            chat: Объект чата из Telegram
            peer_id: Объект peer_id из сообщения (опционально)
            
        Returns:
            "Channel" если это канал, "Chat" если это чат
        """
        # Проверяем через peer_id (если передан)
        if peer_id:
            if isinstance(peer_id, PeerChannel) or hasattr(peer_id, 'channel_id'):
                return "Channel"
            elif isinstance(peer_id, PeerChat) or hasattr(peer_id, 'chat_id'):
                return "Chat"
            elif isinstance(peer_id, PeerUser) or hasattr(peer_id, 'user_id'):
                return "Chat"
        
        # Проверяем через объект чата
        if chat:
            if isinstance(chat, Channel):
                return "Channel"
            elif isinstance(chat, Chat) or isinstance(chat, User):
                return "Chat"
        
        # По умолчанию считаем чатом
        return "Chat"
    
    async def connect(self):
        """
        Подключение к Telegram с обработкой ошибок.
        """
        try:
            await self.client.start()
            logger.info("Успешное подключение к Telegram")
            
            # Проверка авторизации
            if not await self.client.is_user_authorized():
                logger.error("Клиент не авторизован. Запустите скрипт еще раз.")
                return False
            
            me = await self.client.get_me()
            logger.info(f"Авторизован как: {me.first_name} (@{me.username})")
            return True
            
        except SessionPasswordNeededError:
            logger.error("Требуется двухфакторная аутентификация. Введите пароль.")
            return False
        except Exception as e:
            logger.error(f"Ошибка при подключении: {e}")
            return False
    
    async def get_dialogs(self) -> List:
        """
        Получение списка всех доступных диалогов (чатов).
        
        Returns:
            Список диалогов
        """
        try:
            dialogs = await self.client.get_dialogs()
            logger.info(f"Получено {len(dialogs)} диалогов")
            return dialogs
        except Exception as e:
            logger.error(f"Ошибка при получении диалогов: {e}")
            return []
    
    async def get_chat_messages(self, chat_id: int, limit: int = 100) -> List:
        """
        Сбор последних N сообщений из выбранного чата.
        
        Args:
            chat_id: ID чата или username
            limit: Количество сообщений для получения
            
        Returns:
            Список сообщений
        """
        try:
            messages = []
            async for message in self.client.iter_messages(chat_id, limit=limit):
                messages.append(message)
                
                # Сохранение в базу данных
                sender_name = None
                if message.sender:
                    if isinstance(message.sender, User):
                        sender_name = f"{message.sender.first_name or ''} {message.sender.last_name or ''}".strip()
                        if not sender_name:
                            sender_name = message.sender.username or f"User{message.sender.id}"
                    elif hasattr(message.sender, 'title'):
                        sender_name = message.sender.title
                
                text = message.text or message.raw_text or ""
                
                # Извлечение ID чата
                chat_id = self._extract_chat_id(message.peer_id) or message.chat_id
                
                # Получение объекта чата для определения типа
                try:
                    chat = await self.client.get_entity(chat_id)
                    message_type = self._get_chat_type(chat, message.peer_id)
                except Exception:
                    # Если не удалось получить чат, определяем по peer_id
                    message_type = self._get_chat_type(None, message.peer_id)
                
                await self.db.save_message(
                    message_id=message.id,
                    chat_id=chat_id,
                    sender=sender_name,
                    message_type=message_type,
                    text=text,
                    date=message.date
                )
            
            logger.info(f"Получено и сохранено {len(messages)} сообщений из чата {chat_id}")
            return messages
            
        except FloodWaitError as e:
            logger.warning(f"Превышен лимит запросов. Ожидание {e.seconds} секунд...")
            await asyncio.sleep(e.seconds)
            return await self.get_chat_messages(chat_id, limit)
        except Exception as e:
            logger.error(f"Ошибка при получении сообщений из чата {chat_id}: {e}")
            return []
    
    def setup_event_handlers(self):
        """
        Настройка асинхронного обработчика новых сообщений в реальном времени.
        """
        @self.client.on(events.NewMessage)
        async def new_message_handler(event):
            """
            Обработчик новых сообщений.
            Сохраняет сообщения в базу и выводит в консоль.
            """
            try:
                # Получение информации о чате
                chat = await event.get_chat()
                chat_title = getattr(chat, 'title', None) or getattr(chat, 'first_name', 'Unknown')
                
                # Получение информации об отправителе
                sender = await event.get_sender()
                sender_name = "Unknown"
                if sender:
                    if isinstance(sender, User):
                        sender_name = f"{sender.first_name or ''} {sender.last_name or ''}".strip()
                        if not sender_name:
                            sender_name = sender.username or f"User{sender.id}"
                    elif hasattr(sender, 'title'):
                        sender_name = sender.title
                
                # Получение текста сообщения
                text = event.message.text or event.message.raw_text or "[медиа/файл]"
                
                # Получение ID чата
                chat_id = self._extract_chat_id(event.message.peer_id)
                
                # Определение типа чата
                message_type = self._get_chat_type(chat, event.message.peer_id)
                
                # Сохранение в базу данных
                if chat_id:
                    await self.db.save_message(
                        message_id=event.message.id,
                        chat_id=chat_id,
                        sender=sender_name,
                        message_type=message_type,
                        text=text,
                        date=event.message.date
                    )
                
                # Вывод в консоль в формате [CHAT TITLE] sender: text
                print(f"[{chat_title}] {sender_name}: {text}")
                logger.info(f"Новое сообщение из [{chat_title}] от {sender_name}")
                
            except Exception as e:
                logger.error(f"Ошибка при обработке нового сообщения: {e}")
    
    async def run_live_listener(self):
        """
        Запуск live-слушателя новых сообщений.
        """
        logger.info("Запуск live-слушателя новых сообщений...")
        self.setup_event_handlers()
        await self.client.run_until_disconnected()


async def main():
    """
    Основная функция с примерами использования.
    """
    bot = TelegramBot()
    
    # Подключение к Telegram
    if not await bot.connect():
        logger.error("Не удалось подключиться к Telegram")
        return
    
    try:
        # Пример 1: Получение списка чатов
        logger.info("=" * 50)
        logger.info("Пример 1: Получение списка чатов")
        logger.info("=" * 50)
        dialogs = await bot.get_dialogs()
        
        if dialogs:
            print("\nДоступные чаты:")
            for i, dialog in enumerate(dialogs[:10], 1):  # Показываем первые 10
                chat = dialog.entity
                title = getattr(chat, 'title', None) or getattr(chat, 'first_name', 'Unknown')
                print(f"{i}. {title} (ID: {chat.id})")
        
        # Пример 2: Сбор последних 100 сообщений из выбранного чата
        logger.info("=" * 50)
        logger.info("Пример 2: Сбор последних 100 сообщений из первого чата")
        logger.info("=" * 50)
        
        if dialogs:
            first_chat = dialogs[0].entity
            chat_id = first_chat.id
            chat_title = getattr(first_chat, 'title', None) or getattr(first_chat, 'first_name', 'Unknown')
            
            print(f"\nСбор сообщений из чата: {chat_title}")
            messages = await bot.get_chat_messages(chat_id, limit=100)
            print(f"Собрано {len(messages)} сообщений")
            
            # Показываем статистику базы данных
            total_messages = await db.get_message_count()
            print(f"Всего сообщений в базе данных: {total_messages}")
        
        # Пример 3: Запуск live-слушателя новых сообщений
        logger.info("=" * 50)
        logger.info("Пример 3: Запуск live-слушателя новых сообщений")
        logger.info("=" * 50)
        print("\nСлушатель запущен. Ожидание новых сообщений...")
        print("Нажмите Ctrl+C для остановки\n")
        
        await bot.run_live_listener()
        
    except KeyboardInterrupt:
        logger.info("Остановка бота по запросу пользователя")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
    finally:
        await bot.client.disconnect()
        logger.info("Отключение от Telegram")


if __name__ == "__main__":
    # Запуск асинхронной функции
    asyncio.run(main())

