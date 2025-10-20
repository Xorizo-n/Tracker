from flask import Flask, render_template
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, date, timedelta
import os
import re
import sys
import logging
import time
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

app = Flask(__name__)

# =============================================================================
# ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ДЛЯ ЗАЩИТЫ ОТ ЧАСТЫХ ЗАПРОСОВ
# =============================================================================

# Время последнего успешного запроса
last_successful_request = None
# Время последней ошибки
last_error_time = None
# Кэш расписания
schedule_cache = None
# Время кэширования
cache_time = None
# Текст последней ошибки
last_error = None
# Время последнего запроса
last_request_time = 0
# Минимальный интервал между запросами (секунды)
MIN_REQUEST_INTERVAL = 15

# =============================================================================
# НАСТРОЙКА ЛОГИРОВАНИЯ
# =============================================================================

def setup_logging():
    """Настройка логирования для скомпилированного приложения"""
    # Создаем логгер
    logger = logging.getLogger()
    logger.setLevel(logging.WARNING)  # Только WARNING и выше
    
    # Формат логов
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Хендлер для консоли (более подробный)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Хендлер для файла (только серьезные ошибки)
    try:
        file_handler = logging.FileHandler('duty_app.log', encoding='utf-8')
        file_handler.setLevel(logging.WARNING)  # Только WARNING и ERROR
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"Не удалось создать файл лога: {e}")
    
    return logger

# Инициализируем логирование
logger = setup_logging()

# =============================================================================
# КОНФИГУРАЦИЯ ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ
# =============================================================================

GOOGLE_SHEET_URL = os.getenv('GOOGLE_SHEET_URL')
CREDENTIALS_FILE = os.getenv('GOOGLE_CREDENTIALS_FILE', 'credentials.json')

# Проверяем обязательные переменные
if not GOOGLE_SHEET_URL:
    logger.error("GOOGLE_SHEET_URL не установлен в переменных окружения")
    raise ValueError("GOOGLE_SHEET_URL не установлен в переменных окружения")

logger.info(f"Конфигурация загружена: Google Sheet URL = {GOOGLE_SHEET_URL}")

# =============================================================================
# ФУНКЦИИ ДЛЯ РАБОТЫ С GOOGLE SHEETS
# =============================================================================

def get_google_sheets_client():
    """Инициализация клиента Google Sheets"""
    try:
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]
        
        logger.info(f"Загрузка учетных данных из: {CREDENTIALS_FILE}")
        
        if not os.path.exists(CREDENTIALS_FILE):
            logger.error(f"Файл учетных данных не найден: {CREDENTIALS_FILE}")
            return None
            
        creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scope)
        client = gspread.authorize(creds)
        logger.info("Клиент Google Sheets авторизован успешно")
        return client
        
    except Exception as e:
        logger.error(f"Ошибка при инициализации клиента Google Sheets: {e}")
        return None

def clean_name(name):
    """Очистка имени от комментариев и лишних символов"""
    if not name:
        return ""
    
    original_name = name
    # Удаляем текст в скобках и комментарии
    name = re.sub(r'\([^)]*\)', '', name)
    name = re.sub(r'с \d+:\d+', '', name)
    name = re.sub(r'\([^)]*\)', '', name)
    
    # Убираем лишние пробелы и переносы строк
    name = name.replace('<br>', ', ').strip()
    name = re.sub(r'\s+', ' ', name)
    
    cleaned = name.strip(' ,')
    return cleaned

def is_date_cell(cell_value):
    """Проверяет, является ли ячейка датой в формате ДД.ММ.ГГГГ или ДД.ММ"""
    if not cell_value:
        return False
    
    cell_value = str(cell_value).strip()
    
    # Проверяем формат ДД.ММ.ГГГГ
    date_pattern_full = r'^\d{1,2}\.\d{1,2}\.\d{4}$'
    # Проверяем формат ДД.ММ (предполагаем текущий год)
    date_pattern_short = r'^\d{1,2}\.\d{1,2}$'
    
    return bool(re.match(date_pattern_full, cell_value) or re.match(date_pattern_short, cell_value))

def parse_date_cell(date_str):
    """Парсит дату из формата ДД.ММ.ГГГГ или ДД.ММ"""
    try:
        date_str = str(date_str).strip()
        
        # Если формат ДД.ММ.ГГГГ
        if re.match(r'^\d{1,2}\.\d{1,2}\.\d{4}$', date_str):
            return datetime.strptime(date_str, '%d.%m.%Y').date()
        
        # Если формат ДД.ММ - добавляем текущий год
        elif re.match(r'^\d{1,2}\.\d{1,2}$', date_str):
            current_year = datetime.now().year
            date_with_year = f"{date_str}.{current_year}"
            return datetime.strptime(date_with_year, '%d.%m.%Y').date()
        
        return None
    except ValueError as e:
        logger.warning(f"Не удалось распарсить дату '{date_str}': {e}")
        return None

def get_weekday_name(date_obj):
    """Возвращает название дня недели на русском"""
    weekdays = {
        0: 'ПН',
        1: 'ВТ', 
        2: 'СР',
        3: 'ЧТ',
        4: 'ПТ',
        5: 'СБ',  # Суббота
        6: 'ВС'   # Воскресенье
    }
    return weekdays[date_obj.weekday()]

def parse_schedule_data(worksheet):
    """Парсинг данных таблицы дежурств - ищем даты в разных форматах"""
    try:
        # Получаем все значения
        logger.info("Получение данных из Google Sheets...")
        all_values = worksheet.get_all_values()
        logger.info(f"Получено строк: {len(all_values)}")
        
        schedule = []
        found_dates = []
        
        logger.info("Поиск дат в таблице...")
        
        # Проходим по всем строкам и колонкам
        for row_idx, row in enumerate(all_values):
            for col_idx, cell_value in enumerate(row):
                # Проверяем, является ли ячейка датой
                if is_date_cell(cell_value):
                    date_value = parse_date_cell(cell_value)
                    
                    if date_value:
                        # Ищем дежурного в ячейке под датой (следующая строка, та же колонка)
                        if row_idx + 1 < len(all_values):
                            duty_person_cell = all_values[row_idx + 1][col_idx]
                            duty_person = clean_name(duty_person_cell)
                            
                            if duty_person:
                                schedule_item = {
                                    'date': date_value,
                                    'name': duty_person,
                                    'date_str': cell_value.strip(),
                                    'raw_name': duty_person_cell,
                                    'cell_location': f"{chr(65 + col_idx)}{row_idx + 1}",
                                    'weekday': get_weekday_name(date_value)
                                }
                                schedule.append(schedule_item)
                                found_dates.append({
                                    'date': date_value,
                                    'original': cell_value.strip(),
                                    'location': f"{chr(65 + col_idx)}{row_idx + 1}",
                                    'duty': duty_person
                                })
        
        # Выводим информацию о найденных датах
        logger.info(f"Найдено записей о дежурствах: {len(schedule)}")
        for found in found_dates:
            logger.info(f"   {found['date'].strftime('%d.%m.%Y')} ({found['original']}) -> {found['duty']} [{found['location']}]")
        
        return schedule
        
    except Exception as e:
        logger.error(f"Ошибка при парсинге данных: {e}")
        return None

def get_schedule_data_with_protection():
    """Получение данных о дежурствах с защитой от частых запросов"""
    global last_request_time, last_error, schedule_cache, cache_time
    
    current_time = time.time()
    
    # Проверяем минимальный интервал между запросами
    if current_time - last_request_time < MIN_REQUEST_INTERVAL:
        logger.warning(f"Слишком частый запрос. Интервал: {current_time - last_request_time:.1f}с, минимальный: {MIN_REQUEST_INTERVAL}с")
        return schedule_cache, last_error, "rate_limit"
    
    last_request_time = current_time
    
    # Проверяем кэш (актуален 5 минут)
    if schedule_cache and cache_time and (current_time - cache_time < 300):
        logger.info("Используются кэшированные данные")
        return schedule_cache, None, "cached"
    
    try:
        client = get_google_sheets_client()
        if not client:
            error_msg = "Не удалось инициализировать клиент Google Sheets"
            last_error = error_msg
            logger.error(error_msg)
            return None, error_msg, "error"
            
        # Открываем таблицу по URL
        logger.info(f"Открытие таблицы: {GOOGLE_SHEET_URL}")
        sheet = client.open_by_url(GOOGLE_SHEET_URL)
        
        # Получаем лист "Вечернее дежурство"
        logger.info("Получение листа 'Вечернее дежурство'")
        worksheet = sheet.worksheet("Вечернее дежурство")
        
        schedule_data = parse_schedule_data(worksheet)
        
        if schedule_data is not None:
            # Сохраняем в кэш
            schedule_cache = schedule_data
            cache_time = current_time
            last_error = None
            logger.info("Данные успешно получены и закэшированы")
            return schedule_data, None, "success"
        else:
            error_msg = "Не удалось распарсить данные таблицы"
            last_error = error_msg
            logger.error(error_msg)
            return None, error_msg, "error"
            
    except gspread.exceptions.APIError as e:
        error_msg = f"Ошибка API Google Sheets: {e}"
        last_error = error_msg
        logger.error(error_msg)
        return None, error_msg, "api_error"
    except gspread.exceptions.SpreadsheetNotFound:
        error_msg = "Таблица не найдена. Проверьте URL и доступы."
        last_error = error_msg
        logger.error(error_msg)
        return None, error_msg, "not_found"
    except Exception as e:
        error_msg = f"Неизвестная ошибка при получении данных: {e}"
        last_error = error_msg
        logger.error(error_msg)
        return None, error_msg, "error"

def get_today_duty(schedule_data):
    """Получение дежурного на сегодня"""
    if not schedule_data:
        return None
    
    today = date.today()
    logger.info(f"Поиск дежурного на сегодня: {today.strftime('%d.%m.%Y')}")
    
    for duty in schedule_data:
        if duty['date'] == today:
            logger.info(f"Найден дежурный на сегодня: {duty['name']}")
            return duty
    
    logger.warning("На сегодня дежурный не назначен")
    return None

def get_two_work_weeks(schedule_data):
    """Получаем 2 недели рабочих дней (12 дней: ПН-СБ)"""
    if not schedule_data:
        logger.warning("Нет данных для отображения")
        return []
    
    today = date.today()
    
    # Определяем начало текущей недели (понедельник)
    current_week_start = today - timedelta(days=today.weekday())
    
    # Если сегодня воскресенье, начинаем со следующей недели
    if today.weekday() == 6:  # Воскресенье
        current_week_start = today + timedelta(days=1)
    else:
        # Иначе начинаем с текущего понедельника
        current_week_start = today - timedelta(days=today.weekday())
    
    logger.info(f"Сегодня: {today.strftime('%d.%m.%Y')} ({get_weekday_name(today)})")
    
    # Создаем 2 недели рабочих дней (12 дней: ПН-СБ)
    weeks = []
    all_work_days = []
    
    # Генерируем 12 рабочих дней (2 недели × 6 дней)
    for week_offset in range(2):  # 2 недели
        week_start = current_week_start + timedelta(weeks=week_offset)
        week_days = []
        
        # Добавляем дни с понедельника по субботу (6 дней)
        for day_offset in range(6):  # ПН-СБ
            current_date = week_start + timedelta(days=day_offset)
            week_days.append(current_date)
        
        all_work_days.extend(week_days)
    
    logger.info(f"Сгенерировано {len(all_work_days)} рабочих дней для отображения")
    
    # Создаем словарь для быстрого поиска дежурств по дате
    schedule_dict = {duty['date']: duty for duty in schedule_data}
    
    # Формируем данные для отображения
    display_weeks = []
    current_week_data = []
    
    for i, work_date in enumerate(all_work_days):
        # Ищем дежурного на эту дату
        duty = schedule_dict.get(work_date)
        
        if duty:
            # Используем данные из таблицы
            display_duty = duty.copy()
        else:
            # Создаем пустую запись
            display_duty = {
                'date': work_date,
                'name': '',
                'date_str': work_date.strftime('%d.%m.%Y'),
                'raw_name': '',
                'weekday': get_weekday_name(work_date)
            }
        
        current_week_data.append(display_duty)
        
        # Разделяем на недели (по 6 дней)
        if len(current_week_data) == 6:
            display_weeks.append(current_week_data)
            current_week_data = []
    
    # Исправлено: проверяем current_week_data вместо current_work_days
    if current_week_data:
        display_weeks.append(current_week_data)
    
    logger.info(f"Сформировано {len(display_weeks)} недель для отображения")
    
    return display_weeks

# =============================================================================
# МАРШРУТЫ FLASK
# =============================================================================

@app.route('/')
def index():
    """Главная страница с дежурствами"""
    logger.info("Запрос главной страницы")
    
    # Получаем данные с защитой от частых запросов
    schedule_data, error_msg, status = get_schedule_data_with_protection()
    
    today_duty = None
    weeks = []
    error_display = None
    
    if schedule_data:
        today_duty = get_today_duty(schedule_data)
        weeks = get_two_work_weeks(schedule_data)
    else:
        error_display = error_msg or "Не удалось загрузить данные"
        if status == "rate_limit":
            error_display += f" (повторите через {MIN_REQUEST_INTERVAL} секунд)"
    
    current_time = datetime.now().strftime('%H:%M')
    
    logger.info("Рендеринг страницы завершен")
    return render_template('index.html', 
                         today_duty=today_duty,
                         weeks=weeks,
                         today=date.today(),
                         current_time=current_time,
                         last_updated=datetime.now().strftime('%H:%M'),
                         error=error_display)

@app.route('/refresh')
def refresh_data():
    """Принудительное обновление данных"""
    logger.info("Запрос обновления данных")
    
    # Получаем данные с защитой от частых запросов
    schedule_data, error_msg, status = get_schedule_data_with_protection()
    
    today_duty_name = "Не назначен"
    if schedule_data:
        today_duty = get_today_duty(schedule_data)
        if today_duty:
            today_duty_name = today_duty['name']
    
    current_time = datetime.now().strftime('%H:%M')
    
    response_data = {
        'status': 'success' if schedule_data else 'error',
        'today_duty': today_duty_name,
        'current_time': current_time,
        'last_updated': datetime.now().strftime('%H:%M')
    }
    
    if error_msg:
        response_data['error'] = error_msg
        if status == "rate_limit":
            response_data['retry_after'] = MIN_REQUEST_INTERVAL
    
    logger.info("Обновление данных завершено")
    return response_data

@app.route('/debug')
def debug_info():
    """Страница для отладки - показывает все найденные данные"""
    logger.info("Запрос страницы отладки")
    
    schedule_data, error_msg, status = get_schedule_data_with_protection()
    today_duty = get_today_duty(schedule_data) if schedule_data else None
    weeks = get_two_work_weeks(schedule_data) if schedule_data else []
    
    debug_info = {
        'total_records': len(schedule_data) if schedule_data else 0,
        'today_duty': today_duty,
        'display_weeks': weeks,
        'today': date.today().strftime('%d.%m.%Y'),
        'last_error': last_error,
        'cache_status': 'active' if schedule_cache else 'empty',
        'request_status': status
    }
    
    logger.info("Страница отладки сгенерирована")
    return debug_info

# =============================================================================
# ЗАПУСК ПРИЛОЖЕНИЯ
# =============================================================================

def main():
    """Основная функция запуска"""
    print("=" * 60)
    print("🚀 Запуск приложения График дежурств")
    print("=" * 60)
    print(f"📊 Защита от частых запросов: {MIN_REQUEST_INTERVAL} секунд")
    print(f"📅 Отображение: 2 недели рабочих дней (12 дней)")
    print(f"🔗 Google Sheet URL: {GOOGLE_SHEET_URL}")
    print(f"🔑 Credentials file: {CREDENTIALS_FILE}")
    print(f"📝 Логи (только ошибки): duty_app.log")
    print("=" * 60)
    
    try:
        app.run(debug=False, host='0.0.0.0', port=5000)
    except Exception as e:
        logger.error(f"Критическая ошибка при запуске: {e}")
        print(f"❌ Приложение завершилось с ошибкой: {e}")
        input("Нажмите Enter для выхода...")

if __name__ == '__main__':
    main()