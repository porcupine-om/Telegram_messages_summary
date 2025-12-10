"""
Скрипт для исправления структуры таблицы messages
Исправляет PRIMARY KEY с (id) на (id, chat_id)
"""
import sqlite3
import os

# Определяем путь к базе данных
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
db_path = os.path.join(project_root, 'telegram_messages.db')

print(f"Исправление структуры базы данных: {db_path}")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Проверяем текущую структуру
cursor.execute('PRAGMA table_info(messages)')
columns = cursor.fetchall()
has_single_pk = any(col[5] == 1 and col[1] == 'id' for col in columns)

if has_single_pk:
    print("Обнаружена старая структура таблицы. Выполняется миграция...")
    
    # Создаем временную таблицу с правильной структурой
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages_new (
            id INTEGER NOT NULL,
            chat_id INTEGER NOT NULL,
            sender TEXT,
            type TEXT,
            text TEXT,
            date TIMESTAMP,
            PRIMARY KEY (id, chat_id)
        )
    ''')
    
    # Копируем данные
    print("Копирование данных...")
    cursor.execute('''
        INSERT OR IGNORE INTO messages_new (id, chat_id, sender, type, text, date)
        SELECT id, chat_id, sender, type, text, date FROM messages
    ''')
    
    # Проверяем количество скопированных записей
    cursor.execute('SELECT COUNT(*) FROM messages_new')
    new_count = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM messages')
    old_count = cursor.fetchone()[0]
    print(f"Скопировано {new_count} из {old_count} сообщений")
    
    # Удаляем старую таблицу
    cursor.execute('DROP TABLE messages')
    
    # Переименовываем новую таблицу
    cursor.execute('ALTER TABLE messages_new RENAME TO messages')
    
    # Восстанавливаем индексы
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_chat_id ON messages(chat_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_date ON messages(date)')
    
    conn.commit()
    print("✓ Миграция завершена успешно!")
    print("Теперь используется составной PRIMARY KEY (id, chat_id)")
else:
    print("Структура таблицы уже правильная. Миграция не требуется.")

# Проверяем новую структуру
cursor.execute('PRAGMA table_info(messages)')
columns = cursor.fetchall()
print("\nНовая структура таблицы:")
for col in columns:
    pk_info = "PRIMARY KEY" if col[5] == 1 else ""
    print(f"  {col[1]} ({col[2]}) {pk_info}")

conn.close()

