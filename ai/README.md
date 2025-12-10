# GigaChat CLI - Генератор выжимок текста

CLI-инструмент для генерации кратких выжимок текста с использованием GigaChat API.

## Установка

1. Установите зависимости:
```bash
pip install -r ../requirements.txt
```

2. Создайте файл `.env` в директории `ai/` и добавьте ваши учетные данные:
```
CLIENT_ID=your_client_id_here
CLIENT_SECRET=your_client_secret_here
```

Учетные данные можно получить на https://developers.sber.ru/gigachat

## Использование

### Генерация выжимки из файла:
```bash
python main.py summary --file messages.txt
```

### Генерация выжимки из текста:
```bash
python main.py summary --text "Ваш текст для обработки"
```

### Приоритет параметров:
- Если указаны оба параметра (`--file` и `--text`), используется `--text`
- Если не указан ни один параметр, выводится ошибка и справка

## Примеры

```bash
# Из файла
python main.py summary --file telegram_messages.txt

# Из текста
python main.py summary --text "Это длинный текст, который нужно сократить до краткой выжимки..."

# Справка
python main.py summary --help
```

## Структура проекта

- `main.py` - CLI-приложение с командой summary
- `gigachat.py` - модуль для работы с GigaChat API
- `utils.py` - вспомогательные функции для работы с файлами
- `.env` - файл с учетными данными (не коммитится в git)

