"""
Модуль для работы с локальной базой данных SQLite.
Хранит сообщения из Telegram чатов.
"""

import sqlite3
import asyncio
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
        self.db_name = db_name
        self._init_db()
    
    def _init_db(self):
        """Создание таблицы messages, если она не существует."""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY,
                chat_id INTEGER NOT NULL,
                sender TEXT,
                type TEXT,
                text TEXT,
                date TIMESTAMP,
                UNIQUE(id, chat_id)
            )
        ''')
        
        # Добавляем колонку type, если она не существует (миграция для существующих БД)
        try:
            cursor.execute('ALTER TABLE messages ADD COLUMN type TEXT')
        except sqlite3.OperationalError:
            # Колонка уже существует, игнорируем ошибку
            pass
        
        # Создаем индексы для быстрого поиска
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_chat_id ON messages(chat_id)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_date ON messages(date)
        ''')
        
        conn.commit()
        conn.close()
    
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
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO messages (id, chat_id, sender, type, text, date)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (message_id, chat_id, sender, message_type, text, date))
                
                conn.commit()
                inserted = cursor.rowcount > 0
                conn.close()
                return inserted
            except sqlite3.Error as e:
                conn.close()
                print(f"Ошибка при сохранении сообщения: {e}")
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

