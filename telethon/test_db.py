"""
Тестовый скрипт для проверки работы базы данных
"""
import sqlite3
import os

# Определяем путь к базе данных
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
db_path = os.path.join(project_root, 'telegram_messages.db')

print(f"Путь к базе данных: {db_path}")
print(f"База данных существует: {os.path.exists(db_path)}")

if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Проверяем структуру таблицы
    cursor.execute('PRAGMA table_info(messages)')
    columns = cursor.fetchall()
    print("\nСтруктура таблицы messages:")
    for col in columns:
        print(f"  {col[1]} ({col[2]}) - PK: {col[5]}")
    
    # Проверяем количество сообщений
    cursor.execute('SELECT COUNT(*) FROM messages')
    total = cursor.fetchone()[0]
    print(f"\nВсего сообщений в БД: {total}")
    
    # Проверяем последние сообщения
    cursor.execute('SELECT id, chat_id, sender, date FROM messages ORDER BY date DESC LIMIT 5')
    print("\nПоследние 5 сообщений:")
    for row in cursor.fetchall():
        print(f"  ID: {row[0]}, Chat: {row[1]}, Sender: {row[2]}, Date: {row[3]}")
    
    conn.close()
else:
    print("База данных не найдена!")

