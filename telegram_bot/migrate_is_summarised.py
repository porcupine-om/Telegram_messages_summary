"""
Скрипт для миграции базы данных - добавление колонки is_summarised.
Запускается автоматически при инициализации, но можно запустить вручную для проверки.
"""
import sqlite3
import os
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Определяем путь к базе данных
current_dir = Path(__file__).parent
project_root = current_dir.parent
db_path = project_root / 'telegram_messages.db'

print(f"Миграция базы данных: {db_path}")

if not db_path.exists():
    print(f"База данных не найдена: {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    # Проверяем, существует ли колонка is_summarised
    cursor.execute('PRAGMA table_info(messages)')
    columns = cursor.fetchall()
    column_names = [col[1] for col in columns]
    
    if 'is_summarised' in column_names:
        print("✓ Колонка is_summarised уже существует")
        
        # Проверяем количество необработанных сообщений
        cursor.execute('SELECT COUNT(*) FROM messages WHERE is_summarised = 0')
        not_processed = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM messages WHERE is_summarised = 1')
        processed = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM messages')
        total = cursor.fetchone()[0]
        
        print(f"  Всего сообщений: {total}")
        print(f"  Необработанных (is_summarised = 0): {not_processed}")
        print(f"  Обработанных (is_summarised = 1): {processed}")
    else:
        print("Добавление колонки is_summarised...")
        
        # Добавляем колонку
        cursor.execute('ALTER TABLE messages ADD COLUMN is_summarised INTEGER DEFAULT 0')
        
        # Обновляем существующие записи - помечаем как необработанные
        cursor.execute('UPDATE messages SET is_summarised = 0 WHERE is_summarised IS NULL')
        
        # Создаем индекс
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_is_summarised ON messages(is_summarised)')
        
        conn.commit()
        
        cursor.execute('SELECT COUNT(*) FROM messages')
        total = cursor.fetchone()[0]
        print(f"✓ Колонка is_summarised добавлена успешно")
        print(f"  Всего сообщений: {total}")
        print(f"  Все существующие сообщения помечены как необработанные (is_summarised = 0)")
    
    # Показываем структуру таблицы
    print("\nСтруктура таблицы messages:")
    cursor.execute('PRAGMA table_info(messages)')
    for col in cursor.fetchall():
        pk_info = " (PRIMARY KEY)" if col[5] == 1 else ""
        default_info = f" DEFAULT {col[4]}" if col[4] else ""
        print(f"  {col[1]} ({col[2]}){default_info}{pk_info}")

except Exception as e:
    print(f"❌ Ошибка при миграции: {e}")
    conn.rollback()
finally:
    conn.close()

print("\nМиграция завершена.")


