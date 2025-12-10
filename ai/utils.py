"""
Вспомогательные функции для работы с текстом и файлами.
"""

import os
from typing import Optional


def read_text_from_file(file_path: str) -> str:
    """
    Чтение текста из файла.
    
    Args:
        file_path: Путь к файлу
        
    Returns:
        Содержимое файла как строка
        
    Raises:
        FileNotFoundError: Если файл не найден
        IOError: Если произошла ошибка при чтении файла
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Файл не найден: {file_path}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return content
    except UnicodeDecodeError:
        # Пробуем другие кодировки
        for encoding in ['cp1251', 'latin-1']:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    content = f.read()
                return content
            except UnicodeDecodeError:
                continue
        raise IOError(f"Не удалось прочитать файл {file_path}: неверная кодировка")
    except Exception as e:
        raise IOError(f"Ошибка при чтении файла {file_path}: {e}")


def validate_text(text: str) -> bool:
    """
    Проверка валидности текста.
    
    Args:
        text: Текст для проверки
        
    Returns:
        True если текст валиден, False иначе
    """
    if not text:
        return False
    
    if not text.strip():
        return False
    
    return True

