#!/bin/bash

echo "🚀 Настройка Duty Schedule App на Linux"
echo "========================================"

# Текущая директория
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$APP_DIR/.env"
CREDENTIALS_FILE="$APP_DIR/credentials.json"

# Функции
show_menu() {
    echo
    echo "============ ГЛАВНОЕ МЕНЮ ============"
    echo "1. Настроить Google Sheets доступ"
    echo "2. Проверить текущие настройки"
    echo "3. Создать файл .env"
    echo "4. Запустить приложение"
    echo "5. Создать службу systemd"
    echo "6. Скомпилировать приложение"
    echo "7. Выход"
    echo
    read -p "Выберите действие [1-7]: " choice
}

setup_google() {
    echo
    echo "======== НАСТРОЙКА GOOGLE SHEETS ========="
    
    read -p "Введите URL вашей Google таблицы: " google_sheet_url
    if [ -z "$google_sheet_url" ]; then
        echo "❌ URL не может быть пустым!"
        return 1
    fi
    
    # Проверяем URL
    if [[ ! "$google_sheet_url" == *"https://docs.google.com/spreadsheets/"* ]]; then
        echo "⚠️  Предупреждение: URL не похож на Google таблицу"
        read -p "Продолжить? [y/N]: " continue_setup
        if [[ ! "$continue_setup" =~ ^[Yy]$ ]]; then
            return 1
        fi
    fi
    
    # Создаем .env файл
    echo "Создание файла .env..."
    cat > "$ENV_FILE" << EOF
# Конфигурация Duty Schedule App
GOOGLE_SHEET_URL=$google_sheet_url
GOOGLE_CREDENTIALS_FILE=credentials.json
FLASK_DEBUG=False
EOF

    echo "✅ Файл .env создан/обновлен"
    
    # Проверяем credentials.json
    if [ -f "$CREDENTIALS_FILE" ]; then
        echo "✅ Файл credentials.json найден"
    else
        echo "❌ Файл credentials.json не найден!"
        echo
        echo "📝 Инструкция:"
        echo "1. Создайте сервисный аккаунт в Google Cloud Console"
        echo "2. Скачайте JSON файл с ключами"
        echo "3. Переименуйте его в credentials.json"
        echo "4. Положите в папку с приложением"
        echo
        read -p "Нажмите Enter для продолжения..."
    fi
}

check_settings() {
    echo
    echo "======== ТЕКУЩИЕ НАСТРОЙКИ ========="
    
    if [ -f "$ENV_FILE" ]; then
        echo "📄 Файл .env: НАЙДЕН"
        echo "Содержимое:"
        cat "$ENV_FILE"
    else
        echo "📄 Файл .env: НЕ НАЙДЕН"
    fi

    echo
    if [ -f "$CREDENTIALS_FILE" ]; then
        echo "🔑 Файл credentials.json: НАЙДЕН"
    else
        echo "🔑 Файл credentials.json: НЕ НАЙДЕН"
    fi

    echo
    echo "🌐 Переменные окружения:"
    printenv | grep GOOGLE_ || echo "❌ Переменные GOOGLE_ не установлены"
    
    read -p "Нажмите Enter для продолжения..."
}

create_env() {
    echo
    echo "======== СОЗДАНИЕ .ENV ФАЙЛА ========="
    
    if [ -f "$ENV_FILE" ]; then
        read -p "Файл .env уже существует. Перезаписать? [y/N]: " overwrite
        if [[ ! "$overwrite" =~ ^[Yy]$ ]]; then
            return
        fi
    fi
    
    read -p "Введите URL Google таблицы: " google_sheet_url
    if [ -z "$google_sheet_url" ]; then
        echo "❌ URL не может быть пустым!"
        return 1
    fi
    
    cat > "$ENV_FILE" << EOF
# Конфигурация Duty Schedule App
GOOGLE_SHEET_URL=$google_sheet_url
GOOGLE_CREDENTIALS_FILE=credentials.json
FLASK_DEBUG=False
EOF

    echo "✅ Файл .env создан"
    read -p "Нажмите Enter для продолжения..."
}

run_app() {
    echo
    echo "======== ЗАПУСК ПРИЛОЖЕНИЯ ========="
    
    # Проверяем необходимые файлы
    if [ ! -f "$ENV_FILE" ]; then
        echo "❌ Файл .env не найден!"
        echo "Запустите сначала настройку (пункт 1 или 3)"
        read -p "Нажмите Enter для продолжения..."
        return
    fi

    if [ ! -f "$CREDENTIALS_FILE" ]; then
        echo "❌ Файл credentials.json не найден!"
        read -p "Нажмите Enter для продолжения..."
        return
    fi

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
        echo "❌ Исполняемый файл не найден!"
        echo "Убедитесь, что приложение скомпилировано"
        read -p "Нажмите Enter для продолжения..."
        return
    fi

    echo "🚀 Запуск: $APP_EXE"
    echo "📍 Приложение будет доступно по адресу: http://localhost:5000"
    echo "⏹️  Для остановки нажмите Ctrl+C"
    echo
    read -p "Нажмите Enter для запуска..."

    # Запускаем приложение
    cd "$APP_DIR"
    "$APP_EXE"
}

create_systemd_service() {
    echo
    echo "======== СОЗДАНИЕ СЛУЖБЫ SYSTEMD ========="
    
    # Проверяем права
    if [ "$EUID" -ne 0 ]; then
        echo "⚠️  Для создания службы нужны права root"
        echo "Запустите скрипт с sudo: sudo ./setup_linux.sh"
        read -p "Нажмите Enter для продолжения..."
        return
    fi

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
        echo "❌ Исполняемый файл не найден!"
        read -p "Нажмите Enter для продолжения..."
        return
    fi

    # Создаем службу
    SERVICE_FILE="/etc/systemd/system/duty-schedule.service"
    
    cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Duty Schedule App
After=network.target

[Service]
Type=simple
User=$SUDO_USER
WorkingDirectory=$APP_DIR
ExecStart=$APP_EXE
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

    echo "✅ Файл службы создан: $SERVICE_FILE"
    
    # Перезагружаем systemd и запускаем службу
    systemctl daemon-reload
    systemctl enable duty-schedule.service
    systemctl start duty-schedule.service
    
    echo "✅ Служба запущена и добавлена в автозагрузку"
    echo "📊 Статус: systemctl status duty-schedule"
    echo "📋 Логи: journalctl -u duty-schedule -f"
    echo "🛑 Остановка: systemctl stop duty-schedule"
    
    read -p "Нажмите Enter для продолжения..."
}

compile_app() {
    echo
    echo "======== КОМПИЛЯЦИЯ ПРИЛОЖЕНИЯ ========="
    
    if [ ! -f "build_linux.sh" ]; then
        echo "❌ Файл build_linux.sh не найден!"
        read -p "Нажмите Enter для продолжения..."
        return
    fi
    
    chmod +x build_linux.sh
    ./build_linux.sh
    
    read -p "Нажмите Enter для продолжения..."
}

# Основной цикл
while true; do
    show_menu
    case $choice in
        1) setup_google ;;
        2) check_settings ;;
        3) create_env ;;
        4) run_app ;;
        5) create_systemd_service ;;
        6) compile_app ;;
        7) 
            echo
            echo "👋 До свидания!"
            exit 0
            ;;
        *) echo "❌ Неверный выбор" ;;
    esac
done