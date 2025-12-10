"""
CLI-приложение для работы с GigaChat API.
Генерирует краткие выжимки текста.
"""

import argparse
import logging
import sys

from gigachat import generate_summary, GigaChatError
from utils import read_text_from_file, validate_text

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def main():
    """Основная функция CLI-приложения."""
    parser = argparse.ArgumentParser(
        description='Генерация краткой выжимки текста через GigaChat API'
    )
    
    # Создаем подпарсер для команды summary
    subparsers = parser.add_subparsers(dest='command', help='Доступные команды')
    
    # Команда summary
    summary_parser = subparsers.add_parser(
        'summary',
        help='Генерация выжимки текста'
    )
    
    summary_parser.add_argument(
        '--file',
        type=str,
        help='Путь к файлу с текстом для обработки'
    )
    
    summary_parser.add_argument(
        '--text',
        type=str,
        help='Текст для обработки (приоритет над --file)'
    )
    
    # Парсим аргументы
    args = parser.parse_args()
    
    # Проверяем, что команда указана
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Обработка команды summary
    if args.command == 'summary':
        text = None
        
        # Приоритет у --text
        if args.text:
            text = args.text
            logger.info("Используется текст из аргумента --text")
        elif args.file:
            try:
                text = read_text_from_file(args.file)
                logger.info(f"Текст прочитан из файла: {args.file}")
            except FileNotFoundError as e:
                print(f"Ошибка: {e}", file=sys.stderr)
                sys.exit(1)
            except IOError as e:
                print(f"Ошибка при чтении файла: {e}", file=sys.stderr)
                sys.exit(1)
        else:
            print("Ошибка: необходимо указать либо --file, либо --text", file=sys.stderr)
            summary_parser.print_help()
            sys.exit(1)
        
        # Проверяем валидность текста
        if not validate_text(text):
            print("Ошибка: текст не может быть пустым", file=sys.stderr)
            sys.exit(1)
        
        # Генерируем выжимку
        try:
            logger.info("Начало генерации выжимки...")
            summary = generate_summary(text)
            
            # Выводим результат
            print("\n" + "=" * 60)
            print("ВЫЖИМКА ТЕКСТА:")
            print("=" * 60)
            print(summary)
            print("=" * 60 + "\n")
            
            logger.info("Выжимка успешно сгенерирована и выведена")
            
        except GigaChatError as e:
            print(f"Ошибка GigaChat API: {e}", file=sys.stderr)
            logger.error(f"Ошибка GigaChat API: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"Неожиданная ошибка: {e}", file=sys.stderr)
            logger.error(f"Неожиданная ошибка: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()

