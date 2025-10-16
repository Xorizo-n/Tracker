#!/bin/bash

echo "🚀 Запуск Duty Schedule App"
echo "============================"

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$APP_DIR/.env"
CREDENTIALS_FILE="$APP_DIR/credentials.json"

# Проверяем необходимые файлы
if [ ! -f "$ENV_FILE" ]; then
    echo "❌ Ошибка: Файл .env не найден!"
    echo "Запустите setup_linux.sh для настройки приложения"
    exit 1
fi

if [ ! -f "$CREDENTIALS_FILE" ]; then
    echo "❌ Ошибка: Файл credentials.json не найден!"
    echo "Добавьте файл с учетными данными Google в папку приложения"
    exit 1
fi

# Загружаем переменные из .env файла
export $(grep -v '^#' "$ENV_FILE" | xargs)

# Ищем исполняемый файл
APP_EXE=""
for exe in "duty_schedule_linux" "DutySchedule" "duty_app"; do
    if [ -f "$APP_DIR/dist/$exe" ]; then
        APP_EXE="$APP_DIR/dist/$exe"
        break
    elif [ -f "$APP_DIR/$exe" ]; then
        APP_EXE="$APP_DIR/$exe"
        break
    fi
done

if [ -z "$APP_EXE" ]; then
    echo "❌ Ошибка: Исполняемый файл не найден!"
    echo "Убедитесь, что приложение скомпилировано"
    exit 1
fi

echo "✅ Все проверки пройдены"
echo "📍 Запуск приложения..."
echo "🌐 После запуска откройте: http://localhost:5000"
echo "⏹️  Для остановки нажмите Ctrl+C"
echo
echo "========================================"

cd "$APP_DIR"
"$APP_EXE"