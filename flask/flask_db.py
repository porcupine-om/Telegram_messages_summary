"""
Модуль для работы с базой данных сообщений в Flask приложении.
"""

import sqlite3
import os
from pathlib import Path
from typing import List, Dict, Optional
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
        logger.info(f"База данных: {self.db_path}")
    
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
    
    def get_statistics(self) -> Dict:
        """
        Получение статистики по сообщениям.
        
        Returns:
            Словарь со статистикой
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            stats = {}
            
            # Количество каналов (type = 'Channel')
            cursor.execute("SELECT COUNT(DISTINCT chat_id) FROM messages WHERE type = 'Channel'")
            stats['channels'] = cursor.fetchone()[0]
            
            # Количество чатов (type = 'Chat')
            cursor.execute("SELECT COUNT(DISTINCT chat_id) FROM messages WHERE type = 'Chat'")
            stats['chats'] = cursor.fetchone()[0]
            
            # Количество обработанных сообщений (is_summarised = 1)
            cursor.execute("SELECT COUNT(*) FROM messages WHERE is_summarised = 1")
            stats['processed'] = cursor.fetchone()[0]
            
            # Количество необработанных сообщений (is_summarised = 0)
            cursor.execute("SELECT COUNT(*) FROM messages WHERE is_summarised = 0")
            stats['not_processed'] = cursor.fetchone()[0]
            
            return stats
        except Exception as e:
            logger.error(f"Ошибка при получении статистики: {e}")
            return {'channels': 0, 'chats': 0, 'processed': 0, 'not_processed': 0}
        finally:
            conn.close()
    
    def get_last_summary_info(self) -> Optional[Dict]:
        """
        Получение информации о последней выжимке.
        
        Returns:
            Словарь с информацией о последней выжимке или None
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Получаем последнее обработанное сообщение (самое новое с is_summarised = 1)
            cursor.execute('''
                SELECT date
                FROM messages
                WHERE is_summarised = 1
                ORDER BY date DESC
                LIMIT 1
            ''')
            
            result = cursor.fetchone()
            if result and result[0]:
                return {
                    'date': result[0]
                }
            return None
        except Exception as e:
            logger.error(f"Ошибка при получении информации о последней выжимке: {e}")
            return None
        finally:
            conn.close()
    
    def get_all_messages(self, limit: Optional[int] = None) -> List[Dict]:
        """
        Получение всех сообщений из базы данных.
        
        Args:
            limit: Ограничение количества сообщений (если None - все)
            
        Returns:
            Список словарей с информацией о сообщениях
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            if limit:
                cursor.execute('''
                    SELECT id, chat_id, sender, type, text, date, is_summarised
                    FROM messages
                    ORDER BY date DESC, id DESC, chat_id DESC
                    LIMIT ?
                ''', (limit,))
            else:
                cursor.execute('''
                    SELECT id, chat_id, sender, type, text, date, is_summarised
                    FROM messages
                    ORDER BY date DESC, id DESC, chat_id DESC
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
                    'date': row['date'],
                    'is_summarised': row['is_summarised']
                })
            
            return messages
        except Exception as e:
            logger.error(f"Ошибка при получении сообщений: {e}")
            return []
        finally:
            conn.close()

