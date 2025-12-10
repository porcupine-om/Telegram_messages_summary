"""
Модуль для работы с локальной базой данных SQLite.
Хранит сообщения из Telegram чатов.
"""

import sqlite3
import asyncio
import os
from datetime import datetime
from typing import Optional


class Database:
    """Класс для работы с базой данных SQLite."""
    
    def __init__(self, db_name: str = 'telegram_messages.db'):
        """
        Инициализация подключения к базе данных.
        
        Args:
            db_name: Имя файла базы данных
        """
        # Определяем путь к корню проекта (на уровень выше от telethon/)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)  # Поднимаемся на уровень выше
        self.db_name = os.path.join(project_root, db_name)
        self._init_db()
    
    def _init_db(self):
        """Создание таблицы messages, если она не существует."""
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Инициализация базы данных: {self.db_name}")
        
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                sender TEXT,
                type TEXT,
                text TEXT,
                date TIMESTAMP,
                is_summarised INTEGER DEFAULT 0,
                PRIMARY KEY (id, chat_id)
            )
        ''')
        
        # Добавляем колонку type, если она не существует (миграция для существующих БД)
        try:
            cursor.execute('ALTER TABLE messages ADD COLUMN type TEXT')
        except sqlite3.OperationalError:
            # Колонка уже существует, игнорируем ошибку
            pass
        
        # Добавляем колонку is_summarised, если она не существует (миграция для существующих БД)
        try:
            cursor.execute('ALTER TABLE messages ADD COLUMN is_summarised INTEGER DEFAULT 0')
            # Обновляем существующие записи - помечаем как необработанные
            cursor.execute('UPDATE messages SET is_summarised = 0 WHERE is_summarised IS NULL')
            logger.info("Добавлена колонка is_summarised в таблицу messages")
        except sqlite3.OperationalError:
            # Колонка уже существует, игнорируем ошибку
            pass
        
        # Проверяем структуру таблицы и исправляем PRIMARY KEY, если нужно
        cursor.execute('PRAGMA table_info(messages)')
        columns = cursor.fetchall()
        # Ищем, есть ли PRIMARY KEY только на id
        has_single_pk = any(col[5] == 1 and col[1] == 'id' for col in columns)
        
        if has_single_pk:
            logger.info("Обнаружена старая структура таблицы. Выполняется миграция...")
            # Удаляем временную таблицу, если она существует (от предыдущей неудачной миграции)
            cursor.execute('DROP TABLE IF EXISTS messages_new')
            
            # Создаем временную таблицу с правильной структурой (включая is_summarised)
            cursor.execute('''
                CREATE TABLE messages_new (
                    id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    sender TEXT,
                    type TEXT,
                    text TEXT,
                    date TIMESTAMP,
                    is_summarised INTEGER DEFAULT 0,
                    PRIMARY KEY (id, chat_id)
                )
            ''')
            # Копируем данные с установкой is_summarised = 0 для всех существующих записей
            cursor.execute('''
                INSERT OR IGNORE INTO messages_new (id, chat_id, sender, type, text, date, is_summarised)
                SELECT id, chat_id, sender, type, text, date, 0 FROM messages
            ''')
            # Удаляем старую таблицу
            cursor.execute('DROP TABLE messages')
            # Переименовываем новую таблицу
            cursor.execute('ALTER TABLE messages_new RENAME TO messages')
            logger.info("Миграция завершена. Теперь используется составной PRIMARY KEY (id, chat_id)")
        
        # Создаем индексы для быстрого поиска
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_chat_id ON messages(chat_id)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_date ON messages(date)
        ''')
        
        # Проверяем наличие колонки is_summarised перед созданием индекса
        cursor.execute('PRAGMA table_info(messages)')
        columns = cursor.fetchall()
        has_is_summarised = any(col[1] == 'is_summarised' for col in columns)
        
        if has_is_summarised:
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_is_summarised ON messages(is_summarised)
            ''')
        
        conn.commit()
        conn.close()
        logger.info(f"База данных инициализирована: {self.db_name}")
    
    async def save_message(
        self,
        message_id: int,
        chat_id: int,
        sender: Optional[str],
        message_type: Optional[str],
        text: Optional[str],
        date: datetime
    ) -> bool:
        """
        Сохранение сообщения в базу данных с проверкой на дубликаты.
        
        Args:
            message_id: ID сообщения в Telegram
            chat_id: ID чата
            sender: Имя отправителя
            message_type: Тип сообщения ("Channel" или "Chat")
            text: Текст сообщения
            date: Дата и время сообщения
            
        Returns:
            True если сообщение сохранено, False если уже существует
        """
        def _save():
            import logging
            logger = logging.getLogger(__name__)
            
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO messages (id, chat_id, sender, type, text, date, is_summarised)
                    VALUES (?, ?, ?, ?, ?, ?, 0)
                ''', (message_id, chat_id, sender, message_type, text, date))
                
                conn.commit()
                inserted = cursor.rowcount > 0
                
                if inserted:
                    logger.info(f"✓ Сообщение {message_id} из чата {chat_id} сохранено в БД: {self.db_name}")
                else:
                    logger.debug(f"⊘ Сообщение {message_id} из чата {chat_id} уже существует в БД (пропущено)")
                
                conn.close()
                return inserted
            except sqlite3.Error as e:
                conn.close()
                logger.error(f"Ошибка при сохранении сообщения {message_id} в БД {self.db_name}: {e}")
                return False
        
        # Выполняем в executor, чтобы не блокировать event loop
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _save)
    
    async def get_message_count(self, chat_id: Optional[int] = None) -> int:
        """
        Получение количества сообщений в базе.
        
        Args:
            chat_id: ID чата (если None, то для всех чатов)
            
        Returns:
            Количество сообщений
        """
        def _count():
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            
            if chat_id:
                cursor.execute('SELECT COUNT(*) FROM messages WHERE chat_id = ?', (chat_id,))
            else:
                cursor.execute('SELECT COUNT(*) FROM messages')
            
            count = cursor.fetchone()[0]
            conn.close()
            return count
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _count)

