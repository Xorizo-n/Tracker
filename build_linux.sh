#!/bin/bash

echo "🔨 Сборка Duty Schedule App для Linux..."
echo "=========================================="

# Проверяем Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 не установлен"
    exit 1
fi

# Создаем виртуальное окружение
echo "📦 Создание виртуального окружения..."
python3 -m venv linux_venv
source linux_venv/bin/activate

# Устанавливаем зависимости
echo "📥 Установка зависимостей..."
pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

# Компилируем
echo "🔨 Компиляция приложения..."
pyinstaller --onefile \
    --add-data "templates:templates" \
    --add-data "static:static" \
    --add-data ".env:." \
    --add-data "credentials.json:." \
    --console \
    --name "duty_schedule_linux" \
    duty_app.py

# Делаем исполняемым
chmod +x dist/duty_schedule_linux

echo "✅ Сборка завершена!"
echo "📁 Исполняемый файл: dist/duty_schedule_linux"
echo "🚀 Запуск: ./dist/duty_schedule_linux"