import gspread
from google.oauth2.service_account import Credentials
import os
import re
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

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
    except ValueError:
        return None

def clean_name(name):
    """Очистка имени от комментариев и лишних символов"""
    if not name:
        return ""
    
    # Удаляем текст в скобках и комментарии
    name = re.sub(r'\([^)]*\)', '', name)
    name = re.sub(r'с \d+:\d+', '', name)
    name = re.sub(r'\([^)]*\)', '', name)
    
    # Убираем лишние пробелы и переносы строк
    name = name.replace('<br>', ', ').strip()
    name = re.sub(r'\s+', ' ', name)
    
    return name.strip(' ,')

def test_parsing():
    try:
        # Настройки
        GOOGLE_SHEET_URL = os.getenv('GOOGLE_SHEET_URL')
        CREDENTIALS_FILE = os.getenv('GOOGLE_CREDENTIALS_FILE', 'credentials.json')
        
        # Инициализация клиента
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]
        
        creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scope)
        client = gspread.authorize(creds)
        
        # Открываем таблицу
        sheet = client.open_by_url(GOOGLE_SHEET_URL)
        worksheet = sheet.worksheet("Вечернее дежурство")
        
        # Получаем все данные
        all_values = worksheet.get_all_values()
        
        print("🔍 Поиск дат в формате ДД.ММ.ГГГГ и ДД.ММ...")
        print("=" * 70)
        
        date_count = 0
        
        # Проходим по всем строкам и колонкам
        for row_idx, row in enumerate(all_values):
            for col_idx, cell_value in enumerate(row):
                if is_date_cell(cell_value):
                    date_value = parse_date_cell(cell_value)
                    if date_value:
                        date_count += 1
                        # Ищем дежурного под датой
                        if row_idx + 1 < len(all_values):
                            duty_person_raw = all_values[row_idx + 1][col_idx]
                            duty_person_clean = clean_name(duty_person_raw)
                            
                            print(f"📅 Найдена дата: {cell_value} -> {date_value.strftime('%d.%m.%Y')}")
                            print(f"👤 Дежурный: {duty_person_clean} (оригинал: '{duty_person_raw}')")
                            print(f"📍 Координаты: {chr(65 + col_idx)}{row_idx + 1} -> {chr(65 + col_idx)}{row_idx + 2}")
                            print("-" * 50)
        
        print(f"✅ Всего найдено дат: {date_count}")
        
        # Покажем пример первых 10 строк для отладки
        print("\n📋 Пример данных таблицы (первые 10 строк):")
        print("=" * 70)
        for i, row in enumerate(all_values[:10]):
            # Обрезаем пустые ячейки справа
            clean_row = [cell for cell in row if cell != '']
            if clean_row:  # Показываем только непустые строки
                print(f"Строка {i+1}: {clean_row}")
                
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_parsing()