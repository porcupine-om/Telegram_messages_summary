"""
Модуль для работы с базой данных сообщений Telegram.
Используется ботом для получения новых сообщений и создания саммари.
"""

import sqlite3
import os
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class MessagesDB:
    """Класс для работы с базой данных сообщений."""
    
    def __init__(self, db_name: str = 'telegram_messages.db'):
        """
        Инициализация подключения к базе данных.
        
        Args:
            db_name: Имя файла базы данных
        """
        # Определяем путь к корню проекта
        current_dir = Path(__file__).parent
        project_root = current_dir.parent
        self.db_path = project_root / db_name
        self._init_db()
        logger.info(f"База данных инициализирована: {self.db_path}")
    
    def _init_db(self):
        """Инициализация базы данных и создание необходимых таблиц."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Проверяем и добавляем колонку is_summarised в таблицу messages, если её нет
        try:
            cursor.execute('ALTER TABLE messages ADD COLUMN is_summarised INTEGER DEFAULT 0')
            # Обновляем существующие записи - помечаем как необработанные
            cursor.execute('UPDATE messages SET is_summarised = 0 WHERE is_summarised IS NULL')
            logger.info("Добавлена колонка is_summarised в таблицу messages")
        except sqlite3.OperationalError:
            # Колонка уже существует, игнорируем ошибку
            pass
        
        # Создаем индекс для быстрого поиска необработанных сообщений
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_is_summarised ON messages(is_summarised)
        ''')
        
        # Создаем таблицу для отслеживания последнего обработанного сообщения (для обратной совместимости)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS summary_state (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                last_processed_date TIMESTAMP NOT NULL,
                last_processed_id INTEGER,
                last_processed_chat_id INTEGER,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Если таблица пустая, создаем начальную запись
        cursor.execute('SELECT COUNT(*) FROM summary_state')
        if cursor.fetchone()[0] == 0:
            cursor.execute('''
                INSERT INTO summary_state (last_processed_date, last_processed_id, last_processed_chat_id)
                VALUES (datetime('1970-01-01'), 0, 0)
            ''')
        
        conn.commit()
        conn.close()
    
    def get_new_messages(self) -> List[Dict]:
        """
        Получение всех новых сообщений, которые еще не были обработаны.
        Использует колонку is_summarised для определения необработанных сообщений.
        
        Returns:
            Список словарей с информацией о сообщениях
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Для доступа к колонкам по имени
        cursor = conn.cursor()
        
        try:
            # Получаем новые сообщения, которые еще не были обработаны (is_summarised = 0)
            cursor.execute('''
                SELECT id, chat_id, sender, type, text, date
                FROM messages
                WHERE is_summarised = 0
                ORDER BY date ASC, id ASC, chat_id ASC
            ''')
            
            rows = cursor.fetchall()
            messages = []
            for row in rows:
                messages.append({
                    'id': row['id'],
                    'chat_id': row['chat_id'],
                    'sender': row['sender'],
                    'type': row['type'],
                    'text': row['text'] or '',
                    'date': row['date']
                })
            
            logger.info(f"Найдено {len(messages)} новых сообщений для суммаризации")
            
            # Логируем информацию о чатах
            if messages:
                unique_chats = set(msg['chat_id'] for msg in messages)
                logger.info(f"Сообщения из {len(unique_chats)} уникальных чатов: {list(unique_chats)}")
                # Логируем количество сообщений по чатам
                chat_counts = {}
                for msg in messages:
                    chat_id = msg['chat_id']
                    chat_counts[chat_id] = chat_counts.get(chat_id, 0) + 1
                logger.info(f"Распределение по чатам: {chat_counts}")
            
            return messages
            
        except Exception as e:
            logger.error(f"Ошибка при получении новых сообщений: {e}")
            return []
        finally:
            conn.close()
    
    def mark_messages_as_summarised(self, message_ids: List[tuple]):
        """
        Помечает сообщения как обработанные (is_summarised = 1).
        
        Args:
            message_ids: Список кортежей (id, chat_id) сообщений для пометки
        """
        if not message_ids:
            return
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Помечаем сообщения как обработанные
            cursor.executemany('''
                UPDATE messages
                SET is_summarised = 1
                WHERE id = ? AND chat_id = ?
            ''', message_ids)
            
            conn.commit()
            logger.info(f"Помечено {cursor.rowcount} сообщений как обработанные")
        except Exception as e:
            logger.error(f"Ошибка при пометке сообщений: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    def update_last_processed(self, last_date: str, last_id: int, last_chat_id: int):
        """
        Обновление информации о последнем обработанном сообщении (для обратной совместимости).
        
        Args:
            last_date: Дата последнего обработанного сообщения
            last_id: ID последнего обработанного сообщения
            last_chat_id: ID чата последнего обработанного сообщения
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                UPDATE summary_state
                SET last_processed_date = ?,
                    last_processed_id = ?,
                    last_processed_chat_id = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = (SELECT MAX(id) FROM summary_state)
            ''', (last_date, last_id, last_chat_id))
            
            conn.commit()
            logger.info(f"Обновлено состояние: дата={last_date}, id={last_id}, chat_id={last_chat_id}")
        except Exception as e:
            logger.error(f"Ошибка при обновлении состояния: {e}")
        finally:
            conn.close()
    
    def get_message_count(self) -> int:
        """
        Получение общего количества сообщений в базе.
        
        Returns:
            Количество сообщений
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('SELECT COUNT(*) FROM messages')
            count = cursor.fetchone()[0]
            return count
        except Exception as e:
            logger.error(f"Ошибка при подсчете сообщений: {e}")
            return 0
        finally:
            conn.close()

