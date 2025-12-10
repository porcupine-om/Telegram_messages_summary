"""
Flask приложение для дашборда сообщений Telegram.
Отображает статистику и список сообщений.
"""

from flask import Flask, render_template
from flask_db import MessagesDB
from datetime import datetime
import pytz

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'

# Инициализация базы данных
db = MessagesDB()


def convert_to_msk(dt_string):
    """
    Конвертация строки даты/времени в часовой пояс MSK (UTC+3).
    
    Args:
        dt_string: Строка с датой/временем в формате ISO
        
    Returns:
        Строка с датой/временем в MSK
    """
    if not dt_string:
        return None
    
    try:
        dt_str = str(dt_string).strip()
        msk_tz = pytz.timezone('Europe/Moscow')
        
        # Пробуем разные форматы
        formats = [
            '%Y-%m-%d %H:%M:%S%z',
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%dT%H:%M:%S%z',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%dT%H:%M:%S.%f%z',
            '%Y-%m-%dT%H:%M:%S.%f',
        ]
        
        dt = None
        for fmt in formats:
            try:
                if '%z' in fmt:
                    # С timezone
                    dt = datetime.strptime(dt_str.replace('Z', '+00:00'), fmt)
                else:
                    # Без timezone - предполагаем UTC
                    dt = datetime.strptime(dt_str.split('+')[0].split('Z')[0].split('.')[0], fmt)
                    dt = pytz.UTC.localize(dt)
                break
            except (ValueError, AttributeError):
                continue
        
        # Если не удалось распарсить, пробуем fromisoformat
        if dt is None:
            try:
                dt_str_clean = dt_str.replace('Z', '+00:00')
                if '+' not in dt_str_clean and 'T' in dt_str_clean:
                    dt_str_clean = dt_str_clean + '+00:00'
                dt = datetime.fromisoformat(dt_str_clean)
            except (ValueError, AttributeError):
                return str(dt_string)
        
        # Если нет timezone, предполагаем UTC
        if dt.tzinfo is None:
            dt = pytz.UTC.localize(dt)
        
        # Конвертируем в MSK
        dt_msk = dt.astimezone(msk_tz)
        
        # Форматируем для отображения
        return dt_msk.strftime('%Y-%m-%d %H:%M:%S MSK')
    except Exception as e:
        # Если не удалось распарсить, возвращаем как есть
        return str(dt_string)


@app.route('/')
def index():
    """Главная страница со статистикой."""
    try:
        # Получаем общую статистику
        total_messages = db.get_message_count()
        
        # Получаем статистику по типам
        stats = db.get_statistics()
        
        # Получаем информацию о последней выжимке
        last_summary_info = db.get_last_summary_info()
        last_summary_date = None
        if last_summary_info and last_summary_info.get('date'):
            last_summary_date = convert_to_msk(last_summary_info['date'])
        
        return render_template('index.html',
                             total_messages=total_messages,
                             channels_count=stats.get('channels', 0),
                             chats_count=stats.get('chats', 0),
                             processed_count=stats.get('processed', 0),
                             not_processed_count=stats.get('not_processed', 0),
                             last_summary_date=last_summary_date)
    except Exception as e:
        return f"Ошибка: {e}", 500


@app.route('/messages')
def messages():
    """Страница со списком всех сообщений."""
    try:
        # Получаем все сообщения
        all_messages = db.get_all_messages()
        
        # Конвертируем даты в MSK
        for msg in all_messages:
            msg['date_msk'] = convert_to_msk(msg.get('date'))
            msg['is_processed'] = msg.get('is_summarised', 0) == 1
        
        return render_template('messages.html', messages=all_messages)
    except Exception as e:
        return f"Ошибка: {e}", 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

