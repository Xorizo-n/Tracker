#!/bin/bash

set -e  # Выход при ошибке

echo "🚀 Настройка и запуск Duty Schedule App для Linux"
echo "=================================================="

# Текущая директория
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"

echo "📁 Рабочая директория: $APP_DIR"

# =============================================================================
# ФУНКЦИИ
# =============================================================================

install_dependencies() {
    echo "📦 Установка системных зависимостей..."
    sudo apt update
    sudo apt install -y python3 python3-venv python3-pip python3-dev
    echo "✅ Системные зависимости установлены"
}

create_venv() {
    echo "🐍 Создание виртуального окружения..."
    if [ ! -d "venv" ]; then
        python3 -m venv venv
        echo "✅ Виртуальное окружение создано"
    else
        echo "✅ Виртуальное окружение уже существует"
    fi
}

install_python_deps() {
    echo "📥 Установка Python зависимостей..."
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    echo "✅ Python зависимости установлены"
}

setup_environment() {
    echo "⚙️  Настройка окружения..."
    
    if [ ! -f ".env" ]; then
        echo "📝 Создание файла .env..."
        read -p "Введите URL вашей Google таблицы: " google_sheet_url
        
        if [ -z "$google_sheet_url" ]; then
            echo "❌ URL не может быть пустым!"
            exit 1
        fi
        
        cat > .env << EOF
# Конфигурация Duty Schedule App
GOOGLE_SHEET_URL=$google_sheet_url
GOOGLE_CREDENTIALS_FILE=credentials.json
FLASK_DEBUG=False
EOF
        echo "✅ Файл .env создан"
    else
        echo "✅ Файл .env уже существует"
    fi
    
    # Проверяем credentials.json
    if [ ! -f "credentials.json" ]; then
        echo "❌ Файл credentials.json не найден!"
        echo
        echo "📝 Инструкция по получению credentials.json:"
        echo "1. Перейдите в Google Cloud Console: https://console.cloud.google.com/"
        echo "2. Создайте новый проект или выберите существующий"
        echo "3. Включите Google Sheets API и Google Drive API"
        echo "4. Создайте сервисный аккаунт"
        echo "5. Скачайте JSON ключи и переименуйте в credentials.json"
        echo "6. Положите файл в папку: $APP_DIR/"
        echo "7. Дайте доступ к таблице для email сервисного аккаунта"
        echo
        read -p "После добавления credentials.json нажмите Enter..."
    else
        echo "✅ Файл credentials.json найден"
    fi
}

check_environment() {
    echo "🔍 Проверка окружения..."
    
    local errors=0
    
    if [ ! -f ".env" ]; then
        echo "❌ Файл .env не найден"
        ((errors++))
    else
        echo "✅ Файл .env найден"
        # Загружаем переменные для проверки
        export $(grep -v '^#' .env | xargs)
    fi
    
    if [ ! -f "credentials.json" ]; then
        echo "❌ Файл credentials.json не найден"
        ((errors++))
    else
        echo "✅ Файл credentials.json найден"
    fi
    
    if [ ! -d "venv" ]; then
        echo "❌ Виртуальное окружение не найдено"
        ((errors++))
    else
        echo "✅ Виртуальное окружение найдено"
    fi
    
    if [ ! -f "requirements.txt" ]; then
        echo "❌ Файл requirements.txt не найден"
        ((errors++))
    else
        echo "✅ Файл requirements.txt найден"
    fi
    
    if [ $errors -gt 0 ]; then
        echo "❌ Найдено $errors ошибок. Запустите скрипт заново."
        exit 1
    fi
    
    echo "✅ Все проверки пройдены успешно"
}

run_app_directly() {
    echo "🚀 Запуск приложения напрямую..."
    source venv/bin/activate
    cd "$APP_DIR"
    python3 duty_app.py
}

compile_app() {
    echo "🔨 Компиляция приложения..."
    source venv/bin/activate
    
    # Устанавливаем PyInstaller если нужно
    if ! pip list | grep -q pyinstaller; then
        echo "📦 Установка PyInstaller..."
        pip install pyinstaller
    fi
    
    # Очищаем предыдущие сборки
    if [ -d "dist" ]; then
        rm -rf dist
    fi
    if [ -d "build" ]; then
        rm -rf build
    fi
    
    # Компилируем
    echo "🔨 Компиляция..."
    pyinstaller --onefile \
        --add-data "templates:templates" \
        --add-data "static:static" \
        --add-data ".env:." \
        --add-data "credentials.json:." \
        --console \
        --name "duty_schedule" \
        duty_app.py
    
    # Проверяем результат
    if [ -f "dist/duty_schedule" ]; then
        chmod +x dist/duty_schedule
        echo "✅ Приложение скомпилировано: dist/duty_schedule"
    else
        echo "❌ Ошибка компиляции"
        exit 1
    fi
}

run_compiled_app() {
    echo "🚀 Запуск скомпилированного приложения..."
    
    if [ ! -f "dist/duty_schedule" ]; then
        echo "❌ Скомпилированное приложение не найдено"
        echo "Запустите компиляцию сначала (пункт 3)"
        return 1
    fi
    
    cd "$APP_DIR"
    ./dist/duty_schedule
}

create_systemd_service() {
    echo "🔧 Создание службы systemd..."
    
    if [ "$EUID" -ne 0 ]; then
        echo "⚠️  Для создания службы нужны права root"
        echo "Запустите скрипт с sudo: sudo ./setup_linux.sh"
        return 1
    fi
    
    # Определяем путь к приложению
    local app_path="$APP_DIR/dist/duty_schedule"
    if [ ! -f "$app_path" ]; then
        echo "❌ Скомпилированное приложение не найдено: $app_path"
        echo "Запустите компиляцию сначала (пункт 3)"
        return 1
    fi
    
    # Определяем пользователя
    local service_user=$(logname)
    if [ -z "$service_user" ]; then
        service_user="$SUDO_USER"
    fi
    
    echo "👤 Служба будет запущена от пользователя: $service_user"
    
    # Создаем службу
    local service_file="/etc/systemd/system/duty-schedule.service"
    
    cat > "$service_file" << EOF
[Unit]
Description=Duty Schedule App
After=network.target
Wants=network.target

[Service]
Type=simple
User=$service_user
Group=$service_user
WorkingDirectory=$APP_DIR
ExecStart=$app_path
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

    echo "✅ Файл службы создан: $service_file"
    
    # Перезагружаем systemd
    systemctl daemon-reload
    systemctl enable duty-schedule.service
    
    echo "✅ Служба добавлена в автозагрузку"
    echo "🎯 Для запуска выполните: sudo systemctl start duty-schedule"
    echo "📊 Для просмотра статуса: systemctl status duty-schedule"
}

show_status() {
    echo "📊 Статус службы:"
    if systemctl is-active --quiet duty-schedule 2>/dev/null; then
        echo "✅ Служба запущена"
        echo "🌐 Приложение доступно по адресу: http://localhost:5000"
    else
        echo "❌ Служба не запущена"
    fi
    
    echo
    echo "📋 Полезные команды:"
    echo "  systemctl status duty-schedule    - статус службы"
    echo "  journalctl -u duty-schedule -f    - просмотр логов"
    echo "  sudo systemctl start duty-schedule - запуск службы"
    echo "  sudo systemctl stop duty-schedule  - остановка службы"
}

show_menu() {
    echo
    echo "============ ГЛАВНОЕ МЕНЮ ============"
    echo "1. Полная установка (все этапы)"
    echo "2. Только настройка окружения"
    echo "3. Компиляция приложения"
    echo "4. Запуск напрямую (без компиляции)"
    echo "5. Запуск скомпилированного приложения"
    echo "6. Создать службу systemd (требует sudo)"
    echo "7. Показать статус службы"
    echo "8. Выход"
    echo
    read -p "Выберите действие [1-8]: " choice
}

full_installation() {
    echo "🎯 Запуск полной установки..."
    install_dependencies
    create_venv
    install_python_deps
    setup_environment
    check_environment
    compile_app
    echo
    echo "✅ Полная установка завершена!"
    echo "🚀 Теперь вы можете:"
    echo "   - Запустить приложение: ./setup_linux.sh (пункт 5)"
    echo "   - Или создать службу: sudo ./setup_linux.sh (пункт 6)"
}

# =============================================================================
# ОСНОВНАЯ ЛОГИКА
# =============================================================================

main() {
    # Проверяем что мы в правильной директории
    if [ ! -f "duty_app.py" ]; then
        echo "❌ Ошибка: скрипт должен запускаться из папки с duty_app.py"
        echo "Текущая директория: $APP_DIR"
        exit 1
    fi
    
    while true; do
        show_menu
        case $choice in
            1) full_installation ;;
            2) setup_environment ;;
            3) compile_app ;;
            4) run_app_directly ;;
            5) run_compiled_app ;;
            6) create_systemd_service ;;
            7) show_status ;;
            8) 
                echo
                echo "👋 До свидания!"
                exit 0
                ;;
            *) echo "❌ Неверный выбор" ;;
        esac
        
        echo
        read -p "Нажмите Enter чтобы продолжить..."
    done
}

# Запускаем основную функцию
main